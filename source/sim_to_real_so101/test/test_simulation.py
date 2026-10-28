# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Smoke-test the production DR scene with Newton and both OVRtx cameras."""

import importlib

import gymnasium as gym
import pytest
import sim_to_real_so101.tasks  # noqa: F401
import torch
import warp as wp
from isaaclab.app import launch_simulation
from isaaclab.utils.math import quat_apply, quat_apply_inverse, quat_conjugate, quat_mul
from isaaclab_tasks.utils import resolve_task_config
from PIL import Image
from sim_to_real_so101 import mdp
from sim_to_real_so101.utils.camera_cfg import apply_camera_selection

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("task", [
    "Newton-So101-Teleop-Vials-To-Rack-DR-v0",
    "Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-v0",
])
def test_simulation_steps_renders_and_resets_independently(tmp_path, monkeypatch, task):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["lerobot_agent"])
    agent = importlib.import_module("sim_to_real_so101.scripts.lerobot_agent")
    cfg, _ = resolve_task_config(task, "", overrides=["presets=newton,ovrtx_renderer"])
    cfg.scene.num_envs = 2
    cfg.seed = 42
    active_cameras = apply_camera_selection(cfg, "all")
    with launch_simulation(cfg), torch.inference_mode():
        env = gym.make(task, cfg=cfg)
        try:
            obs, _ = env.reset()
            external = env.unwrapped.scene["camera_external"]
            external_position = external.data.pos_w.torch.clone()
            external_rotation = external.data.quat_w_opengl.torch.clone()
            external_intrinsics = external.data.intrinsic_matrices.torch.clone()
            nominal = torch.tensor(external.cfg.offset.rot, device=env.unwrapped.device)
            nominal = (nominal / nominal.norm()).expand(2, -1)
            relative = quat_mul(quat_conjugate(nominal), external_rotation)
            torch.testing.assert_close(relative[:, 1:3], torch.zeros_like(relative[:, 1:3]), atol=1e-6, rtol=0)
            assert torch.all((2 * torch.atan2(relative[:, 0], relative[:, 3])).abs() <= torch.deg2rad(torch.tensor(5.0)))
            nominal_fx = external.cfg.spawn.focal_length / external.cfg.spawn.horizontal_aperture * external.cfg.width
            assert torch.all(external_intrinsics[:, 0, 0] >= 0.97 * nominal_fx - 1e-4)
            assert torch.all(external_intrinsics[:, 0, 0] <= nominal_fx + 1e-4)
            torch.testing.assert_close(external_intrinsics[0], external_intrinsics[1])
            robot = env.unwrapped.scene["robot"]
            base_pose = robot.data.root_link_pose_w.torch.clone()
            up = torch.tensor([0.0, 0.0, 1.0], device=env.unwrapped.device).expand(2, -1)
            base_up = quat_apply(base_pose[:, 3:], up)
            sampled_tilt = torch.rad2deg(torch.atan2(-base_up[:, 0], base_up[:, 2]))
            assert torch.all((sampled_tilt >= -3.0) & (sampled_tilt <= 6.0))
            torch.testing.assert_close(base_up[:, 1], torch.zeros_like(base_up[:, 1]), atol=1e-6, rtol=0)
            torch.testing.assert_close(
                base_pose[:, :3], robot.data.default_root_pose.torch[:, :3] + env.unwrapped.scene.env_origins,
            )
            before_refresh = robot.data.joint_pos.torch.clone()
            physics_step = env.unwrapped.sim.get_physics_step_count()
            agent._refresh_reset_visuals(env, obs, active_cameras)
            assert env.unwrapped.sim.get_physics_step_count() == physics_step
            torch.testing.assert_close(robot.data.joint_pos.torch, before_refresh)
            for name in ("wrist", "external"):
                assert obs["visual"][f"rgb_{name}"].shape == (2, 480, 640, 3)
                for frame in obs["visual"][f"rgb_{name}"]:
                    assert frame.float().std() > 1, f"Blank {name} reset image"
            assert robot.joint_names == [
                "shoulder_pan", "shoulder_lift", "elbow_flex",
                "wrist_flex", "wrist_roll", "gripper",
            ]
            mat = env.unwrapped.scene["mat"]
            mat_pose = mat.data.root_link_pose_w.torch.clone()
            torch.testing.assert_close(
                mat_pose[:, :3],
                mat.data.default_root_pose.torch[:, :3] + env.unwrapped.scene.env_origins,
            )
            torch.testing.assert_close(mat_pose[:, 3:5], torch.zeros_like(mat_pose[:, 3:5]))
            mat_yaw = 2 * torch.atan2(mat_pose[:, 5], mat_pose[:, 6])
            assert torch.all(torch.abs(mat_yaw - torch.pi / 2) <= 0.3)
            actions = robot.data.default_joint_pos.torch.clone()
            for _ in range(10):
                obs, _, terminated, truncated, _ = env.step(actions)
                assert torch.isfinite(obs["policy"]["joint_pos_obs"]).all()
                assert not (terminated | truncated).any()
            before = robot.data.joint_pos.torch.clone()
            actions[:, 0] += 0.15
            for _ in range(20):
                obs, _, _, _, _ = env.step(actions)
            assert torch.all(torch.abs(robot.data.joint_pos.torch[:, 0] - before[:, 0]) > 0.01)
            for name in ("wrist", "external"):
                rgb = obs["visual"][f"rgb_{name}"]
                assert rgb.shape == (2, 480, 640, 3)
                assert rgb.dtype == torch.uint8
                for frame in rgb:
                    assert frame.float().std() > 1, f"Blank {name} camera image"
            torch.testing.assert_close(mat.data.root_link_pose_w.torch, mat_pose)
            torch.testing.assert_close(
                mat.data.root_vel_w.torch, torch.zeros_like(mat.data.root_vel_w.torch),
            )
            before_reset = env.unwrapped.scene.get_state()
            torch.testing.assert_close(robot.data.root_link_pose_w.torch, base_pose)
            env.unwrapped.reset(env_ids=torch.tensor([0], device=env.unwrapped.device))
            after_reset = env.unwrapped.scene.get_state()
            assert not torch.allclose(robot.data.root_link_pose_w.torch[0, 3:], base_pose[0, 3:])
            torch.testing.assert_close(external.data.pos_w.torch, external_position)
            torch.testing.assert_close(external.data.quat_w_opengl.torch[1], external_rotation[1])
            torch.testing.assert_close(external.data.intrinsic_matrices.torch, external_intrinsics)
            assert env.unwrapped.episode_length_buf.tolist() == [0, 30]
            assert not torch.allclose(mat.data.root_link_pose_w.torch[0, 3:], mat_pose[0, 3:])
            for kind, assets in before_reset.items():
                for name, fields in assets.items():
                    for field, value in fields.items():
                        torch.testing.assert_close(after_reset[kind][name][field][1], value[1])
            for _ in range(10):
                obs, _, _, _, _ = env.step(actions)
            assert torch.isfinite(obs["policy"]["joint_pos_obs"]).all()
            for name in ("wrist", "external"):
                for frame in obs["visual"][f"rgb_{name}"]:
                    assert frame.float().std() > 1, f"Blank {name} camera image after reset"

            # Render lens and tilt endpoints with the same scene and physics state.
            event = cfg.events.reset_external_camera
            baseline_rgb = None
            physics_step = env.unwrapped.sim.get_physics_step_count()
            for label, tilt, scale in [
                ("nominal", 0.0, 1.0), ("wide", 0.0, 0.97),
                ("tilt_minus5", -5.0, 1.0), ("tilt_plus5", 5.0, 1.0),
                ("nominal_repeat", 0.0, 1.0),
            ]:
                mdp.randomize_external_camera(
                    env.unwrapped, None, event.params["camera_cfg"],
                    (tilt, tilt), (scale, scale),
                )
                agent._refresh_reset_visuals(env, obs, active_cameras)
                rgb = obs["visual"]["rgb_external"].clone()
                if label == "nominal":
                    baseline_rgb = rgb
                elif label != "nominal_repeat":
                    difference = (rgb.float() - baseline_rgb.float()).abs().mean(dim=(1, 2, 3))
                    assert torch.all(difference > 0.1), f"Unchanged projection for {label}"
                else:
                    torch.testing.assert_close(external.data.quat_w_opengl.torch, nominal)
                    torch.testing.assert_close(
                        external.data.intrinsic_matrices.torch[:, 0, 0],
                        torch.full((2,), nominal_fx, device=env.unwrapped.device),
                    )
                for index, frame in enumerate(rgb):
                    if label == "nominal_repeat":
                        # This patch covers the left wall at the fixed nominal camera pose.
                        wall = frame[24:80, 24:64].float().mean(dim=(0, 1))
                        assert wall.mean() > 20 and wall[2] > wall[0] + 5
                    Image.fromarray(frame.cpu().numpy()).save(tmp_path / f"external_{label}_{index}.png")
            for name in ("wrist", "external"):
                for index, frame in enumerate(obs["visual"][f"rgb_{name}"]):
                    Image.fromarray(frame.cpu().numpy()).save(tmp_path / f"{name}_final_{index}.png")
            assert env.unwrapped.sim.get_physics_step_count() == physics_step
            torch.testing.assert_close(external.data.pos_w.torch, external_position)

            # A fixed oblique reference view exposes the base and lightbox opening.
            origins = env.unwrapped.scene.env_origins
            external.set_world_poses_from_view(
                eyes=origins + torch.tensor([-0.55, -0.50, 0.30], device=env.unwrapped.device),
                targets=origins + torch.tensor([0.0, 0.0, 0.15], device=env.unwrapped.device),
            )
            joints = robot.data.joint_pos.torch.clone()
            local_links = None
            baseline_views = None
            for label, tilt in [("nominal", 0.0), ("minus3", -3.0), ("plus6", 6.0), ("nominal_repeat", 0.0)]:
                mdp.randomize_robot_base_tilt(
                    env.unwrapped, None, cfg.events.reset_robot_base_tilt.params["asset_cfg"], (tilt, tilt),
                )
                agent._refresh_reset_visuals(env, obs, active_cameras)
                pose = robot.data.root_link_pose_w.torch.clone()
                base_up = quat_apply(pose[:, 3:], up)
                torch.testing.assert_close(
                    torch.rad2deg(torch.atan2(-base_up[:, 0], base_up[:, 2])),
                    torch.full((2,), tilt, device=env.unwrapped.device), atol=1e-5, rtol=0,
                )
                torch.testing.assert_close(pose[:, :3], base_pose[:, :3])
                torch.testing.assert_close(robot.data.joint_pos.torch, joints)
                links = robot.data.body_link_pos_w.torch
                relative_links = quat_apply_inverse(
                    pose[:, None, 3:].expand(-1, links.shape[1], -1), links - pose[:, None, :3],
                )
                if local_links is None:
                    local_links = relative_links.clone()
                    baseline_views = {name: obs["visual"][f"rgb_{name}"].clone() for name in ("external", "wrist")}
                else:
                    torch.testing.assert_close(relative_links, local_links, atol=1e-5, rtol=1e-5)
                for name in ("external", "wrist"):
                    rgb = obs["visual"][f"rgb_{name}"]
                    if tilt != 0.0:
                        difference = (rgb.float() - baseline_views[name].float()).abs().mean(dim=(1, 2, 3))
                        assert torch.all(difference > 0.1), f"Unchanged {name} view for base {label}"
                    for index, frame in enumerate(rgb):
                        Image.fromarray(frame.cpu().numpy()).save(tmp_path / f"base_{label}_{name}_{index}.png")
                if label == "nominal_repeat":
                    torch.testing.assert_close(pose[:, 3:], robot.data.default_root_pose.torch[:, 3:])
            assert env.unwrapped.sim.get_physics_step_count() == physics_step

            # A hard stop provides sustained blockage without relying on a successful grasp.
            env.reset()
            gripper = robot.joint_names.index("gripper")
            protection = env.unwrapped.event_manager.get_term_cfg("gripper_protection").func
            stiffness = robot.data.joint_stiffness.torch.clone()
            damping = robot.data.joint_damping.torch.clone()
            actions = robot.data.default_joint_pos.torch.clone()
            actions[:, gripper] = robot.data.joint_pos_limits.torch[:, gripper, 0] - 0.2
            for _ in range(150):
                _, _, terminated, truncated, _ = env.step(actions)
                assert not (terminated | truncated).any()
            assert protection.protection.history.numpy()["protected_direction"].tolist() == [-1, -1]
            assert robot.data.joint_effort_limits.torch[:, gripper].tolist() == pytest.approx([0.67, 0.67])
            # MJWarp's actuator force verifies that the solver enforces the ceiling.
            from isaaclab_newton.physics import NewtonManager

            solver = NewtonManager._solver
            mj_joints = protection.mj_joints.numpy()
            qfrc = solver.mjw_data.qfrc_actuator.numpy()
            dof_addresses = solver.mj_model.jnt_dofadr
            for e, joint in enumerate(mj_joints):
                assert qfrc[e, dof_addresses[joint]] == pytest.approx(-0.67, abs=1e-4)
            env.unwrapped.reset(env_ids=torch.tensor([0], device=env.unwrapped.device))
            assert protection.protection.history.numpy()["protected_direction"].tolist() == [0, -1]
            assert robot.data.joint_effort_limits.torch[:, gripper].tolist() == pytest.approx([1.675, 0.67])
            actions[:, gripper] = 0.8
            for _ in range(60):
                env.step(actions)
            assert robot.data.joint_pos.torch[:, gripper].tolist() == pytest.approx([0.8, 0.8], abs=0.02)
            assert protection.protection.history.numpy()["protected_direction"].tolist() == [0, 0]
            torch.testing.assert_close(robot.data.joint_stiffness.torch, stiffness)
            torch.testing.assert_close(robot.data.joint_damping.torch, damping)

            if "Expanded" in task:
                # Force one layout to exhaust, then let normal episode reset recover it.
                reset = env.unwrapped.event_manager.get_term_cfg("reset_vials_setup")
                invalid = dict(reset.params, rack_min_center_distance=10.0)
                ids = torch.tensor([0], device=env.unwrapped.device)
                mdp.reset_vials_rack(env.unwrapped, ids, **invalid)
                assert env.unwrapped._vials_layout_sampling_failed.tolist() == [True, False]
                _, _, terminated, _, _ = env.step(actions)
                assert terminated.tolist() == [True, False]
                assert env.unwrapped.termination_manager.get_term("invalid_vial_layout").tolist() == [True, False]
                assert not env.unwrapped._vials_layout_sampling_failed.any()
        finally:
            env.close()


