# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Stage and encode successful scripted episodes while simulation continues."""

from __future__ import annotations

import json
import multiprocessing
import os
import queue
import shutil
import threading
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch
from lerobot.datasets import LeRobotDataset
from lerobot.datasets.dataset_tools import merge_datasets

from ..lerobot_recorder import LeRobotRecorder


def _encode_staged_episode(
    episode_path: Path, repo_id: str, task_name: str, fps: int, features: dict, cameras: dict,
) -> Path:
    """Build an independent LeRobot episode; publish its directory after finalization."""
    output = episode_path / "dataset"
    if output.exists():
        return output
    temporary = episode_path / ".encoding"
    if temporary.exists():
        shutil.rmtree(temporary)
    actions = np.load(episode_path / "action.npy", mmap_mode="r")
    observations = np.load(episode_path / "observation_state.npy", mmap_mode="r")
    rgb = {
        name: np.load(episode_path / f"rgb_{name}.npy", mmap_mode="r")
        for name in cameras
    }
    dataset = LeRobotDataset.create(
        repo_id, fps=fps, features=features, root=temporary,
        robot_type="so101_follower", use_videos=bool(cameras),
        image_writer_threads=2, encoder_threads=2,
    )
    try:
        for index in range(len(actions)):
            dataset.add_frame({
                "action": np.asarray(actions[index]),
                "observation.state": np.asarray(observations[index]),
                "task": task_name,
                **{f"observation.images.{name}": np.asarray(frames[index]) for name, frames in rgb.items()},
            })
        # Each process owns an episode; avoid a second process pool for cameras.
        dataset.save_episode(parallel_encoding=False)
    finally:
        dataset.finalize()
    temporary.rename(output)
    return output


