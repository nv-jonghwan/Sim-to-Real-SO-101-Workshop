# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Live measurements and independently sampled procedural execution state."""

import warp as wp

PhaseDurations = wp.types.vector(length=7, dtype=wp.float32)


@wp.struct
class ControllerState:
    state: int
    state_time: float
    active_time: float
    episode_index: int
    warmup_steps_remaining: int
    phase_time: float
    tempo: float
    durations: PhaseDurations
    reach_speed: float
    carry_speed: float
    return_speed: float
    approach_height: float
    lift_clearance: float
    grasp_pitch_jitter: float
    path_bend: float
    noise_amplitude: float
    noise_phase: float
    reach_gripper: float
    pinch_gripper: float
    open_gripper: float
    selected_vial: int
    selected_rack_slot: int
    grasp_axial_offset: float
    home_center: wp.vec3
    home_axis: wp.vec3
    return_center: wp.vec3
    return_axis: wp.vec3
    warmup_gripper: float
    pickup_axis: wp.vec3
    upright_axis: wp.vec3
    approach_center: wp.vec3
    clearance_center: wp.vec3
    reach_travel_start: float
    transit_center: wp.vec3
    phase_start_center: wp.vec3
    phase_start_axis: wp.vec3
    phase_start_gripper: float
    pickup_center: wp.vec3
    place_center: wp.vec3
    rack_slot_position_b: wp.vec3
    release_fixed_point: wp.vec3
    release_anchored: bool
    release_gripper_floor: float
    tip_engaged: bool
    command_position: wp.vec3
    command_axis: wp.vec3
    command_gripper: float
    lift_origin_z: float
    grasp_tip_distance: float
    contact_time: float
    lost_time: float
    placement_confirmed: bool
    grasp_validated: bool
    task_failed: bool


@wp.struct
class SceneSample:
    up_axis_b: wp.vec3
    selected_vial_pose_b: wp.transform
    selected_vial_position_w: wp.vec3
    selected_vial_axis_b: wp.vec3
    selected_vial_axis_z_w: float
    selected_vial_tip_b: wp.vec3
    grasp_center_b: wp.vec3
    fixed_jaw_center_b: wp.vec3
    wrist_roll: float
    contact_force: float
    jaw_contact_force: float
    surface_contact_force: float
    wrist_flex: float
    gripper: float
    gripper_velocity: float
    wrist_flex_axis_b: wp.vec3
    wrist_roll_axis_b: wp.vec3