def test_dagger_records_corrections_with_simulated_leader(tmp_path, monkeypatch):
    """Exercise real physics, reset RGB and video writing without USB hardware."""
    import time
    from types import SimpleNamespace

    import av
    import pyarrow.parquet as pq
    from sim_to_real_so101.utils.dagger import sim_dagger
    from sim_to_real_so101.utils.dagger.dagger_leader import DaggerLeader
    from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface
    from sim_to_real_so101.utils.lerobot_recorder import LeRobotRecorder

    monkeypatch.chdir(tmp_path)
    task = "Newton-So101-Teleop-Vials-To-Rack-Eval-v0"
    cfg, _ = resolve_task_config(task, "", overrides=["presets=newton,ovrtx_renderer"])
    cfg.scene.num_envs = 1
    cfg.seed = 42
    cameras = apply_camera_selection(cfg, "all")
    with launch_simulation(cfg), torch.inference_mode():
        env = gym.make(task, cfg=cfg)
        recorder = LeRobotRecorder(
            task_name="Pick up the vial and place it in the rack",
            repo_id="test/dagger", dataset_root=str(tmp_path / "dataset"), fps=30,
            cameras={name: {"height": 480, "width": 640} for name in ("wrist", "external")},
            isolated_writer=True,
        )
        try:
            recorder.init_dataset()
            iface = LeRobotSO101Interface(port=None, robot_id="test", sim_device=env.unwrapped.device)
            positions = dict.fromkeys(iface.SO101_JOINT_ORDER, 0.0)
            iface.teleop = SimpleNamespace(
                get_action=lambda: positions.copy(), send_feedback=lambda target: positions.update(target),
                enable_torque=lambda: None, disable_torque=lambda: None,
                bus=SimpleNamespace(disconnect=lambda **kwargs: None),
            )
            leader = DaggerLeader(iface.teleop, iface.SO101_JOINT_ORDER, rest_pose=[0.0] * 6)
            leader.start()
            policy = SimpleNamespace(reset=lambda: None, close=lambda: None, get_action=lambda state, _visual: state.clone())
            session = sim_dagger.SimDAgger(env, iface, policy, recorder, cameras, leader)

            def wait_phase(phase):
                deadline = time.monotonic() + 15
                while session.phase != phase and time.monotonic() < deadline:
                    session.advance(lambda: ())
                    time.sleep(1 / 30)
                assert session.phase == phase, session.message
            session.reset()
            before_pause = env.unwrapped.sim.get_physics_step_count()
            wait_phase("paused")
            session.advance(lambda: ())
            assert env.unwrapped.sim.get_physics_step_count() == before_pause
            session.handle("toggle_correction")
            wait_phase("correction_ready")
            session.handle("guide_start")
            wait_phase("correcting")
            for _ in range(6):
                session.advance(lambda: ())
            assert session.phase == "correcting"
            session.handle("pause_resume")
            wait_phase("autonomous")
            session.handle("pause_resume")
            assert session.phase == "paused"
            assert recorder.pending_frames == 0
            before_reset = env.unwrapped.sim.get_physics_step_count()
            session.handle("reset_world")
            assert env.unwrapped.sim.get_physics_step_count() == before_reset
            reset_raw = iface.sim_radians_to_raw(session.obs["policy"]["joint_pos_obs"][0].cpu().numpy())
            wait_phase("paused")
            np_target = [positions[name] for name in iface.SO101_JOINT_ORDER]
            torch.testing.assert_close(torch.tensor(np_target), torch.tensor(reset_raw), check_dtype=False)
            assert leader.snapshot()["mode"] == "holding" and session.phase == "paused"
            session.advance(lambda: ())
            assert env.unwrapped.sim.get_physics_step_count() == before_reset
            session.stop()
        finally:
            if "session" in locals():
                session.stop()
            recorder.close()
            env.close()
    root = tmp_path / "dataset"
    data = pq.read_table(next((root / "data").rglob("*.parquet"))).to_pandas()
    assert len(data) == 6
    assert data.episode_index.nunique() == 1
    assert data.frame_index.tolist() == list(range(6))
    for camera in ("wrist", "external"):
        path = next((root / "videos" / f"observation.images.{camera}").rglob("*.mp4"))
        with av.open(str(path)) as video:
            frames = list(video.decode(video=0))
        assert len(frames) == len(data)
        assert frames[0].to_ndarray(format="rgb24").std() > 1

