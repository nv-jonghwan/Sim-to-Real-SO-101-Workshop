# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Procedural approach, carry, insertion and withdrawal with physical event gates."""

import warp as wp

from . import parameters as C
from .data import ControllerState, SceneSample
from .motion import between_axes, interpolate_axis, path_variation, smooth_fraction


@wp.func
def trajectory_goal(s: ControllerState, scene: SceneSample, current_axis: wp.vec3):
    duration = s.durations[s.state - 1]
    u = wp.clamp(s.phase_time / duration, 0.0, 1.0)
    t = smooth_fraction(u)
    position = s.phase_start_center
    axis = s.phase_start_axis
    grip = s.pinch_gripper
    up = scene.up_axis_b
    if s.state == C.REACH:
        # A clearance waypoint separates workspace travel from the final descent.
        if u < s.reach_travel_start:
            position = wp.lerp(
                s.home_center,
                s.clearance_center,
                smooth_fraction(u / s.reach_travel_start),
            )
        elif u < 0.62:
            v = (u - s.reach_travel_start) / (0.62 - s.reach_travel_start)
            position = wp.lerp(
                s.clearance_center, s.approach_center, smooth_fraction(v)
            )
            position += path_variation(
                s.home_center,
                s.approach_center,
                up,
                v,
                s.path_bend,
                s.noise_amplitude,
                s.noise_phase,
            )
        else:
            position = wp.lerp(
                s.approach_center, s.pickup_center, smooth_fraction((u - 0.62) / 0.38)
            )
        axis = interpolate_axis(s.home_axis, s.pickup_axis, u / 0.85)
        grip = wp.lerp(s.warmup_gripper, s.reach_gripper, smooth_fraction(u / 0.5))
    elif s.state == C.PINCH:
        grip = wp.lerp(s.phase_start_gripper, s.pinch_gripper, t)
    elif s.state == C.LIFT_TURN:
        # Lift before crossing the rack footprint; turn while carrying above its rim.
        travel = wp.clamp((u - 0.45) / 0.55, 0.0, 1.0)
        horizontal = smooth_fraction(travel)
        position = wp.lerp(s.phase_start_center, s.transit_center, horizontal)
        height = wp.lerp(
            wp.dot(s.phase_start_center, up),
            wp.dot(s.transit_center, up),
            smooth_fraction(u / 0.65),
        )
        position += (height - wp.dot(position, up)) * up
        position += path_variation(
            s.phase_start_center,
            s.transit_center,
            up,
            travel,
            s.path_bend,
            s.noise_amplitude,
            s.noise_phase,
        )
        # An inward bow preserves elbow bend while the wrist turns upright.
        inward = -s.phase_start_center + wp.dot(s.phase_start_center, up) * up
        envelope = 64.0 * u * u * u * (1.0 - u) * (1.0 - u) * (1.0 - u)
        if wp.length(inward) > 0.10:
            position += 0.025 * envelope * wp.normalize(inward)
        axis = interpolate_axis(s.phase_start_axis, s.upright_axis, (u - 0.10) / 0.80)
    elif s.state == C.GUIDE_IN:
        upright = between_axes(scene.selected_vial_axis_b, up)
        aligned_axis = wp.quat_rotate(upright, current_axis)
        axis = interpolate_axis(s.phase_start_axis, aligned_axis, u / 0.60)
        held_offset = wp.quat_rotate(
            upright, scene.grasp_center_b - scene.selected_vial_tip_b
        )
        target = s.rack_slot_position_b + held_offset - C.TIP_ENGAGEMENT_M * up
        position = wp.lerp(s.phase_start_center, target, t)
    elif s.state == C.OPEN or s.state == C.SETTLE:
        # Opening moves the jaw midpoint; anchor the fixed finger to avoid arm counter-motion.
        position = (
            s.release_fixed_point + scene.grasp_center_b - scene.fixed_jaw_center_b
        )
        grip = wp.lerp(s.phase_start_gripper, s.open_gripper, t)
        if s.state == C.SETTLE:
            grip = wp.max(s.open_gripper, s.release_gripper_floor)
    elif s.state == C.RETURN:
        grip = wp.max(s.open_gripper, s.release_gripper_floor)
        if u < 0.30:
            position = s.phase_start_center + up * (0.065 * smooth_fraction(u / 0.30))
        else:
            start = s.phase_start_center + up * 0.065
            v = (u - 0.30) / 0.70
            position = wp.lerp(start, s.return_center, smooth_fraction(v))
            position += path_variation(
                start,
                s.return_center,
                up,
                v,
                s.path_bend,
                s.noise_amplitude,
                s.noise_phase,
            )
        axis = interpolate_axis(s.phase_start_axis, s.return_axis, (u - 0.25) / 0.75)
    return position, wp.normalize(axis), wp.min(grip, C.MAX_OPENING_RAD)


@wp.func
def phase_ready(s: ControllerState, scene: SceneSample, duration: float):
    ready = s.phase_time >= duration
    if s.state == C.REACH:
        error = scene.grasp_center_b - s.command_position
        axial_error = wp.dot(error, scene.selected_vial_axis_b)
        across_error = wp.length(error - axial_error * scene.selected_vial_axis_b)
        # Axial tolerance follows the long grasp band; lateral error determines enclosure.
        ready = ready and across_error < 0.012 and wp.abs(axial_error) < 0.020
    elif s.state == C.PINCH:
        # Sustained contact permits lift as soon as closing force and jaw motion settle.
        ready = (
            s.contact_time >= 0.10
            and scene.contact_force < C.MAX_GRASP_FORCE_N
            and wp.abs(scene.gripper_velocity) < 0.3
        )
    elif s.state == C.LIFT_TURN:
        ready = ready and s.grasp_validated
    elif s.state == C.GUIDE_IN:
        delta = scene.selected_vial_tip_b - s.rack_slot_position_b
        depth = wp.dot(delta, scene.up_axis_b)
        lateral = wp.length(delta - depth * scene.up_axis_b)
        engaged = (depth <= -C.TIP_ENGAGEMENT_M and lateral < 0.008) or (
            depth <= 0.001 and lateral < 0.004
        )
        ready = ready and engaged and scene.selected_vial_axis_z_w > 0.98
    elif s.state == C.OPEN:
        ready = ready and scene.gripper >= s.command_gripper - 0.06
    elif s.state == C.SETTLE:
        ready = (
            ready
            and s.placement_confirmed
            and scene.selected_vial_axis_z_w > C.UPRIGHT_AXIS_Z
            and wp.dot(
                scene.selected_vial_tip_b - s.rack_slot_position_b, scene.up_axis_b
            )
            < -0.055
            and scene.jaw_contact_force < 0.05
        )
    elif s.state == C.RETURN:
        ready = (
            ready
            and s.placement_confirmed
            and scene.jaw_contact_force < 0.05
            and scene.selected_vial_axis_z_w > C.UPRIGHT_AXIS_Z
            and wp.length(scene.grasp_center_b - s.command_position) < 0.025
        )
    return ready
