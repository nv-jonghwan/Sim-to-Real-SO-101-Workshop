# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Exercise the teleop loop with reused sensor buffers and distinct time steps."""

import importlib
import json
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest
import torch

pytestmark = pytest.mark.unit


@pytest.fixture
def local_recorder(tmp_path, monkeypatch):
    from huggingface_hub import HfApi
    from sim_to_real_so101.utils.lerobot_recorder import LeRobotRecorder

    def unexpected_hub_call(*args, **kwargs):
        pytest.fail("Local recording must not look up Hub repositories")

    monkeypatch.setattr(HfApi, "list_repo_refs", unexpected_hub_call)
    recorders = []

    def create(cameras=None):
        recorder = LeRobotRecorder("Pick up the vial", "test/local", str(tmp_path / "dataset"), 30, cameras or {})
        recorders.append(recorder)
        return recorder

    yield create
    for recorder in recorders:
        recorder.close()


def test_resume_empty_camera_session(local_recorder, tmp_path):
    cameras = {name: {"width": 640, "height": 480} for name in ("wrist", "external")}
    first = local_recorder(cameras)
    first.init_dataset()
    first.close()
    assert not (tmp_path / "dataset/meta/tasks.parquet").exists()

    second = local_recorder(cameras)
    second.init_dataset(resume=True)
    assert second.num_recorded_episodes == 0
    assert second.dataset.meta.total_frames == 0
    assert set(second.dataset.meta.video_keys) == {f"observation.images.{name}" for name in cameras}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dataset"]


def test_resume_empty_then_append_saved_episodes(local_recorder, tmp_path):
    first = local_recorder()
    first.init_dataset()
    first.close()
    for episode in range(2):
        recorder = local_recorder()
        recorder.init_dataset(resume=True)
        assert recorder.num_recorded_episodes == episode
        for _ in range(3):
            recorder.push_frame_to_buffer(np.full(6, episode), np.zeros(6), {})
        recorder.save_episode()
        recorder.close()
        assert recorder.num_recorded_episodes == episode + 1
        assert recorder.dataset.meta.total_frames == (episode + 1) * 3

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    dataset = LeRobotDataset("test/local", root=tmp_path / "dataset")
    assert len(dataset) == 6
    assert dataset[0]["episode_index"].item() == 0
    assert dataset[3]["episode_index"].item() == 1
    assert dataset[0]["action"].tolist() == [0] * 6
    assert dataset[3]["action"].tolist() == [1] * 6


def test_recorder_reports_disk_failure_and_refuses_more_saves(local_recorder, monkeypatch):
    recorder = local_recorder()
    recorder.init_dataset()

    def disk_full(frame):
        raise OSError("disk full")

    monkeypatch.setattr(recorder.dataset, "add_frame", disk_full)
    recorder.push_frame_to_buffer(np.zeros(6), np.zeros(6), {})
    recorder.save_episode()
    recorder.close()
    assert recorder.saving_status()["error"] == "disk full"
    assert recorder.num_recorded_episodes == 0
    with pytest.raises(RuntimeError, match="disk full"):
        recorder.save_episode()


@pytest.mark.parametrize("case", ["saved_counts", "partial_data", "missing_info", "no_resume"])
def test_resume_preserves_incomplete_or_unapproved_root(local_recorder, tmp_path, case):
    recorder = local_recorder()
    recorder.init_dataset()
    recorder.close()
    root = tmp_path / "dataset"
    info_path = root / "meta/info.json"
    if case == "saved_counts":
        info = json.loads(info_path.read_text())
        info.update(total_episodes=1, total_frames=3)
        info_path.write_text(json.dumps(info))
    elif case == "partial_data":
        (root / "partial.mp4").write_bytes(b"partial recording")
    elif case == "missing_info":
        info_path.unlink()
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    second = local_recorder()
    with pytest.raises(ValueError, match="already exists" if case == "no_resume" else "incomplete"):
        second.init_dataset(resume=case != "no_resume")
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setattr("sys.argv", ["lerobot_agent"])
    return importlib.import_module("sim_to_real_so101.scripts.lerobot_agent")


@pytest.mark.parametrize("fps,stride", [(30, 1), (15, 2), (10, 3), (1, 30)])
def test_recording_rate_preserves_timebase(agent, fps, stride):
    assert agent._recording_decimation(1 / 30, fps) == stride


@pytest.mark.parametrize("fps", [0, -1, 20, 29, 31, 60])
def test_recording_rate_rejects_inaccurate_timebase(agent, fps):
    with pytest.raises(ValueError, match="divide the control rate"):
        agent._recording_decimation(1 / 30, fps)


def test_control_pacer_sleeps_only_until_deadline(agent, monkeypatch):
    sleeps = []
    monkeypatch.setattr(agent.time, "perf_counter", lambda: 10.01)
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)

    next_deadline = agent._pace_control_loop(10.03, 1 / 30)

    assert sleeps == [pytest.approx(0.02)]
    assert next_deadline == pytest.approx(10.03 + 1 / 30)


def test_control_pacer_rebases_without_sleep_after_overrun(agent, monkeypatch):
    sleeps = []
    monkeypatch.setattr(agent.time, "perf_counter", lambda: 10.04)
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)

    next_deadline = agent._pace_control_loop(10.03, 1 / 30)

    assert sleeps == []
    assert next_deadline == pytest.approx(10.04 + 1 / 30)


class _Recorder:
    num_recorded_episodes = 0

    def __init__(self):
        self.cameras = {"wrist": {}}
        self.frames = []
        self.saved = []
        self.discarded = []
        self.events = []

    @property
    def pending_frames(self):
        return len(self.frames)

    def push_frame_to_buffer(self, action, state, images):
        self.events.append("capture")
        self.frames.append((action.copy(), state.copy(), images["wrist"].clone()))

    def save_episode(self):
        self.saved.append(self.frames)
        self.frames = []

    def cancel_recording(self):
        self.discarded.append(self.frames)
        self.frames = []

    def init_dataset(self, **kwargs):
        pass

    def saving_status(self):
        return {}

    def close(self):
        pass


