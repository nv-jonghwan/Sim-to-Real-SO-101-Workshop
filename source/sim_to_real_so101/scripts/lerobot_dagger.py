# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Collect human corrections during Newton or real-follower policy rollouts."""

import argparse
import math
import os
import sys
import time
from contextlib import ExitStack

import gymnasium as gym
import sim_to_real_so101.tasks  # noqa: F401
import torch
from isaaclab.app import add_launcher_args, launch_simulation
from isaaclab_tasks.utils import resolve_task_config
from lerobot.teleoperators.so_leader import SOLeader
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig
from sim_to_real_so101.utils.camera_cfg import (
    add_browser_display_args,
    add_camera_args,
    apply_camera_selection,
    build_sensor_display,
)
from sim_to_real_so101.utils.dagger.dagger_leader import (
    DaggerLeader,
    physical_rest_pose,
)
from sim_to_real_so101.utils.dagger.demo_video import DemoVideo
from sim_to_real_so101.utils.dagger.real_so101 import RealSO101Env
from sim_to_real_so101.utils.dagger.sim_dagger import SimDAgger
from sim_to_real_so101.utils.dataset_paths import dataset_root_from_repo_id
from sim_to_real_so101.utils.lerobot_interface import (
    LeRobotPolicyServerClient,
    LeRobotSO101Interface,
)
from sim_to_real_so101.utils.lerobot_recorder import LeRobotRecorder


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="Newton-So101-Teleop-Vials-To-Rack-Eval-v0")
    parser.add_argument("--num_envs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--port", default=os.getenv("TELEOP_PORT", "/dev/ttyACM0"))
    parser.add_argument("--robot_id", default=os.getenv("TELEOP_ID", "leader_bot"))
    parser.add_argument("--teach-rest", action="store_true", help="Save the supported leader's current pose as physical rest; no simulation or movement.")
    parser.add_argument("--repo_id", help="Correction dataset id; stored under datasets/<repo_id>.")
    parser.add_argument("--resume", action="store_true", help="Append to an existing correction dataset.")
    parser.add_argument("--server_address", default="localhost:8080")
    parser.add_argument("--pretrained_name_or_path")
    parser.add_argument("--policy_type", default="groot")
    parser.add_argument("--policy_device", default="cuda")
    parser.add_argument("--action_horizon", type=int, default=12)
    parser.add_argument("--episode_length_s", type=float, default=120.0, help="Simulated seconds per DAgger rollout.")
    parser.add_argument("--lang_instruction", default="Pick up the vial and place it in the rack")
    parser.add_argument("--real", action="store_true", help="Drive the physical follower instead of the Newton task.")
    parser.add_argument("--follower_port", default=os.getenv("ROBOT_PORT"))
    parser.add_argument("--follower_id", default=os.getenv("ROBOT_ID"))
    parser.add_argument("--follower_cameras", default=os.getenv("ROBOT_CAMERAS"), help="LeRobot camera dict, YAML or JSON.")
    parser.add_argument("--leader_follows", action="store_true",
                        help="Leader tracks the arm during policy rollouts and moves to the start pose on reset.")
    parser.add_argument("--demo_video", help="Also save the camera views under a POLICY / HUMAN TAKEOVER banner "
                                             "to this MP4 file. Not a dataset.")
    add_camera_args(parser)
    add_browser_display_args(parser)
    add_launcher_args(parser)
    args, hydra_args = parser.parse_known_args()
    if args.teach_rest:
        return args
    if not args.repo_id or not args.pretrained_name_or_path:
        parser.error("--repo_id and --pretrained_name_or_path are required for collection.")
    if args.num_envs != 1:
        parser.error("DAgger supports exactly one environment.")
    if not args.browser_display or args.headless_render:
        parser.error("DAgger requires --browser-display for takeover controls; omit --headless-render.")
    if args.action_horizon < 1:
        parser.error("--action_horizon must be positive.")
    if not math.isfinite(args.episode_length_s) or args.episode_length_s <= 0:
        parser.error("--episode_length_s must be finite and positive.")
    if args.real and not (args.follower_port and args.follower_id and args.follower_cameras):
        parser.error("--real needs --follower_port, --follower_id and --follower_cameras (or ROBOT_* variables).")
    sys.argv = [sys.argv[0]] + hydra_args
    return args


def _disconnect_leader(iface, owner):
    if owner:
        return
    teleop = getattr(iface, "teleop", None)
    if teleop is not None and teleop.is_connected:
        teleop.bus.disconnect(disable_torque=False)


def run_session(session, display, demo=None):
    """Serve browser controls and camera views while stepping only active modes."""
    def publish():
        display.push_status(
            session.phase == "correcting",
            session.recorder.saving_status(),
            session.recorder.num_recorded_episodes,
            phase=session.phase,
            message=session.message,
        )

    session.on_phase = publish
    with torch.inference_mode():
        session.reset()
        print(
            "[DAGGER]: Paused, leader held. Space: policy/pause. Tab (paused): align. G: correct. "
            "Space: save + resume. X hold, C discard, R reset, Esc exit to rest, L release + exit.",
            flush=True,
        )
        while session.running:
            start = time.monotonic()
            try:
                for command in display.drain_control_actions():
                    session.handle(command)
                    if not session.running:
                        break
            except Exception as exc:  # noqa: BLE001 - hold and report failures at the control boundary
                session.report_fault(exc)
            if not session.running:
                break
            session.advance(display.drain_control_actions)
            for name in session.recorder.cameras:
                display.update(name, session.obs["visual"][f"rgb_{name}"][0])
            if demo is not None:
                # Name order puts the external view left of the wrist view.
                images = [session.obs["visual"][f"rgb_{name}"][0].cpu().numpy() for name in sorted(session.recorder.cameras)]
                demo.add(images, session.phase)
            display.push_telemetry(session.obs["policy"]["joint_pos_obs"][0], session.action)
            publish()
            display.flush()
            # Human input is sampled at the control rate even on fast simulations.
            time.sleep(max(0, session.env.unwrapped.step_dt - (time.monotonic() - start)))


