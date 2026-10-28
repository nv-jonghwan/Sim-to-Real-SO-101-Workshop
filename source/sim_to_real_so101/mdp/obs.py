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
import warp as wp
from isaaclab.managers import SceneEntityCfg
from sim_to_real_so101.utils.warp_bridge import manager_stream
from sim_to_real_so101.utils.warp_math import frame_in_root


def ee_frame_state(
    env,
    ee_frame_cfg: SceneEntityCfg = SceneEntityCfg("ee_frame"),
    robot_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
):
    """Return an XYZW end-effector pose in the root frame to the observation manager."""
    robot = env.scene[robot_cfg.name].data
    frame = env.scene[ee_frame_cfg.name].data
    root = robot.root_pos_w.warp
    with manager_stream(root.device):
        pose = wp.empty(root.shape[0], dtype=wp.transform, device=root.device)
        wp.launch(
            frame_in_root,
            root.shape[0],
            [
                root,
                robot.root_quat_w.warp,
                frame.target_pos_w.warp,
                frame.target_quat_w.warp,
                0,
                pose,
            ],
            device=root.device,
        )
    return wp.to_torch(pose)