class _Environment:
    device = "cpu"
    step_dt = 1 / 30
    action_space = SimpleNamespace(shape=(1, 6))

    def __init__(self, recorder, max_steps, done_steps):
        self.observation_space = {}
        self.unwrapped = self
        self.steps = 0
        self.resets = 0
        self.max_steps = max_steps
        self.done_steps = done_steps
        self.recorder = recorder
        self.state = torch.zeros(1, 6)
        self.rgb = torch.zeros(1, 2, 2, 3, dtype=torch.uint8)
        self.obs = {"policy": {"joint_pos_obs": self.state}, "visual": {"rgb_wrist": self.rgb}}
        self.camera = SimpleNamespace(
            data=SimpleNamespace(output={"rgb": self.rgb}),
            reset=lambda: None,
            update=self.refresh,
        )
        self.scene = _Scene(self.camera)
        self.observation_manager = SimpleNamespace(compute_group=lambda name: {"rgb_wrist": self.rgb})
        self.sim = SimpleNamespace(
            visualizers=[SimpleNamespace(is_running=lambda: self.steps < self.max_steps, is_closed=False)],
            get_physics_step_count=lambda: self.steps * 2,
        )
        self.applied = []

    def refresh(self, dt, force_recompute):
        assert dt == 0 and force_recompute
        self.rgb.fill_(int(self.state[0, 0]))

    def reset(self, options=None):
        self.resets += 1
        self.state.fill_(self.resets * 20)
        self.rgb.fill_(255)
        return self.obs, {}

    def step(self, actions):
        self.recorder.events.append("step")
        self.applied.append(actions.clone())
        self.steps += 1
        done = self.steps in self.done_steps
        if done:
            self.reset()
        else:
            self.state.add_(1)
            self.rgb.fill_(int(self.state[0, 0]))
        return self.obs, None, torch.tensor([done]), torch.tensor([False]), {}

    def close(self):
        pass


class _Scene(dict):
    def __init__(self, camera):
        super().__init__(camera_wrist=camera)
        self.cfg = SimpleNamespace(camera_wrist=SimpleNamespace(height=2, width=2))


def _run(agent, monkeypatch, controls, *, fps=30, done_steps=()):
    recorder = _Recorder()
    env = _Environment(recorder, len(controls), done_steps)
    controls_iter = iter(controls)
    display = SimpleNamespace(
        drain_control_actions=lambda: next(controls_iter),
        update=lambda *args: None,
        push_telemetry=lambda *args: None,
        push_status=lambda *args: None,
        flush=lambda: None,
        close=lambda: None,
    )
    iface = SimpleNamespace(
        connect=lambda **kwargs: None,
        disconnect=lambda: None,
        read_action=lambda **kwargs: (
            np.full(6, 100 + env.steps, dtype=np.float32),
            torch.full((6,), 100 + env.steps, dtype=torch.float32),
        ),
        sim_radians_to_raw=lambda value: value.copy(),
    )
    cfg = SimpleNamespace(scene=SimpleNamespace(num_envs=1), sim=SimpleNamespace(dt=1 / 60), decimation=2)
    monkeypatch.setattr(agent, "resolve_task_config", lambda *args: (cfg, None))
    monkeypatch.setattr(agent, "apply_camera_selection", lambda *args: {"camera_wrist"})
    monkeypatch.setattr(agent, "launch_simulation", lambda *args: nullcontext())
    monkeypatch.setattr(agent.gym, "make", lambda *args, **kwargs: env)
    monkeypatch.setattr(agent, "LeRobotSO101Interface", lambda **kwargs: iface)
    monkeypatch.setattr(agent, "LeRobotRecorder", lambda **kwargs: recorder)
    monkeypatch.setattr(agent, "build_sensor_display", lambda *args, **kwargs: display)
    monkeypatch.setattr(agent, "dataset_root_from_repo_id", lambda value: "/unused")
    monkeypatch.setattr(
        agent,
        "_pace_control_loop",
        lambda next_step_deadline, step_dt: next_step_deadline + step_dt,
    )
    monkeypatch.setattr(agent, "args_cli", SimpleNamespace(
        task="test", cameras="all", num_envs=1, device=None, port="unused",
        robot_id="unused", rerun=False, repo_id="test/timing", task_name="test",
        record_fps=fps, resume=False,
    ))
    # Reset controls consume a loop iteration without a physics step.
    env.max_steps -= sum("reset_world" in row for row in controls)
    agent.main()
    return env, recorder


def _assert_frame(frame, state, action):
    np.testing.assert_array_equal(frame[0], np.full(6, action))
    np.testing.assert_array_equal(frame[1], np.full(6, state))
    assert torch.all(frame[2] == state)


def test_capture_precedes_action_and_owns_mutated_buffers(agent, monkeypatch):
    env, recorder = _run(agent, monkeypatch, [["toggle_recording"], [], ["toggle_recording"]])
    assert recorder.events == ["capture", "step", "capture", "step", "step"]
    assert len(recorder.saved[0]) == 2
    _assert_frame(recorder.saved[0][0], 20, 100)
    _assert_frame(recorder.saved[0][1], 21, 101)
    assert env.state[0, 0] == 23
    assert [int(a[0, 0]) for a in env.applied] == [100, 101, 102]


def test_immediate_stop_start_restarts_subsampling(agent, monkeypatch):
    _, recorder = _run(agent, monkeypatch, [
        ["toggle_recording"], ["toggle_recording", "toggle_recording"],
        [], [], ["toggle_recording"],
    ], fps=15)
    assert [len(frames) for frames in recorder.saved] == [1, 2]
    _assert_frame(recorder.saved[0][0], 20, 100)
    _assert_frame(recorder.saved[1][0], 21, 101)
    _assert_frame(recorder.saved[1][1], 23, 103)