def _collect(args, env, iface, cameras, rest_pose, reset_cameras):
    """Run one collection session on the Newton task or the real follower."""
    device = env.unwrapped.device
    with ExitStack() as cleanup:
        cleanup.callback(env.close)
        demo = None
        if args.demo_video:
            # Closes after the recorder, so a slow video never delays saving corrections.
            demo = DemoVideo(args.demo_video, fps=round(1 / env.unwrapped.step_dt))
            cleanup.callback(demo.close)
        recorder = LeRobotRecorder(
            task_name=args.lang_instruction, repo_id=args.repo_id,
            dataset_root=dataset_root_from_repo_id(args.repo_id), fps=round(1 / env.unwrapped.step_dt),
            cameras=cameras, isolated_writer=True,
        )
        cleanup.callback(recorder.close)
        recorder.init_dataset(resume=args.resume)
        policy = LeRobotPolicyServerClient(
            robot_iface=iface, camera_names=list(cameras),
            pretrained_name_or_path=args.pretrained_name_or_path,
            policy_type=args.policy_type, policy_device=args.policy_device,
            server_address=args.server_address, actions_per_chunk=args.action_horizon,
            lang_instruction=args.lang_instruction,
        )
        cleanup.callback(policy.close)
        policy.connect()
        display = build_sensor_display(
            {f"camera_{name}" for name in cameras}, args, device=device,
            control_actions={"pause_resume", "toggle_correction", "cancel_episode", "reset_world", "stop_session",
                             "guide_start", "control_heartbeat", "control_lost",
                             "hold_position", "release_exit"},
        )
        cleanup.callback(display.close)
        leader_owner = []
        cleanup.callback(_disconnect_leader, iface, leader_owner)
        iface.connect(hold_position=True)
        leader = DaggerLeader(iface.teleop, iface.SO101_JOINT_ORDER, rest_pose=rest_pose)
        leader.start()
        leader_owner.append(leader)
        cleanup.callback(leader.close)
        session = SimDAgger(env, iface, policy, recorder, reset_cameras, leader, leader_follows=args.leader_follows)
        cleanup.callback(session.stop)
        if isinstance(env, RealSO101Env):
            # Runs before session.stop, so the follower returns while the leader parks.
            cleanup.callback(env.start_return)
        try:
            run_session(session, display, demo)
        except KeyboardInterrupt:
            print("\n[DAGGER]: Exit requested; returning leader to taught physical rest, then finalizing saved episodes.")


def main():
    args = parse_args()
    if args.teach_rest:
        iface = LeRobotSO101Interface(port=args.port, robot_id=args.robot_id, sim_device="cpu")
        try:
            iface.connect(hold_position=True)
            measured = iface.get_raw_action(iface.teleop.get_action())
            physical_rest_pose(iface.teleop, iface.SO101_JOINT_ORDER, measured=measured)
            print("[DAGGER]: Rest taught; motor torque remains ON. Support arm before powering off.")
        finally:
            _disconnect_leader(iface, [])
        return
    teleop = SOLeader(SOLeaderTeleopConfig(port=args.port, id=args.robot_id, use_degrees=True))
    rest_pose = physical_rest_pose(teleop, LeRobotSO101Interface.SO101_JOINT_ORDER)
    if args.real:
        iface = LeRobotSO101Interface(port=args.port, robot_id=args.robot_id, sim_device=args.device)
        env = RealSO101Env(iface, args.follower_port, args.follower_id, args.follower_cameras, device=args.device)
        # Real cameras need no render refresh after a reset.
        _collect(args, env, iface, env.cameras, rest_pose, reset_cameras=set())
        return
    cfg, _ = resolve_task_config(args.task, "")
    cfg.scene.num_envs = 1
    cfg.episode_length_s = args.episode_length_s
    if args.seed is not None:
        cfg.seed = args.seed
    if args.device:
        cfg.sim.device = args.device
    active_cameras = apply_camera_selection(cfg, args.cameras)
    if not active_cameras:
        raise ValueError("DAgger requires cameras for policy observations and correction recording.")
    if not math.isclose(round(1 / (cfg.sim.dt * cfg.decimation)) * cfg.sim.dt * cfg.decimation, 1.0):
        raise ValueError("DAgger requires an integer simulation control frequency for dataset timestamps.")

    with launch_simulation(cfg, args):
        env = gym.make(args.task, cfg=cfg)
        iface = LeRobotSO101Interface(port=args.port, robot_id=args.robot_id, sim_device=env.unwrapped.device)
        cameras = {
            name.replace("camera_", ""): {
                "height": getattr(cfg.scene, name).height,
                "width": getattr(cfg.scene, name).width,
            }
            for name in sorted(active_cameras)
        }
        _collect(args, env, iface, cameras, rest_pose, reset_cameras=active_cameras)


if __name__ == "__main__":
    main()