def test_measured_asset_offsets_match_upstream_forward_kinematics(tmp_path, monkeypatch):
    import isaaclab.sim as sim_utils
    from isaaclab_assets.robots.so101 import SO101_CFG as UPSTREAM_SO101_CFG
    from sim_to_real_so101.tasks.vials_state_machine_assets import (
        ROBOT_TASK_FRAMES,
        with_task_frames,
    )
    from sim_to_real_so101.utils.gripper_calibration import WORKSHOP_GRIPPER_CALIBRATION
    from sim_to_real_so101.utils.vials_state_machine.data import ControllerState
    from sim_to_real_so101.utils.vials_state_machine.scene import VialSceneView
    from sim_to_real_so101.utils.warp_bridge import manager_stream

    monkeypatch.chdir(tmp_path)
    task = "Newton-So101-Auto-Vials-State-Machine-v0"
    cfg, _ = resolve_task_config(task, "", overrides=["presets=newton"])
    cfg.scene.num_envs = 2
    apply_camera_selection(cfg, "none")
    cfg.scene.reference = cfg.scene.robot.copy()
    cfg.scene.reference.prim_path = "{ENV_REGEX_NS}/Reference"
    cfg.scene.reference.spawn = UPSTREAM_SO101_CFG.spawn.copy()
    cfg.scene.reference.init_state.joint_pos["elbow_flex"] += torch.deg2rad(torch.tensor(-6.4)).item()
    cfg.scene.reference = with_task_frames(cfg.scene.reference, ROBOT_TASK_FRAMES)
    assert cfg.scene.robot.spawn.usd_path != cfg.scene.reference.spawn.usd_path
    assert cfg.scene.robot.spawn.variants == cfg.scene.reference.spawn.variants
    assert cfg.scene.robot.actuators == cfg.scene.reference.actuators
    with launch_simulation(cfg), torch.inference_mode():
        env = gym.make(task, cfg=cfg)
        try:
            env.reset()
            scene, sim = env.unwrapped.scene, env.unwrapped.sim
            robot, reference = scene["robot"], scene["reference"]
            vial = scene["vial_1"]
            view = VialSceneView(num_envs=2, device=env.unwrapped.device)
            states = wp.zeros(2, dtype=ControllerState, device=env.unwrapped.device)
            with manager_stream(env.unwrapped.device):
                pose = vial.data.root_link_pose_w.torch.clone()
                pose[:, 3:] = torch.tensor(
                    [[0, 0, 0, 1], [0, 0.6, 0, 0.8]], device=pose.device,
                )
                vial.write_root_pose_to_sim_index(root_pose=pose)
                sim.forward()
                scene.update(0.0)
                view.capture(env.unwrapped, states)
                # The collider's bottom is 17 mm below the vial root, independent
                # of the scripted grasp-frame origin and environment translation.
                bottom = torch.tensor([[0, 0, -0.017]] * 2, device=pose.device)
                tip_w = pose[:, :3] + quat_apply(pose[:, 3:], bottom)
                expected = quat_apply(
                    quat_conjugate(robot.data.root_quat_w.torch),
                    tip_w - robot.data.root_pos_w.torch,
                )
                actual = torch.tensor(
                    view.samples.numpy()["selected_vial_tip_b"], device=pose.device,
                )
                torch.testing.assert_close(actual, expected, atol=1e-6, rtol=0)
            for name in ("Robot", "Reference"):
                for frame in ROBOT_TASK_FRAMES:
                    path = f"/World/envs/env_0/{name}/{frame.parent_path}/{frame.name}"
                    prim = sim_utils.get_current_stage().GetPrimAtPath(path)
                    assert prim.IsValid(), f"Missing scripted-task frame: {path}"
                    assert tuple(prim.GetAttribute("xformOp:translate").Get()) == pytest.approx(frame.position, abs=1e-8)
                    view = sim_utils.FrameView(path.replace("env_0", "env_.*"), device=env.unwrapped.device)
                    positions, rotations = view.get_world_poses()
                    assert positions.torch.shape == (2, 3)
                    assert rotations.torch.shape == (2, 4)
                    assert torch.isfinite(positions.torch).all()
            assert robot.joint_names == reference.joint_names
            assert robot.body_names == reference.body_names
            offset = torch.deg2rad(torch.tensor(
                [[0, 0, -6.4, 0, 0, 0]], device=env.unwrapped.device,
            ))
            torch.testing.assert_close(
                robot.data.default_joint_pos.torch + offset, reference.data.default_joint_pos.torch,
            )
            expected_limits = reference.data.joint_pos_limits.torch.clone()
            gripper_id = robot.joint_names.index("gripper")
            calibration = WORKSHOP_GRIPPER_CALIBRATION
            expected_limits[:, gripper_id] = torch.deg2rad(torch.tensor([
                calibration.zero_degrees,
                calibration.zero_degrees + 100 * calibration.degrees_per_percent,
            ], device=env.unwrapped.device))
            torch.testing.assert_close(
                robot.data.joint_pos_limits.torch + offset.unsqueeze(-1), expected_limits,
            )
            with manager_stream(env.unwrapped.device):
                for degrees in ([0, 0, 0, 0, 0, 20], [20, 40, -30, 25, 30, 50], [-30, -50, 60, -45, -80, 5]):
                    q = torch.deg2rad(torch.tensor([degrees] * 2, device=env.unwrapped.device, dtype=torch.float32))
                    robot.write_joint_state_to_sim_index(position=q, velocity=torch.zeros_like(q))
                    reference.write_joint_state_to_sim_index(position=q + offset, velocity=torch.zeros_like(q))
                    sim.forward()
                    scene.update(0.0)
                    torch.testing.assert_close(robot.data.joint_pos.torch, q)
                    torch.testing.assert_close(
                        robot.data.body_link_pos_w.torch, reference.data.body_link_pos_w.torch, atol=1e-6, rtol=0,
                    )
                    a, b = robot.data.body_link_quat_w.torch, reference.data.body_link_quat_w.torch
                    torch.testing.assert_close((a * b).sum(-1).abs(), torch.ones_like(a[..., 0]), atol=1e-6, rtol=0)
        finally:
            env.close()
