# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run the automatic vials-to-rack state-machine framework."""

import argparse
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np
import sim_to_real_so101.tasks  # noqa: F401
import torch
import warp as wp
from isaaclab.app import add_launcher_args, launch_simulation
from isaaclab_tasks.utils import resolve_task_config
from sim_to_real_so101.utils.camera_cfg import (
    DISPLAY_JOINT_NAMES,
    add_browser_display_args,
    add_camera_args,
    apply_camera_selection,
    build_sensor_display,
)
from sim_to_real_so101.utils.dataset_paths import dataset_root_from_repo_id
from sim_to_real_so101.utils.vials_state_machine import VialsStateMachine

# Termination term that marks a vial as placed. The task also terminates on
# `unsafe_rack_state`, which must never be recorded as a demonstration.
_SUCCESS_TERM = "success"

parser = argparse.ArgumentParser(
    description="Run the automatic SO-101 vials state machine."
)
parser.add_argument(
    "--num_envs", type=int, default=None, help="Number of environments to simulate."
)
parser.add_argument(
    "--debug-state-machine",
    action="store_true",
    help="Print state, measured EE position, and commanded EE position.",
)
parser.add_argument(
    "--run-seconds",
    type=float,
    default=None,
    help="Stop after this many seconds of wall-clock rollout time.",
)
parser.add_argument(
    "--task",
    type=str,
    default="Newton-So101-Auto-Vials-State-Machine-v0",
    help="Name of the vials state-machine task.",
)
parser.add_argument(
    "--record",
    action="store_true",
    help="Encode successful episodes in the background and merge a LeRobot dataset at the end.",
)
parser.add_argument(
    "--repo_id",
    type=str,
    default=None,
    help=(
        "LeRobot dataset repo id (user/dataset); local data is stored under "
        "the workshop datasets directory."
    ),
)
parser.add_argument("--task_name", type=str, default=None)
parser.add_argument(
    "--num_episodes",
    type=int,
    default=None,
    help="Number of new successful episodes to collect.",
)
parser.add_argument(
    "--record_fps",
    type=int,
    default=30,
    help="LeRobot dataset frame rate.",
)
parser.add_argument(
    "--encoding_workers",
    type=int,
    default=2,
    help="Number of successful episodes to encode concurrently during collection.",
)
parser.add_argument(
    "--staging_root",
    type=str,
    default=None,
    help="Temporary successful-episode staging directory.",
)
add_camera_args(parser)
add_browser_display_args(parser)
add_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
if args_cli.headless_render:
    args_cli.browser_display = False
if args_cli.run_seconds is not None and args_cli.run_seconds <= 0.0:
    parser.error("--run-seconds must be positive")
sys.argv = [sys.argv[0]] + hydra_args


@dataclass
class _RecordingContext:
    recorder: Any
    interface: Any
    joint_ids: list[int]


def _validate_recording_args(active_cameras: set[str]) -> None:
    missing = [
        name
        for name in ("repo_id", "task_name", "num_episodes")
        if getattr(args_cli, name) in (None, "")
    ]
    if missing:
        raise ValueError(
            "--record requires " + ", ".join(f"--{name}" for name in missing)
        )
    if args_cli.num_episodes <= 0:
        raise ValueError("--num_episodes must be positive.")
    if args_cli.record_fps <= 0:
        raise ValueError("--record_fps must be positive.")
    if args_cli.encoding_workers <= 0:
        raise ValueError("--encoding_workers must be positive.")

    required_cameras = {"camera_wrist", "camera_external"}
    if active_cameras != required_cameras:
        raise ValueError(
            "Offline recording requires both cameras. Use "
            "--cameras all presets=newton,ovrtx_renderer "
            "--visualizer newton."
        )


