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
"""SO-101 teleop agent (Newton physics).

Connects to the SO-101 leader arm via LeRobot and drives the sim env.
With ``--browser-display``, browser-scoped controls use SPACE to start/stop
recording (stop saves), C to discard the in-flight take, and R to reset the
world (discarding the in-flight take). Other display modes do not install
application keyboard controls.

Pass --repo_id and --task_name together to record teleop episodes into a
LeRobotDataset (RGB + 6-DoF state/action). The local dataset path is derived
from the repo id.

Usage:
    lerobot_agent --task Newton-So101-Teleop-Base-v0 \
        --port /dev/ttyACM0 --robot_id leader_bot \
        presets=newton --visualizer newton

    # with dataset recording (task env with cameras):
    lerobot_agent \
        --task Newton-So101-Teleop-Vials-To-Rack-v0 \
        --cameras all presets=newton,ovrtx_renderer --visualizer newton \
        --repo_id user/so101_vials \
        --task_name "Pick up the vial and place it in the rack"
"""

import argparse
import math
import os
import sys
import time

import gymnasium as gym
import sim_to_real_so101.tasks  # noqa: F401
import torch
from isaaclab.app import add_launcher_args, launch_simulation
from isaaclab_tasks.utils import resolve_task_config
from sim_to_real_so101.utils.camera_cfg import (
    add_browser_display_args,
    add_camera_args,
    apply_camera_selection,
    build_sensor_display,
)
from sim_to_real_so101.utils.dataset_paths import dataset_root_from_repo_id
from sim_to_real_so101.utils.lerobot_interface import (
    LeaderReadError,
    LeRobotSO101Interface,
)
from sim_to_real_so101.utils.lerobot_recorder import LeRobotRecorder
from sim_to_real_so101.utils.sim_observations import (
    refresh_reset_visuals as _refresh_reset_visuals,
)

parser = argparse.ArgumentParser(description="SO-101 Teleop agent (Newton).")
parser.add_argument(
    "--num_envs", type=int, default=None, help="Number of environments."
)
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument(
    "--rerun",
    action="store_true",
    default=False,
    help="Stream observations to Rerun visualizer.",
)
parser.add_argument(
    "--port",
    type=str,
    default=os.getenv("TELEOP_PORT", "/dev/ttyACM0"),
    help="Serial port of the leader arm.",
)
parser.add_argument(
    "--robot_id",
    type=str,
    default=os.getenv("TELEOP_ID", "leader_bot"),
    help="LeRobot ID of the leader arm.",
)
parser.add_argument(
    "--repo_id",
    type=str,
    default=None,
    help="LeRobot dataset repo id (e.g. user/so101_vials). Enables recording.",
)
parser.add_argument(
    "--task_name",
    type=str,
    default=None,
    help="Natural-language task string stored in each recorded frame. Enables recording.",
)
parser.add_argument(
    "--record_fps",
    type=int,
    default=None,
    help="Dataset fps. Defaults to 30 to match the real SO-101 camera.",
)
parser.add_argument(
    "--resume",
    action="store_true",
    default=False,
    help="Append episodes to an existing local dataset instead of erroring.",
)
add_camera_args(parser)
add_browser_display_args(parser)
add_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
if args_cli.headless_render:
    args_cli.browser_display = False
    args_cli.rerun = False
if args_cli.rerun and args_cli.browser_display:
    parser.error("--rerun and --browser-display are mutually exclusive")
sys.argv = [sys.argv[0]] + hydra_args


def _recording_decimation(step_dt: float, record_fps: int) -> int:
    """Return an integer capture stride that preserves the dataset timebase."""
    ratio = 1.0 / (step_dt * record_fps) if record_fps > 0 else 0.0
    stride = round(ratio)
    if stride < 1 or not math.isclose(ratio, stride, rel_tol=1e-6):
        raise ValueError(
            f"Recording rate {record_fps} Hz must be positive and divide "
            f"the control rate {1.0 / step_dt:g} Hz exactly."
        )
    return stride