class OfflineLeRobotRecorder(LeRobotRecorder):
    """Encode accepted episodes in background processes and merge them in acceptance order."""

    def __init__(
        self,
        *,
        task_name: str,
        repo_id: str,
        dataset_root: str,
        staging_root: str,
        fps: int,
        cameras: dict,
        num_envs: int,
        warmup_steps: int = 0,
        capture_decimation: int = 1,
        gpu_ring_depth: int = 8,
        encoding_workers: int = 2,
    ) -> None:
        for path in (Path(dataset_root), Path(staging_root)):
            if path.exists():
                raise FileExistsError(
                    f"State-machine recording cannot resume existing output: {path}. "
                    "Choose a new --repo_id or move/remove the existing directory."
                )
        self.num_envs = num_envs
        self.warmup_steps = warmup_steps
        self.capture_decimation = capture_decimation
        self.staging_root = Path(staging_root)
        self._episode_steps = np.zeros(num_envs, dtype=np.int64)
        self._actions_by_env: list[list[np.ndarray]] = [[] for _ in range(num_envs)]
        self._observations_by_env: list[list[np.ndarray]] = [
            [] for _ in range(num_envs)
        ]
        self._rgb_by_env: list[dict[str, list[np.ndarray]]] = [
            {name: [] for name in cameras} for _ in range(num_envs)
        ]
        self._stage_lock = threading.Lock()
        self._stage_error: Exception | None = None
        self._flushed = False
        self._encoding_slots = threading.BoundedSemaphore(2 * encoding_workers)
        self._encoding_futures: list[Future] = []
        self._recovery_submitted = threading.Event()
        self._prepare_staging(
            task_name=task_name,
            repo_id=repo_id,
            fps=fps,
            cameras=cameras,
        )
        # Spawn isolates encoders from the simulator's CUDA and renderer threads.
        self._encoders = ProcessPoolExecutor(
            max_workers=encoding_workers,
            mp_context=multiprocessing.get_context("spawn"),
        )
        super().__init__(
            task_name=task_name,
            repo_id=repo_id,
            dataset_root=dataset_root,
            fps=fps,
            cameras=cameras,
            gpu_ring_depth=gpu_ring_depth,
            episode_queue_size=2 * encoding_workers,
        )

    @property
    def num_staged_episodes(self) -> int:
        with self._stage_lock:
            return len(self._episode_paths())

    def saving_status(self) -> dict:
        status = super().saving_status()
        with self._stage_lock:
            pending = sum(not future.done() for future in self._encoding_futures)
        status["active"] |= pending > 0
        status["queued"] += pending
        return status

    def push_batch_to_buffer(
        self,
        actions: np.ndarray,
        observations: np.ndarray,
        rgb_buffers: dict[str, torch.Tensor],
        active_mask: np.ndarray,
    ) -> None:
        """Capture one batched control step for active environments."""
        self._check_recording_error()
        active_mask = np.asarray(active_mask, dtype=np.bool_)
        capture_mask = (
            active_mask
            & (self._episode_steps >= self.warmup_steps)
            & ((self._episode_steps - self.warmup_steps) % self.capture_decimation == 0)
        )
        self._episode_steps[active_mask] += 1
        if not capture_mask.any():
            return

        if self.cameras and self._copy_stream is None:
            self._alloc_ring(rgb_buffers)

        slot = None
        if self.cameras:
            self._free_slots.acquire()
            slot = self._write_slot
            self._write_slot = (self._write_slot + 1) % self.gpu_ring_depth
            stream = torch.cuda.current_stream()
            for camera_name in self.cameras:
                self._ring[camera_name][slot].copy_(rgb_buffers[camera_name])
            self._slot_events[slot].record(stream)

        self._drain_queue.put(
            (
                slot,
                np.asarray(actions, dtype=np.float32).copy(),
                np.asarray(observations, dtype=np.float32).copy(),
                capture_mask,
            )
        )

    def accept_episode(self, env_id: int) -> bool:
        """Queue one successful environment episode for staging and encoding."""
        self._check_recording_error()
        self._drain_queue.join()
        total_frames = len(self._actions_by_env[env_id])
        if total_frames == 0:
            self._reset_env_buffer(env_id)
            return False

        episode = {
            "action": self._actions_by_env[env_id],
            "observation.state": self._observations_by_env[env_id],
            "rgb": self._rgb_by_env[env_id],
            "total_frames": total_frames,
        }
        self.episode_queue.put(episode)
        self._reset_env_buffer(env_id)
        print(
            f"[INFO]: Accepted env {env_id} episode "
            f"({total_frames} frames) for staging."
        )
        return True

    def discard_episode(self, env_id: int) -> None:
        """Discard one failed environment without affecting other buffers."""
        self._drain_queue.join()
        self._reset_env_buffer(env_id)
        print(f"[INFO]: Discarded failed env {env_id} episode.")

    def flush_dataset(self, *, resume: bool) -> None:
        """Wait for pending encoders, then merge finished episodes without re-encoding."""
        self._drain_queue.join()
        self._recovery_submitted.wait()
        self.episode_queue.join()
        self._encoders.shutdown(wait=True)
        self._check_recording_error()

        if not self._encoding_futures:
            raise RuntimeError("No successful staged episodes to write.")
        parts = [LeRobotDataset(self.repo_id, root=future.result()) for future in self._encoding_futures]
        destination = Path(self.dataset_root)
        if destination.exists():
            if not resume:
                raise ValueError(f"Dataset already exists: {destination}")
            parts.insert(0, LeRobotDataset(self.repo_id, root=destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"[INFO]: Merging {len(parts)} encoded dataset part(s), without video encoding.")
        with TemporaryDirectory(prefix=f".{destination.name}-merge-", dir=destination.parent) as work:
            merged = Path(work) / "merged"
            previous = Path(work) / "previous"
            merge_datasets(
                parts, output_repo_id=self.repo_id, output_dir=merged,
                concatenate_videos=False, concatenate_data=False,
            )
            if destination.exists():
                destination.rename(previous)
            try:
                merged.rename(destination)
            except BaseException:
                if previous.exists():
                    previous.rename(destination)
                raise
        self.dataset = LeRobotDataset(self.repo_id, root=destination)
        self.num_recorded_episodes = self.dataset.num_episodes
        self._flushed = True

    def close(self) -> None:
        """Drain workers, retain unfinished collection, and remove successfully merged staging."""
        try:
            self._recovery_submitted.wait()
            super().close()
        finally:
            self._encoders.shutdown(wait=True)
        if self._flushed:
            shutil.rmtree(self.staging_root)
            print(f"[INFO]: Removed staging directory {self.staging_root}")
        elif self.staging_root.exists():
            print(f"[INFO]: Preserved staged episodes at {self.staging_root}")
        self._check_recording_error()

    def _check_recording_error(self) -> None:
        if self._stage_error is not None:
            raise RuntimeError("An episode failed to stage or encode.") from self._stage_error

    def _submit_encoding(self, episode_path: Path) -> None:
        self._encoding_slots.acquire()
        try:
            future = self._encoders.submit(
                _encode_staged_episode, episode_path, self.repo_id,
                self.task_name, self.fps, self.dataset_features, self.cameras,
            )
        except BaseException:
            self._encoding_slots.release()
            raise
        with self._stage_lock:
            self._encoding_futures.append(future)
        future.add_done_callback(self._encoding_finished)

    def _encoding_finished(self, future: Future) -> None:
        try:
            path = future.result()
            self.num_recorded_episodes += 1
            print(f"[INFO]: Encoded {path.parent.name} | {self.num_recorded_episodes} episode(s) ready.")
        except Exception as exc:  # noqa: BLE001
            self._stage_error = exc
            print(f"[ERROR]: Failed to encode episode: {exc}")
        finally:
            self._encoding_slots.release()

    def _drain_frames(self) -> None:
        while not self._drain_stop_event.is_set():
            try:
                slot, actions, observations, active_mask = self._drain_queue.get(
                    timeout=1
                )
            except queue.Empty:
                continue

            try:
                rgb_batch: dict[str, np.ndarray] = {}
                if slot is not None:
                    with torch.inference_mode():
                        with torch.cuda.stream(self._copy_stream):
                            self._copy_stream.wait_event(self._slot_events[slot])
                            for camera_name in self.cameras:
                                self._pinned[camera_name].copy_(
                                    self._ring[camera_name][slot],
                                    non_blocking=True,
                                )
                        self._copy_stream.synchronize()
                        rgb_batch = {
                            name: self._pinned[name].numpy().copy()
                            for name in self.cameras
                        }
                    self._free_slots.release()

                for env_id in np.flatnonzero(active_mask):
                    self._actions_by_env[env_id].append(actions[env_id])
                    self._observations_by_env[env_id].append(observations[env_id])
                    for name in self.cameras:
                        self._rgb_by_env[env_id][name].append(rgb_batch[name][env_id])
            finally:
                self._drain_queue.task_done()

    def _async_episode_processor(self) -> None:
        try:
            for episode_path in self._episode_paths():
                self._submit_encoding(episode_path)
        except Exception as exc:  # noqa: BLE001
            self._stage_error = exc
        finally:
            self._recovery_submitted.set()
        while not self._stop_event.is_set():
            try:
                episode = self.episode_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                with self._save_lock:
                    self._save_active = True
                    self._save_written = 0
                    self._save_total = episode["total_frames"]
                self._submit_encoding(self._stage_episode(episode))
            except Exception as exc:  # noqa: BLE001
                self._stage_error = exc
                print(f"[ERROR]: Failed to stage episode: {exc}")
            finally:
                with self._save_lock:
                    self._save_active = False
                self.episode_queue.task_done()

    def _stage_episode(self, episode: dict) -> Path:
        with self._stage_lock:
            episode_index = len(self._episode_paths())
        final_path = self.staging_root / f"episode_{episode_index:06d}"
        temp_path = self.staging_root / f".episode_{episode_index:06d}.tmp"
        if temp_path.exists():
            shutil.rmtree(temp_path)
        temp_path.mkdir(parents=True)

        total_frames = episode["total_frames"]
        np.save(
            temp_path / "action.npy",
            np.asarray(episode["action"], dtype=np.float32),
        )
        np.save(
            temp_path / "observation_state.npy",
            np.asarray(episode["observation.state"], dtype=np.float32),
        )
        for name, spec in self.cameras.items():
            rgb = np.lib.format.open_memmap(
                temp_path / f"rgb_{name}.npy",
                mode="w+",
                dtype=np.uint8,
                shape=(total_frames, spec["height"], spec["width"], 3),
            )
            for frame_index, frame in enumerate(episode["rgb"][name]):
                rgb[frame_index] = frame
                with self._save_lock:
                    self._save_written = frame_index + 1
            del rgb

        os.replace(temp_path, final_path)
        print(f"[INFO]: Staged successful episode at {final_path}")
        return final_path

    def _prepare_staging(
        self,
        *,
        task_name: str,
        repo_id: str,
        fps: int,
        cameras: dict,
    ) -> None:
        self.staging_root.mkdir(parents=True, exist_ok=True)
        metadata_path = self.staging_root / "metadata.json"
        metadata = {
            "task_name": task_name,
            "repo_id": repo_id,
            "fps": fps,
            "cameras": cameras,
        }
        if metadata_path.exists():
            existing = json.loads(metadata_path.read_text())
            if existing != metadata:
                raise ValueError(f"Staging metadata mismatch at {metadata_path}")
        else:
            metadata_path.write_text(json.dumps(metadata, indent=2))

    def _episode_paths(self) -> list[Path]:
        return sorted(self.staging_root.glob("episode_[0-9][0-9][0-9][0-9][0-9][0-9]"))

    def _reset_env_buffer(self, env_id: int) -> None:
        self._episode_steps[env_id] = 0
        self._actions_by_env[env_id] = []
        self._observations_by_env[env_id] = []
        self._rgb_by_env[env_id] = {name: [] for name in self.cameras}