def _build_recording(
    unwrapped,
    active_cameras: set[str],
) -> _RecordingContext | None:
    if not args_cli.record:
        return None

    active_terms = unwrapped.termination_manager.active_terms
    if _SUCCESS_TERM not in active_terms:
        raise ValueError(
            f"--record needs a '{_SUCCESS_TERM}' termination term to label "
            f"episodes; {args_cli.task} only has {sorted(active_terms)}."
        )

    from sim_to_real_so101.utils.lerobot_interface import (
        LeRobotSO101Interface,
    )
    from sim_to_real_so101.utils.vials_state_machine.recorder import (
        OfflineLeRobotRecorder,
    )

    control_fps = round(1.0 / unwrapped.step_dt)
    if control_fps % args_cli.record_fps != 0:
        raise ValueError(
            f"Control rate {control_fps} Hz is not divisible by requested "
            f"recording rate {args_cli.record_fps} Hz."
        )
    record_decimation = control_fps // args_cli.record_fps

    cameras: dict[str, dict[str, int]] = {}
    for cam_attr in sorted(active_cameras):
        cam_cfg = getattr(unwrapped.scene.cfg, cam_attr)
        cameras[cam_attr.removeprefix("camera_")] = {
            "height": cam_cfg.height,
            "width": cam_cfg.width,
        }

    dataset_root = dataset_root_from_repo_id(args_cli.repo_id)
    staging_root = args_cli.staging_root or f"{dataset_root}.staging"
    recorder = OfflineLeRobotRecorder(
        task_name=args_cli.task_name,
        repo_id=args_cli.repo_id,
        dataset_root=dataset_root,
        staging_root=staging_root,
        fps=args_cli.record_fps,
        cameras=cameras,
        num_envs=unwrapped.num_envs,
        warmup_steps=VialsStateMachine.WARMUP_STEPS,
        capture_decimation=record_decimation,
        encoding_workers=args_cli.encoding_workers,
    )
    interface = LeRobotSO101Interface(
        port="",
        robot_id="offline_state_machine",
        sim_device=str(unwrapped.device),
    )
    robot_joint_names = unwrapped.scene["robot"].joint_names
    joint_ids = [robot_joint_names.index(name) for name in interface.joint_names]
    print(
        f"[INFO]: Offline recording at {args_cli.record_fps} fps "
        f"(control {control_fps} Hz, keeping 1 of every "
        f"{record_decimation} steps), {args_cli.encoding_workers} background encoders."
    )
    if recorder.num_staged_episodes:
        print(
            f"[INFO]: Reusing {recorder.num_staged_episodes} successful "
            f"episode(s) from {staging_root}."
        )
    return _RecordingContext(
        recorder=recorder,
        interface=interface,
        joint_ids=joint_ids,
    )


def _capture_recording_step(
    recording: _RecordingContext,
    unwrapped,
    obs: dict,
) -> None:
    """Capture the current observation with the joint targets applied next."""
    active_mask = np.ones(unwrapped.num_envs, dtype=np.bool_)
    robot = unwrapped.scene["robot"]
    state_radians = obs["policy"]["joint_pos_obs"].detach().cpu().numpy()
    action_radians = (
        robot.data.joint_pos_target.torch[:, recording.joint_ids].detach().cpu().numpy()
    )
    observations = recording.interface.sim_radians_to_raw(state_radians)
    actions = recording.interface.sim_radians_to_raw(action_radians)
    visual_obs = obs.get("visual")
    if visual_obs is None:
        raise RuntimeError(
            "Recording requires the synchronized 'visual' observation group."
        )
    rgb_buffers = {
        name: visual_obs[f"rgb_{name}"] for name in recording.recorder.cameras
    }
    recording.recorder.push_batch_to_buffer(
        actions,
        observations,
        rgb_buffers,
        active_mask,
    )


def _step_with_recording(env, actions, obs: dict, recording: _RecordingContext | None):
    """Capture after action terms apply and before the decimated physics interval.

    The temporary observer pairs the target written for the next control
    interval with its preceding observation. It restores the action manager
    even on failure. Episode acceptance/discard runs after the step's
    termination checks.
    """
    if recording is None:
        return env.step(actions)

    manager = env.unwrapped.action_manager
    apply_action = manager.apply_action
    had_override = "apply_action" in vars(manager)
    captured = False

    def apply_and_capture():
        nonlocal captured
        apply_action()
        if not captured:
            _capture_recording_step(recording, env.unwrapped, obs)
            captured = True

    manager.apply_action = apply_and_capture
    try:
        result = env.step(actions)
        if not captured:
            raise RuntimeError("Recording step did not apply any joint targets.")
        return result
    finally:
        if had_override:
            manager.apply_action = apply_action
        else:
            del manager.apply_action


