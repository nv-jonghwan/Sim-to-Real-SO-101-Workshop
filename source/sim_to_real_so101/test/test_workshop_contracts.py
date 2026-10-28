# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
import sim_to_real_so101.mdp.terms as mdp_terms
import sim_to_real_so101.tasks  # noqa: F401
import torch
import warp as wp
from isaaclab_ov.renderers.ovrtx_renderer import OVRTXRenderer
from isaaclab_tasks.utils import resolve_task_config
from pxr import Sdf, Usd, UsdGeom
from sim_to_real_so101 import mdp
from sim_to_real_so101.assets.vial import (
    VIAL_AXIAL_MAX_M,
    VIAL_AXIAL_MIN_M,
    VIAL_RADIUS_M,
)
from sim_to_real_so101.utils.camera_cfg import (
    apply_camera_selection,
    build_sensor_display,
)
from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface
from sim_to_real_so101.utils.lerobot_recorder import SO101_FEATURE_NAMES
from sim_to_real_so101.utils.ovrtx import SO101OVRTXRenderer
from sim_to_real_so101.utils.ovstream import BrowserSensorDisplay
from sim_to_real_so101.utils.vials_state_machine import VialsStateMachine
from sim_to_real_so101.utils.vials_state_machine import parameters as C
from sim_to_real_so101.utils.vials_state_machine.data import (
    ControllerState,
    PhaseDurations,
    SceneSample,
)
from sim_to_real_so101.utils.vials_state_machine.machine import step_controller
from sim_to_real_so101.utils.vials_state_machine.phases import (
    phase_ready,
    trajectory_goal,
)
from sim_to_real_so101.utils.vials_state_machine.scene import (
    grasp_access_clearance,
    select_vial,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def calibration_scripts():
    scripts = Path(__file__).resolve().parents[3] / "docker" / "scripts"
    modules = []
    for name in ("so101_check_calibration", "so101_calibration_stats"):
        spec = importlib.util.spec_from_file_location(name, scripts / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return scripts, *modules


@pytest.mark.parametrize("arm,expected_gripper", [("follower", 1485.3), ("teleop", 1261.6)])
def test_calibration_reference_statistics(calibration_scripts, arm, expected_gripper):
    scripts, checker, generator = calibration_scripts
    folder = "sample_callibrations" if arm == "follower" else "sample_teleop_calibrations"
    stats_path = checker.DEFAULT_STATS_PATH if arm == "follower" else checker.TELEOP_STATS_PATH
    ranges, files = generator.load_all(scripts / folder)
    stats = checker.load_stats(stats_path)
    assert len(files) == 10
    assert generator.compute_stats(ranges) == stats
    assert all(s["n"] == 10 for s in stats.values())
    assert stats["gripper"]["mean"] == expected_gripper
    assert stats["wrist_roll"]["std"] == 0


@pytest.mark.parametrize("width,expected_status", [(4095, "PASS"), (4000, "WARN")])
def test_calibration_zero_variance_range(calibration_scripts, width, expected_status):
    _, checker, _ = calibration_scripts
    calibration = {"wrist_roll": SimpleNamespace(range_min=0, range_max=width, homing_offset=0)}
    result, = checker.static_check(calibration, checker.load_stats(checker.DEFAULT_STATS_PATH))
    assert result["status"] == expected_status


@pytest.mark.parametrize("arm", ["follower", "teleop"])
@pytest.mark.parametrize("mode", ["static", "live", "disconnected"])
def test_calibration_checker_selects_arm(calibration_scripts, monkeypatch, tmp_path, capsys, arm, mode):
    scripts, checker, _ = calibration_scripts
    teleop = arm == "teleop"
    namespace = "teleoperators/so_leader" if teleop else "robots/so_follower"
    sample = "sample_teleop_calibrations/so-t-003.json" if teleop else "sample_callibrations/so-r-003.json"
    path = tmp_path / namespace / "test_arm.json"
    path.parent.mkdir(parents=True)
    path.write_text((scripts / sample).read_text())
    monkeypatch.setattr(checker, "HF_LEROBOT_CALIBRATION", tmp_path)
    monkeypatch.delenv("STATS_JSON", raising=False)
    monkeypatch.setenv("TELEOP_ID" if teleop else "ROBOT_ID", "test_arm")
    monkeypatch.setenv("TELEOP_PORT" if teleop else "ROBOT_PORT", "/dev/test-arm")
    monkeypatch.setenv("ROBOT_ID" if teleop else "TELEOP_ID", "wrong_arm")
    calls = []

    def read_positions(register, normalize):
        assert register == "Present_Position" and normalize is False
        return {joint: (c["range_min"] + c["range_max"]) // 2 for joint, c in json.loads(path.read_text()).items()}

    device = SimpleNamespace(is_connected=False, bus=SimpleNamespace(sync_read=read_positions))

    def connect(*, calibrate):
        assert calibrate is False
        if mode == "disconnected":
            raise OSError("test arm unplugged")
        device.is_connected = True

    def disconnect():
        calls.append("disconnect")
        device.is_connected = False

    def make_device(config):
        assert mode != "static"
        assert config.port == "/dev/test-arm"
        assert config.id == "test_arm"
        assert config.calibration_dir == path.parent
        calls.append("connect")
        return device

    def wrong_device(config):
        pytest.fail("Checker selected the wrong arm")

    device.connect = connect
    device.disconnect = disconnect
    monkeypatch.setattr(checker, "SOLeader" if teleop else "make_robot_from_config", make_device)
    if teleop:
        make_device.name = "so_leader"
    monkeypatch.setattr(checker, "make_robot_from_config" if teleop else "SOLeader", wrong_device)
    assert checker.main(["--arm", arm] + (["--static-only"] if mode == "static" else [])) == 0
    report = capsys.readouterr().out
    assert f"Arm:   {arm}" in report
    assert str(path) in report
    assert str(checker.TELEOP_STATS_PATH if teleop else checker.DEFAULT_STATS_PATH) in report
    assert ("Live Encoder Positions" in report) == (mode == "live")
    assert calls == ([] if mode == "static" else ["connect", "disconnect"] if mode == "live" else ["connect"])


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_joint_order_and_conversion_match_recorded_datasets(dtype):
    interface = LeRobotSO101Interface(port="unused", robot_id="unused", sim_device="cpu")
    names = [
        "shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos",
        "wrist_flex.pos", "wrist_roll.pos", "gripper.pos",
    ]
    assert interface.SO101_JOINT_ORDER == SO101_FEATURE_NAMES == names
    raw = np.array([
        [-100, -90, -80, -70, -60, 0],
        [0, 0, 0, 0, 0, 50],
        [100, 90, 80, 70, 60, 100],
        [200, -200, 150, -150, 180, 120],
        [31, -59, 75, 62, -87, 16.32919660352711],
    ], dtype=dtype)
    original = raw.copy()
    expected_degrees = [
        [-100, -90, -80, -70, -60, -12.5057518848],
        [0, 0, 0, 0, 0, 52.7689733899],
        [100, 90, 80, 70, 60, 118.0436986646],
        [200, -200, 150, -150, 180, 144.1535887745],
        [31, -59, 75, 62, -87, 8.8119245602],
    ]
    radians = interface.raw_to_sim_radians(raw)
    np.testing.assert_allclose(np.rad2deg(radians), expected_degrees, atol=2e-5)
    np.testing.assert_allclose(interface.sim_radians_to_raw(radians), raw, atol=2e-5)
    np.testing.assert_array_equal(raw, original)
    shuffled = dict(reversed(list(zip(names, range(6)))))
    np.testing.assert_array_equal(interface.get_raw_action(shuffled), range(6))


def test_leader_requests_degree_units(monkeypatch):
    import sim_to_real_so101.utils.lerobot_interface as module

    configs = []
    monkeypatch.setattr(
        module,
        "SOLeader",
        lambda cfg: configs.append(cfg) or SimpleNamespace(connect=lambda: None),
    )
    LeRobotSO101Interface(
        port="unused", robot_id="unused", sim_device="cpu"
    ).connect()
    assert configs[0].use_degrees is True


def test_teleop_converts_the_calibrated_gripper_opening_without_hardware():
    interface = LeRobotSO101Interface("unused", "unused", "cpu")
    supplied = [31, -59, 75, 62, -87, 16.32919660352711]
    interface.teleop = SimpleNamespace(
        get_action=lambda: dict(zip(interface.SO101_JOINT_ORDER, supplied)),
    )
    interface._visualize = False
    raw, action = interface.read_action()
    np.testing.assert_allclose(raw, supplied, atol=2e-5)
    np.testing.assert_allclose(
        np.rad2deg(action.numpy()), [31, -59, 75, 62, -87, 8.8119245602], atol=2e-5,
    )


@pytest.mark.parametrize("interrupt", [False, True])
def test_rollout_smooth_motion_reaches_target_or_stops(monkeypatch, interrupt):
    import sim_to_real_so101.scripts.lerobot_rollout as rollout

    initial_pose = dict(zip(LeRobotSO101Interface.SO101_JOINT_ORDER, [1., -20., 30., 10., -40., 25.]))
    actions = []
    stop = Event()
    robot = SimpleNamespace(
        get_observation=lambda: {
            key: 0.0 for key in initial_pose
        },
        send_action=lambda action: actions.append(action),
    )
    monkeypatch.setattr(
        rollout, "precise_sleep", lambda _duration: stop.set() if interrupt else None
    )

    completed = rollout._move_to_initial_pose(robot, initial_pose, duration_s=1.0, fps=2, stop_event=stop)
    assert completed is not interrupt
    assert len(actions) == (1 if interrupt else 2)
    for key, target in initial_pose.items():
        assert actions[0][key] == pytest.approx(target / 2)
        if not interrupt:
            assert actions[-1][key] == pytest.approx(target)

@pytest.mark.parametrize("record,video,streaming,exit_key", [
    (False, False, False, "q"), (True, False, False, "esc"),
    (True, True, False, "q"), (True, True, True, "esc"),
])
def test_rollout_manual_trials_preserve_frames_and_reset_inference(
    monkeypatch, caplog, tmp_path, record, video, streaming, exit_key
):
    import sim_to_real_so101.scripts.lerobot_rollout as rollout
    from lerobot.datasets import LeRobotDataset

    calls = []
    actions = []
    observations = []
    paused_observations = []
    targets = iter([None, 1.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0])
    shutdown = Event()
    monkeypatch.setattr(rollout, "dataset_start_pose", lambda _repo: {"joint.pos": 0.0})
    strategy = rollout.WorkshopStrategy(rollout.WorkshopStrategyConfig())
    features = {
        "observation.state": {"dtype": "float32", "shape": (1,), "names": ["joint.pos"]},
        "action": {"dtype": "float32", "shape": (1,), "names": ["joint.pos"]},
        "observation.images.wrist": {
            "dtype": "video" if video else "image", "shape": (32, 32, 3),
            "names": ["height", "width", "channels"],
        },
    }
    dataset = (
        LeRobotDataset.create(
            "test/rollout_trials", 60, features, root=tmp_path / "dataset",
            use_videos=video, streaming_encoding=streaming,
        )
        if record else None
    )

    def send_action(action):
        actions.append(action["joint.pos"])
        if len(actions) == 4:
            for key in ("S", "S", "F"):
                strategy._queue_key(key)
        elif len(actions) == 5:
            strategy._queue_key("right")
        elif len(actions) == 6:
            strategy._queue_key("n")
        elif len(actions) == 8:
            for key in ("F", "F", "S"):
                strategy._queue_key(key)
        elif len(actions) == 9:
            strategy._queue_key(exit_key)

    def home(*_args, **_kwargs):
        calls.append("home")
        strategy._queue_key("P")
        return True

    pause_keys = iter(["s", "f", "right", "P", "P", "f", "n", "P", "s", "P", "P", "P"])

    def sleep(_duration):
        completed = int(len(actions) >= 4) + int(len(actions) >= 8)
        assert strategy.successes + strategy.failures == completed
        if record:
            assert dataset.num_episodes == completed
        strategy._queue_key(next(pause_keys))

    def get_action(_obs):
        target = next(targets)
        if target is None:
            strategy._queue_key("S")
            return None
        return torch.tensor([target])

    engine = SimpleNamespace(
        stop=lambda: calls.append("stop"),
        reset=lambda: calls.append("reset"),
        start=lambda: calls.append("start"),
        resume=lambda: calls.append("resume"),
        notify_observation=lambda obs: observations.append(obs["joint.pos"]),
        get_action=get_action,
    )
    robot = SimpleNamespace(
        get_observation=lambda: {
            "joint.pos": float(len(actions)),
            "wrist": np.full((32, 32, 3), 24 * (len(actions) + 1), dtype=np.uint8),
        },
        send_action=send_action,
        inner=SimpleNamespace(is_connected=True, disconnect=lambda: calls.append("disconnect")),
    )
    ctx = SimpleNamespace(
        runtime=SimpleNamespace(
            shutdown_event=shutdown,
            cfg=SimpleNamespace(
                fps=30, interpolation_multiplier=2, use_torch_compile=False,
                display_data=True, return_to_initial_position=False,
                task="place the vial", start_pose_dataset="test/source",
                dataset=SimpleNamespace(single_task="place the vial", push_to_hub=False) if record else None,
            ),
        ),
        hardware=SimpleNamespace(robot_wrapper=robot, teleop=None),
        policy=SimpleNamespace(inference=engine),
        processors=SimpleNamespace(
            robot_observation_processor=lambda obs: obs,
            robot_action_processor=lambda action_obs: action_obs[0],
        ),
        data=SimpleNamespace(dataset=dataset, dataset_features=features, ordered_action_keys=["joint.pos"]),
    )
    monkeypatch.setattr(
        rollout, "TerminalKeyListener",
        lambda *_args: SimpleNamespace(start=lambda: None, stop=lambda: calls.append("listener_stop")),
    )
    monkeypatch.setattr(rollout.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    def log_telemetry(obs, action, _runtime):
        if strategy._paused:
            assert action is None
            paused_observations.append(obs)

    monkeypatch.setattr(strategy, "_log_telemetry", log_telemetry)
    monkeypatch.setattr(rollout, "_move_to_initial_pose", home)
    monkeypatch.setattr(rollout, "precise_sleep", sleep)
    ticks = iter(step / 10 for step in range(100))
    monkeypatch.setattr(rollout, "time", SimpleNamespace(perf_counter=lambda: next(ticks)))

    with caplog.at_level("INFO", logger=rollout.__name__):
        strategy.setup(ctx)
        strategy.run(ctx)
        strategy.teardown(ctx)

    assert actions == [1.0, 50.5, 100.0, 150.0, 300.0, 400.0, 500.0, 550.0, 700.0]
    assert observations == [0.0, 0.0, 1.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    assert ctx.policy.inference is engine
    assert {obs["joint.pos"] for obs in paused_observations} >= {0.0, 4.0, 8.0}
    for obs in paused_observations:
        np.testing.assert_array_equal(obs["wrist"], 24 * (obs["joint.pos"] + 1))
    assert calls == ["home"] + ["reset", "start", "resume", "stop", "home"] * 5 + [
        "reset", "start", "resume", "listener_stop", "stop", "disconnect",
    ]
    assert (strategy.successes, strategy.failures) == (1, 1)
    assert shutdown.is_set()
    assert caplog.text.count("Control loop behind target") == 1
    assert caplog.text.count("Waiting | first policy action") == 6
    assert caplog.text.count("Running | first policy action after") == 5
    assert "Summary | 1 / 2 successful (50.0%) | 1 failed" in caplog.text
    if record:
        saved = LeRobotDataset("test/rollout_trials", root=tmp_path / "dataset")
        assert saved.num_episodes == strategy.successes + strategy.failures == 2
        assert len(saved) == 6
        for i, observation_index in enumerate([0, 1, 2, 3, 6, 7]):
            frame = saved[i]
            assert frame["episode_index"].item() == (0 if i < 4 else 1)
            assert frame["frame_index"].item() == (i if i < 4 else i - 4)
            assert frame["observation.state"].item() == observation_index
            assert frame["action"].item() == actions[observation_index]
            assert frame["observation.images.wrist"].mean().item() == pytest.approx(
                24 * (observation_index + 1) / 255, abs=2 / 255 if video else 1e-6
            )


def test_rollout_keys_are_scoped_to_its_terminal(monkeypatch):
    import os
    import pty
    import termios
    from queue import Empty

    import sim_to_real_so101.scripts.lerobot_rollout as rollout

    master, slave = pty.openpty()
    other_master, other_slave = pty.openpty()
    original_attrs = termios.tcgetattr(slave)
    monkeypatch.setattr(rollout, "dataset_start_pose", lambda _repo: {"joint.pos": 0.0})
    strategy = rollout.WorkshopStrategy(rollout.WorkshopStrategyConfig())
    shutdown = Event()
    ctx = SimpleNamespace(runtime=SimpleNamespace(
        shutdown_event=shutdown, cfg=SimpleNamespace(start_pose_dataset="test/source")
    ))
    monkeypatch.setattr(strategy, "_home_and_pause", lambda _ctx: None)
    try:
        with os.fdopen(os.dup(slave), "r") as terminal:
            monkeypatch.setattr(rollout.sys, "stdin", terminal)
            strategy.setup(ctx)
            os.write(other_master, b"psfnq\n")
            with pytest.raises(Empty):
                strategy._commands.get(timeout=0.15)
            assert not shutdown.is_set()
            os.write(master, b"P\x1b[C")
            assert strategy._commands.get(timeout=1) == "p"
            assert strategy._commands.get(timeout=1) == "right"
            os.write(master, b"q")
            assert shutdown.wait(timeout=1)
            strategy._listener.stop()
            assert termios.tcgetattr(slave) == original_attrs
    finally:
        if strategy._listener is not None:
            strategy._listener.stop()
        for fd in (master, slave, other_master, other_slave):
            os.close(fd)


def test_rollout_rejects_noninteractive_input_before_homing(monkeypatch):
    import sim_to_real_so101.scripts.lerobot_rollout as rollout

    monkeypatch.setattr(rollout, "dataset_start_pose", lambda _repo: {"joint.pos": 0.0})
    strategy = rollout.WorkshopStrategy(rollout.WorkshopStrategyConfig())
    homes = []
    monkeypatch.setattr(rollout.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(strategy, "_home_and_pause", homes.append)
    ctx = SimpleNamespace(runtime=SimpleNamespace(shutdown_event=Event()))
    with pytest.raises(RuntimeError, match="interactive terminal"):
        strategy.setup(ctx)
    assert homes == []
    assert strategy._listener is None


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("pose_dataset", [None, "test/source"])
def test_rollout_cli_uses_workshop_dataset_path_and_control_rate(monkeypatch, resume, pose_dataset):
    import draccus
    import sim_to_real_so101.scripts.lerobot_rollout as rollout

    cfg = draccus.parse(rollout.WorkshopRolloutConfig, args=[
        "--robot.type=so101_follower", "--robot.port=/unused", "--robot.use_degrees=true",
        "--policy.type=act", "--policy.device=cpu", "--device=cpu",
        *([f"--start_pose_dataset={pose_dataset}"] if pose_dataset else []),
        "--dataset.repo_id=test/rollout_trials", "--interpolation_multiplier=2",
        f"--resume={str(resume).lower()}",
    ])
    supplied = []
    monkeypatch.setattr(rollout.upstream_rollout.rollout, "__wrapped__", supplied.append)

    rollout.rollout(cfg)

    assert supplied == [cfg]
    assert cfg.start_pose_dataset == pose_dataset
    assert isinstance(cfg.strategy, rollout.WorkshopStrategyConfig)
    assert cfg.dataset.root == "/workspace/Sim-to-Real-SO-101-Workshop/datasets/test/rollout_trials"
    assert type(cfg.dataset.fps) is int
    assert cfg.dataset.fps == 60
    assert cfg.dataset.push_to_hub is False
    cfg.dataset.stamp_repo_id()
    assert cfg.dataset.repo_id == "test/rollout_trials"

    cfg.fps = 29.97
    with pytest.raises(ValueError, match="whole-number control rate"):
        rollout.rollout(cfg)


@pytest.mark.parametrize("robot_type,use_degrees", [
    ("so101_follower", False), ("incompatible_robot", True),
])
def test_rollout_rejects_incompatible_robot_before_setup(monkeypatch, robot_type, use_degrees):
    import sim_to_real_so101.scripts.lerobot_rollout as rollout
    from lerobot.robots.so_follower import SO101FollowerConfig

    cfg = rollout.WorkshopRolloutConfig(
        robot=(
            SO101FollowerConfig(port="/unused", use_degrees=use_degrees)
            if robot_type == "so101_follower" else SimpleNamespace(type=robot_type)
        ),
        policy=SimpleNamespace(device="cpu"), device="cpu",
    )
    supplied = []
    monkeypatch.setattr(rollout.upstream_rollout.rollout, "__wrapped__", supplied.append)

    with pytest.raises(ValueError, match="requires --robot.type=so101_follower and --robot.use_degrees=true"):
        rollout.rollout(cfg)

    assert supplied == []


@pytest.mark.parametrize("interrupt", [False, True])
def test_rollout_delegates_cleanup_on_startup_failure(monkeypatch, interrupt):
    import sim_to_real_so101.scripts.lerobot_rollout as rollout
    from lerobot.robots.so_follower import SO101FollowerConfig

    calls = []
    shutdown = Event()
    upstream = rollout.upstream_rollout
    original_factory = upstream.create_strategy
    original_logging = upstream.init_logging
    cfg = rollout.WorkshopRolloutConfig(
        robot=SO101FollowerConfig(port="/unused", use_degrees=True),
        policy=SimpleNamespace(device="cpu"),
        device="cpu", display_data=True, return_to_initial_position=False,
        start_pose_dataset="test/source",
    )
    robot = SimpleNamespace(
        inner=SimpleNamespace(is_connected=True, disconnect=lambda: calls.append("disconnect"))
    )
    ctx = SimpleNamespace(
        runtime=SimpleNamespace(cfg=cfg, shutdown_event=shutdown),
        hardware=SimpleNamespace(robot_wrapper=robot, teleop=None),
        data=SimpleNamespace(dataset=None),
    )

    def home(*_args, **_kwargs):
        calls.append("home")
        if interrupt:
            shutdown.set()
            return False
        raise ValueError("home failed")

    monkeypatch.setattr(rollout, "dataset_start_pose", lambda _repo: {"joint.pos": 0.0})
    monkeypatch.setattr(rollout, "_init_logging", lambda: None)
    monkeypatch.setattr(upstream, "build_rollout_context", lambda *_args: ctx)
    monkeypatch.setattr(
        upstream, "ProcessSignalHandler", lambda **_kwargs: SimpleNamespace(shutdown_event=shutdown)
    )
    monkeypatch.setattr(upstream, "init_visualization", lambda *_args, **_kwargs: calls.append("display"))
    monkeypatch.setattr(upstream, "shutdown_visualization", lambda *_args: calls.append("display_stop"))
    monkeypatch.setattr(
        rollout, "TerminalKeyListener",
        lambda *_args: SimpleNamespace(start=lambda: None, stop=lambda: calls.append("listener_stop")),
    )
    monkeypatch.setattr(rollout.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(rollout, "_move_to_initial_pose", home)

    if interrupt:
        rollout.rollout(cfg)
    else:
        with pytest.raises(ValueError, match="home failed"):
            rollout.rollout(cfg)

    assert calls == ["display", "home", "listener_stop", "disconnect", "display_stop"]
    assert upstream.create_strategy is original_factory
    assert upstream.init_logging is original_logging


def test_rollout_filters_only_rtc_delay_mismatch_warning():
    import sim_to_real_so101.scripts.lerobot_rollout as rollout

    warning_filter = rollout._RtcDelayWarningFilter()
    mismatch = rollout.logging.LogRecord(
        "lerobot.policies.rtc.action_queue",
        rollout.logging.WARNING,
        "",
        0,
        "Indexes diff is not equal to real delay. indexes_diff=0, real_delay=3",
        (),
        None,
    )
    other = rollout.logging.LogRecord(
        "test", rollout.logging.WARNING, "", 0, "another warning", (), None
    )
    assert warning_filter.filter(mismatch) is False
    assert warning_filter.filter(other) is True
    mismatch.levelno = rollout.logging.ERROR
    assert warning_filter.filter(mismatch) is True
    mismatch.levelno = rollout.logging.WARNING
    mismatch.name = "another.logger"
    assert warning_filter.filter(mismatch) is True


def test_robot_preserves_sysid_parameters_with_shared_gripper_protection():
    from sim_to_real_so101.mdp.gripper_protection import GripperProtectionTerm

    cfg, _ = resolve_task_config(
        "Newton-So101-Teleop-Vials-To-Rack-v0", "", overrides=["presets=newton"],
    )
    assert cfg.scene.robot.init_state.joint_pos["elbow_flex"] == pytest.approx(1.5155 + np.deg2rad(6.4))
    for task in [
        "Newton-So101-Teleop-Base-v0",
        "Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0",
        "Newton-So101-Auto-Vials-State-Machine-DR-v0",
    ]:
        task_cfg, _ = resolve_task_config(task, "", overrides=["presets=newton"])
        assert set(task_cfg.scene.robot.actuators) == {"usd"}
        actuator = task_cfg.scene.robot.actuators["usd"]
        assert actuator.stiffness is actuator.damping is actuator.actuator_effort_limit is None
        assert task_cfg.sim.use_newton_actuators is True
        assert task_cfg.events.gripper_protection.func is GripperProtectionTerm
        assert task_cfg.scene.robot.spawn.usd_path == cfg.scene.robot.spawn.usd_path
    assert cfg.scene.robot.spawn.make_uninstanceable is False
    assert cfg.scene.robot.spawn.physics_material is None
    assert cfg.scene.vial_1.spawn.collision_props[0].condim == 6
    assert cfg.sim.physics.solver_cfg.ls_iterations == 50


@pytest.fixture
def gripper_actuator():
    from sim_to_real_so101.mdp.gripper_protection import STSGripperProtection

    return STSGripperProtection(wp.full((3, 1), 3.35, device="cpu"), gripper=0, dt=1 / 60)


def _step_gripper(actuator, targets, velocities=None):
    def array(values):
        return wp.array(np.asarray(values, dtype=np.float32).reshape(3, 1), device="cpu")

    zero = array([0, 0, 0])
    actuator.step(
        zero, zero if velocities is None else array(velocities), array(targets), zero, zero,
        array([68.25] * 3), array([2.81873] * 3),
    )
    return actuator.limits.numpy()[:, 0].tolist()


@pytest.mark.parametrize("dt", [1 / 60, 1 / 120])
def test_gripper_overload_has_physical_duration_and_requires_blockage(dt):
    from sim_to_real_so101.mdp.gripper_protection import STSGripperProtection

    actuator = STSGripperProtection(wp.full((3, 1), 3.35, device="cpu"), gripper=0, dt=dt)
    for _ in range(round(0.1 / dt) - 1):
        limits = _step_gripper(actuator, [-0.2, -0.2, -0.005], [0.0, 0.2, 0.0])
    assert limits == pytest.approx([1.675] * 3)
    limits = _step_gripper(actuator, [-0.2, -0.2, -0.005], [0.0, 0.2, 0.0])
    assert limits == pytest.approx([0.67, 1.675, 1.675])
    assert actuator.history.numpy()["protected_direction"].tolist() == [-1, 0, 0]


def test_gripper_protection_survives_streaming_and_recovers_on_reverse_or_reset(gripper_actuator):
    actuator = gripper_actuator
    for _ in range(6):
        _step_gripper(actuator, [-0.2, -0.2, -0.2])
    for i in range(20):
        limits = _step_gripper(actuator, [-0.19 - 0.001 * (i % 2)] * 3)
        assert limits == pytest.approx([0.67] * 3)
    actuator.reset(wp.array([False, True, False], dtype=wp.bool, device="cpu"))
    limits = _step_gripper(actuator, [-0.2, -0.2, 0.2])
    assert limits == pytest.approx([0.67, 1.675, 1.675])
    limits = _step_gripper(actuator, [0.0, 0.0, 0.0])
    assert limits == pytest.approx([1.675] * 3)
    actuator.reset(wp.ones(3, dtype=wp.bool, device="cpu"))
    assert not actuator.history.numpy()["blocked_steps"].any()
    assert actuator.limits.numpy()[:, 0].tolist() == pytest.approx([1.675] * 3)


def test_gripper_overload_timer_does_not_accumulate_separate_stalls(gripper_actuator):
    actuator = gripper_actuator
    for _ in range(4):
        _step_gripper(actuator, [-0.2] * 3)
    _step_gripper(actuator, [-0.2] * 3, [0.3] * 3)
    for _ in range(5):
        limits = _step_gripper(actuator, [-0.2] * 3)
    assert limits == pytest.approx([1.675] * 3)
    limits = _step_gripper(actuator, [-0.2] * 3)
    assert limits == pytest.approx([0.67] * 3)


def test_vial_escape_termination_uses_environment_local_distance():
    class Scene(dict):
        pass

    scene = Scene()
    scene.env_origins = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [5.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [15.0, 0.0, 0.0],
        ]
    )
    positions = (
        [
            (0.2, 0.0, 0.2),
            (5.2, 0.0, 0.2),
            (10.2, 0.0, 0.2),
            (15.2, 0.0, 0.2),
        ],
        [
            (0.0, 0.2, 0.2),
            (5.0, 0.0, -1.01),
            (11.01, 0.0, 0.0),
            (15.0, 0.0, float("nan")),
        ],
    )
    for index, values in enumerate(positions):
        root_pos_w = SimpleNamespace(warp=wp.array(values, dtype=wp.vec3, device="cpu"))
        scene[f"vial_{index + 1}"] = SimpleNamespace(
            data=SimpleNamespace(root_pos_w=root_pos_w)
        )
    env = SimpleNamespace(device="cpu", num_envs=4, scene=scene)

    result = mdp.any_vial_outside_radius(
        env, ["vial_1", "vial_2"], max_distance=1.0
    )

    assert result.tolist() == [False, True, True, True]


def test_vial_visuals_colliders_and_reset_envelope_match_measured_dimensions():
    path = Path(__file__).parents[1] / "assets/usd/Vial_three_primitive_collision.usda"
    stage = Usd.Stage.Open(str(path))
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    for name, diameter in [
        ("visual/Mesh_002", 0.0289),
        ("visual/Mesh_001", 0.0354),
    ]:
        prim = stage.GetPrimAtPath(f"/Vial/{name}")
        bound = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
        low, high = np.asarray(bound.GetMin()), np.asarray(bound.GetMax())
        np.testing.assert_allclose((high - low)[:2], diameter, atol=1e-7)
        assert np.max(np.abs([low[:2], high[:2]])) <= VIAL_RADIUS_M + 1e-7
        assert low[2] >= VIAL_AXIAL_MIN_M - 1e-7
        assert high[2] <= VIAL_AXIAL_MAX_M + 1e-7
    cap = bounds.ComputeWorldBound(stage.GetPrimAtPath("/Vial/visual/Mesh_001")).ComputeAlignedRange()
    assert cap.GetSize()[2] == pytest.approx(0.01277, abs=1e-7)
    assert cap.GetMax()[2] == pytest.approx(VIAL_AXIAL_MAX_M, abs=1e-7)
    collision = stage.GetPrimAtPath("/Vial/collision/cap")
    assert collision.IsA(UsdGeom.Mesh)
    assert collision.GetAttribute("physics:collisionEnabled").Get()
    cap = bounds.ComputeWorldBound(collision).ComputeAlignedRange()
    low, high = np.asarray(cap.GetMin()), np.asarray(cap.GetMax())
    assert np.max(np.abs([low[:2], high[:2]])) <= VIAL_RADIUS_M
    # The beveled cap extends within 0.15 mm of the nominal axial envelope.
    assert low[2] >= VIAL_AXIAL_MIN_M
    assert high[2] <= VIAL_AXIAL_MAX_M + 0.00015
    visual = bounds.ComputeWorldBound(stage.GetPrimAtPath("/Vial/visual")).ComputeAlignedRange()
    assert visual.GetSize()[2] == pytest.approx(0.11643, abs=0.00015)


def test_rack_slot_frames_lie_on_the_opening_rim():
    path = Path(__file__).parents[1] / "assets/usd/Vial_rack_313g.usda"
    stage = Usd.Stage.Open(str(path))
    mesh = stage.GetPrimAtPath("/World/Body1/Mesh/Mesh")
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    rim_z = bounds.ComputeWorldBound(mesh).ComputeAlignedRange().GetMax()[2]
    transforms = UsdGeom.XformCache()
    for index in range(1, 5):
        frame = stage.GetPrimAtPath(f"/World/Body1/Mesh/top_{index:02d}")
        position = transforms.GetLocalToWorldTransform(frame).ExtractTranslation()
        assert position[2] == pytest.approx(rim_z, abs=1e-7)


@pytest.mark.parametrize("task", [
    "Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0",
    "Newton-So101-Auto-Vials-State-Machine-DR-v0",
])
@pytest.mark.parametrize("selection,names", [
    ("none", set()), ("wrist", {"wrist"}),
    ("external", {"external"}), ("all", {"wrist", "external"}),
])
def test_camera_selection_preserves_usable_task_config(task, selection, names):
    cfg, _ = resolve_task_config(task, "", overrides=["presets=newton,ovrtx_renderer"])
    cameras = {f"camera_{name}" for name in names}
    assert apply_camera_selection(cfg, selection) == cameras
    assert (cfg.events.reset_external_camera is not None) == ("external" in names)
    assert cfg.sim.dt * cfg.decimation == pytest.approx(1 / 30)
    if len(cameras) > 1:
        assert cfg.scene.lazy_sensor_update is False
    for name in ("wrist", "external"):
        camera = getattr(cfg.scene, f"camera_{name}")
        if name in names:
            assert (camera.height, camera.width) == (480, 640)
            assert camera.update_period == pytest.approx(1 / 30)
        else:
            assert camera is None
    visual = cfg.observations.visual
    if names:
        assert {key for key, value in vars(visual).items() if key.startswith("rgb_") and value} == {
            f"rgb_{name}" for name in names
        }
    else:
        assert visual is None
    for term in vars(cfg.events).values():
        for value in getattr(term, "params", {}).values():
            name = getattr(value, "name", None)
            if name in {"camera_wrist", "camera_external"}:
                assert name in cameras


@pytest.mark.parametrize("task", [
    "Newton-So101-Teleop-Vials-To-Rack-v0",
    "Newton-So101-Teleop-Vials-To-Rack-Eval-v0",
    "Newton-So101-Auto-Vials-State-Machine-v0",
])
def test_base_tasks_preserve_fixed_external_camera(task):
    cfg, _ = resolve_task_config(task, "", overrides=["presets=newton,ovrtx_renderer"])
    assert not hasattr(cfg.events, "reset_external_camera")


def test_browser_display_receives_camera_cuda_device(monkeypatch):
    import sim_to_real_so101.utils.ovstream as ovstream_module

    displays = []
    monkeypatch.setattr(
        ovstream_module,
        "BrowserSensorDisplay",
        lambda feeds, **kwargs: displays.append((feeds, kwargs)) or object(),
    )
    args = SimpleNamespace(
        browser_display=True,
        task="test-task",
        signal_port=49100,
        http_port=8090,
    )

    build_sensor_display(
        {"camera_external"},
        args,
        "cuda:2",
        num_envs=3,
        control_actions={"reset_world"},
    )

    feeds, kwargs = displays[0]
    assert feeds == {"external": (480, 640)}
    assert kwargs["device"] == "cuda:2"
    assert kwargs["num_envs"] == 3
    assert kwargs["control_actions"] == {"reset_world"}


def test_browser_display_closes_http_socket_when_thread_did_not_start():
    calls = []
    httpd = SimpleNamespace(
        shutdown=lambda: calls.append("shutdown"),
        server_close=lambda: calls.append("server_close"),
    )
    display = object.__new__(BrowserSensorDisplay)
    display._closed = False
    display.running = True
    display._server = None
    display._httpd = httpd
    display._http_thread = object()
    display._http_thread_started = False
    display._video_frame = None
    display._bgra_buffer = None
    display._canvas = None
    display._producer_event = None
    display._ovstream_initialized = False

    display.close()

    assert calls == ["server_close"]
    assert display._closed


def _procedural_state_and_sample(phase):
    state = ControllerState()
    state.state = phase
    state.phase_time = 1.0
    state.durations = PhaseDurations(*([1.0] * 7))
    state.command_position = wp.vec3(0.2, 0.0, 0.18)
    state.phase_start_center = state.command_position
    state.return_center = state.command_position
    state.command_axis = wp.vec3(0.0, 0.0, 1.0)
    state.phase_start_axis = state.command_axis
    state.return_axis = state.command_axis
    state.upright_axis = state.command_axis
    state.rack_slot_position_b = wp.vec3(0.2, 0.0, 0.1)
    state.pinch_gripper = C.PINCH_MIN_RAD
    state.open_gripper = C.RELEASE_MAX_RAD
    state.command_gripper = state.open_gripper
    state.phase_start_gripper = state.open_gripper
    state.release_gripper_floor = state.open_gripper
    state.release_fixed_point = wp.vec3(0.19, 0.0, 0.18)
    state.contact_time = 0.1
    state.grasp_validated = True
    state.placement_confirmed = True
    state.tempo = 1.0
    state.carry_speed = 0.18
    state.return_speed = 0.11
    state.lift_clearance = 0.08
    sample = SceneSample()
    sample.up_axis_b = wp.vec3(0.0, 0.0, 1.0)
    sample.grasp_center_b = state.command_position
    sample.fixed_jaw_center_b = state.release_fixed_point
    sample.selected_vial_position_w = wp.vec3(0.2, 0.0, 0.1)
    sample.selected_vial_axis_b = wp.vec3(0.0, 0.0, 1.0)
    sample.selected_vial_axis_z_w = 1.0
    sample.selected_vial_tip_b = wp.vec3(0.2, 0.0, 0.03)
    sample.gripper = state.open_gripper
    sample.contact_force = 3.0
    return state, sample


def _step_procedural_contract(states, samples, *, placement=True, steps=1):
    count = len(states)
    controller = VialsStateMachine(1.0 / 30.0, count, "cpu", 42)
    controller.state.assign(wp.array(states, dtype=ControllerState, device="cpu"))
    poses = wp.array(
        [wp.transform(wp.vec3(), wp.quat_from_axis_angle(wp.vec3(1.0, 0.0, 0.0), wp.pi / 2))]
        * count,
        dtype=wp.transform,
        device="cpu",
    )
    frames = wp.array(
        [[wp.transform(state.rack_slot_position_b, wp.quat_identity())] * 9 for state in states],
        dtype=wp.transform,
        device="cpu",
    )
    samples = wp.array(samples, dtype=SceneSample, device="cpu")
    placement = wp.array([placement] * count, dtype=bool, device="cpu")
    for _ in range(steps):
        wp.launch(
            step_controller,
            count,
            [controller.state, samples, poses, frames, frames, placement, controller.dt,
             controller.actions, controller.complete],
            device="cpu",
        )
    return controller


def test_procedural_sampling_is_seeded_continuous_and_reset_isolated():
    count = 64
    poses = wp.array([wp.transform_identity()] * count, dtype=wp.transform, device="cpu")
    joints = wp.zeros((count, 6), dtype=float, device="cpu")
    first = VialsStateMachine(1.0 / 30.0, count, "cpu", 42)
    repeated = VialsStateMachine(1.0 / 30.0, count, "cpu", 42)
    first.reset(poses, joints)
    repeated.reset(poses, joints)
    before = first.state.numpy().copy()
    np.testing.assert_array_equal(before, repeated.state.numpy())
    for name in ("reach_speed", "carry_speed", "grasp_axial_offset", "reach_gripper"):
        assert len(np.unique(before[name])) > 50
    first.reset(poses, joints, wp.array([1], dtype=wp.int64, device="cpu"))
    after = first.state.numpy()
    np.testing.assert_array_equal(after[np.arange(count) != 1], before[np.arange(count) != 1])
    assert after[1]["episode_index"] == before[1]["episode_index"] + 1
    assert after[1]["grasp_axial_offset"] != before[1]["grasp_axial_offset"]
    assert not first.complete.numpy().any()


def test_procedural_warmup_holds_actual_pose_and_caps_initial_opening():
    state, sample = _procedural_state_and_sample(C.WARMUP)
    state.warmup_steps_remaining = C.WARMUP_STEPS
    controller = _step_procedural_contract([state], [sample], steps=C.WARMUP_STEPS - 1)
    result = controller.state.numpy()[0]
    np.testing.assert_allclose(result["command_position"], sample.grasp_center_b)
    np.testing.assert_allclose(result["command_axis"], [0.0, 0.0, 1.0], atol=1e-6)
    assert result["state"] == C.WARMUP
    assert not result["task_failed"]
    poses = wp.array([wp.transform_identity()], dtype=wp.transform, device="cpu")
    joints = wp.array([[0, 0, 0, 0, 0, 2.0]], dtype=float, device="cpu")
    controller.reset(poses, joints)
    assert controller.state.numpy()[0]["command_gripper"] == pytest.approx(C.MAX_OPENING_RAD)


@pytest.mark.parametrize("phase,contact,depth,expected", [
    (C.PINCH, 0.0, -0.07, C.PINCH),
    (C.PINCH, 3.0, -0.07, C.LIFT_TURN),
    (C.GUIDE_IN, 3.0, 0.002, C.GUIDE_IN),
    (C.GUIDE_IN, 3.0, -0.003, C.OPEN),
    (C.SETTLE, 0.2, -0.07, C.SETTLE),
    (C.SETTLE, 0.0, -0.02, C.SETTLE),
    (C.SETTLE, 0.0, -0.07, C.RETURN),
])
def test_procedural_transitions_require_grasp_engagement_and_clear_seating(phase, contact, depth, expected):
    state, sample = _procedural_state_and_sample(phase)
    sample.contact_force = contact
    sample.jaw_contact_force = contact if phase == C.SETTLE else 0.0
    sample.selected_vial_tip_b = wp.vec3(0.2, 0.0, 0.1 + depth)
    controller = _step_procedural_contract([state], [sample])
    assert controller.state.numpy()[0]["state"] == expected
    assert not controller.complete.numpy()[0]


def test_procedural_release_holds_fixed_finger_and_bounds_contact_clearance():
    state, sample = _procedural_state_and_sample(C.SETTLE)
    sample.jaw_contact_force = 0.2
    sample.grasp_center_b = wp.vec3(0.23, 0.02, 0.18)
    sample.fixed_jaw_center_b = wp.vec3(0.20, 0.0, 0.18)
    controller = _step_procedural_contract([state], [sample], steps=60)
    actions = controller.actions.numpy()[0]
    expected_midpoint = np.asarray(state.release_fixed_point) + (
        np.asarray(sample.grasp_center_b) - np.asarray(sample.fixed_jaw_center_b)
    )
    np.testing.assert_allclose(actions[:3], expected_midpoint, atol=1e-6)
    assert actions[6] == pytest.approx(C.MAX_OPENING_RAD)
    assert not controller.complete.numpy()[0]
    assert controller.state.numpy()[0]["state"] == C.SETTLE


@pytest.mark.parametrize("seated,placement,contact,accepted", [
    (True, True, 0.0, True),
    (False, True, 0.0, False),
    (True, False, 0.0, False),
    (True, True, 0.2, False),
])
def test_procedural_return_never_accepts_lost_placement_or_remaining_contact(seated, placement, contact, accepted):
    state, sample = _procedural_state_and_sample(C.RETURN)
    sample.jaw_contact_force = contact
    if not seated:
        sample.selected_vial_tip_b = wp.vec3(0.2, 0.0, 0.101)
    controller = _step_procedural_contract([state], [sample], placement=placement)
    assert bool(controller.complete.numpy()[0]) == accepted


@wp.kernel
def _evaluate_procedural_goal(
    states: wp.array(dtype=ControllerState),
    samples: wp.array(dtype=SceneSample),
    actions: wp.array2d(dtype=float),
    ready: wp.array(dtype=bool),
):
    i = wp.tid()
    state = states[i]
    position, axis, grip = trajectory_goal(state, samples[i], state.command_axis)
    for j in range(3):
        actions[i, j] = position[j]
        actions[i, j + 3] = axis[j]
    actions[i, 6] = grip
    ready[i] = phase_ready(state, samples[i], state.durations[state.state - 1])


@pytest.mark.parametrize("phase,time,tip_depth,expected_ready", [
    (C.LIFT_TURN, 0.5, 0.025, False),
    (C.GUIDE_IN, 0.5, 0.025, False),
    (C.GUIDE_IN, 1.0, -0.004, True),
    (C.GUIDE_IN, 1.0, 0.002, False),
    (C.SETTLE, 1.0, -0.070, True),
])
def test_procedural_gravity_relative_targets_survive_tilted_base_coordinates(
    phase, time, tip_depth, expected_ready,
):
    rotation = wp.quat_from_axis_angle(wp.normalize(wp.vec3(1.0, 2.0, -0.5)), 0.31)
    states, samples = [], []
    for transform in (wp.quat_identity(), rotation):
        state, sample = _procedural_state_and_sample(phase)
        state.phase_time = time
        state.phase_start_center = wp.vec3(0.24, -0.12, 0.16)
        state.transit_center = wp.vec3(0.18, 0.04, 0.28)
        state.phase_start_axis = wp.normalize(wp.vec3(0.1, -0.9, 0.4))
        state.path_bend = 0.006
        state.noise_amplitude = 0.0008
        state.noise_phase = 0.7
        sample.selected_vial_axis_b = wp.normalize(wp.vec3(0.08, -0.04, 1.0))
        sample.selected_vial_axis_z_w = sample.selected_vial_axis_b[2]
        sample.selected_vial_tip_b = state.rack_slot_position_b + wp.vec3(0.001, 0, tip_depth)
        for name in (
            "phase_start_center", "transit_center", "phase_start_axis", "upright_axis",
            "rack_slot_position_b", "command_axis", "release_fixed_point",
        ):
            setattr(state, name, wp.quat_rotate(transform, getattr(state, name)))
        for name in (
            "up_axis_b", "grasp_center_b", "fixed_jaw_center_b",
            "selected_vial_axis_b", "selected_vial_tip_b",
        ):
            setattr(sample, name, wp.quat_rotate(transform, getattr(sample, name)))
        states.append(state)
        samples.append(sample)
    actions = wp.empty((2, 7), dtype=float, device="cpu")
    ready = wp.empty(2, dtype=bool, device="cpu")
    wp.launch(
        _evaluate_procedural_goal, 2,
        [wp.array(states, dtype=ControllerState, device="cpu"),
         wp.array(samples, dtype=SceneSample, device="cpu"), actions, ready],
        device="cpu",
    )
    values = actions.numpy()
    for offset in (0, 3):
        expected = wp.quat_rotate(rotation, wp.vec3(*values[0, offset:offset + 3]))
        np.testing.assert_allclose(values[1, offset:offset + 3], expected, atol=2e-6)
    assert values[0, 6] == pytest.approx(values[1, 6])
    assert ready.numpy().tolist() == [expected_ready, expected_ready]


@wp.kernel
def _select_accessible_vial(
    world: wp.array2d(dtype=wp.transform),
    base: wp.array2d(dtype=wp.transform),
    starts: wp.array(dtype=wp.vec3),
    selected: wp.array(dtype=int),
    available: wp.array(dtype=bool),
    clearances: wp.array2d(dtype=float),
):
    i = wp.tid()
    choice, found = select_vial(world, base, i, starts[i], 0.0, 0.035)
    selected[i] = choice
    available[i] = found
    for vial in range(2):
        clearances[i, vial] = grasp_access_clearance(world, i, vial, 0.0, 0.035)


def test_procedural_selection_rejects_rack_obstructed_fingers_in_rotated_mirrored_layouts():
    points = (
        (0.095, 0.12, 0.025), (0.01, 0.15, 0.025), (0.21, 0.15, 0.12),
        (0.15, 0.09, 0.10), (0.21, 0.09, 0.10),
        (0.21, 0.15, 0.10), (0.15, 0.15, 0.10),
    )
    world, base, starts = [], [], []
    for index, (yaw, mirror) in enumerate(((0, 1), (0, -1), (0.8, 1), (-0.55, -1))):
        rotation = wp.quat_from_axis_angle(wp.vec3(0, 0, 1), float(yaw))
        vial_rotation = rotation * wp.quat_from_axis_angle(wp.vec3(1, 0, 0), -wp.pi / 2)
        origin = wp.vec3(2.0 * index, 0.0, 0.0)
        base_row, world_row = [], []
        for frame, (x, y, z) in enumerate(points):
            position = wp.quat_rotate(rotation, wp.vec3(mirror * x, y, z))
            orientation = vial_rotation if frame < 2 else rotation
            base_row.append(wp.transform(position, orientation))
            world_row.append(wp.transform(position + origin, orientation))
        base.append(base_row)
        world.append(world_row)
        starts.append(wp.quat_rotate(rotation, wp.vec3(mirror * 0.095, 0.10, 0.15)))
    selected = wp.empty(4, dtype=int, device="cpu")
    available = wp.empty(4, dtype=bool, device="cpu")
    clearances = wp.empty((4, 2), dtype=float, device="cpu")
    wp.launch(
        _select_accessible_vial, 4,
        [wp.array(world, dtype=wp.transform, device="cpu"),
         wp.array(base, dtype=wp.transform, device="cpu"),
         wp.array(starts, dtype=wp.vec3, device="cpu"), selected, available, clearances],
        device="cpu",
    )
    assert available.numpy().all()
    assert selected.numpy().tolist() == [1, 1, 1, 1]
    assert (clearances.numpy()[:, 0] < 0.0).all()
    assert (clearances.numpy()[:, 1] > 0.002).all()


def test_state_machine_success_waits_for_retreat_completion(monkeypatch):
    confirmed = torch.tensor([True, False])
    monkeypatch.setattr(
        mdp_terms,
        "vial_placed_on_rack_termination",
        lambda *args, **kwargs: confirmed,
    )
    env = SimpleNamespace()
    result = mdp_terms.state_machine_vial_placed_on_rack_termination(
        env, None, [], "rack"
    )
    torch.testing.assert_close(env._vials_state_machine_placement_success, confirmed)
    torch.testing.assert_close(result, torch.tensor([False, False]))

    retreat_complete = torch.tensor([True, False])
    env._vials_state_machine_retreat_complete = retreat_complete
    result = mdp_terms.state_machine_vial_placed_on_rack_termination(
        env, None, [], "rack"
    )
    torch.testing.assert_close(result, retreat_complete)


def test_state_machine_task_uses_retreat_gated_success():
    cfg, _ = resolve_task_config(
        "Newton-So101-Auto-Vials-State-Machine-v0",
        "",
        overrides=["presets=newton"],
    )
    assert (
        cfg.terminations.success.func
        is mdp.state_machine_vial_placed_on_rack_termination
    )


def test_workshop_renderer_batches_sequential_camera_reads(monkeypatch):
    renderer = object.__new__(SO101OVRTXRenderer)
    cameras = [object(), object()]
    renderer._use_ovstage = True
    renderer._camera_render_data = cameras
    renderer._pending_camera_reads = set()
    batches = []
    monkeypatch.setattr(
        OVRTXRenderer,
        "render_batch",
        lambda self, render_data: batches.append(tuple(render_data)),
    )

    renderer.render_batch((cameras[0],))
    renderer.render_batch((cameras[1],))
    assert batches == [tuple(cameras)]

    renderer.render_batch((cameras[0],))
    assert batches == [tuple(cameras), tuple(cameras)]

    renderer.render_batch(tuple(cameras))
    assert batches == [tuple(cameras), tuple(cameras), tuple(cameras)]
    assert renderer._pending_camera_reads == set()


def test_gripper_mapping_override_preserves_physical_pose_and_arm_coordinates():
    from sim_to_real_so101.utils.gripper_calibration import (
        WORKSHOP_GRIPPER_CALIBRATION,
        GripperCalibration,
    )

    model = GripperCalibration(span_ticks=1531)
    interface = LeRobotSO101Interface("unused", "unused", "cpu", calibration=model)
    raw = np.array([31., -59., 75., 62., -87., 45.])
    radians = interface.raw_to_sim_radians(raw)
    np.testing.assert_allclose(np.rad2deg(radians[:5]), raw[:5])
    assert np.rad2deg(radians[5]) == pytest.approx(model.percent_to_degrees(45))
    np.testing.assert_allclose(interface.sim_radians_to_raw(radians), raw)
    robot_percent = WORKSHOP_GRIPPER_CALIBRATION.degrees_to_percent(model.percent_to_degrees(45))
    assert robot_percent == pytest.approx(45 * 1531 / 1485)
    assert model.degrees_to_percent(WORKSHOP_GRIPPER_CALIBRATION.percent_to_degrees(robot_percent)) == pytest.approx(45)


@pytest.mark.parametrize("rename_map,targets", [
    ({}, {"external": "external", "wrist": "wrist"}),
    ({"external": "front"}, {"external": "front", "wrist": "wrist"}),
    ({"observation.images.external": "observation.images.front"},
     {"external": "front", "wrist": "wrist"}),
    ({"external": "front", "observation.images.external": "observation.images.front"},
     {"external": "front", "wrist": "wrist"}),
    ({"external": "wrist", "wrist": "external"},
     {"external": "wrist", "wrist": "external"}),
])
def test_policy_camera_rename_before_server_resize(rename_map, targets, monkeypatch):
    from lerobot.async_inference.helpers import prepare_raw_observation
    from lerobot.configs import FeatureType, PolicyFeature
    from sim_to_real_so101.utils.lerobot_interface import LeRobotPolicyServerClient

    iface = LeRobotSO101Interface(port=None, robot_id="test", sim_device="cpu")
    client = LeRobotPolicyServerClient(
        iface, ["external", "wrist"], "unused", rename_map=rename_map,
        camera_shape=(48, 64, 3),
    )
    visual = {
        "rgb_external": torch.full((1, 48, 64, 3), 51, dtype=torch.uint8),
        "rgb_wrist": torch.full((1, 48, 64, 3), 204, dtype=torch.uint8),
    }
    joints = np.array([12, -30, 40, 20, -90, 50], dtype=np.float32)
    raw = client._build_raw_observation(torch.from_numpy(iface.raw_to_sim_radians(joints)), visual)
    features = {
        f"observation.images.{name}": PolicyFeature(type=FeatureType.VISUAL, shape=(3, 24, 32))
        for name in targets.values()
    }
    import pickle

    import grpc
    from lerobot.processor.rename_processor import RenameObservationsProcessorStep
    from lerobot.transport import services_pb2_grpc

    sent = []
    stub = SimpleNamespace(Ready=lambda _, timeout: None, SendPolicyInstructions=lambda request: sent.append(request))
    monkeypatch.setattr(grpc, "insecure_channel", lambda *args: None)
    monkeypatch.setattr(services_pb2_grpc, "AsyncInferenceStub", lambda _: stub)
    client.connect()
    spec = pickle.loads(sent[0].data)
    assert spec.rename_map == {}
    observation = prepare_raw_observation(raw, spec.lerobot_features, features)
    observation = RenameObservationsProcessorStep(rename_map=spec.rename_map).observation(observation)
    for camera, value in [("external", 51), ("wrist", 204)]:
        image = observation[f"observation.images.{targets[camera]}"]
        assert image.shape == (3, 24, 32)
        torch.testing.assert_close(image, torch.full_like(image, value))
    np.testing.assert_allclose(observation["observation.state"].numpy().reshape(-1), joints, atol=2e-5)
    assert observation["task"] == "Pick up the vial and place it in the rack"


@pytest.mark.parametrize("rename_map", [
    {"wrist": "external"},
    {"missing": "front"},
    {"external": "front", "observation.images.external": "rear"},
    {"observation.images.external": "rear", "external": "front"},
])
def test_policy_camera_rename_rejects_invalid_mapping(rename_map):
    from sim_to_real_so101.utils.lerobot_interface import LeRobotPolicyServerClient

    iface = LeRobotSO101Interface(port=None, robot_id="test", sim_device="cpu")
    with pytest.raises(ValueError, match="rename_map"):
        LeRobotPolicyServerClient(iface, ["external", "wrist"], "unused", rename_map=rename_map)


@pytest.mark.parametrize("variant", ["", "-DR"])
@pytest.mark.parametrize("camera_order", [
    ("wrist", "external", "inspection"),
    ("inspection", "external", "wrist"),
])
def test_camera_response_preserves_tiled_products_independent_of_registration_order(
    monkeypatch, camera_order, variant
):
    from isaaclab_ov.renderers import ovrtx_renderer as module

    cfg, _ = resolve_task_config(
        f"Newton-So101-Teleop-Vials-To-Rack{variant}-v0",
        "",
        overrides=["presets=newton,ovrtx_renderer"],
    )
    original_builder = module.build_render_product_as_string
    generated = []

    def create_product(self, spec):
        data = SimpleNamespace(
            render_scope_name=f"RenderCamera_{len(generated)}",
            render_product_name="RenderProduct",
        )
        data.render_product_path = f"/{data.render_scope_name}/{data.render_product_name}"
        data.content = module.build_render_product_as_string(spec, data, device_id=0)
        generated.append(data)
        return data

    monkeypatch.setattr(OVRTXRenderer, "create_render_data", create_product)
    renderer = object.__new__(SO101OVRTXRenderer)
    renderer._pending_writes = []
    renderer._camera_paths = {}
    renderer._camera_responses = cfg.scene.camera_wrist.renderer_cfg.camera_responses
    for name in camera_order:
        camera = getattr(cfg.scene, f"camera_{name}", None)
        if camera is None:
            camera = SimpleNamespace(
                prim_path="{ENV_REGEX_NS}/InspectionCamera",
                width=640, height=480, data_types=["rgb"], isp_cfg=None,
            )
        paths = tuple(
            camera.prim_path.replace("{ENV_REGEX_NS}", f"/World/envs/env_{index}")
            for index in range(4)
        )
        spec = SimpleNamespace(cfg=camera, num_instances=4, camera_prim_paths=paths)
        data = renderer.create_render_data(spec)
        assert module.build_render_product_as_string is original_builder
        layer = Sdf.Layer.CreateAnonymous("camera-response-test.usda")
        assert layer.ImportFromString(data.content)
        stage = Usd.Stage.Open(layer)
        product = stage.GetPrimAtPath(f"/{data.render_scope_name}/{data.render_product_name}")
        assert product.GetRelationship("camera").GetTargets() == [Sdf.Path(paths[0])]
        assert product.GetAttribute("resolution").Get() == (1280, 960)
        assert product.GetRelationship("orderedVars").GetTargets() == [
            Sdf.Path(f"/{data.render_scope_name}/Vars/LdrColor")
        ]
        assert product.GetAttribute("omni:rtx:rt:ambientLight:intensity").Get() == 0.0
        if name == "inspection":
            assert not product.GetAttribute("omni:rtx:post:grade:enabled").HasAuthoredValueOpinion()
            continue
        assert product.GetAttribute("omni:rtx:post:grade:enabled").Get() is True
        expected_gamma = (1.12, 1.12, 1.12) if name == "wrist" else (1.4, 1.4, 1.4)
        assert product.GetAttribute("omni:rtx:post:grade:gamma").Get() == pytest.approx(expected_gamma)
        assert product.GetAttribute("omni:rtx:post:tonemap:operator").Get() == "none"
        if name == "external":
            assert product.GetAttribute("omni:rtx:post:colorcorr:enabled").Get() is True
        if variant:
            assert product.GetAttribute("omni:rtx:post:tvNoise:filmGrain:amount").Get() > 0.0
        else:
            assert not product.GetAttribute("omni:rtx:post:tvNoise:enabled").HasAuthoredValueOpinion()


@pytest.fixture
def camera_blur_renderer(monkeypatch):
    renderer = object.__new__(SO101OVRTXRenderer)
    renderer._device = wp.get_device("cpu")
    renderer._camera_paths = {}
    renderer._camera_blur = {}
    renderer._camera_render_data = []
    sources = {}
    cameras = {}
    for name, suffix in [
        ("external", "/ExternalStandaloneCamera"),
        ("wrist", "/Robot/gripper/wowrobo_2MP_camera"),
        ("inspection", "/InspectionCamera"),
    ]:
        product = f"/{name}/RenderProduct"
        source = np.zeros((3, 11, 11, 4), dtype=np.uint8)
        source[:, :, :, 0] = np.asarray([0, 64, 192], dtype=np.uint8)[:, None, None]
        source[:, 5, 5, 1] = 255
        source[:, :, :, 3] = np.arange(121, dtype=np.uint8).reshape(11, 11)
        sources[product] = source
        data = SimpleNamespace(
            render_product_path=product, num_envs=3,
            warp_buffers={
                "rgba": wp.zeros(source.shape, dtype=wp.uint8, device="cpu"),
                "distance_to_camera": wp.full((3, 11, 11, 1), 0.75, device="cpu"),
            },
        )
        renderer._camera_paths[product] = f"/World/envs/env_0{suffix}"
        renderer._camera_render_data.append(data)
        cameras[name] = data

    def populate_native_outputs(self, render_data, products):
        for data in render_data:
            data.warp_buffers["rgba"].assign(products[data.render_product_path])

    monkeypatch.setattr(OVRTXRenderer, "_process_render_products", populate_native_outputs)
    return renderer, cameras, sources


@pytest.mark.parametrize("path", [
    "{ENV_REGEX_NS}/Robot/gripper/wowrobo_2MP_camera",
    "/World/envs/env_[^/]+/Robot/gripper/wowrobo_2MP_camera",
])
def test_camera_blur_is_opt_in_and_preserves_tiles_alpha_and_shared_rgb(camera_blur_renderer, path):
    renderer, cameras, sources = camera_blur_renderer
    wrist = cameras["wrist"]
    buffer = wrist.warp_buffers["rgba"]
    rgb_view = wp.to_torch(buffer)[..., :3]
    renderer._process_render_products(list(cameras.values()), sources)
    np.testing.assert_array_equal(buffer.numpy(), sources[wrist.render_product_path])

    renderer.set_camera_blur(path, [0], [1.8])
    renderer._process_render_products(list(cameras.values()), sources)
    first = buffer.numpy().copy()
    assert first.shape == (3, 11, 11, 4) and first.dtype == np.uint8
    np.testing.assert_array_equal(first[1:], sources[wrist.render_product_path][1:])
    np.testing.assert_array_equal(first[..., 0], sources[wrist.render_product_path][..., 0])
    np.testing.assert_array_equal(first[..., 3], sources[wrist.render_product_path][..., 3])
    assert 0 < first[0, 5, 5, 1] < 255
    assert first[0, 5, 4, 1] == first[0, 5, 6, 1] > 0
    np.testing.assert_array_equal(rgb_view.numpy(), first[..., :3])
    recorded_rgb = rgb_view.clone()
    for name in ("external", "inspection"):
        camera = cameras[name]
        np.testing.assert_array_equal(camera.warp_buffers["rgba"].numpy(), sources[camera.render_product_path])
    for camera in cameras.values():
        assert np.all(camera.warp_buffers["distance_to_camera"].numpy() == 0.75)

    renderer._process_render_products([wrist], sources)
    np.testing.assert_array_equal(buffer.numpy(), first)
    renderer.set_camera_blur(path, [2], [0.4])
    renderer._process_render_products([wrist], sources)
    partial = buffer.numpy()
    np.testing.assert_array_equal(partial[:2], first[:2])
    assert partial[2, 5, 5, 1] < first[2, 5, 5, 1]
    np.testing.assert_array_equal(recorded_rgb.numpy(), first[..., :3])

    renderer.set_camera_blur(path, [0, 2], [0.0, 0.0])
    renderer._process_render_products([wrist], sources)
    np.testing.assert_array_equal(buffer.numpy(), sources[wrist.render_product_path])


def test_camera_blur_reset_sampling_is_seeded_independent_and_partial(
    monkeypatch, camera_blur_renderer
):
    import torch
    from isaaclab.managers import SceneEntityCfg
    from sim_to_real_so101.mdp import vision
    from sim_to_real_so101.tasks.vials_to_rack_env_cfg import VialsToRackEventDRCfg

    renderer, cameras, sources = camera_blur_renderer
    monkeypatch.setattr(vision, "_get_all_ovrtx_renderers", lambda env: [renderer])

    class Scene(dict):
        num_envs = 3

    scene = Scene({
        f"camera_{name}": SimpleNamespace(cfg=SimpleNamespace(
            prim_path=renderer._camera_paths[data.render_product_path],
        ))
        for name, data in cameras.items()
    })
    env = SimpleNamespace(scene=scene, device="cpu")
    sigma_range = VialsToRackEventDRCfg().reset_wrist_blur.params["sigma_range"]
    snapshots = []
    for _ in range(2):
        torch.manual_seed(731)
        vision.randomize_camera_blur(
            env, None, SceneEntityCfg("camera_wrist"), sigma_range,
        )
        renderer._process_render_products(list(cameras.values()), sources)
        snapshots.append({
            name: data.warp_buffers["rgba"].numpy().copy() for name, data in cameras.items()
        })
    for name in cameras:
        np.testing.assert_array_equal(snapshots[0][name], snapshots[1][name])
    assert len(np.unique(snapshots[0]["wrist"][:, 5, 5, 1])) > 1
    assert cameras["external"].render_product_path not in renderer._camera_blur
    np.testing.assert_array_equal(snapshots[0]["external"], sources[cameras["external"].render_product_path])

    torch.manual_seed(842)
    vision.randomize_camera_blur(
        env, torch.tensor([1]), SceneEntityCfg("camera_wrist"), sigma_range,
    )
    renderer._process_render_products(list(cameras.values()), sources)
    wrist = cameras["wrist"].warp_buffers["rgba"].numpy()
    np.testing.assert_array_equal(wrist[[0, 2]], snapshots[0]["wrist"][[0, 2]])
    assert not np.array_equal(wrist[1], snapshots[0]["wrist"][1])
    np.testing.assert_array_equal(cameras["external"].warp_buffers["rgba"].numpy(), snapshots[0]["external"])


@pytest.mark.parametrize("task", [
    "Newton-So101-Teleop-Vials-To-Rack-DR-v0",
    "Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0",
    "Newton-So101-Auto-Vials-State-Machine-DR-v0",
])
@pytest.mark.parametrize("selection,names", [
    ("none", set()), ("wrist", {"wrist"}),
    ("external", {"external"}), ("all", {"wrist", "external"}),
])
def test_dr_blur_events_follow_camera_selection(task, selection, names):
    cfg, _ = resolve_task_config(task, "", overrides=["presets=newton,ovrtx_renderer"])
    assert apply_camera_selection(cfg, selection) == {f"camera_{name}" for name in names}
    assert not hasattr(cfg.events, "reset_external_blur")
    event = cfg.events.reset_wrist_blur
    if "wrist" in names:
        assert event.mode == "reset"
        assert event.params["sensor_cfg"].name == "camera_wrist"
    else:
        assert event is None
    if "wrist" in names:
        assert cfg.scene.camera_wrist.renderer_cfg.class_type is SO101OVRTXRenderer
        assert cfg.scene.camera_wrist.renderer_cfg.camera_responses
    if "external" in names:
        assert cfg.scene.camera_external.renderer_cfg.camera_responses
    assert cfg.events.reset_lightbox_light_exposure.params["exposure_range"] == (1.5, 2.25)
    assert cfg.events.reset_sky_light.params["exposure_range"] == (-5.5, -4.5)


@pytest.mark.parametrize("source,material_path", [
    ("lightbox-backing-colliders.usda", "/World/LightBox/Looks/PerceptionWall"),
    ("mat-thick-collision.usda", "/World/Mat/Looks/PerceptionMat"),
    ("Vial_three_primitive_collision.usda", "/Vial/Looks/PerceptionVialBody"),
])
def test_base_assets_supply_task_materials(source, material_path):
    usd_dir = Path(__file__).parents[1] / "assets/usd"
    stage = Usd.Stage.Open(str(usd_dir / source))
    assert not stage.GetRootLayer().subLayerPaths
    assert stage.GetPrimAtPath(material_path).GetTypeName() == "Material"
    shader = stage.GetPrimAtPath(f"{material_path}/Shader")
    assert shader and not shader.IsInstanceProxy()
    assert shader.GetAttribute("inputs:reflection_roughness_constant").Get() > 0.5
    if source == "lightbox-backing-colliders.usda":
        light = stage.GetPrimAtPath("/World/LightBox/RectLight")
        for dimension in ("width", "height"):
            assert light.GetAttribute(f"inputs:{dimension}").Get() == pytest.approx(0.28)
    else:
        assert shader.GetAttribute("inputs:diffuse_texture").Get().path
        if source == "mat-thick-collision.usda":
            for name in ("diffuse_texture", "normalmap_texture"):
                texture = shader.GetAttribute(f"inputs:{name}").Get()
                assert texture.resolvedPath and Path(texture.resolvedPath).is_file()


@pytest.mark.parametrize("prefix,suffix", [
    ("Teleop-Vials-To-Rack", ""), ("Teleop-Vials-To-Rack", "-Eval"),
    ("Auto-Vials-State-Machine", ""),
])
def test_base_and_dr_task_composition(prefix, suffix):
    base, dr = [resolve_task_config(
        f"Newton-So101-{prefix}{variant}{suffix}-v0", "",
        overrides=["presets=newton,ovrtx_renderer"],
    )[0] for variant in ("", "-DR")]
    for cfg in (base, dr):
        assert cfg.scene.mat.spawn.usd_path == base.scene.mat.spawn.usd_path
        assert cfg.scene.vial_1.spawn.usd_path == base.scene.vial_1.spawn.usd_path
        assert cfg.scene.camera_wrist.renderer_cfg.class_type is SO101OVRTXRenderer
    base_response = base.scene.camera_wrist.renderer_cfg.camera_responses
    dr_response = dr.scene.camera_wrist.renderer_cfg.camera_responses
    assert base_response
    assert base.scene.camera_wrist.renderer_cfg == base.scene.camera_external.renderer_cfg
    for path, attributes in base_response.items():
        assert attributes["omni:rtx:post:grade:enabled"] is True
        assert attributes["omni:rtx:post:tonemap:operator"] == "none"
        assert not any(":tvNoise:" in key for key in attributes)
        assert {key: value for key, value in dr_response[path].items() if ":tvNoise:" not in key} == attributes
        assert dr_response[path]["omni:rtx:post:tvNoise:enabled"] is True
    assert not hasattr(base.events, "reset_wrist_blur")
    assert not hasattr(base.events, "reset_task_materials")
    assert dr.events.reset_wrist_blur.params["sigma_range"] == (0.7, 1.1)
    assert dr.events.reset_task_materials is not None
    assert dr.scene.camera_wrist.renderer_cfg.camera_responses
    assert dr.scene.camera_wrist.renderer_cfg == dr.scene.camera_external.renderer_cfg


@pytest.mark.parametrize("prefix,suffix", [
    ("Teleop-Vials-To-Rack", ""), ("Teleop-Vials-To-Rack", "-Eval"),
    ("Auto-Vials-State-Machine", ""),
])
def test_expanded_dr_preserves_dr_and_controller_configuration(prefix, suffix):
    dr, expanded = [resolve_task_config(
        f"Newton-So101-{prefix}{variant}{suffix}-v0", "",
        overrides=["presets=newton,ovrtx_renderer"],
    )[0] for variant in ("-DR", "-Expanded-DR")]
    assert expanded.scene.to_dict() == dr.scene.to_dict()
    assert expanded.actions.to_dict() == dr.actions.to_dict()
    assert expanded.terminations.to_dict() == dr.terminations.to_dict()
    assert expanded.episode_length_s == dr.episode_length_s
    for name, event in vars(dr.events).items():
        if name != "reset_vials_setup":
            assert getattr(expanded.events, name) == event
    assert "rack_centers" not in dr.events.reset_vials_setup.params
    params = expanded.events.reset_vials_setup.params
    assert len(params["rack_centers"]) == 3
    assert params["rack_min_center_distance"] == 0.33
    for key in ("rack_pose_range", "vial_pose_range"):
        def area(ranges):
            return np.prod([ranges[axis][1] - ranges[axis][0] for axis in ("x", "y")])
        assert area(params[key]) == pytest.approx(1.2 * area(dr.events.reset_vials_setup.params[key]))


@pytest.mark.parametrize("center", [(0.27, 0.14), (0.29, 0.0), (0.27, -0.14)])
def test_expanded_layout_containment_opposite_sides_and_exhaustion(center):
    from sim_to_real_so101.mdp.resets import (
        _aabb_inside_xy,
        _aabb_overlap_xy,
        _rack_xy_aabb,
        _sample_coordinated_vials_rack,
        _vial_xy_aabb,
    )
    from sim_to_real_so101.tasks.vials_to_rack_env_cfg import (
        VialsToRackEventExpandedDRCfg,
    )

    params = VialsToRackEventExpandedDRCfg().reset_vials_setup.params
    args = {key: params[key] for key in (
        "rack_min_center_distance", "rack_pose_range", "vial_pose_range", "mat_bounds", "clearance",
    )}
    args.update(rack_centers=(center,), robot_xy=(-0.05, 0.0),
                reach_range=params["vial_reach_range"], max_sample_tries=1000)
    state = np.random.get_state()
    try:
        np.random.seed(42)
        sample = _sample_coordinated_vials_rack(3, **args, is_accessible=lambda *_: True)
        assert sample is not None
        rack, vials = sample
        rack_box = _rack_xy_aabb(*rack)
        assert np.linalg.norm(np.array(rack_box[0]) - args["robot_xy"]) >= 0.33
        boxes = [rack_box] + [_vial_xy_aabb(*vial[:3]) for vial in vials]
        for index, box in enumerate(boxes):
            assert _aabb_inside_xy(box, args["mat_bounds"])
            assert all(not _aabb_overlap_xy(box, other, args["clearance"]) for other in boxes[:index])
        assert all(vial[1] * vials[0][1] > 0 for vial in vials)
        if center[1]:
            assert all(vial[1] * center[1] < 0 for vial in vials)
        assert _sample_coordinated_vials_rack(3, **args, is_accessible=lambda *_: False) is None
    finally:
        np.random.set_state(state)


def test_layout_access_requires_floor_grasp_and_reachable_slot():
    from sim_to_real_so101.utils.vials_state_machine.scene import (
        layout_has_grasp_access,
    )

    points = (
        (0.095, 0.12, 0.025), (0.01, 0.15, 0.025), (0.21, 0.15, 0.12),
        (0.15, 0.09, 0.10), (0.21, 0.09, 0.10),
        (0.21, 0.15, 0.10), (0.15, 0.15, 0.10),
    )
    horizontal = wp.quat_from_axis_angle(wp.vec3(1, 0, 0), -wp.pi / 2)
    poses = [tuple(wp.transform(wp.vec3(*point), horizontal if i < 2 else wp.quat_identity()))
             for i, point in enumerate(points)]
    robot = wp.transform_identity()
    assert layout_has_grasp_access(poses, robot)
    upright = [tuple(wp.transform(wp.vec3(*point), wp.quat_identity())) for point in points]
    assert not layout_has_grasp_access(upright, robot)
    unreachable = poses[:3] + [tuple(wp.transform(wp.vec3(1.0, y, z), wp.quat_identity()))
                               for _, y, z in points[3:]]
    assert not layout_has_grasp_access(unreachable, robot)


def test_layout_failure_termination_survives_reset():
    env = SimpleNamespace(num_envs=2, device="cpu")
    assert not mdp_terms.vial_layout_sampling_failed(env).any()
    env._vials_layout_sampling_failed = torch.tensor([True, False])
    snapshot = mdp_terms.vial_layout_sampling_failed(env)
    env._vials_layout_sampling_failed[0] = False
    assert snapshot.tolist() == [True, False]


def test_dr_material_sampling_preserves_scripted_frames_and_reset_selection():
    from sim_to_real_so101.tasks.vials_state_machine_env_cfg import (
        VialsStateMachineDREnvCfg,
        VialsStateMachineEnvCfg,
    )

    scripted = VialsStateMachineDREnvCfg()
    base = VialsStateMachineEnvCfg()
    for name in ("robot", "mat", "vial_1", "vial_2", "vial_3"):
        assert getattr(scripted.scene, name).to_dict() == getattr(base.scene, name).to_dict()
    assert scripted.actions.to_dict() == base.actions.to_dict()
    assert scripted.terminations.to_dict() == base.terminations.to_dict()
    assert scripted.scene.robot_printed_material.channels == ("color",)
    assert scripted.scene.robot_sensor_printed_material.channels == ("color",)
    for index in range(1, 4):
        assert getattr(scripted.scene, f"vial_{index}_body_material").channels == ("color", "roughness", "specular")

    import torch

    event = scripted.events.reset_task_materials
    writes = []
    scene = {
        name: value for name, value in vars(scripted.scene).items()
        if name.endswith("_material") and value is not None
    }
    env = SimpleNamespace(
        scene=scene, num_envs=2, device="cpu",
        sim=SimpleNamespace(render_context=SimpleNamespace(
            write_visual_materials=lambda materials, channels, ids: writes.append((materials, channels, ids)),
        )),
    )
    selected = torch.tensor([1])
    event.func(env, selected, **event.params)
    assert writes
    for materials, channels, ids in writes:
        assert ids is selected
        assert set(channels) == set(materials[0].channels)
        for values in channels.values():
            assert values.shape[:2] == (len(materials), 1)
            assert torch.isfinite(values).all() and ((0 <= values) & (values <= 1)).all()


@pytest.fixture
def linear_vial_arm():
    from sim_to_real_so101.utils.vials_state_machine.arm_action import (
        VialArmAction,
        VialArmActionCfg,
    )

    action = object.__new__(VialArmAction)
    action.cfg = VialArmActionCfg()
    action._env = SimpleNamespace(
        episode_length_buf=torch.zeros(2, dtype=torch.int64), max_episode_length=100,
    )
    action._dt = 1 / 60
    action._joint_ids = list(range(6))
    action._jaw_body_ids = [0, 1]
    position = torch.zeros((2, 6))
    position[:, 0] = 0.5
    limits = torch.tensor([-1.0, 1.0]).expand(2, 6, 2).clone()
    limits[:, 0, 1] = 0.5
    quaternion = torch.tensor([0.0, 0.0, 0.0, 1.0]).expand(2, 4)
    action._asset = SimpleNamespace(
        data=SimpleNamespace(
            joint_pos=SimpleNamespace(torch=position),
            joint_vel=SimpleNamespace(torch=torch.zeros_like(position)),
            default_joint_pos=SimpleNamespace(torch=position.clone()),
            root_quat_w=SimpleNamespace(torch=quaternion),
            body_quat_w=SimpleNamespace(torch=quaternion[:, None].expand(2, 2, 4)),
            soft_joint_pos_limits=SimpleNamespace(torch=limits),
        ),
        set_joint_position_target_index=lambda **_kwargs: None,
    )
    action._target = torch.zeros_like(position)
    action._velocity = torch.zeros_like(position)
    action._initialized = torch.zeros(2, dtype=torch.bool)
    action._failed = torch.zeros(2, dtype=torch.bool)
    action._identity = torch.eye(5)
    action._speed_limit = torch.tensor((*action.cfg.joint_velocity_limits, 4.0))
    action._acceleration_limit = torch.tensor((*action.cfg.joint_acceleration_limits, 30.0))
    direction = torch.tensor([0.0, 1.0, 0.0]).expand(2, 3)
    jacobian = torch.zeros((2, 6, 5))
    jacobian[:, :3, :3] = torch.eye(3)
    jacobian[:, 3, 3] = jacobian[:, 5, 4] = 1.0
    action._compute_grasp_kinematics = lambda: (position[:, :3], direction, jacobian)
    action._raw_actions = torch.cat((position[:, :3], direction, position[:, 5:6]), dim=1)
    action._raw_actions[:, 1] = 0.08
    return action, position, jacobian


def test_vial_ik_builds_bounded_preload_with_an_idle_joint_at_its_limit(linear_vial_arm):
    action, position, _ = linear_vial_arm
    for _ in range(60):
        action.apply_actions()
        assert (action._target[:, :5] - position[:, :5]).abs().max() <= action.cfg.max_target_lead + 1e-5
    assert torch.all(action._target[:, 1] > 0.09)
    torch.testing.assert_close(action._target[:, 0], position[:, 0])
    for _ in range(120):
        position[:, 1] = (action._target[:, 1] - 0.04).clamp_min(0.0)
        action.apply_actions()
    torch.testing.assert_close(position[:, 1], action._raw_actions[:, 1], atol=0.001, rtol=0)


def test_vial_ik_nonfinite_jacobian_isolates_and_resets_one_environment(linear_vial_arm):
    action, _, jacobian = linear_vial_arm
    action.apply_actions()
    held = action._target[0].clone()
    healthy = action._target[1].clone()
    jacobian[0, 0, 0] = float("nan")
    action.apply_actions()
    assert torch.isfinite(action._target).all()
    torch.testing.assert_close(action._target[0], held)
    assert action._target[1, 1] > healthy[1]
    assert action._env.episode_length_buf.tolist() == [100, 0]
    action.reset(torch.tensor([0]))
    assert not action._failed.any()
    assert action._initialized.tolist() == [False, True]


@pytest.mark.parametrize("missing_files", [None, "data", "meta"])
def test_dataset_start_pose_averages_first_states_and_preserves_videos(tmp_path, monkeypatch, missing_files):
    import shutil

    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from sim_to_real_so101.utils import dataset_start_pose as helper

    root = tmp_path / "dataset"
    names = list(reversed(LeRobotSO101Interface.SO101_JOINT_ORDER))
    dataset = LeRobotDataset.create(
        "test/start_pose", fps=30, root=root, use_videos=False,
        features={"observation.state": {"dtype": "float32", "shape": (6,), "names": names}},
    )
    for episode in range(21):
        for value in (episode, 1000):
            dataset.add_frame({"observation.state": np.full(6, value, dtype=np.float32), "task": "test"})
        dataset.save_episode()
    dataset.finalize()
    info_path = root / "meta/info.json"
    info = json.loads(info_path.read_text())
    info["features"]["observation.images.wrist"] = {
        "dtype": "video", "shape": [32, 32, 3], "names": ["height", "width", "channels"],
    }
    info["video_path"] = "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
    info_path.write_text(json.dumps(info))
    if missing_files:
        remote_files = tmp_path / "remote_files"
        shutil.move(root / missing_files, remote_files)
    video = root / "videos" / "existing.mp4"
    video.parent.mkdir()
    video.write_bytes(b"existing video bytes")
    monkeypatch.setattr(helper, "dataset_root_from_repo_id", lambda _repo: str(root))

    downloads = []

    def download_missing_files(*args, **kwargs):
        if not missing_files or downloads:
            pytest.fail("Complete local dataset must not require a download")
        assert kwargs["allow_patterns"] == ("meta/" if missing_files == "meta" else ["data/**"])
        assert Path(kwargs["local_dir"]) == root
        downloads.append(args)
        shutil.copytree(remote_files, root / missing_files)

    monkeypatch.setattr(helper, "snapshot_download", download_missing_files)
    monkeypatch.setattr("lerobot.datasets.dataset_metadata.snapshot_download", download_missing_files)
    monkeypatch.setattr("lerobot.datasets.dataset_metadata.get_safe_version", lambda _repo, revision: revision)
    expected = 10.0
    pose = helper.dataset_start_pose("test/start_pose")
    assert list(pose) == names
    assert list(pose.values()) == pytest.approx([expected] * 6)
    assert helper.dataset_start_pose("test/start_pose") == pose
    assert video.read_bytes() == b"existing video bytes"
    assert len(downloads) == int(missing_files is not None)


@pytest.mark.parametrize("span_ticks", [1485.0, 1700.0])
def test_start_pose_fallback_warns_and_preserves_sim_pose(monkeypatch, caplog, span_ticks):
    from sim_to_real_so101.tasks.vials_state_machine_env_cfg import (
        VIALS_START_POSE_RAD,
    )
    from sim_to_real_so101.utils import dataset_start_pose as helper
    from sim_to_real_so101.utils.gripper_calibration import GripperCalibration

    def unexpected_dataset(*args, **kwargs):
        pytest.fail("Fallback must not load or download a dataset")

    monkeypatch.setattr(helper, "snapshot_download", unexpected_dataset)
    calibration = GripperCalibration(span_ticks=span_ticks)
    pose = helper.dataset_start_pose(None, calibration)
    interface = LeRobotSO101Interface("unused", "unused", "cpu", calibration=calibration)
    radians = interface.raw_to_sim_radians(interface.get_raw_action(pose))
    np.testing.assert_allclose(
        radians, [VIALS_START_POSE_RAD[name] for name in interface.joint_names], atol=1e-6
    )
    assert "No --start_pose_dataset supplied" in caplog.text