def test_manual_reset_discards_take_and_refreshes_initial_images(agent, monkeypatch):
    env, recorder = _run(agent, monkeypatch, [
        ["toggle_recording"], ["reset_world"], ["toggle_recording"], ["toggle_recording"],
    ])
    assert env.resets == 2
    _assert_frame(recorder.discarded[0][0], 20, 100)
    _assert_frame(recorder.saved[0][0], 40, 101)


def test_automatic_reset_cannot_stitch_episodes(agent, monkeypatch):
    _, recorder = _run(agent, monkeypatch, [
        ["toggle_recording"], [], ["toggle_recording"], ["toggle_recording"],
    ], done_steps=(1,))
    assert len(recorder.discarded) == 1
    _assert_frame(recorder.discarded[0][0], 20, 100)
    assert len(recorder.saved[0]) == 1
    _assert_frame(recorder.saved[0][0], 41, 102)


class _LeaderHardware:
    def __init__(self):
        self.position = np.full(6, 20.0)
        self.sag = np.zeros(6)
        self.events = []
        self.jammed = False
        self.bus = SimpleNamespace(disconnect=lambda **kw: self.events.append(("disconnect", kw)))

    def get_action(self):
        return dict(zip([f"joint{i}.pos" for i in range(6)], self.position.tolist(), strict=True))

    def send_feedback(self, target):
        values = np.array(list(target.values()))
        self.events.append(("goal", values.copy()))
        if not self.jammed:
            self.position = values - self.sag

    def enable_torque(self):
        self.events.append(("enable", None))

    def disable_torque(self):
        self.events.append(("disable", None))


@pytest.fixture
def leader(monkeypatch):
    from sim_to_real_so101.utils.dagger import dagger_leader

    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(dagger_leader, "time", SimpleNamespace(monotonic=lambda: clock.now))
    hardware = _LeaderHardware()
    controller = dagger_leader.DaggerLeader(hardware, list(hardware.get_action()), rest_pose=np.full(6, 10.0))
    controller.tick(clock.now)
    def sleep(seconds):
        clock.now += seconds
        controller.tick(clock.now)
    dagger_leader.time.sleep = sleep
    return controller, hardware, clock


class _ImmediateExecutor:
    def __init__(self, **kwargs):
        pass

    def submit(self, fn, *args):
        from concurrent.futures import Future
        future = Future()
        try:
            future.set_result(fn(*args))
        except Exception as exc:  # noqa: BLE001 - emulate Future exception propagation
            future.set_exception(exc)
        return future

    def shutdown(self, **kwargs):
        pass


@pytest.fixture
def dagger(monkeypatch, leader):
    from sim_to_real_so101.utils.dagger import sim_dagger

    monkeypatch.setattr(sim_dagger, "ThreadPoolExecutor", _ImmediateExecutor)
    controller, hardware, clock = leader
    recorder = _Recorder()
    env = _Environment(recorder, max_steps=100, done_steps=())
    env.termination_manager = SimpleNamespace(
        active_terms=["success", "unsafe_rack_state", "escaped_vial"],
        get_term=lambda name: torch.tensor([name == "success"]),
    )
    iface = SimpleNamespace(
        sim_radians_to_raw=lambda x: x.copy(), raw_to_sim_radians=lambda x: x.copy(),
    )
    policy = SimpleNamespace(reset=lambda: None, close=lambda: None, get_action=lambda state, images: state + 2)
    session = sim_dagger.SimDAgger(env, iface, policy, recorder, {"camera_wrist"}, controller)
    session.reset()
    _until(session, clock, "paused")
    recorder.discarded.clear()
    yield session, hardware, clock
    session.stop()


def _tick(session, clock):
    clock.now += 1 / 30
    session.leader.tick(clock.now)
    session.advance(lambda: ())


def _until(session, clock, phase):
    for _ in range(250):
        _tick(session, clock)
        if session.phase == phase:
            return
    pytest.fail(f"Did not reach {phase}: {session.phase}, {session.message}")


def _guide(session, clock):
    session.handle("toggle_correction")
    _until(session, clock, "correction_ready")
    session.handle("guide_start")
    _until(session, clock, "correcting")


def test_dagger_clutch_preserves_target_without_torque_drop_on_tab(dagger):
    session, hardware, clock = dagger
    session.handle("pause_resume")
    _tick(session, clock)
    assert session.env.steps == 1
    previous_target = session.action.clone()
    assert previous_target[0] != session.obs["policy"]["joint_pos_obs"][0, 0]
    session.handle("toggle_correction")
    assert session.phase == "autonomous"
    session.handle("pause_resume")
    assert session.phase == "paused"
    np.testing.assert_allclose(hardware.position, np.full(6, 20.0))
    session.handle("toggle_correction")
    _until(session, clock, "correction_ready")
    assert session.env.steps == 1
    assert not any(event == "disable" for event, _ in hardware.events)
    session.handle("guide_start")
    _until(session, clock, "correcting")
    assert hardware.events[-1][0] == "disable"
    _tick(session, clock)
    torch.testing.assert_close(session.action, previous_target)
    hardware.position += 10
    _tick(session, clock)
    assert torch.max(session.action[:5] - previous_target[:5]) <= 2.00001
    assert len(session.recorder.frames) == 2
    np.testing.assert_allclose(session.recorder.frames[-1][0], session.action.numpy())
    session.handle("hold_position")
    before = session.env.steps
    _tick(session, clock)
    assert session.env.steps == before
    assert hardware.events[-1][0] == "enable"
    _until(session, clock, "correction_ready")
    session.handle("pause_resume")
    _until(session, clock, "autonomous")
    assert len(session.recorder.saved[0]) == 2
    assert session.env.steps == before