def _finish_recording_episodes(
    recorder,
    unwrapped,
    terminated: torch.Tensor,
    truncated: torch.Tensor,
    accepted_episodes: int,
    target_episodes: int,
) -> int:
    terminated_cpu = terminated.detach().cpu().numpy()
    truncated_cpu = truncated.detach().cpu().numpy()
    # Reject aborts and timeouts even when success fires in the same interval.
    manager = unwrapped.termination_manager
    success_mask = manager.get_term(_SUCCESS_TERM)
    for name in manager.active_terms:
        if name != _SUCCESS_TERM:
            success_mask = success_mask & ~manager.get_term(name)
    success_cpu = success_mask.detach().cpu().numpy()
    done_env_ids = np.flatnonzero(terminated_cpu | truncated_cpu)
    for env_id in done_env_ids:
        success = success_cpu[env_id] and not truncated_cpu[env_id]
        if success and accepted_episodes < target_episodes:
            if recorder.accept_episode(int(env_id)):
                accepted_episodes += 1
                print(
                    f"[INFO]: Collected successful episode "
                    f"{accepted_episodes}/{target_episodes}."
                )
        else:
            recorder.discard_episode(int(env_id))
    return accepted_episodes


def _update_browser_display(
    sensor_display,
    unwrapped,
    active_cameras: set[str],
    stream_frame: bool,
    obs: dict,
    display_joint_ids: list[int],
    recorder,
    accepted_episodes: int,
) -> None:
    """Stream one environment selected by the browser."""
    if sensor_display is None:
        return

    env_id = sensor_display.selected_environment
    scene = unwrapped.scene
    sensor_display.tick_control()
    if stream_frame:
        if "camera_wrist" in active_cameras:
            sensor_display.update(
                "wrist",
                scene["camera_wrist"].data.output["rgb"][env_id],
                frame_is_new=True,
            )
        if "camera_external" in active_cameras:
            sensor_display.update(
                "external",
                scene["camera_external"].data.output["rgb"][env_id],
                frame_is_new=True,
            )

    joint_pos_obs = obs.get("policy", {}).get("joint_pos_obs")
    if joint_pos_obs is not None:
        joint_targets = scene["robot"].data.joint_pos_target.torch
        sensor_display.push_telemetry(
            joint_pos_obs[env_id],
            joint_targets[env_id, display_joint_ids],
            env_index=env_id,
        )
    if recorder is not None:
        sensor_display.push_status(
            True,
            recorder.saving_status(),
            accepted_episodes,
        )
    else:
        sensor_display.push_status(False)
    if stream_frame:
        sensor_display.flush()


