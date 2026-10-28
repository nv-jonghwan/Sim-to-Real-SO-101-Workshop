# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""RGB LeRobot dataset recorder for teleop episodes.

Records the visual observation group (``rgb_wrist`` / ``rgb_external``) plus
6-DoF state/action. During recording the sim loop only clones each camera frame
into a small fixed-size GPU ring on the render stream; a drain thread copies
those frames off the GPU on a separate CUDA stream into per-episode host lists,
so the loop never blocks on a device-to-host transfer. On stop the lists are
handed to a writer thread that writes a :class:`LeRobotDataset`; a discard drops
them. The agent loop calls :meth:`save_episode` / :meth:`cancel_recording`
in response to focused browser controls.

With ``isolated_writer=True`` the drain thread instead streams each frame to a
spawned writer process that encodes video while recording (LeRobot streaming
encoding). Saving an episode then only finalizes it, so the control loop never
waits on encoding or shares its interpreter with the writer.

LeRobot lifecycle: ``create`` (or ``resume`` to append to an existing root) ->
(``add_frame`` + ``save_episode``) per episode -> ``finalize`` once at shutdown.
Without ``--resume`` the dataset root must not already exist; with ``--resume``
new episodes are appended via ``LeRobotDataset.resume``.
"""

import json
import multiprocessing
import queue
import shutil
import signal
import threading
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import numpy as np
import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from tqdm import tqdm

SO101_FEATURE_NAMES = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]

# LeRobot's recommended writer settings for corrections-only DAgger recording.
_STREAMING_WRITER = {"streaming_encoding": True, "encoder_threads": 2}


class LeRobotRecorder:
    """Records teleop episodes to a LeRobot dataset (RGB + 6-DoF state/action)."""

    def __init__(
        self,
        task_name: str,
        repo_id: str,
        dataset_root: str,
        fps: int,
        cameras: dict,
        gpu_ring_depth: int = 8,
        isolated_writer: bool = False,
        episode_queue_size: int = 0,
    ):
        self._writer_process = (
            ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn"), initializer=_initialize_writer_process,
            )
            if isolated_writer else None
        )
        self.task_name = task_name
        self.repo_id = repo_id
        self.dataset_root = dataset_root
        self.fps = fps
        self.cameras = cameras
        self.gpu_ring_depth = gpu_ring_depth

        self.dataset_features = {
            "observation.state": {
                "dtype": "float32",
                "shape": (6,),
                "names": SO101_FEATURE_NAMES,
            },
            "action": {
                "dtype": "float32",
                "shape": (6,),
                "names": SO101_FEATURE_NAMES,
            },
        }
        for camera_name, spec in self.cameras.items():
            self.dataset_features[f"observation.images.{camera_name}"] = {
                "dtype": "video",
                "shape": (spec["height"], spec["width"], 3),
                "names": ["height", "width", "channels"],
            }

        # Per-episode host buffers, written only by the drain thread.
        self._actions: list[np.ndarray] = []
        self._observations: list[np.ndarray] = []
        self._rgb: dict[str, list[np.ndarray]] = {name: [] for name in self.cameras}
        self._episode_frames = 0

        # GPU capture ring + host-copy plumbing, allocated on the first frame
        # once the camera tensor device/shape is known. The sim loop clones into
        # a free ring slot; the drain thread copies it to host on _copy_stream.
        self._ring: dict[str, torch.Tensor] = {}
        self._pinned: dict[str, torch.Tensor] = {}
        self._slot_events: list[torch.cuda.Event] = []
        self._copy_stream: torch.cuda.Stream | None = None
        self._write_slot = 0
        self._free_slots = threading.Semaphore(gpu_ring_depth)
        self._drain_queue: queue.Queue = queue.Queue()
        self._drain_stop_event = threading.Event()
        self._drain_thread = threading.Thread(target=self._drain_frames, daemon=True)
        self._drain_thread.start()

        # Background episode -> disk writer.
        self.num_recorded_episodes = 0
        self.episode_queue: queue.Queue = queue.Queue(maxsize=episode_queue_size)

        # Save-progress state, read by the browser display via saving_status()
        # so the client can show a "saving — do not close" banner while the
        # writer thread drains an episode (the tqdm progress, mirrored to the UI).
        self._save_lock = threading.Lock()
        self._save_active = False
        self._save_written = 0
        self._save_total = 0
        self._save_error = None
        self._pending_saves = 0

        self._stop_event = threading.Event()
        self._processor_thread = threading.Thread(
            target=self._async_episode_processor, daemon=True
        )
        self._processor_thread.start()

    # ------------------------------------------------------------------
    # Dataset lifecycle
    # ------------------------------------------------------------------

    def init_dataset(self, resume: bool = False):
        """Create the dataset, or with ``resume`` append to an existing local one.

        New episodes must match the existing dataset's fps and features. Without
        ``resume`` an existing root raises instead of being overwritten.
        """
        if self._writer_process is not None:
            self.num_recorded_episodes = self._writer_process.submit(
                _process_writer_command, "init", {
                    "task_name": self.task_name, "repo_id": self.repo_id, "dataset_root": self.dataset_root,
                    "fps": self.fps, "features": self.dataset_features, "resume": resume,
                },
            ).result()
            return
        self.dataset = _open_dataset(self.repo_id, self.dataset_root, self.fps, self.dataset_features, resume)
        self.num_recorded_episodes = self.dataset.meta.total_episodes

    # ------------------------------------------------------------------
    # Per-step capture (called from the sim loop, inside inference_mode)
    # ------------------------------------------------------------------

    def _alloc_ring(self, rgb_buffers: dict[str, torch.Tensor]) -> None:
        """Allocate the GPU ring, pinned host staging, events and copy stream."""
        device = next(iter(rgb_buffers.values())).device
        self._copy_stream = torch.cuda.Stream(device=device)
        self._slot_events = [
            torch.cuda.Event() for _ in range(self.gpu_ring_depth)
        ]
        for name, buf in rgb_buffers.items():
            self._ring[name] = torch.empty(
                (self.gpu_ring_depth, *buf.shape), dtype=buf.dtype, device=device
            )
            self._pinned[name] = torch.empty(
                buf.shape, dtype=buf.dtype, device="cpu", pin_memory=True
            )

    def push_frame_to_buffer(
        self,
        action: np.ndarray,
        observation: np.ndarray,
        rgb_buffers: dict[str, torch.Tensor],
    ):
        """Capture one frame. ``action`` / ``observation`` are CPU numpy (6,);
        each ``rgb_buffers`` tensor is a GPU uint8 (H, W, 3) frame.

        Clones the camera frames into a free GPU ring slot on the current
        (render) stream and hands the slot to the drain thread. Blocks only if
        the ring is full (drain not keeping up); no device-to-host copy happens
        here.
        """
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
                np.asarray(action, dtype=np.float32).copy(),
                np.asarray(observation, dtype=np.float32).copy(),
            )
        )

    def _drain_frames(self) -> None:
        """Copy captured ring slots off the render stream to the episode buffer or writer."""
        while not self._drain_stop_event.is_set():
            try:
                slot, action, observation = self._drain_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                rgb = {}
                if slot is not None:
                    # The ring/pinned buffers are captured under the sim loop's
                    # inference_mode, so mutate them under it here too.
                    with torch.inference_mode():
                        with torch.cuda.stream(self._copy_stream):
                            self._copy_stream.wait_event(self._slot_events[slot])
                            for camera_name in self.cameras:
                                self._pinned[camera_name].copy_(
                                    self._ring[camera_name][slot], non_blocking=True
                                )
                        self._copy_stream.synchronize()
                        rgb = {name: self._pinned[name].numpy().copy() for name in self.cameras}
                    self._free_slots.release()
                if self._writer_process is not None:
                    self._submit("frame", (action, observation, rgb))
                else:
                    self._actions.append(action)
                    self._observations.append(observation)
                    for camera_name, image in rgb.items():
                        self._rgb[camera_name].append(image)
                self._episode_frames += 1
            finally:
                self._drain_queue.task_done()

    # ------------------------------------------------------------------
    # Stop / cancel (called directly from the agent loop)
    # ------------------------------------------------------------------

    @property
    def pending_frames(self) -> int:
        """Number of captured-but-unsaved frames in the in-flight episode."""
        return self._episode_frames + self._drain_queue.qsize()

    def saving_status(self) -> dict:
        """Thread-safe snapshot of background episode-writing progress.

        Returns ``active`` (an episode is currently being written to disk),
        ``written`` / ``total`` frames for that in-progress episode, and
        ``queued`` episodes still waiting behind it. The display uses this to
        show a saving banner and warn against closing the tab mid-write.
        """
        with self._save_lock:
            return {
                "active": self._save_active or self._pending_saves > 0,
                "written": self._save_written,
                "total": self._save_total,
                "queued": self.episode_queue.qsize() + max(self._pending_saves - 1, 0),
                "error": self._save_error,
            }

    def save_episode(self):
        """Queue the captured episode for writing; never waits for encoding."""
        if self.saving_status()["error"]:
            raise RuntimeError(f"Dataset writer failed: {self.saving_status()['error']}")
        self._drain_queue.join()
        total_frames = self._episode_frames
        if total_frames == 0:
            print("[INFO]: No frames captured - nothing to save.")
            self._reset_buffers()
            return
        if self._writer_process is not None:
            with self._save_lock:
                self._pending_saves += 1
            self._submit("save")
            print(f"[INFO]: Episode queued ({total_frames} frames).")
            self._reset_buffers()
            return

        episode_data = {
            "action": self._actions,
            "observation.state": self._observations,
            "rgb": self._rgb,
            "total_frames": total_frames,
        }
        self.episode_queue.put(episode_data)
        print(f"[INFO]: Episode queued ({total_frames} frames).")
        self._reset_buffers()

    def cancel_recording(self):
        """Discard the in-flight episode; saved episodes are unaffected."""
        self._drain_queue.join()
        total_frames = self._episode_frames
        if self._writer_process is not None and total_frames:
            self._submit("cancel")
        self._reset_buffers()
        if total_frames:
            print(f"[INFO]: Episode discarded ({total_frames} frames).")

    def _reset_buffers(self):
        self._actions = []
        self._observations = []
        self._rgb = {name: [] for name in self.cameras}
        self._episode_frames = 0

    def _submit(self, command, payload=None):
        """Queue one command for the writer process, which runs them in order."""
        future = self._writer_process.submit(_process_writer_command, command, payload)
        future.add_done_callback(partial(self._writer_done, command))

    def _writer_done(self, command, future):
        with self._save_lock:
            if command == "save":
                self._pending_saves -= 1
            if future.cancelled():
                return
            if future.exception() is not None:
                self._save_error = self._save_error or str(future.exception())
            elif command == "save":
                self.num_recorded_episodes = future.result()

    # ------------------------------------------------------------------
    # Background writer
    # ------------------------------------------------------------------

    def _async_episode_processor(self):
        while not self._stop_event.is_set():
            try:
                episode = self.episode_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                total_frames = episode["total_frames"]
                actions = episode["action"]
                observations = episode["observation.state"]
                rgb = episode["rgb"]

                with self._save_lock:
                    self._save_active = True
                    self._save_written = 0
                    self._save_total = total_frames

                for i in tqdm(
                    range(total_frames), desc="Writing episode", unit="frame"
                ):
                    frame = {
                        "action": actions[i],
                        "observation.state": observations[i],
                        "task": self.task_name,
                    }
                    for name in self.cameras:
                        frame[f"observation.images.{name}"] = rgb[name][i]
                    self.dataset.add_frame(frame)
                    with self._save_lock:
                        self._save_written = i + 1

                self.dataset.save_episode()
                # LeRobot buffers episode metadata until finalize(), leaving a
                # just-saved dataset unreadable by tools such as
                # lerobot-dataset-viz. Finalize and reopen the writer after
                # every take so each successful save is immediately complete.
                self.dataset.finalize()
                self.dataset = LeRobotDataset.resume(
                    self.repo_id,
                    root=self.dataset_root,
                )
                self.num_recorded_episodes += 1
                print(f"[INFO]: Episode {self.num_recorded_episodes} saved.")
            except Exception as exc:  # noqa: BLE001 - keep the writer thread alive
                with self._save_lock:
                    self._save_error = str(exc)
                print(f"[ERROR]: Failed to write episode: {exc}")
            finally:
                with self._save_lock:
                    self._save_active = False
                self.episode_queue.task_done()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self):
        """Drain the queues, finalize the dataset, and stop the background threads."""
        print("[INFO]: Finalizing dataset (draining pending episodes)...")
        self._drain_queue.join()
        self._drain_stop_event.set()
        self._drain_thread.join(timeout=5)
        self.episode_queue.join()
        self._stop_event.set()
        self._processor_thread.join(timeout=5)
        if self._writer_process is not None:
            try:
                self.num_recorded_episodes = self._writer_process.submit(_process_writer_command, "close").result()
            finally:
                self._writer_process.shutdown(wait=True, cancel_futures=True)
                self._writer_process = None
        if hasattr(self, "dataset"):
            self.dataset.finalize()
            print(
                f"[INFO]: Dataset finalized - {self.num_recorded_episodes} "
                f"episode(s) at {self.dataset.root}"
            )


def _open_dataset(repo_id, root, fps, features, resume, **writer_options):
    """Create a local dataset at ``root``, or with ``resume`` append to it.

    Raises ``ValueError`` for an existing root without ``resume``, or for an
    incomplete root, which is left untouched.
    """
    root = Path(root)
    if root.exists() and resume and not (root / "meta/tasks.parquet").is_file():
        # LeRobot writes tasks with the first saved episode, and its resume API
        # treats missing local metadata as a Hub download. A session that saved
        # nothing leaves only meta/info.json, which holds no data to keep.
        info_path = root / "meta/info.json"
        info = json.loads(info_path.read_text()) if info_path.is_file() else {}
        files = {p.relative_to(root).as_posix() for p in root.rglob("*") if not p.is_dir() or p.is_symlink()}
        if info.get("total_episodes") != 0 or info.get("total_frames") != 0 or files != {"meta/info.json"}:
            raise ValueError(
                f"Local dataset {root} is incomplete: missing meta/tasks.parquet. "
                "Files were left untouched. Inspect the dataset or choose a new --repo_id."
            )
        shutil.rmtree(root)
    if root.exists():
        if not resume:
            raise ValueError(
                f"Dataset root already exists: {root}. Pass --resume to append new episodes to it, "
                "or choose a new --repo_id / remove the existing folder."
            )
        dataset = LeRobotDataset.resume(repo_id, root=root, **writer_options)
        print(f"[INFO]: Resuming dataset - {dataset.root} ({dataset.meta.total_episodes} existing episode(s))")
        return dataset
    dataset = LeRobotDataset.create(
        repo_id, fps=fps, features=features, root=root, robot_type="so101_follower", use_videos=True,
        **writer_options,
    )
    print(f"[INFO]: New dataset initialized - {dataset.root}")
    return dataset


_writer = {}


def _initialize_writer_process():
    # The parent handles terminal Ctrl+C, parks the leader, and then drains
    # accepted episodes; the shared foreground-group signal must not stop the writer.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _process_writer_command(command, payload=None):
    """Run one ordered dataset command in the writer process; return the saved-episode count."""
    if command == "init":
        _writer.update(payload)
        _writer["dataset"] = _open_dataset(
            _writer["repo_id"], _writer["dataset_root"], _writer["fps"], _writer["features"], _writer["resume"],
            **_STREAMING_WRITER,
        )
    elif command == "frame":
        action, observation, rgb = payload
        frame = {"action": action, "observation.state": observation, "task": _writer["task_name"]}
        frame.update({f"observation.images.{name}": image for name, image in rgb.items()})
        _writer["dataset"].add_frame(frame)
    elif command == "save":
        _writer["dataset"].save_episode()
        # Finalize and reopen so every saved episode is readable immediately.
        _writer["dataset"].finalize()
        _writer["dataset"] = LeRobotDataset.resume(
            _writer["repo_id"], root=_writer["dataset_root"], **_STREAMING_WRITER,
        )
        print(f"[INFO]: Episode {_writer['dataset'].meta.total_episodes} saved.", flush=True)
    elif command == "cancel":
        _writer["dataset"].clear_episode_buffer()
    elif command == "close":
        if "dataset" not in _writer:
            return 0
        _writer["dataset"].finalize()
        print(
            f"[INFO]: Dataset finalized - {_writer['dataset'].meta.total_episodes} "
            f"episode(s) at {_writer['dataset'].root}",
            flush=True,
        )
    else:
        raise ValueError(f"Unknown writer command: {command}")
    return _writer["dataset"].meta.total_episodes
