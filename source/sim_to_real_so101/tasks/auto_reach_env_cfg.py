# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Automatic Cartesian reach task built on the vials-to-rack scene."""

from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils.configclass import configclass
from isaaclab_tasks.contrib.stack.config.so101.pose_ik_action import (
    SO101PoseIKActionCfg,
)
from isaaclab_tasks.contrib.stack.config.so101.pose_ik_controller import (
    SO101PoseIKControllerCfg,
)

from sim_to_real_so101 import mdp
from sim_to_real_so101.assets.so101 import SO101_JOINT_NAMES

from .task_env_cfg import TaskObservationsCfg
from .vials_to_rack_env_cfg import VialsToRackEnvCfg

EPISODE_STEPS = 200
COMMAND_NAME = "ee_pose"
ARM_JOINT_NAMES = SO101_JOINT_NAMES[:-1]


@configclass
class AutoReachCommandsCfg:
    """One independently sampled reachable target per environment and episode."""

    ee_pose = mdp.FixedOrientationUniformPoseCommandCfg(
        asset_name="robot",
        body_name="gripper",
        # Longer than an episode, so reset is the only resampling point.
        resampling_time_range=(10.0, 10.0),
        debug_vis=True,
        position_success_threshold=0.02,
        orientation_success_threshold=0.1,
        ranges=mdp.UniformPoseCommandCfg.Ranges(
            # Robot-base frame. This compact box surrounds the workshop's
            # nominal gripper pose while staying inside the SO-101 workspace.
            pos_x=(-0.08, 0.08),
            pos_y=(-0.25, -0.15),
            pos_z=(0.12, 0.26),
            # Required by the base pose-command config; the custom command
            # replaces this sample with the initial gripper orientation.
            roll=(0.0, 0.0),
            pitch=(0.0, 0.0),
            yaw=(0.0, 0.0),
        ),
    )


@configclass
class AutoReachActionsCfg:
    """Position-prioritized absolute pose control for the 5-DOF arm."""

    arm_pose = SO101PoseIKActionCfg(
        asset_name="robot",
        joint_names=ARM_JOINT_NAMES,
        body_name="gripper",
        scale=1.0,
        controller=SO101PoseIKControllerCfg(
            command_type="pose",
            use_relative_mode=False,
            ik_method="adaptive_dls",
            ik_params={
                "lambda_min": 0.05,
                "lambda_max": 0.2,
                "sigma_thresh": 0.02,
            },
            # The SO-101 cannot exactly serve an arbitrary 6-DOF pose.
            # Position remains full weight; orientation is best-effort and
            # restricted to the two wrist joints.
            orientation_weight=0.5,
            orientation_joint_names=("wrist_flex", "wrist_roll"),
            joint_limit_avoidance_gain=0.5,
            joint_limit_avoidance_margin=0.3,
        ),
    )


@configclass
class AutoReachObservationsCfg(TaskObservationsCfg):
    """Workshop observations augmented with the Cartesian target."""

    @configclass
    class PolicyCfg(TaskObservationsCfg.PolicyCfg):
        target_pose = ObsTerm(
            func=mdp.generated_commands,
            params={"command_name": COMMAND_NAME},
        )

    policy: PolicyCfg = PolicyCfg()


@configclass
class AutoReachRewardsCfg:
    """Dense position reward with a weaker orientation penalty."""

    position_tracking = RewTerm(
        func=mdp.position_command_error_tanh,
        weight=1.0,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=["gripper"]),
            "command_name": COMMAND_NAME,
            "std": 0.05,
        },
    )

    orientation_tracking = RewTerm(
        func=mdp.orientation_command_error,
        weight=-0.1,
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=["gripper"]),
            "command_name": COMMAND_NAME,
        },
    )


@configclass
class AutoReachTerminationsCfg:
    """End every environment after its fixed 200-step horizon."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)


@configclass
class AutoReachEnvCfg(VialsToRackEnvCfg):
    """Vials-to-rack scene with random Cartesian targets and IK actions."""

    commands: AutoReachCommandsCfg = AutoReachCommandsCfg()
    actions: AutoReachActionsCfg = AutoReachActionsCfg()
    observations: AutoReachObservationsCfg = AutoReachObservationsCfg()
    rewards: AutoReachRewardsCfg = AutoReachRewardsCfg()
    terminations: AutoReachTerminationsCfg = AutoReachTerminationsCfg()

    def __post_init__(self) -> None:
        super().__post_init__()
        self.episode_length_s = EPISODE_STEPS * self.decimation * self.sim.dt
