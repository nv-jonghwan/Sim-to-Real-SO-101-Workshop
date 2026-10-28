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
#
# This file contains code derived from Isaac Lab
# (https://github.com/isaac-sim/IsaacLab)
# Copyright (c) 2022-2026, The Isaac Lab Project Developers. All rights reserved.
# Licensed under the BSD-3-Clause License.

"""Script to run an environment from ``sim_to_real_so101`` with a zero-action agent."""

import argparse
import sys

import gymnasium as gym
import torch

import sim_to_real_so101.tasks  # noqa: F401
from isaaclab.app import add_launcher_args, launch_simulation
from isaaclab_tasks.utils import resolve_task_config

from sim_to_real_so101.utils.camera_cfg import (
    add_browser_display_args,
    add_camera_args,
    apply_camera_selection,
    build_sensor_display,
)

parser = argparse.ArgumentParser(description="Zero agent for sim_to_real_so101 environments.")
parser.add_argument(
    "--disable_fabric",
    action="store_true",
    default=False,
    help="Disable fabric and use USD I/O operations.",
)
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
add_camera_args(parser)
add_browser_display_args(parser)
add_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
if args_cli.headless_render:
    args_cli.browser_display = False

# pass remaining args to Hydra
sys.argv = [sys.argv[0]] + hydra_args


def main():
    """Run a sim_to_real_so101 environment with zero actions."""
    env_cfg, _ = resolve_task_config(args_cli.task, "")

    active_cameras = apply_camera_selection(env_cfg, args_cli.cameras)

    with launch_simulation(env_cfg, args_cli):
        env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs
        env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device
        if args_cli.disable_fabric:
            env_cfg.sim.use_fabric = False

        env = gym.make(args_cli.task, cfg=env_cfg)

        print(f"[INFO]: Gym observation space: {env.observation_space}")
        print(f"[INFO]: Gym action space: {env.action_space}")
        print(f"[INFO]: Active cameras: {sorted(active_cameras) or 'none'}")

        env.reset()

        sensor_display = build_sensor_display(
            active_cameras, args_cli, env.unwrapped.device
        )

        sim = env.unwrapped.sim
        actions = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
        try:
            while True:
                if sim.visualizers:
                    if not any(v.is_running() and not v.is_closed for v in sim.visualizers):
                        break
                with torch.inference_mode():
                    obs, _, _, _, _ = env.step(actions)

                if sensor_display is not None:
                    scene = env.unwrapped.scene
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
        finally:
            if sensor_display is not None:
                sensor_display.close()
            env.close()


if __name__ == "__main__":
    main()
