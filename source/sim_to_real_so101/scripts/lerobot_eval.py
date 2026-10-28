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
"""LeRobot policy-server sim-eval client (Newton physics).

Drives the vials-to-rack eval env from a LeRobot async-inference policy server
(``lerobot.async_inference.policy_server``) over gRPC and reports a success
rate. Mirrors the Newton launch path (``add_launcher_args`` +
``resolve_task_config`` + ``launch_simulation``).

The server is policy-agnostic: this client sends the checkpoint id + feature
spec, and the server loads the policy and runs its own pre/post-processor
pipeline (modality packing, normalization, image resize, relative-action
decoding).

See ``E2E_Workflow.md`` for server startup and evaluation commands.
"""

import argparse
import json
import math
import sys

import grpc
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
from sim_to_real_so101.utils.dataset_start_pose import dataset_start_pose
from sim_to_real_so101.utils.gripper_calibration import (
    WORKSHOP_GRIPPER_CALIBRATION,
    GripperCalibration,
)
from sim_to_real_so101.utils.lerobot_interface import (
    LeRobotPolicyServerClient,
    LeRobotSO101Interface,
)
from tqdm import tqdm

parser = argparse.ArgumentParser(description="SO-101 LeRobot policy-server eval client (Newton).")
parser.add_argument("--start_pose_dataset", default=None, help="Training dataset user/dataset for the mean starting pose; defaults to the state-machine pose.")
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments.")
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument("--seed", type=int, default=None, help="Override the environment seed.")
parser.add_argument("--num_episodes", type=int, default=10, help="Number of episodes to evaluate.")
parser.add_argument(
    "--rename_map",
    type=str,
    default=None,
    help=(
        "JSON map from sim camera names to checkpoint camera names, applied "
        "before sending observations. observation.images.<name> keys are also accepted. "
        "For Johnny42, use "
        "'{\"external\":\"front\"}'."
    ),
)
parser.add_argument(
    "--server_address",
    type=str,
    default="localhost:8080",
    help="LeRobot async policy server address (host:port).",
)
parser.add_argument(
    "--pretrained_name_or_path",
    type=str,
    default="liorbenhorin-nv/GR17-Teleop-Vials-To-Rack-DR-v0-sim",
    help="Checkpoint repo id or path the server should load.",
)
parser.add_argument(
    "--policy_type", type=str, default="groot", help="LeRobot policy type to load on the server."
)
parser.add_argument(
    "--policy_device", type=str, default="cuda", help="Device the server loads the policy on."
)
parser.add_argument(
    "--action_horizon",
    type=int,
    default=16,
    help="Actions per chunk requested from the server (<= checkpoint chunk_size).",
)
parser.add_argument(
    "--lang_instruction",
    type=str,
    default="Pick up the vial and place it in the rack",
    help="Language instruction for the policy.",
)
parser.add_argument(
    "--gripper_span_ticks", type=float, default=WORKSHOP_GRIPPER_CALIBRATION.span_ticks,
    help="Gripper encoder span used by the model's training data (default: workshop mapping).",
)
add_camera_args(parser)
add_browser_display_args(parser)
add_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
if args_cli.headless_render:
    args_cli.browser_display = False
sys.argv = [sys.argv[0]] + hydra_args

_SUCCESS_TERM = "success"


def _require_single_environment(num_envs: int) -> None:
    if num_envs != 1:
        raise ValueError(
            "lerobot_eval supports exactly one environment because policy "
            "observations and episode accounting use environment 0."
        )


def _episode_outcome(
    terminated: torch.Tensor,
    truncated: torch.Tensor,
    success: torch.Tensor,
) -> tuple[bool, bool]:
    is_terminated = bool(terminated[0].item())
    is_truncated = bool(truncated[0].item())
    is_finished = is_terminated or is_truncated
    is_success = is_finished and bool(success[0].item()) and not is_truncated
    return is_finished, is_success


def check_policy_server(address: str, timeout: float = 5.0):
    """Exit with a clear message if no policy server answers at ``address`` (host:port)."""
    channel = grpc.insecure_channel(address)
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
    except grpc.FutureTimeoutError:
        sys.exit(
            f"[ERROR]: No LeRobot policy server reachable at {address}. Start it first "
            "(see E2E_Workflow.md): python -m lerobot.async_inference.policy_server "
            "--host=0.0.0.0 --port=8080 --fps=30"
        )
    finally:
        channel.close()