@pytest.mark.parametrize("command", ["cancel_episode", "reset_world", "stop_session", "hold_position", "control_lost"])
def test_dagger_controls_freeze_and_hold(dagger, command):
    session, hardware, clock = dagger
    _guide(session, clock)
    _tick(session, clock)
    before = session.env.steps
    session.handle(command)
    for _ in range(120):
        _tick(session, clock)
    assert session.env.steps == before
    assert not session.recorder.saved
    assert hardware.events[-1][0] != "disable"
    if command in {"cancel_episode", "reset_world"}:
        assert not session.recorder.frames
    if command == "reset_world":
        np.testing.assert_allclose(hardware.position, np.full(6, 40))
        assert session.phase == "paused"
    if command == "stop_session":
        assert not session.running
        session.stop()
        np.testing.assert_allclose(hardware.position, np.full(6, 10))


def test_dagger_publishes_reset_phase_before_blocking_follower_move(dagger):
    session, _hardware, clock = dagger
    published = []
    session.on_phase = lambda: published.append(session.phase)
    reset = session.env.reset
    session.env.reset = lambda options=None: (published.append("follower move"), reset(options))[1]
    session.handle("reset_world")
    assert published[:2] == ["resetting", "follower move"]
    _until(session, clock, "paused")
    assert published[-1] == "paused"


def test_dagger_leader_follows_policy_holds_on_pause_and_returns_on_reset(dagger):
    session, hardware, clock = dagger
    session.leader_follows = True
    session.handle("pause_resume")
    for _ in range(10):
        _tick(session, clock)
    np.testing.assert_allclose(hardware.position, session.env.state[0].numpy(), atol=1.0)
    session.handle("pause_resume")
    _tick(session, clock)
    held = hardware.position.copy()
    for _ in range(5):
        _tick(session, clock)
    np.testing.assert_allclose(hardware.position, held)
    session.handle("reset_world")
    _until(session, clock, "paused")
    np.testing.assert_allclose(hardware.position, np.full(6, 40.0))


def test_dagger_exit_returns_to_taught_rest_after_sim_reset(dagger):
    session, hardware, clock = dagger
    session.handle("reset_world")
    _until(session, clock, "paused")
    np.testing.assert_allclose(hardware.position, np.full(6, 40))
    session.handle("stop_session")
    for _ in range(120):
        _tick(session, clock)
    assert not session.running
    session.stop()
    np.testing.assert_allclose(hardware.position, np.full(6, 10))
    assert not any(event == "disable" for event, _ in hardware.events)


@pytest.mark.parametrize("outcome", ["success", "unsafe_rack_state", "escaped_vial", "success_and_escape", "time_out"])
def test_dagger_terminal_saves_only_success_and_returns_to_new_reset_pose(dagger, outcome):
    session, hardware, clock = dagger
    session.env.done_steps = (1,)
    session.env.termination_manager.get_term = lambda name: torch.tensor([
        name == outcome or outcome == "success_and_escape" and name in {"success", "escaped_vial"}
    ])
    if outcome == "time_out":
        step = session.env.step
        def timeout(action):
            obs, reward, terminated, _truncated, info = step(action)
            return obs, reward, torch.tensor([False]), terminated, info
        session.env.step = timeout
    _guide(session, clock)
    _tick(session, clock)
    assert session.phase == "resetting"
    assert bool(session.recorder.saved) == (outcome == "success")
    assert not session.recorder.frames
    _until(session, clock, "paused")
    np.testing.assert_allclose(hardware.position, np.full(6, 40))
    assert session.env.steps == 1


def test_dagger_motor_watchdog_holds_without_simulation_progress(leader):
    controller, hardware, clock = leader
    controller.guide()
    controller.tick(clock.now)
    hardware.position += 2
    clock.now += 0.6
    controller.tick(clock.now)
    assert controller.snapshot()["mode"] == "fault"
    assert "heartbeat expired" in controller.snapshot()["error"]
    assert hardware.events[-2][0] == "goal"
    assert hardware.events[-1][0] == "enable"
    np.testing.assert_array_equal(hardware.events[-2][1], hardware.position)


def test_dagger_alignment_requires_readback_and_is_rate_limited(leader):
    controller, hardware, clock = leader
    hardware.jammed = True
    controller.move_to(np.full(6, 40))
    for _ in range(180):
        controller.renew()
        clock.now += 1 / 30
        controller.tick(clock.now)
        if controller.snapshot()["mode"] == "fault":
            break
    assert controller.snapshot()["mode"] == "fault"
    assert "alignment timed out" in controller.snapshot()["error"]
    goals = [value for event, value in hardware.events if event == "goal"]
    assert np.max(np.diff(np.array(goals)[:-1, :5], axis=0)) <= 1.00001
    assert hardware.events[-1][0] == "enable"


def test_dagger_alignment_settles_under_gravity_sag_and_hold_does_not_resag(leader):
    controller, hardware, clock = leader
    hardware.sag = np.array([0.1, 1.2, 3.4, 1.4, 0.2, 0.1])
    controller.move_to(np.full(6, 40))
    for _ in range(180):
        controller.renew()
        clock.now += 1 / 30
        controller.tick(clock.now)
        if controller.snapshot()["mode"] == "holding":
            break
    assert controller.snapshot()["mode"] == "holding"
    settled = hardware.position.copy()
    controller.hold()
    for _ in range(10):
        clock.now += 1 / 30
        controller.tick(clock.now)
    assert controller.snapshot()["mode"] == "holding"
    np.testing.assert_allclose(hardware.position, settled)


def test_dagger_leader_follow_is_rate_limited_and_retargets_without_rehold(leader):
    controller, hardware, clock = leader
    enables = [event for event, _ in hardware.events].count("enable")
    for _ in range(40):
        controller.follow(np.full(6, 35.0))
        clock.now += 1 / 30
        controller.tick(clock.now)
    goals = np.array([value for event, value in hardware.events if event == "goal"])
    assert np.max(np.abs(np.diff(goals[:, :5], axis=0))) <= 1.00001
    np.testing.assert_allclose(hardware.position, np.full(6, 35.0))
    assert [event for event, _ in hardware.events].count("enable") == enables + 1
    controller.hold()
    clock.now += 1 / 30
    controller.tick(clock.now)
    assert controller.snapshot()["mode"] == "holding"
    np.testing.assert_allclose(hardware.position, np.full(6, 35.0))