def main() -> None:
    """Run the state machine until the visualizer closes."""
    env_cfg, _ = resolve_task_config(args_cli.task, "")
    active_cameras = apply_camera_selection(env_cfg, args_cli.cameras)
    if args_cli.record:
        _validate_recording_args(active_cameras)
    else:
        # Browser streaming consumes live sensor buffers directly. Avoid cloning
        # full images when synchronized recording tensors are not needed.
        env_cfg.observations.visual = None

    with launch_simulation(env_cfg, args_cli):
        if args_cli.num_envs is not None:
            env_cfg.scene.num_envs = args_cli.num_envs
        if args_cli.device is not None:
            env_cfg.sim.device = args_cli.device

        env = gym.make(args_cli.task, cfg=env_cfg)
        obs, _ = env.reset()
        unwrapped = env.unwrapped
        state_machine = VialsStateMachine(
            dt=unwrapped.step_dt,
            num_envs=unwrapped.num_envs,
            device=unwrapped.device,
            seed=unwrapped.cfg.seed,
        )
        unwrapped._vials_state_machine_retreat_complete = wp.to_torch(
            state_machine.complete
        )
        ee_pose_b = state_machine.gripper_pose_b(unwrapped)
        state_machine.reset(
            ee_pose_b,
            unwrapped.scene["robot"].data.joint_pos.warp,
        )

        recording = _build_recording(unwrapped, active_cameras)
        recorder = recording.recorder if recording is not None else None
        sensor_display = build_sensor_display(
            active_cameras,
            args_cli,
            unwrapped.device,
            num_envs=unwrapped.num_envs,
        )
        display_joint_ids: list[int] = []
        display_decimation = 1
        if sensor_display is not None:
            robot_joint_names = unwrapped.scene["robot"].joint_names
            display_joint_ids = [
                robot_joint_names.index(name) for name in DISPLAY_JOINT_NAMES
            ]
            camera_periods = [
                unwrapped.scene[name].cfg.update_period
                for name in active_cameras
                if unwrapped.scene[name].cfg.update_period > 0.0
            ]
            if camera_periods:
                display_decimation = max(
                    1,
                    round(min(camera_periods) / unwrapped.step_dt),
                )
        sim = unwrapped.sim
        step = 0
        rollout_start = time.perf_counter()
        accepted_episodes = recorder.num_staged_episodes if recorder is not None else 0
        try:
            while recorder is None or accepted_episodes < args_cli.num_episodes:
                if (
                    args_cli.run_seconds is not None
                    and time.perf_counter() - rollout_start >= args_cli.run_seconds
                ):
                    break
                if sim.visualizers and not any(
                    v.is_running() and not v.is_closed for v in sim.visualizers
                ):
                    break
                with torch.inference_mode():
                    ee_pose_b = state_machine.gripper_pose_b(unwrapped)
                    placement_success = getattr(
                        unwrapped,
                        "_vials_state_machine_placement_success",
                        None,
                    )
                    actions = wp.to_torch(
                        state_machine.compute(
                            unwrapped,
                            ee_pose_b,
                            placement_success,
                        )
                    )
                    state_machine.expire_failed(
                        unwrapped.episode_length_buf, unwrapped.max_episode_length
                    )
                    if args_cli.debug_state_machine and step % 30 == 0:
                        print(
                            f"state_machine={state_machine.diagnostics()} ee={ee_pose_b.numpy()} command={actions.tolist()}",
                            flush=True,
                        )
                    obs, _, terminated, truncated, _ = _step_with_recording(
                        env, actions, obs, recording
                    )
                    step += 1
                    reset_env_ids = torch.where(terminated | truncated)[0]
                    if len(reset_env_ids) > 0:
                        if args_cli.debug_state_machine:
                            print(
                                f"episode_result env_ids={reset_env_ids.tolist()} state_machine={state_machine.diagnostics()}",
                                flush=True,
                            )
                        if recorder is not None:
                            accepted_episodes = _finish_recording_episodes(
                                recorder,
                                unwrapped,
                                terminated,
                                truncated,
                                accepted_episodes,
                                args_cli.num_episodes,
                            )
                        state_machine.reset(
                            state_machine.gripper_pose_b(unwrapped),
                            unwrapped.scene["robot"].data.joint_pos.warp,
                            wp.from_torch(reset_env_ids),
                        )
                    _update_browser_display(
                        sensor_display,
                        unwrapped,
                        active_cameras,
                        step % display_decimation == 0,
                        obs,
                        display_joint_ids,
                        recorder,
                        accepted_episodes,
                    )
        finally:
            with ExitStack() as cleanup:
                cleanup.callback(env.close)
                if sensor_display is not None:
                    cleanup.callback(sensor_display.close)
                if recorder is not None:
                    cleanup.callback(recorder.close)
                    if accepted_episodes >= args_cli.num_episodes:
                        recorder.flush_dataset(resume=False)


if __name__ == "__main__":
    main()