def _recorded_environment_done(
    terminated: torch.Tensor, truncated: torch.Tensor
) -> bool:
    """Return whether environment 0, the teleop recording source, ended."""
    return bool((terminated[0] | truncated[0]).item())


def _pace_control_loop(next_step_deadline: float, step_dt: float) -> float:
    """Wait for the next control deadline, rebasing after an overrun."""
    now = time.perf_counter()
    remaining = next_step_deadline - now
    if remaining > 0.0:
        time.sleep(remaining)
        return next_step_deadline + step_dt
    return now + step_dt


def main():
    env_cfg, _ = resolve_task_config(args_cli.task, "")

    active_cameras = apply_camera_selection(env_cfg, args_cli.cameras)
    recording_mode = all([args_cli.repo_id, args_cli.task_name])
    if recording_mode:
        record_fps = 30 if args_cli.record_fps is None else args_cli.record_fps
        record_decim = _recording_decimation(env_cfg.sim.dt * env_cfg.decimation, record_fps)

    with launch_simulation(env_cfg, args_cli):
        env_cfg.scene.num_envs = args_cli.num_envs or env_cfg.scene.num_envs
        if args_cli.device:
            env_cfg.sim.device = args_cli.device

        env = gym.make(args_cli.task, cfg=env_cfg)
        sim_device = env.unwrapped.device

        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")
        print(f"[INFO]: Active cameras: {sorted(active_cameras) or 'none'}")

        obs, _ = env.reset()
        with torch.inference_mode():
            _refresh_reset_visuals(env, obs, active_cameras)

        robot_iface = LeRobotSO101Interface(
            port=args_cli.port,
            robot_id=args_cli.robot_id,
            sim_device=sim_device,
        )
        robot_iface.connect(visualize=args_cli.rerun)

        recorder = None
        if recording_mode:
            dataset_root = dataset_root_from_repo_id(args_cli.repo_id)
            cameras: dict[str, dict] = {}
            for cam_attr in sorted(active_cameras):
                cam_cfg = getattr(env.unwrapped.scene.cfg, cam_attr, None)
                if cam_cfg is not None:
                    cameras[cam_attr.replace("camera_", "")] = {
                        "height": cam_cfg.height,
                        "width": cam_cfg.width,
                    }
            if not cameras:
                print("[WARNING]: Recording enabled but no active cameras — frames will have no video.")
            control_fps = 1.0 / env.unwrapped.step_dt
            recorder = LeRobotRecorder(
                task_name=args_cli.task_name,
                repo_id=args_cli.repo_id,
                dataset_root=dataset_root,
                fps=record_fps,
                cameras=cameras,
            )
            try:
                recorder.init_dataset(resume=args_cli.resume)
            except ValueError as exc:
                print(f"[ERROR]: {exc}")
                recorder.close()
                robot_iface.disconnect()
                env.close()
                return
            print(
                f"[INFO]: Recording to {dataset_root} at {record_fps} fps "
                f"(control {control_fps} Hz, keeping 1 of every {record_decim} steps)"
            )

        control_actions = {"reset_world"}
        if recorder is not None:
            control_actions.update({"toggle_recording", "cancel_episode"})
        sensor_display = build_sensor_display(
            active_cameras,
            args_cli,
            sim_device,
            control_actions=control_actions,
        )
        recording = False
        if sensor_display is not None:
            controls = "R resets"
            if recorder is not None:
                controls = "SPACE starts/stops recording, C discards, and R resets"
            print(f"[INFO]: Browser controls: {controls} while the browser has focus")

        actions = torch.zeros(env.action_space.shape, device=sim_device)
        sim = env.unwrapped.sim
        visual_obs = obs.get("visual") if args_cli.rerun else None
        record_frame_idx = 0
        next_step_deadline = time.perf_counter() + env.unwrapped.step_dt

        try:
            while True:
                if sim.visualizers and not any(
                    v.is_running() and not v.is_closed for v in sim.visualizers
                ):
                    break

                reset_world = False
                if sensor_display is not None:
                    for action in sensor_display.drain_control_actions():
                        if action == "toggle_recording" and recorder is not None:
                            if recording:
                                recording = False
                                recorder.save_episode()
                            else:
                                recording = True
                                record_frame_idx = 0
                        elif action == "cancel_episode" and recorder is not None:
                            if recording:
                                recording = False
                                recorder.cancel_recording()
                        elif action == "reset_world":
                            if recorder is not None and recording:
                                recording = False
                                recorder.cancel_recording()
                            reset_world = True
                if reset_world:
                    obs, _ = env.reset()
                    with torch.inference_mode():
                        _refresh_reset_visuals(env, obs, active_cameras)
                    visual_obs = obs.get("visual") if args_cli.rerun else None
                    record_frame_idx = 0
                    continue

                with torch.inference_mode():
                    try:
                        raw, sim_action = robot_iface.read_action(visual_obs=visual_obs)
                    except LeaderReadError as exc:
                        print(f"\n[ERROR]: {exc}")
                        if recorder is not None and recorder.pending_frames > 0:
                            print(
                                f"[INFO]: Auto-saving in-flight episode "
                                f"({recorder.pending_frames} frames) before shutdown..."
                            )
                            recorder.save_episode()
                            recording = False
                        print(
                            "[INFO]: Leader unreadable - stopping teleop. "
                            "Recorded episodes will be finalized."
                        )
                        break
                    actions[0, :] = sim_action
                    rec_visual = obs.get("visual")

                    if recorder is not None and recording:
                        if rec_visual is None and recorder.cameras:
                            print(
                                "[WARNING]: No 'visual' obs group — recording needs a task with cameras. Stopping."
                            )
                            recording = False
                        else:
                            # Subsample control steps when their configured rate
                            # is higher than the requested dataset frame rate.
                            if record_frame_idx % record_decim == 0:
                                joint_pos = obs["policy"]["joint_pos_obs"][0]
                                obs_raw = robot_iface.sim_radians_to_raw(
                                    joint_pos.detach().cpu().numpy()
                                )
                                rgb_buffers = {
                                    name: rec_visual[f"rgb_{name}"][0]
                                    for name in recorder.cameras
                                }
                                # Capture owns its RGB/state/action buffers before env.step
                                # can overwrite sensors or return an automatic-reset state.
                                recorder.push_frame_to_buffer(raw, obs_raw, rgb_buffers)
                            record_frame_idx += 1
                    elif recorder is not None:
                        record_frame_idx = 0

                    obs, _, terminated, truncated, _ = env.step(actions)
                    if _recorded_environment_done(terminated, truncated):
                        if recorder is not None and recording:
                            recorder.cancel_recording()
                            recording = False
                            print("[INFO]: Automatic reset discarded the active take.")
                        record_frame_idx = 0
                        _refresh_reset_visuals(env, obs, active_cameras)
                    visual_obs = obs.get("visual") if args_cli.rerun else None

                if sensor_display is not None:
                    scene = env.unwrapped.scene
                    if "camera_wrist" in active_cameras:
                        sensor_display.update(
                            "wrist", scene["camera_wrist"].data.output["rgb"][0]
                        )
                    if "camera_external" in active_cameras:
                        sensor_display.update(
                            "external",
                            scene["camera_external"].data.output["rgb"][0],
                        )
                    joint_pos_obs = obs.get("policy", {}).get("joint_pos_obs")
                    if joint_pos_obs is not None:
                        sensor_display.push_telemetry(joint_pos_obs[0], actions[0])
                    if recorder is not None:
                        sensor_display.push_status(
                            recording,
                            recorder.saving_status(),
                            recorder.num_recorded_episodes,
                        )
                    else:
                        sensor_display.push_status(False)
                    sensor_display.flush()

                next_step_deadline = _pace_control_loop(
                    next_step_deadline, env.unwrapped.step_dt
                )

        except KeyboardInterrupt:
            print("\n[INFO]: Interrupted by user.")
        finally:
            if recorder is not None:
                recorder.close()
            if sensor_display is not None:
                sensor_display.close()
            robot_iface.disconnect()
            env.close()


if __name__ == "__main__":
    main()