def test_dagger_held_drift_and_serial_loss_report_unconfirmed_support(leader):
    controller, hardware, clock = leader
    read = hardware.get_action
    glitch = iter([ConnectionError("no status packet")])

    def one_lost_packet():
        for error in glitch:
            raise error
        return read()

    hardware.get_action = one_lost_packet
    clock.now += 1 / 30
    controller.tick(clock.now)
    assert controller.snapshot()["mode"] == "holding"
    hardware.get_action = read
    hardware.position += 6
    for _ in range(3):
        clock.now += 1 / 30
        controller.tick(clock.now)
    assert controller.snapshot()["mode"] == "fault"
    assert "drifted" in controller.snapshot()["error"]

    def disconnected():
        raise ConnectionError("USB disconnected")

    hardware.get_action = disconnected
    controller.hold()
    controller.tick(clock.now)
    assert "unable to hold" in controller.snapshot()["error"]
    assert not controller.close()


def test_dagger_stale_serial_feedback_is_not_used_for_guidance(leader):
    controller, _hardware, clock = leader
    clock.now += 0.6
    assert "feedback is stale" in controller.snapshot()["error"]


@pytest.mark.parametrize("calibrated,mode", [(True, 0), (False, 0), (True, 1)])
def test_dagger_held_connection_does_not_run_torque_releasing_configuration(monkeypatch, calibrated, mode):
    from sim_to_real_so101.utils import lerobot_interface

    hardware = _LeaderHardware()
    hardware.is_calibrated = calibrated
    hardware.bus.connect = lambda: hardware.events.append(("connect", None))
    hardware.bus.sync_read = lambda *args, **kwargs: {"joint": mode}
    monkeypatch.setattr(lerobot_interface, "SOLeader", lambda cfg: hardware)
    iface = lerobot_interface.LeRobotSO101Interface("unused", "test", "cpu")
    if calibrated and mode == 0:
        iface.connect(hold_position=True)
        assert [event for event, _ in hardware.events] == ["connect", "goal", "enable"]
    else:
        with pytest.raises(RuntimeError):
            iface.connect(hold_position=True)
        assert hardware.events == [("connect", None)]


@pytest.mark.parametrize("release", [False, True])
def test_dagger_shutdown_holds_unless_release_is_explicit(leader, release):
    controller, hardware, _clock = leader
    hardware.position = np.full(6, 25.0)
    controller.close(release=release)
    assert hardware.events[-1] == ("disconnect", {"disable_torque": False})
    assert hardware.events[-2][0] == ("disable" if release else "enable")
    if not release:
        np.testing.assert_array_equal(hardware.events[-3][1], hardware.position)
    count = len(hardware.events)
    controller.close()
    assert len(hardware.events) == count


def test_dagger_stale_policy_reply_cannot_step_after_takeover(dagger):
    from concurrent.futures import Future

    session, _hardware, clock = dagger
    pending = Future()
    session.policy.executor = SimpleNamespace(submit=lambda *args: pending, shutdown=lambda **kwargs: None)
    session.handle("pause_resume")
    _tick(session, clock)
    assert session.env.steps == 0
    session.handle("pause_resume")
    session.handle("toggle_correction")
    pending.set_result(torch.full((6,), 99.0))
    _until(session, clock, "correction_ready")
    assert session.env.steps == 0
    assert not session.recorder.frames
    session.policy.executor = _ImmediateExecutor()
    session.handle("pause_resume")
    _until(session, clock, "autonomous")
    _tick(session, clock)
    assert session.env.steps == 1
    assert session.action.tolist() == [22] * 6


def test_dagger_policy_error_and_writer_error_freeze_with_visible_reason(dagger):
    session, _hardware, clock = dagger
    def fail(*args):
        raise TimeoutError("policy stalled")
    session.policy.policy.get_action = fail
    session.handle("pause_resume")
    _tick(session, clock)
    assert session.phase == "fault"
    assert "policy stalled" in session.message
    assert session.env.steps == 0
    session.handle("hold_position")
    session.recorder.saving_status = lambda: {"error": "disk full"}
    _tick(session, clock)
    assert session.phase == "fault"
    assert "disk full" in session.message


def test_dagger_browser_lease_deduplicates_controls_without_clutch_chatter(monkeypatch):
    import threading
    from collections import deque

    from sim_to_real_so101.utils.ovstream import display as module

    clock = SimpleNamespace(now=1.0)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    display = object.__new__(module.BrowserSensorDisplay)
    display._lock = threading.Lock()
    display._enabled_control_actions = {"guide_start", "control_heartbeat", "control_lost", "pause_resume", "stop_session"}
    display._control_actions = deque()
    display._control_sequences = {}
    display._client_source = None
    display._client_floor = 0
    display._client_deadline = 0
    display._control_lost_reported = True
    display.enqueue_control_action("control_heartbeat", "page", 1)
    assert display.drain_control_actions() == ()
    display.enqueue_control_action("guide_start", "page", 2)
    display.enqueue_control_action("guide_start", "page", 2)
    assert display.drain_control_actions() == ("guide_start",)
    for sequence in range(3, 30):
        clock.now += 0.1
        display.enqueue_control_action("control_heartbeat", "page", sequence)
        assert display.drain_control_actions() == ()
    clock.now += 1.1
    assert display.drain_control_actions() == ("control_lost",)
    assert display.drain_control_actions() == ()
    display.enqueue_control_action("control_heartbeat", "page", 40)
    display.enqueue_control_action("guide_start", "page", 35)
    assert display.drain_control_actions() == ("control_lost",)
    display.enqueue_control_action("stop_session", "page", 41)
    clock.now += 2
    display.enqueue_control_action("control_heartbeat", "page", 42)
    assert "stop_session" in display.drain_control_actions()
    display.enqueue_control_action("control_lost", "page", 44)
    display.enqueue_control_action("stop_session", "page", 43)
    assert display.drain_control_actions() == ("stop_session",)


