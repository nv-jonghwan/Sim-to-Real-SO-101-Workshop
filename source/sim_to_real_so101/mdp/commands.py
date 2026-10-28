# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Command generators for automatic SO-101 motion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from isaaclab.envs.mdp.commands.commands_cfg import UniformPoseCommandCfg
from isaaclab.envs.mdp.commands.pose_command import UniformPoseCommand
from isaaclab.utils.configclass import configclass
from isaaclab.utils.math import subtract_frame_transforms

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedEnv


class FixedOrientationUniformPoseCommand(UniformPoseCommand):
    """Sample positions while preserving the end effector's initial orientation."""

    cfg: FixedOrientationUniformPoseCommandCfg

    def __init__(self, cfg: FixedOrientationUniformPoseCommandCfg, env: ManagerBasedEnv):
        super().__init__(cfg, env)
        _, orientation_b = subtract_frame_transforms(
            self.robot.data.root_pos_w.torch,
            self.robot.data.root_quat_w.torch,
            self.robot.data.body_pos_w.torch[:, self.body_idx],
            self.robot.data.body_quat_w.torch[:, self.body_idx],
        )
        self._fixed_orientation_b = orientation_b.clone()

    def _resample_command(self, env_ids) -> None:
        super()._resample_command(env_ids)
        self.pose_command_b[env_ids, 3:] = self._fixed_orientation_b[env_ids]


@configclass
class FixedOrientationUniformPoseCommandCfg(UniformPoseCommandCfg):
    """Configuration for position sampling with a fixed initial orientation."""

    class_type: type[FixedOrientationUniformPoseCommand] = FixedOrientationUniformPoseCommand
