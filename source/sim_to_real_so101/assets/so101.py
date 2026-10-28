# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Workshop adapter for Isaac Lab's SO-101 configuration and local overrides."""

from pathlib import Path

import warp as wp
from isaaclab.assets import ArticulationCfg
from isaaclab_assets.robots.so101 import SO101_CFG as ISAACLAB_SO101_CFG

SO101_JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]


# Isaac Lab's canonical SO-101 definition supplies the public
# `so101_new_calib_SysID` asset with the `Robot=robot`, `Sensor=sensors`,
# `Physics=physics` variants and the depenetration velocity and self-collision
# settings. A local wrapper layers workshop-specific overrides over that asset.
#
# Actuator parameters resolve from the AnchorBench system-identification values
# authored in the asset's `physics` variant.
SO101_CFG = ISAACLAB_SO101_CFG.copy()
SO101_CFG.spawn.usd_path = str(
    Path(__file__).parent / "usd" / "so101_workshop_overrides.usda"
)
SO101_CFG.init_state = ArticulationCfg.InitialStateCfg(
    joint_pos={
        "shoulder_pan": -0.1435,
        "shoulder_lift": -1.7450,  # real rest -1.7752, clamped to joint limit
        "elbow_flex": 1.627201072127637,
        "wrist_flex": 1.2966,
        "wrist_roll": -2.0733,
        "gripper": -0.1525,
    },
    pos=(-0.05, 0.0, 0.0),
    rot=tuple(wp.quat_rpy(0.0, 0.0, wp.pi / 2.0)),
)
# The rest pose sits on the `shoulder_lift` stop by design. A factor below 1.0
# shifts that pose on every clamped reset and shrinks the mapped teleop range.
SO101_CFG.soft_joint_pos_limit_factor = 1.0

SO101_CONTACT_GRASP_CFG = SO101_CFG.copy()
SO101_CONTACT_GRASP_CFG.spawn.activate_contact_sensors = True