def test_dagger_repeated_g_does_not_toggle_torque_and_space_hands_back(dagger):
    session, hardware, clock = dagger
    for _ in range(2):
        session.handle("pause_resume")
        _tick(session, clock)
        session.handle("pause_resume")
        before = session.env.steps
        _guide(session, clock)
        for _ in range(30):
            session.handle("guide_start")
            _tick(session, clock)
        assert session.phase == "correcting"
        assert session.env.steps == before + 30
        session.handle("pause_resume")
        _until(session, clock, "autonomous")
        assert len(session.recorder.saved[-1]) == 30
        assert session.leader.snapshot()["mode"] == "holding"
        _tick(session, clock)
        session.handle("pause_resume")
    assert sum(event == "disable" for event, _ in hardware.events) == 2


def test_dagger_ctrl_c_cleanup_parks_without_simulation_or_browser(dagger):
    session, hardware, clock = dagger
    _guide(session, clock)
    hardware.position += 3
    _tick(session, clock)
    before = session.env.steps
    session.stop()
    assert session.env.steps == before
    np.testing.assert_allclose(hardware.position, np.full(6, 10))
    assert hardware.events[-1] == ("disconnect", {"disable_torque": False})


def test_dagger_exit_cannot_be_overridden_by_later_reset_or_release(dagger):
    session, hardware, clock = dagger
    session.handle("reset_world")
    _tick(session, clock)
    session.handle("stop_session")
    session.handle("release_exit")
    session.handle("reset_world")
    session.stop()
    np.testing.assert_allclose(hardware.position, np.full(6, 10))
    assert not any(event == "disable" for event, _ in hardware.events)


def test_dagger_second_interrupt_holds_without_claiming_rest(dagger, monkeypatch, capsys):
    session, hardware, _clock = dagger

    def interrupted_return():
        raise KeyboardInterrupt

    monkeypatch.setattr(session.leader, "park", interrupted_return)
    session.stop()
    assert "Rest NOT confirmed" in capsys.readouterr().out
    assert hardware.events[-1] == ("disconnect", {"disable_torque": False})


def test_dagger_browser_loss_holds_and_retains_correction_until_deliberate_resume(dagger):
    session, hardware, clock = dagger
    _guide(session, clock)
    _tick(session, clock)
    session.handle("control_lost")
    _until(session, clock, "correction_ready")
    steps = session.env.steps
    for _ in range(10):
        session.handle("control_lost")
        _tick(session, clock)
    assert session.env.steps == steps
    assert len(session.recorder.frames) == 1
    assert sum(event == "disable" for event, _ in hardware.events) == 1
    session.handle("pause_resume")
    _until(session, clock, "autonomous")
    assert len(session.recorder.saved[-1]) == 1


def test_physical_rest_survives_restarts_and_requires_matching_calibration(tmp_path):
    from sim_to_real_so101.utils.dagger.dagger_leader import physical_rest_pose
    calibration = tmp_path / "leader.json"
    calibration.write_text('{"calibration": 1}')
    teleop = SimpleNamespace(id="leader", calibration_fpath=calibration)
    joints = [f"joint{i}.pos" for i in range(6)]
    with pytest.raises(ValueError, match="Teach physical rest first"):
        physical_rest_pose(teleop, joints)
    physical_rest_pose(teleop, joints, measured=np.full(6, 10))
    np.testing.assert_array_equal(physical_rest_pose(teleop, joints), np.full(6, 10))
    calibration.write_text('{"calibration": 2}')
    with pytest.raises(ValueError, match="does not match"):
        physical_rest_pose(teleop, joints)


def test_isolated_writer_streams_cancels_and_resumes_in_separate_process(tmp_path):
    import os
    import signal

    from sim_to_real_so101.utils.lerobot_recorder import LeRobotRecorder
    root = str(tmp_path / "dataset")
    for resume, expected in [(False, 1), (True, 2)]:
        recorder = LeRobotRecorder("test", "test/process-writer", root, 30, {}, isolated_writer=True)
        try:
            recorder.init_dataset(resume=resume)
            writer_pid = recorder._writer_process.submit(os.getpid).result()
            assert writer_pid != os.getpid()
            os.kill(writer_pid, signal.SIGINT)
            assert recorder._writer_process.submit(os.getpid).result() == writer_pid
            recorder.push_frame_to_buffer(np.full(6, -1.0), np.zeros(6), {})
            recorder.cancel_recording()
            for _ in range(2):
                recorder.push_frame_to_buffer(np.full(6, float(expected)), np.zeros(6), {})
            recorder.save_episode()
        finally:
            recorder.close()
        assert recorder.saving_status() == {"active": False, "written": 0, "total": 0, "queued": 0, "error": None}
        assert recorder.num_recorded_episodes == expected

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    dataset = LeRobotDataset("test/process-writer", root=root)
    assert [row["action"][0].item() for row in dataset] == [1, 1, 2, 2]


def test_demo_video_labels_who_controls_the_arm(tmp_path):
    import av
    from sim_to_real_so101.utils.dagger.demo_video import DemoVideo

    video = DemoVideo(tmp_path / "demo.mp4", fps=30)
    phases = ["autonomous"] * 5 + ["correcting"] * 5 + ["paused"] * 5
    for phase in phases:
        video.add([np.zeros((48, 64, 3), np.uint8), np.zeros((24, 32, 3), np.uint8)], phase)
    video.close()
    with av.open(str(tmp_path / "demo.mp4")) as container:
        frames = [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]
    assert len(frames) == len(phases) and frames[0].shape == (88, 128, 3)
    # Top banner rows above the label text: green policy, red takeover, grey otherwise.
    colors = [frame[:4].reshape(-1, 3).mean(axis=0) for frame in frames[2::5]]
    np.testing.assert_allclose(colors, [(46, 160, 67), (207, 34, 46), (110, 110, 110)], atol=12)


