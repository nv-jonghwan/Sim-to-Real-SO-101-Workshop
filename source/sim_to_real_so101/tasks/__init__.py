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

"""Package containing task implementations for the extension."""

import gymnasium as gym

##
# Register Gym environments.
##

gym.register(
    id="Newton-So101-Teleop-Base-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.so101_env_cfg:SO101TeleopEnvCfg",
    },
)

gym.register(
    id="Newton-So101-Teleop-Task-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.task_env_cfg:SO101TaskEnvCfg",
    },
)

gym.register(
    id="Newton-So101-Teleop-Vials-To-Rack-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.vials_to_rack_env_cfg:VialsToRackEnvCfg",
    },
)

gym.register(
    id="Newton-So101-Teleop-Vials-To-Rack-DR-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.vials_to_rack_env_cfg:VialsToRackDREnvCfg",
    },
)

gym.register(
    id="Newton-So101-Teleop-Vials-To-Rack-Eval-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.vials_to_rack_env_cfg:VialsToRackEvalEnvCfg",
    },
)

gym.register(
    id="Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.vials_to_rack_env_cfg:VialsToRackEvalDREnvCfg",
    },
)

gym.register(
    id="Newton-So101-Auto-Reach-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.auto_reach_env_cfg:AutoReachEnvCfg",
    },
)

gym.register(
    id="Newton-So101-Auto-Vials-State-Machine-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            f"{__name__}.vials_state_machine_env_cfg:VialsStateMachineEnvCfg"
        ),
    },
)

gym.register(
    id="Newton-So101-Auto-Vials-State-Machine-DR-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            f"{__name__}.vials_state_machine_env_cfg:VialsStateMachineDREnvCfg"
        ),
    },
)


gym.register(
    id="Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            f"{__name__}.vials_to_rack_env_cfg:VialsToRackExpandedDREnvCfg"
        ),
    },
)


gym.register(
    id="Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-Eval-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            f"{__name__}.vials_to_rack_env_cfg:VialsToRackEvalExpandedDREnvCfg"
        ),
    },
)


gym.register(
    id="Newton-So101-Auto-Vials-State-Machine-Expanded-DR-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": (
            f"{__name__}.vials_state_machine_env_cfg:VialsStateMachineExpandedDREnvCfg"
        ),
    },
)