def main():
    check_policy_server(args_cli.server_address)

    env_cfg, _ = resolve_task_config(args_cli.task, "")
    if args_cli.seed is not None:
        env_cfg.seed = args_cli.seed

    calibration = GripperCalibration(span_ticks=args_cli.gripper_span_ticks)
    pose = dataset_start_pose(args_cli.start_pose_dataset, calibration)
    env_cfg.scene.robot.init_state.joint_pos = {
        name.removesuffix(".pos"): math.radians(
            float(calibration.percent_to_degrees(value)) if name == "gripper.pos" else value
        )
        for name, value in pose.items()
    }

    active_cameras = apply_camera_selection(env_cfg, args_cli.cameras)
    env_cfg.scene.num_envs = args_cli.num_envs or env_cfg.scene.num_envs
    _require_single_environment(env_cfg.scene.num_envs)

    with launch_simulation(env_cfg, args_cli):
        if args_cli.device:
            env_cfg.sim.device = args_cli.device

        env = gym.make(args_cli.task, cfg=env_cfg)
        sim_device = env.unwrapped.device
        if _SUCCESS_TERM not in env.unwrapped.termination_manager.active_terms:
            raise ValueError(
                f"{args_cli.task} needs a '{_SUCCESS_TERM}' termination term "
                "for evaluation."
            )

        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")
        print(f"[INFO]: Active cameras: {sorted(active_cameras) or 'none'}")

        camera_names = sorted(name.replace("camera_", "") for name in active_cameras)
        if not camera_names:
            print("[WARN]: No active cameras — the policy will receive no video frames.")

        rename_map = json.loads(args_cli.rename_map) if args_cli.rename_map else None

        robot_iface = LeRobotSO101Interface(
            port=None,
            robot_id="eval",
            sim_device=sim_device,
            calibration=calibration,
        )

        policy = LeRobotPolicyServerClient(
            robot_iface=robot_iface,
            camera_names=camera_names,
            pretrained_name_or_path=args_cli.pretrained_name_or_path,
            policy_type=args_cli.policy_type,
            server_address=args_cli.server_address,
            policy_device=args_cli.policy_device,
            actions_per_chunk=args_cli.action_horizon,
            lang_instruction=args_cli.lang_instruction,
            rename_map=rename_map,
        )
        policy.connect()

        sensor_display = build_sensor_display(
            active_cameras,
            args_cli,
            sim_device,
            control_actions={"reset_world"},
        )
        if sensor_display is not None:
            print("[INFO]: Browser control: R resets while the browser has focus")

        obs, _ = env.reset()
        policy.reset()

        actions = torch.zeros(env.action_space.shape, device=sim_device)

        scene = env.unwrapped.scene
        sim = env.unwrapped.sim
        step = 0
        num_episodes = 0
        num_successes = 0
        success_rate = 0.0
        pbar = None

        def _close_pbar():
            nonlocal pbar
            if pbar is not None:
                pbar.close()
                pbar = None

        try:
            while True:
                if sim.visualizers and not any(
                    v.is_running() and not v.is_closed for v in sim.visualizers
                ):
                    break

                if sensor_display is not None:
                    actions_requested = sensor_display.drain_control_actions()
                    if "reset_world" in actions_requested:
                        _close_pbar()
                        print(f"[MANUAL RESET] Episode interrupted at step {step}")
                        obs, _ = env.reset()
                        policy.reset()
                        step = 0
                        continue

                with torch.inference_mode():
                    if step == 0:
                        pbar = tqdm(
                            total=env.unwrapped.max_episode_length,
                            desc=f"Rollout (ep {num_episodes + 1}, success: {success_rate:5.1f}%)",
                            unit="step",
                            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                        )


                    joint_positions = obs["policy"]["joint_pos_obs"][0].clone()
                    actions[:] = policy.get_action(joint_positions, obs["visual"])

                    obs, _, terminated, truncated, _ = env.step(actions)
                    step += 1
                    if pbar is not None:
                        pbar.update(1)

                if sensor_display is not None:
                    if "camera_wrist" in active_cameras:
                        sensor_display.update(
                            "wrist", scene["camera_wrist"].data.output["rgb"][0]
                        )
                    if "camera_external" in active_cameras:
                        sensor_display.update(
                            "external", scene["camera_external"].data.output["rgb"][0]
                        )
                    joint_pos_obs = obs.get("policy", {}).get("joint_pos_obs")
                    if joint_pos_obs is not None:
                        sensor_display.push_telemetry(joint_pos_obs[0], actions[0])
                    sensor_display.flush()

                success = env.unwrapped.termination_manager.get_term(_SUCCESS_TERM)
                is_finished, is_success = _episode_outcome(
                    terminated, truncated, success
                )

                if is_finished:
                    _close_pbar()
                    num_episodes += 1
                    if is_success:
                        num_successes += 1
                    success_rate = (num_successes / num_episodes) * 100

                    if num_episodes >= args_cli.num_episodes:
                        print(f"[INFO]: Evaluated {args_cli.num_episodes} episodes")
                        print(
                            f"[INFO]: Success Rate: {num_successes}/{args_cli.num_episodes} "
                            f"({success_rate:.1f}%)"
                        )
                        break

                    obs, _ = env.reset()
                    policy.reset()
                    step = 0
                    continue

        except KeyboardInterrupt:
            print("\n[INFO]: Interrupted by user.")
        finally:
            _close_pbar()
            if sensor_display is not None:
                sensor_display.close()
            policy.close()
            env.close()


if __name__ == "__main__":
    main()