def test_real_follower_resets_steps_and_returns_to_its_starting_pose(monkeypatch):
    from sim_to_real_so101.utils.dagger import real_so101
    from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface

    class Follower:
        def __init__(self, _config):
            self.sent, self.is_connected = [], False
            self.position = dict.fromkeys(LeRobotSO101Interface.SO101_JOINT_ORDER, 0.0)

        def connect(self):
            self.is_connected = True

        def get_observation(self):
            return {**self.position, "wrist": np.zeros((480, 640, 3), dtype=np.uint8)}

        def send_action(self, action):
            self.sent.append(np.array(list(action.values())))
            self.position = dict(action)

        def disconnect(self):
            self.is_connected = False

    monkeypatch.setattr(real_so101, "SOFollower", Follower)
    monkeypatch.setattr(real_so101.time, "sleep", lambda seconds: None)
    iface = LeRobotSO101Interface(port=None, robot_id="test", sim_device="cpu")
    # ROBOT_CAMERAS as written in E2E_Workflow.md.
    cameras = '{ wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"} }'
    env = real_so101.RealSO101Env(iface, "/dev/null", "follower", cameras, device="cpu")
    waypoints = []
    obs, _ = env.reset(options={"on_move": waypoints.append})
    sent = np.array(env.robot.sent)
    np.testing.assert_allclose(np.array(waypoints), sent)
    np.testing.assert_allclose(sent[-1], real_so101.DR500_START_POSE)
    assert np.max(np.abs(np.diff(sent, axis=0))) <= 30 * env.step_dt + 1e-6
    # The gripper opens before the arm moves; the arm rises before the base and wrist roll turn.
    opened = np.argmax(sent[:, 5] >= 40)
    assert not sent[: opened + 1, :5].any()
    turned = np.argmax(sent[:, 4] != 0)
    np.testing.assert_allclose(sent[turned - 1, 1:4], real_so101.DR500_START_POSE[1:4])
    assert obs["visual"]["rgb_wrist"].shape == (1, 480, 640, 3)
    action = torch.as_tensor(iface.raw_to_sim_radians(np.full(6, 10.0)), dtype=torch.float32)[None]
    obs, _, terminated, truncated, _ = env.step(action)
    np.testing.assert_allclose(env.robot.sent[-1], np.full(6, 10.0), atol=1e-4)
    np.testing.assert_allclose(iface.sim_radians_to_raw(obs["policy"]["joint_pos_obs"][0].numpy()), 10.0, atol=1e-4)
    assert not terminated.any() and not truncated.any()
    env.start_return()
    env.close()
    returned = np.array(env.robot.sent[len(sent) + 1:])
    assert np.isclose(returned, real_so101.DR500_START_POSE).all(axis=1).any()
    np.testing.assert_allclose(env.robot.sent[-1], np.zeros(6))
    assert not env.robot.is_connected


