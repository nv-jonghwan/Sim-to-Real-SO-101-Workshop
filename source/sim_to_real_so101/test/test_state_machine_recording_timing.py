# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Check scripted recording at the action/physics boundary with reused buffers."""

import hashlib
import importlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface
from sim_to_real_so101.utils.vials_state_machine import parameters as C

pytestmark = pytest.mark.unit


@pytest.fixture
def script(monkeypatch):
    monkeypatch.setattr("sys.argv", ["vials_state_machine"])
    return importlib.import_module("sim_to_real_so101.scripts.vials_state_machine")


@pytest.fixture
def eval_script(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lerobot_eval"])
    return importlib.import_module("sim_to_real_so101.scripts.lerobot_eval")


class _Manager:
    def __init__(self, env):
        self.env = env
        self.calls = 0

    def apply_action(self):
        self.calls += 1
        self.env.targets[:] = torch.arange(6) + 100 * self.calls
        self.env.events.append("apply")


class _Env:
    num_envs = 2

    def __init__(self, fail=False):
        self.unwrapped = self
        self.fail = fail
        self.events = []
        self.state = torch.full((2, 6), 10.0)
        self.rgb = torch.full((2, 2, 2, 3), 10, dtype=torch.uint8)
        self.targets = torch.full((2, 6), -1.0)
        self.obs = {
            "policy": {"joint_pos_obs": self.state},
            "visual": {"rgb_wrist": self.rgb},
        }
        self.scene = {
            "robot": SimpleNamespace(
                data=SimpleNamespace(
                    joint_pos_target=SimpleNamespace(torch=self.targets),
                )
            )
        }
        self.action_manager = _Manager(self)

    def step(self, actions):
        self.action_manager.apply_action()
        if self.fail:
            raise RuntimeError("physics failed")
        for _ in range(2):
            self.events.append("physics")
            self.state.add_(10)
            self.rgb.add_(10)
        self.state[0] = 99
        self.rgb[0] = 99
        self.targets[0] = -99
        return (
            self.obs,
            None,
            torch.tensor([True, False]),
            torch.tensor([False, False]),
            {},
        )


class _Recorder:
    def __init__(self, env):
        self.cameras = {"wrist": {}}
        self.env = env
        self.frames = []

    def push_batch_to_buffer(self, actions, states, images, mask):
        self.env.events.append("capture")
        self.frames.append(
            (actions.copy(), states.copy(), images["wrist"].clone(), mask.copy())
        )


def _recording(script, env):
    return script._RecordingContext(
        recorder=_Recorder(env),
        interface=SimpleNamespace(sim_radians_to_raw=lambda array: array.copy()),
        joint_ids=[2, 1, 0, 3, 4, 5],
    )


def test_records_measured_gripper_units_without_rescaling_physical_targets(script):
    env = _Env()
    env.targets[:] = 0
    env.state[:] = 0
    env.targets[:, 5] = torch.tensor([C.PINCH_MIN_RAD, C.RELEASE_MAX_RAD])
    env.state[:, 5] = np.deg2rad(9.4722700932)
    original_targets = env.targets.clone()
    original_states = env.state.clone()
    recording = _recording(script, env)
    recording.interface = LeRobotSO101Interface("unused", "unused", "cpu")
    script._capture_recording_step(recording, env, env.obs)
    actions, states, _, _ = recording.recorder.frames[0]
    np.testing.assert_allclose(actions[:, 5], [1.0, 46.0], atol=2e-5)
    np.testing.assert_allclose(states[:, 5], 16.8350168350, atol=2e-5)
    np.testing.assert_allclose(recording.interface.raw_to_sim_radians(actions), env.targets, atol=1e-7)
    torch.testing.assert_close(env.targets, original_targets)
    torch.testing.assert_close(env.state, original_states)


def test_records_control_target_before_decimated_physics_or_reset(script):
    env = _Env()
    recording = _recording(script, env)
    script._step_with_recording(env, None, env.obs, recording)
    assert env.events == ["apply", "capture", "physics", "physics"]
    assert len(recording.recorder.frames) == 1
    actions, states, rgb, mask = recording.recorder.frames[0]
    np.testing.assert_array_equal(
        actions,
        np.tile([102, 101, 100, 103, 104, 105], (2, 1)),
    )
    np.testing.assert_array_equal(states, np.full((2, 6), 10))
    assert torch.all(rgb == 10)
    np.testing.assert_array_equal(mask, [True, True])
    assert env.state[0, 0] == 99
    assert "apply_action" not in vars(env.action_manager)


@pytest.mark.parametrize("instance_override", [False, True])
def test_action_manager_restored_when_step_fails(script, instance_override):
    env = _Env(fail=True)
    if instance_override:
        env.action_manager.apply_action = env.action_manager.apply_action
    original = env.action_manager.apply_action
    with pytest.raises(RuntimeError, match="physics failed"):
        script._step_with_recording(env, None, env.obs, _recording(script, env))
    assert env.action_manager.apply_action == original
    assert ("apply_action" in vars(env.action_manager)) == instance_override


def test_successful_terminal_transition_is_accepted_failures_discarded(script):
    events = []
    recorder = SimpleNamespace(
        accept_episode=lambda env_id: events.append(("accept", env_id)) or True,
        discard_episode=lambda env_id: events.append(("discard", env_id)),
    )
    terms = {
        "success": torch.tensor([True, False, True, True]),
        "vial_escaped": torch.tensor([False, True, False, True]),
    }
    env = SimpleNamespace(
        termination_manager=SimpleNamespace(active_terms=list(terms), get_term=terms.__getitem__)
    )
    count = script._finish_recording_episodes(
        recorder,
        env,
        torch.tensor([True, True, True, True]),
        torch.tensor([False, False, True, False]),
        0,
        5,
    )
    assert count == 1
    assert events == [("accept", 0), ("discard", 1), ("discard", 2), ("discard", 3)]


@pytest.mark.parametrize(
    "failures", [(), ("flush",), ("recorder",), ("flush", "recorder"), ("display",), ("recorder", "display")]
)
def test_shutdown_closes_every_resource_even_if_recording_or_display_fails(script, monkeypatch, failures):
    events = []

    def finish(name):
        events.append(name)
        if name in failures:
            raise RuntimeError(name)

    recorder = SimpleNamespace(
        num_staged_episodes=1,
        flush_dataset=lambda **kwargs: finish("flush"),
        close=lambda: finish("recorder"),
    )
    display = SimpleNamespace(close=lambda: finish("display"))
    robot = SimpleNamespace(
        joint_names=script.DISPLAY_JOINT_NAMES,
        data=SimpleNamespace(joint_pos=SimpleNamespace(warp=None)),
    )
    env = SimpleNamespace(
        step_dt=1 / 30, num_envs=1, device="cpu", cfg=SimpleNamespace(seed=0),
        scene={"robot": robot}, sim=SimpleNamespace(),
        reset=lambda: ({}, {}), close=lambda: finish("env"),
    )
    env.unwrapped = env
    cfg = SimpleNamespace(scene=SimpleNamespace(), sim=SimpleNamespace())
    machine = SimpleNamespace(complete=None, gripper_pose_b=lambda env: None, reset=lambda *args: None)
    monkeypatch.setattr(script.args_cli, "record", True)
    monkeypatch.setattr(script.args_cli, "num_episodes", 1)
    monkeypatch.setattr(script, "resolve_task_config", lambda *args: (cfg, None))
    monkeypatch.setattr(script, "apply_camera_selection", lambda *args: set())
    monkeypatch.setattr(script, "_validate_recording_args", lambda *args: None)
    monkeypatch.setattr(script, "launch_simulation", lambda *args: nullcontext())
    monkeypatch.setattr(script.gym, "make", lambda *args, **kwargs: env)
    monkeypatch.setattr(script, "VialsStateMachine", lambda **kwargs: machine)
    monkeypatch.setattr(script.wp, "to_torch", lambda value: value)
    monkeypatch.setattr(script, "_build_recording", lambda *args: SimpleNamespace(recorder=recorder))
    monkeypatch.setattr(script, "build_sensor_display", lambda *args, **kwargs: display)

    expected_error = pytest.raises(RuntimeError, match=failures[-1]) if failures else nullcontext()
    with expected_error:
        script.main()
    assert events == ["flush", "recorder", "display", "env"]


@pytest.mark.parametrize(
    "terminated,truncated,success,expected",
    [
        (True, False, True, (True, True)),
        (True, False, False, (True, False)),
        (False, True, False, (True, False)),
        (False, False, False, (False, False)),
    ],
)
def test_eval_counts_only_success_term(
    eval_script, terminated, truncated, success, expected
):
    result = eval_script._episode_outcome(
        torch.tensor([terminated]),
        torch.tensor([truncated]),
        torch.tensor([success]),
    )
    assert result == expected


def test_eval_rejects_multiple_environments(eval_script):
    with pytest.raises(ValueError, match="exactly one environment"):
        eval_script._require_single_environment(2)


def _wait_for_encodings(recorder, count):
    deadline = time.monotonic() + 60
    while recorder.num_recorded_episodes < count:
        assert time.monotonic() < deadline, "Background encoding did not finish"
        time.sleep(0.05)


def test_background_encoding_continues_during_collection_and_preserves_order(tmp_path, monkeypatch):
    from sim_to_real_so101.utils.vials_state_machine import recorder as module

    second_encoded = threading.Event()
    encode = module._encode_staged_episode
    completed = []

    def encode_second_first(path, *args):
        if path.name == "episode_000000":
            assert second_encoded.wait(30)
        result = encode(path, *args)
        completed.append(path.name)
        if path.name == "episode_000001":
            second_encoded.set()
        return result

    monkeypatch.setattr(module, "_encode_staged_episode", encode_second_first)
    monkeypatch.setattr(module, "ProcessPoolExecutor", lambda **kw: ThreadPoolExecutor(kw["max_workers"]))
    recorder = module.OfflineLeRobotRecorder(
        task_name="place the vial", repo_id="test/background", fps=30, cameras={},
        dataset_root=str(tmp_path / "dataset"), staging_root=str(tmp_path / "staging"), num_envs=2,
    )
    try:
        for step in range(3):
            actions = np.full((2, 6), step, dtype=np.float32)
            actions[1] += 10
            recorder.push_batch_to_buffer(actions, actions + 100, {}, np.ones(2, dtype=bool))
        assert recorder.accept_episode(1)
        assert recorder.accept_episode(0)
        _wait_for_encodings(recorder, 2)
        assert completed == ["episode_000001", "episode_000000"]
        assert not (tmp_path / "dataset").exists()
        recorder.flush_dataset(resume=False)
        dataset = recorder.dataset
        assert dataset.num_episodes == 2
        np.testing.assert_array_equal(dataset.hf_dataset["episode_index"], [0, 0, 0, 1, 1, 1])
        np.testing.assert_array_equal(np.asarray(dataset.hf_dataset["action"])[:, 0], [10, 11, 12, 0, 1, 2])
        np.testing.assert_array_equal(np.asarray(dataset.hf_dataset["observation.state"])[:, 0], [110, 111, 112, 100, 101, 102])
    finally:
        recorder.close()
    assert not (tmp_path / "staging").exists()


@pytest.mark.parametrize("existing", [("dataset",), ("staging",), ("dataset", "staging")])
def test_recording_rejects_existing_output_at_startup(tmp_path, existing):
    from sim_to_real_so101.utils.vials_state_machine.recorder import (
        OfflineLeRobotRecorder,
    )

    for name in existing:
        root = tmp_path / name
        root.mkdir()
        (root / "keep.txt").write_text("existing recording")
    with pytest.raises(FileExistsError, match="cannot resume existing output"):
        OfflineLeRobotRecorder(
            task_name="place the vial", repo_id="test/fresh", fps=30, cameras={}, num_envs=1,
            dataset_root=str(tmp_path / "dataset"), staging_root=str(tmp_path / "staging"),
        )
    assert {path.name for path in tmp_path.iterdir()} == set(existing)
    for name in existing:
        assert (tmp_path / name / "keep.txt").read_text() == "existing recording"


def test_spawned_video_encoders_merge_and_report_errors(tmp_path):
    from lerobot.datasets import LeRobotDataset
    from sim_to_real_so101.utils.vials_state_machine.recorder import (
        OfflineLeRobotRecorder,
    )

    cameras = {name: {"height": 32, "width": 32} for name in ("wrist", "external")}
    config = {
        "task_name": "place the vial", "repo_id": "test/background", "fps": 30, "cameras": cameras,
        "dataset_root": str(tmp_path / "dataset"), "staging_root": str(tmp_path / "staging"), "num_envs": 1,
    }
    staging = tmp_path / "staging"

    def episode(value):
        return {
            "action": np.full((3, 6), value, dtype=np.float32),
            "observation.state": np.full((3, 6), value + 1, dtype=np.float32),
            "rgb": {name: np.full((3, 32, 32, 3), value, dtype=np.uint8) for name in cameras},
            "total_frames": 3,
        }

    recorder = OfflineLeRobotRecorder(**config)
    try:
        for value in [32, 192, 96]:
            recorder.episode_queue.put(episode(value))
        _wait_for_encodings(recorder, 3)
        video_hashes = sorted(hashlib.sha256(path.read_bytes()).hexdigest() for path in staging.rglob("*.mp4"))
        recorder.flush_dataset(resume=False)
    finally:
        recorder.close()

    dataset = LeRobotDataset(config["repo_id"], root=config["dataset_root"], return_uint8=True)
    assert dataset.num_episodes == 3
    assert len(dataset) == 9
    np.testing.assert_array_equal(dataset.hf_dataset["episode_index"], np.repeat([0, 1, 2], 3))
    np.testing.assert_array_equal(dataset.hf_dataset["index"], np.arange(9))
    for index, value in enumerate([32, 192, 96]):
        for frame_index in range(index * 3, index * 3 + 3):
            frame = dataset[frame_index]
            np.testing.assert_array_equal(frame["action"], np.full(6, value))
            np.testing.assert_array_equal(frame["observation.state"], np.full(6, value + 1))
            assert frame["task"] == config["task_name"]
            for name in cameras:
                assert abs(frame[f"observation.images.{name}"].float().mean().item() - value) < 4
    assert video_hashes == sorted(
        hashlib.sha256(path.read_bytes()).hexdigest() for path in (tmp_path / "dataset").rglob("*.mp4")
    )
    assert not staging.exists()

    config["dataset_root"] = str(tmp_path / "failed_dataset")
    config["staging_root"] = str(tmp_path / "failed_staging")
    recorder = OfflineLeRobotRecorder(**config)
    bad_episode = episode(0)
    bad_episode["observation.state"] = np.zeros((3, 5), dtype=np.float32)
    recorder.episode_queue.put(bad_episode)
    try:
        with pytest.raises(RuntimeError, match="failed to stage or encode"):
            recorder.flush_dataset(resume=False)
    finally:
        with pytest.raises(RuntimeError, match="failed to stage or encode"):
            recorder.close()
    assert (tmp_path / "failed_staging").exists()
    assert not (tmp_path / "failed_dataset").exists()
