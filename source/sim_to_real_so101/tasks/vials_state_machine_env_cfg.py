# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Environment configuration for the automatic vials state machine."""

import math

from isaaclab.assets import ArticulationCfg, RigidObjectCfg
from isaaclab.sensors import ContactSensorCfg
from isaaclab.utils.configclass import configclass
from sim_to_real_so101 import mdp
from sim_to_real_so101.utils.gripper_calibration import GripperCalibration
from sim_to_real_so101.utils.vials_state_machine.arm_action import VialArmActionCfg

from .auto_reach_env_cfg import AutoReachEnvCfg
from .task_env_cfg import TaskObservationsCfg
from .vials_state_machine_assets import (
    ROBOT_TASK_FRAMES,
    VIAL_TASK_FRAMES,
    with_task_frames,
)
from .vials_to_rack_env_cfg import (
    VialsToRackDRSceneCfg,
    VialsToRackEventDRCfg,
    VialsToRackEventExpandedDRCfg,
    VialsToRackSceneCfg,
    VialsToRackTerminationsCfg,
)

# Radians in simulator joint order; the retracted posture frames the workspace.
VIALS_START_POSE_RAD = {
    "shoulder_pan": -0.0983,
    "shoulder_lift": -1.7331,
    "elbow_flex": 1.1753,
    "wrist_flex": 0.8592,
    "wrist_roll": -1.6088,
    "gripper": 0.3640,
}


def vials_start_pose_in_lerobot_units(calibration: GripperCalibration) -> dict[str, float]:
    """Return the vial start pose as named arm degrees and calibrated gripper percent."""
    pose = {}
    for joint_name, angle_radians in VIALS_START_POSE_RAD.items():
        value = math.degrees(angle_radians)
        if joint_name == "gripper":
            value = float(calibration.degrees_to_percent(value))
        pose[f"{joint_name}.pos"] = value
    return pose


_BASE_VIALS_SCENE = VialsToRackSceneCfg()
_BASE_VIALS_DR_SCENE = VialsToRackDRSceneCfg()
_BASE_VIALS_TERMINATIONS = VialsToRackTerminationsCfg()
_GRASP_MAT = _BASE_VIALS_SCENE.mat.copy()
_GRASP_MAT.spawn.activate_contact_sensors = True
_FIXED_JAW_CONTACT = _BASE_VIALS_SCENE.contact_grasp.replace(
    prim_path="{ENV_REGEX_NS}/Robot/gripper"
)
_GRASP_SURFACE_CONTACT = ContactSensorCfg(
    prim_path="{ENV_REGEX_NS}/Mat",
    update_period=0.0,
    history_length=1,
    filter_prim_paths_expr=[
        "{ENV_REGEX_NS}/Robot/gripper",
        "{ENV_REGEX_NS}/Robot/moving_jaw_so101_v1",
    ],
)


@configclass
class VialsStateMachineSceneCfg(VialsToRackSceneCfg):
    """Vials scene whose asset derivatives carry task-local semantic frames."""

    mat = _GRASP_MAT.copy()
    contact_grasp_surface = _GRASP_SURFACE_CONTACT.copy()
    contact_grasp_fixed = _FIXED_JAW_CONTACT.copy()

    robot: ArticulationCfg = with_task_frames(
        _BASE_VIALS_SCENE.robot,
        ROBOT_TASK_FRAMES,
    )
    vial_1: RigidObjectCfg = with_task_frames(
        _BASE_VIALS_SCENE.vial_1,
        VIAL_TASK_FRAMES,
    )
    vial_2: RigidObjectCfg = with_task_frames(
        _BASE_VIALS_SCENE.vial_2,
        VIAL_TASK_FRAMES,
    )
    vial_3: RigidObjectCfg = with_task_frames(
        _BASE_VIALS_SCENE.vial_3,
        VIAL_TASK_FRAMES,
    )


@configclass
class VialsStateMachineDRSceneCfg(VialsToRackDRSceneCfg):
    """Domain-randomized vial scene with state-machine semantic frames."""

    mat = _GRASP_MAT.copy()
    contact_grasp_surface = _GRASP_SURFACE_CONTACT.copy()
    contact_grasp_fixed = _FIXED_JAW_CONTACT.copy()

    robot: ArticulationCfg = with_task_frames(
        _BASE_VIALS_DR_SCENE.robot,
        ROBOT_TASK_FRAMES,
    )
    vial_1: RigidObjectCfg = with_task_frames(
        _BASE_VIALS_DR_SCENE.vial_1,
        VIAL_TASK_FRAMES,
    )
    vial_2: RigidObjectCfg = with_task_frames(
        _BASE_VIALS_DR_SCENE.vial_2,
        VIAL_TASK_FRAMES,
    )
    vial_3: RigidObjectCfg = with_task_frames(
        _BASE_VIALS_DR_SCENE.vial_3,
        VIAL_TASK_FRAMES,
    )


@configclass
class VialsStateMachineActionsCfg:
    """Coupled grasp-point and gripper-axis tracking with five arm joints.

    Action order: ``[grasp_xyz, gripper_y_direction_xyz, gripper_radians]``.
    """

    arm_position = VialArmActionCfg(asset_name="robot")


@configclass
class VialsStateMachineTerminationsCfg(VialsToRackTerminationsCfg):
    """Terminate confirmed placements after the controller completes its return."""

    success = _BASE_VIALS_TERMINATIONS.success.replace(
        func=mdp.state_machine_vial_placed_on_rack_termination
    )


@configclass
class VialsStateMachineEnvCfg(AutoReachEnvCfg):
    """Vials scene controlled by the scripted vial collection pipeline."""

    scene: VialsStateMachineSceneCfg = VialsStateMachineSceneCfg()
    actions: VialsStateMachineActionsCfg = VialsStateMachineActionsCfg()
    observations: TaskObservationsCfg = TaskObservationsCfg()
    commands = None
    rewards = None
    terminations: VialsStateMachineTerminationsCfg = (
        VialsStateMachineTerminationsCfg()
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        # Allow time for pick-and-place, stable-release confirmation, and retreat.
        self.episode_length_s = 30.0
        self.scene.robot.init_state.joint_pos = dict(VIALS_START_POSE_RAD)
        self.events.reset_robot_position.func = mdp.reset_vials_collection_start_pose
        self.events.reset_robot_position.params = {
            "asset_cfg": self.events.reset_robot_position.params["asset_cfg"],
        }


@configclass
class VialsStateMachineDREnvCfg(VialsStateMachineEnvCfg):
    """State-machine collection environment with workshop domain randomization."""

    scene: VialsStateMachineDRSceneCfg = VialsStateMachineDRSceneCfg()
    events: VialsToRackEventDRCfg = VialsToRackEventDRCfg()


@configclass
class VialsStateMachineExpandedDREnvCfg(VialsStateMachineDREnvCfg):
    """Scripted collection with coordinated expanded layouts and full visual DR."""

    events: VialsToRackEventExpandedDRCfg = VialsToRackEventExpandedDRCfg()