@pytest.mark.parametrize("pose_dataset", [None, "test/source"])
def test_rollout_dagger_serves_the_session_contracts_with_lerobot_parts(monkeypatch, pose_dataset):
    import draccus
    from datasets import Dataset
    from sim_to_real_so101.scripts import lerobot_rollout_dagger as rollout_dagger
    from sim_to_real_so101.utils import dataset_start_pose as helper
    from sim_to_real_so101.utils.dagger import real_so101
    from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface

    iface = LeRobotSO101Interface(port=None, robot_id="test", sim_device="cpu")
    joints = iface.SO101_JOINT_ORDER
    batches = []

    class Stage:
        def reset(self):
            pass

        def __call__(self, value):
            return value

    # Two-step chunks in the policy's own action order, offset by the inference count.
    model = SimpleNamespace(reset=lambda: None, predict_action_chunk=lambda batch: batches.append(batch) or torch.tensor(
        [[[20.0, 30, 40, 50, 60, 10], [21.0, 31, 41, 51, 61, 11]]]) + 100 * (len(batches) - 1))
    ctx = SimpleNamespace(
        runtime=SimpleNamespace(cfg=SimpleNamespace(device="cpu", task="Pick up the vial")),
        hardware=SimpleNamespace(robot_wrapper=SimpleNamespace(robot_type="so101_follower")),
        policy=SimpleNamespace(policy=model, preprocessor=Stage(), postprocessor=Stage()),
        data=SimpleNamespace(ordered_action_keys=[*joints[1:], joints[0]], hw_features={
            "observation.state": {"dtype": "float32", "shape": (6,), "names": joints},
            "observation.images.wrist": {"dtype": "image", "shape": (2, 2, 3), "names": ["height", "width", "channels"]},
        }),
        processors=SimpleNamespace(robot_observation_processor=lambda obs: obs, robot_action_processor=lambda pair: pair[0]),
    )
    # One inference per chunk on the observation in LeRobot units; actions return in simulator radians.
    policy = rollout_dagger._ChunkPolicy(ctx, iface, ["wrist"])
    policy.reset()
    state = torch.as_tensor(iface.raw_to_sim_radians(np.array([1.0, 2, 3, 4, 5, 50])), dtype=torch.float32)
    images = {"rgb_wrist": torch.zeros((1, 2, 2, 3), dtype=torch.uint8)}
    first, second = (iface.sim_radians_to_raw(policy.get_action(state, images).numpy()) for _ in range(2))
    assert len(batches) == 1 and batches[0]["task"] == ["Pick up the vial"]
    np.testing.assert_allclose(batches[0]["observation.state"][0], [1, 2, 3, 4, 5, 50], atol=1e-4)
    np.testing.assert_allclose(first, [10, 20, 30, 40, 50, 60], atol=1e-4)
    np.testing.assert_allclose(second, [11, 21, 31, 41, 51, 61], atol=1e-4)
    # A reset drops the rest of the chunk: the next action comes from a fresh inference.
    policy.get_action(state, images)
    policy.reset()
    fresh = iface.sim_radians_to_raw(policy.get_action(state, images).numpy())
    assert len(batches) == 3
    np.testing.assert_allclose(fresh, [210, 220, 230, 240, 250, 260], atol=1e-3)

    class Follower:
        def __init__(self, config=None):
            self.sent, self.is_connected = [], True
            self.position = dict.fromkeys(joints, 0.0)
            self.config = SimpleNamespace(cameras={"wrist": SimpleNamespace(width=640, height=480)})

        def connect(self):
            self.is_connected = True

        def get_observation(self):
            return {**self.position, "wrist": np.zeros((480, 640, 3), dtype=np.uint8)}

        def send_action(self, action):
            self.sent.append(np.array(list(action.values())))
            self.position = dict(action)

        def disconnect(self):
            self.is_connected = False

    monkeypatch.setattr(real_so101, "SOFollower", Follower)
    monkeypatch.setattr(real_so101.time, "sleep", lambda seconds: None)
    own = real_so101.RealSO101Env(iface, "/dev/null", "follower", "{ wrist: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30} }", device="cpu")
    follower = Follower()
    cfg = draccus.parse(rollout_dagger.WorkshopDAggerRolloutConfig, args=[
        "--robot.type=so101_follower", "--robot.port=/unused", "--robot.use_degrees=true",
        "--policy.type=act", "--policy.device=cpu", "--device=cpu",
        "--strategy.repo_id=test/corrections",
        *([f"--start_pose_dataset={pose_dataset}"] if pose_dataset else []),
    ])
    assert cfg.start_pose_dataset == pose_dataset
    # The shared selector must average episode starts, not all frames, and map joint names.
    def load_frames(repo_id):
        assert repo_id == "test/source"
        return SimpleNamespace(
            episodes={"dataset_from_index": [0, 2]}, total_episodes=2,
            features={"observation.state": {"names": list(reversed(joints))}},
        ), Dataset.from_dict({"observation.state": [
            [20, -90, 40, 60, -90, -10], [999] * 6, [40, -70, 50, 70, -80, -6],
        ]})

    monkeypatch.setattr(helper, "_load_dataset_frames", load_frames)
    monkeypatch.setattr(rollout_dagger, "LeRobotSO101Interface", lambda **kwargs: iface)
    monkeypatch.setattr(rollout_dagger, "_follower_rest", lambda robot: None)
    collected = []
    monkeypatch.setattr(rollout_dagger.lerobot_dagger, "_collect", lambda args, env, *a, **kw: collected.append(env))
    ctx.runtime.cfg = cfg
    ctx.hardware.robot_wrapper.inner = follower
    rollout_dagger.WorkshopDAggerStrategy(cfg.strategy, None).run(ctx)
    env, = collected
    # The wrapper must hold the same state as a follower the base class connects itself.
    assert vars(own).keys() <= vars(env).keys() and env.cameras == own.cameras
    own.close()
    # Without a dataset, resets use the calibrated state-machine fallback.
    from sim_to_real_so101.tasks.vials_state_machine_env_cfg import (
        vials_start_pose_in_lerobot_units,
    )

    start_pose = vials_start_pose_in_lerobot_units(iface.calibration)
    start = np.array([start_pose[name] for name in joints] if pose_dataset is None else [-8, -85, 65, 45, -80, 30])
    # The leader moves in step from its own pose: already at the start pose while the
    # follower is far away, its arm stays put and only its gripper opens and closes.
    leader_rest = np.array([1.0, 2, 3, 4, 5, 6])
    env.leader = SimpleNamespace(snapshot=lambda: {"position": start.copy(), "error": None}, rest_pose=leader_rest)
    sent, moves = len(follower.sent), []
    from sim_to_real_so101.utils.dagger import dagger_leader

    session_rate = dagger_leader._RATE
    env.reset(options={"on_move": moves.append})
    np.testing.assert_allclose(follower.sent[-1], start, atol=1e-9)
    assert len(moves) == len(follower.sent) - sent
    np.testing.assert_allclose(np.array(moves)[:, :5], np.tile(start[:5], (len(moves), 1)), atol=1e-9)
    assert max(move[5] for move in moves) >= 40 and np.isclose(moves[-1][5], start[5])
    # Reset moves stay within their speed caps; the leader's own cap returns to the session's afterwards.
    speed = np.abs(np.diff(np.vstack([np.zeros(6), follower.sent[sent:]]), axis=0)) / env.step_dt
    assert speed[:, :5].max() <= rollout_dagger._ARM_SPEED + 1e-6 and speed[:, 5].max() <= rollout_dagger._GRIPPER_SPEED + 1e-6
    lead = np.abs(np.diff(np.vstack([start, moves]), axis=0)) / env.step_dt
    assert lead[:, 5].max() <= rollout_dagger._LEADER_RATE[5] + 1e-6
    assert dagger_leader._RATE is session_rate
    env.start_return()
    env.close()
    np.testing.assert_allclose(follower.sent[-1], np.zeros(6))
    assert not follower.is_connected
    # On exit the leader parks along its published path, gripper release first, ending at its own rest.
    from sim_to_real_so101.utils.dagger.dagger_leader import DaggerLeader

    followed = []
    monkeypatch.setattr(DaggerLeader, "follow", lambda self, target: followed.append(np.array(target)))
    monkeypatch.setattr(DaggerLeader, "park", lambda self: "parked")
    leader = rollout_dagger._MirroringLeader(SimpleNamespace(), joints, rest_pose=leader_rest, path=env.return_path)
    assert leader.park() == "parked"
    assert max(target[5] for target in followed) >= 40
    np.testing.assert_allclose(followed[0][:5], start[:5], atol=1e-9)
    np.testing.assert_allclose(followed[-1], leader_rest)
