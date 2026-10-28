# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Generate scene-relative manipulation with correlated continuous motion variation."""

from enum import IntEnum
from typing import Any

import warp as wp
from sim_to_real_so101.assets.vial import (
    VIAL_AXIAL_MAX_M,
    VIAL_AXIAL_MIN_M,
    VIAL_GRASP_OFFSET_M,
)
from sim_to_real_so101.utils.warp_bridge import manager_stream

from . import parameters as C
from .data import ControllerState, PhaseDurations, SceneSample
from .motion import between_axes
from .phases import phase_ready, trajectory_goal
from .scene import VialSceneView, select_rack_slot, select_vial


class VialsState(IntEnum):
    """Observable manipulation intents, separated by physical contact events."""

    WARMUP = C.WARMUP
    REACH = C.REACH
    PINCH = C.PINCH
    LIFT_TURN = C.LIFT_TURN
    GUIDE_IN = C.GUIDE_IN
    OPEN = C.OPEN
    SETTLE = C.SETTLE
    RETURN = C.RETURN


@wp.kernel
def reset_controller(
    states: wp.array(dtype=ControllerState),
    complete: wp.array(dtype=bool),
    joints: wp.array2d(dtype=float),
    ids: wp.array(dtype=Any),
    seed: int,
):
    i = int(ids[wp.tid()])
    s = ControllerState()
    s.episode_index = states[i].episode_index + 1
    rng = wp.rand_init(seed + 7919 * s.episode_index, i)
    # One pace factor correlates transport speeds and contact dwell durations.
    s.tempo = wp.randf(rng, 0.90, 1.10)
    s.reach_speed = wp.randf(rng, 0.078, 0.096) * s.tempo
    s.carry_speed = wp.randf(rng, 0.160, 0.206) * s.tempo
    s.return_speed = wp.randf(rng, 0.090, 0.126) * s.tempo
    s.approach_height = wp.randf(rng, 0.050, 0.070)
    s.lift_clearance = wp.randf(rng, 0.030, 0.055)
    s.grasp_pitch_jitter = wp.randf(rng, -0.087, 0.093)
    s.path_bend = wp.randf(rng, -0.008, 0.008)
    s.noise_amplitude = wp.randf(rng, 0.0, 0.001)
    s.noise_phase = wp.randf(rng, -wp.pi, wp.pi)
    s.reach_gripper = wp.randf(rng, C.REACH_OPEN_MIN_RAD, C.REACH_OPEN_MAX_RAD)
    s.pinch_gripper = wp.randf(rng, C.PINCH_MIN_RAD, C.PINCH_MAX_RAD)
    s.open_gripper = wp.randf(rng, C.RELEASE_MIN_RAD, C.RELEASE_MAX_RAD)
    fraction = wp.randf(rng, C.GRASP_FRACTION_MIN, C.GRASP_FRACTION_MAX)
    # The axial lead compensates jaw closure tracking, independent of the measured grasp band.
    s.grasp_axial_offset = (
        VIAL_AXIAL_MIN_M
        + fraction * (VIAL_AXIAL_MAX_M - VIAL_AXIAL_MIN_M)
        - VIAL_GRASP_OFFSET_M
        + C.GRASP_AXIAL_LEAD_M
    )
    s.durations = PhaseDurations(
        3.5,
        0.65 * wp.randf(rng, 0.60, 0.90) / s.tempo,
        1.83,
        1.77,
        wp.randf(rng, 0.50, 0.85) / s.tempo,
        wp.randf(rng, 0.35, 0.75) / s.tempo,
        2.22,
    )
    s.warmup_steps_remaining = C.WARMUP_STEPS
    s.command_gripper = wp.min(joints[i, 5], C.MAX_OPENING_RAD)
    s.release_gripper_floor = s.open_gripper
    states[i] = s
    complete[i] = False


@wp.func
def enter_phase(s: ControllerState):
    s.state += 1
    s.phase_time = 0.0
    s.state_time = 0.0
    s.phase_start_center = s.command_position
    s.phase_start_axis = s.command_axis
    s.phase_start_gripper = s.command_gripper
    return s


@wp.kernel
def step_controller(
    states: wp.array(dtype=ControllerState),
    scenes: wp.array(dtype=SceneSample),
    poses: wp.array(dtype=wp.transform),
    world: wp.array2d(dtype=wp.transform),
    base: wp.array2d(dtype=wp.transform),
    placement: wp.array(dtype=bool),
    dt: float,
    actions: wp.array2d(dtype=float),
    complete: wp.array(dtype=bool),
):
    i = wp.tid()
    s = states[i]
    scene = scenes[i]
    up = scene.up_axis_b
    current_axis = wp.quat_rotate(
        wp.transform_get_rotation(poses[i]), wp.vec3(0.0, 1.0, 0.0)
    )
    s.state_time += dt
    if s.state == C.WARMUP:
        # Settling holds the actual pose; all planned translation and rotation start in REACH.
        s.command_position = scene.grasp_center_b
        s.command_axis = current_axis
        s.return_center = scene.grasp_center_b
        s.return_axis = current_axis
        s.warmup_gripper = s.command_gripper
        s.warmup_steps_remaining -= 1
        if s.warmup_steps_remaining <= 0:
            # The opening envelope includes the fingers, not just the vial radius.
            width = C.GRASP_APPROACH_HALF_WIDTH_MIN_M + (
                C.GRASP_APPROACH_HALF_WIDTH_MAX_M - C.GRASP_APPROACH_HALF_WIDTH_MIN_M
            ) * (s.reach_gripper - C.REACH_OPEN_MIN_RAD) / (
                C.REACH_OPEN_MAX_RAD - C.REACH_OPEN_MIN_RAD
            )
            vial, available = select_vial(
                world, base, i, scene.grasp_center_b, s.grasp_axial_offset, width
            )
            slot, position, clear = select_rack_slot(
                base, i, vial, C.RACK_SLOT_OCCUPANCY_RADIUS_M
            )
            s.selected_vial = vial
            s.selected_rack_slot = slot
            s.rack_slot_position_b = position
            s.task_failed = not available or not clear
            vial_axis = wp.quat_rotate(
                wp.transform_get_rotation(base[i, vial]), wp.vec3(0.0, 0.0, 1.0)
            )
            s.pickup_center = (
                wp.transform_get_translation(base[i, vial])
                + s.grasp_axial_offset * vial_axis
            )
            heading = wp.normalize(vial_axis - wp.dot(vial_axis, up) * up)
            # Pooled acquisition FK gives elevation = 2.247 * radius - .313 (r = .87).
            radius = wp.length(wp.vec2(s.pickup_center[0], s.pickup_center[1]))
            elevation = wp.clamp(
                2.247 * radius - 0.313 + s.grasp_pitch_jitter, 0.15, 0.65
            )
            s.pickup_axis = wp.normalize(
                wp.cos(elevation) * heading + wp.sin(elevation) * up
            )
            # Lower the fingertip target to seat the vial inside the fingers.
            s.pickup_center -= 0.006 * up
            s.home_center = scene.grasp_center_b
            s.home_axis = current_axis
            s.approach_center = s.pickup_center + s.approach_height * up
            # Crossing the rack during reach requires clearance for the open fingertips.
            clearance_height = wp.dot(position, up) + 0.045
            s.approach_center += (
                wp.max(0.0, clearance_height - wp.dot(s.approach_center, up)) * up
            )
            initial_lift = wp.max(0.0, clearance_height - wp.dot(s.home_center, up))
            s.clearance_center = s.home_center + initial_lift * up
            if initial_lift > 0.005:
                s.reach_travel_start = 0.20
            length = (
                wp.length(s.clearance_center - s.home_center)
                + wp.length(s.approach_center - s.clearance_center)
                + wp.length(s.pickup_center - s.approach_center)
            )
            s.durations[0] = wp.max(2.4, length / s.reach_speed)
            s = enter_phase(s)
    else:
        live_slot = wp.transform_get_translation(base[i, 3 + s.selected_rack_slot])
        if not s.release_anchored:
            s.transit_center += live_slot - s.rack_slot_position_b
        s.rack_slot_position_b = live_slot
        s.active_time += dt
        planned = 0.0
        for phase in range(7):
            planned += s.durations[phase]
        s.task_failed = (
            s.task_failed or s.active_time > C.MAX_ACTIVE_DURATION_RATIO * planned
        )
        duration = s.durations[s.state - 1]
        tracking = wp.length(s.command_position - scene.grasp_center_b)
        clock_rate = wp.clamp(1.0 - wp.max(tracking - 0.015, 0.0) / 0.05, 0.10, 1.0)
        angular_error = wp.acos(
            wp.clamp(wp.dot(s.command_axis, current_axis), -1.0, 1.0)
        )
        clock_rate = wp.min(
            clock_rate,
            wp.clamp(1.0 - wp.max(angular_error - 0.08, 0.0) / 0.35, 0.10, 1.0),
        )
        if s.state == C.RETURN and scene.jaw_contact_force > 0.05:
            clock_rate = 0.0
        previous_phase_time = s.phase_time
        s.phase_time = wp.min(s.phase_time + dt * clock_rate, duration)
        if (
            s.state == C.LIFT_TURN
            and wp.dot(scene.selected_vial_tip_b - live_slot, up) < 0.020
        ):
            s.phase_time = wp.min(
                s.phase_time, wp.max(previous_phase_time, 0.45 * duration)
            )
        position, axis, grip = trajectory_goal(s, scene, current_axis)
        if s.state == C.GUIDE_IN:
            step = position - s.command_position
            position = s.command_position + step * wp.min(
                1.0, 0.14 * dt / wp.max(wp.length(step), 1.0e-6)
            )
            s.task_failed = (
                s.task_failed
                or wp.length(scene.selected_vial_tip_b - s.rack_slot_position_b) > 0.20
            )
        if s.state == C.SETTLE and scene.jaw_contact_force > 0.05:
            s.release_gripper_floor = wp.min(
                C.MAX_OPENING_RAD,
                wp.max(s.release_gripper_floor, s.command_gripper) + 0.4 * dt,
            )
            grip = wp.max(grip, s.release_gripper_floor)
        s.command_position = position
        s.command_axis = axis
        s.command_gripper = grip
        if s.state == C.PINCH:
            if scene.contact_force >= C.MIN_GRASP_FORCE_N:
                s.contact_time += dt
            else:
                s.contact_time = 0.0
        if s.state == C.LIFT_TURN or s.state == C.GUIDE_IN:
            if scene.selected_vial_position_w[2] > s.lift_origin_z + 0.018:
                s.grasp_validated = True
            if scene.contact_force < 0.5 and s.state_time > 0.25:
                s.lost_time += dt
            else:
                s.lost_time = 0.0
            s.task_failed = s.task_failed or s.lost_time > 0.25
        selected_seated = wp.bool(False)
        if s.state >= C.OPEN:
            delta = scene.selected_vial_tip_b - s.rack_slot_position_b
            depth = wp.dot(delta, up)
            selected_seated = (
                depth < -0.055
                and wp.length(delta - depth * up) < C.TIP_CENTER_TOLERANCE_M
                and scene.selected_vial_axis_z_w > C.UPRIGHT_AXIS_Z
            )
            s.placement_confirmed = s.placement_confirmed or (
                placement[i] and selected_seated
            )
        ready = phase_ready(s, scene, duration)
        if s.state == C.REACH:
            ready = ready and wp.dot(s.command_axis, current_axis) > 0.98
        if s.state == C.RETURN:
            s.task_failed = s.task_failed or not selected_seated
            ready = ready and placement[i] and selected_seated
        if ready and s.state == C.RETURN:
            complete[i] = not s.task_failed
        elif ready:
            if s.state == C.PINCH:
                s.pickup_center = scene.grasp_center_b
                s.lift_origin_z = scene.selected_vial_position_w[2]
                s.grasp_tip_distance = wp.dot(
                    scene.grasp_center_b - scene.selected_vial_tip_b,
                    scene.selected_vial_axis_b,
                )
                upright = between_axes(scene.selected_vial_axis_b, up)
                offset = wp.quat_rotate(
                    upright, scene.grasp_center_b - scene.selected_vial_tip_b
                )
                s.upright_axis = wp.quat_rotate(upright, current_axis)
                s.place_center = (
                    s.rack_slot_position_b + offset - C.TIP_ENGAGEMENT_M * up
                )
                s.transit_center = s.place_center + s.lift_clearance * up
                chord = s.transit_center - s.pickup_center
                rise = wp.dot(chord, up)
                length = wp.abs(rise) + wp.length(chord - rise * up)
                s.durations[2] = wp.max(1.45, length / s.carry_speed)
                s.durations[3] = wp.max(1.10, s.lift_clearance / (0.060 * s.tempo))
            if s.state == C.GUIDE_IN:
                s.release_fixed_point = (
                    scene.fixed_jaw_center_b + s.command_position - scene.grasp_center_b
                )
                s.release_anchored = True
                s.tip_engaged = True
            if s.state == C.SETTLE:
                length = 0.065 + wp.length(
                    s.return_center - scene.grasp_center_b - 0.065 * up
                )
                s.durations[6] = wp.max(1.9, length / s.return_speed)
            s = enter_phase(s)
        s.task_failed = s.task_failed or s.state_time > duration + C.MAX_PHASE_OVERRUN_S
    for j in range(3):
        actions[i, j] = s.command_position[j]
        actions[i, j + 3] = s.command_axis[j]
    actions[i, 6] = s.command_gripper
    states[i] = s


@wp.kernel
def expire_failed(
    states: wp.array(dtype=ControllerState),
    lengths: wp.array(dtype=wp.int64),
    limit: int,
):
    i = wp.tid()
    if states[i].task_failed:
        lengths[i] = wp.int64(limit)


class VialsStateMachine:
    """Generate independent scene-relative paths from pooled demonstration statistics."""

    WARMUP_STEPS = C.WARMUP_STEPS

    def __init__(self, dt: float, num_envs: int, device, seed: int):
        self.dt, self.num_envs, self.device, self.seed = (
            float(dt),
            num_envs,
            str(device),
            seed,
        )
        self.state = wp.zeros(num_envs, dtype=ControllerState, device=self.device)
        self.complete = wp.zeros(num_envs, dtype=bool, device=self.device)
        self.actions = wp.empty((num_envs, 7), dtype=float, device=self.device)
        self._no_success = wp.zeros(num_envs, dtype=bool, device=self.device)
        self._all_ids = wp.array(range(num_envs), dtype=wp.int64, device=self.device)
        self._scene = VialSceneView(num_envs=num_envs, device=self.device)

    def gripper_pose_b(self, env):
        return self._scene.gripper_pose_b(env)

    def reset(self, ee_pose_b, joint_pos, env_ids=None):
        """Reset selected episodes, preserving other environments' execution clocks."""
        ids = self._all_ids if env_ids is None else env_ids
        with manager_stream(self.device):
            wp.launch(
                reset_controller,
                ids.size,
                [
                    self.state,
                    self.complete,
                    joint_pos,
                    ids,
                    self.seed,
                ],
                device=self.device,
            )

    def compute(self, env, ee_pose_b, placement_success=None):
        """Return seven-component point, axis, and jaw commands for the next interval."""
        success = (
            self._no_success
            if placement_success is None
            else wp.from_torch(placement_success)
        )
        with manager_stream(self.device):
            scene = self._scene.capture(env, self.state)
            wp.launch(
                step_controller,
                self.num_envs,
                [
                    self.state,
                    scene,
                    ee_pose_b,
                    self._scene.world,
                    self._scene.base,
                    success,
                    self.dt,
                    self.actions,
                    self.complete,
                ],
                device=self.device,
            )
        return self.actions

    def expire_failed(self, episode_lengths, max_episode_length):
        with manager_stream(self.device):
            wp.launch(
                expire_failed,
                self.num_envs,
                [self.state, wp.from_torch(episode_lengths), max_episode_length],
                device=self.device,
            )

    def diagnostics(self):
        snapshot = self.state.numpy()
        result = {
            key: snapshot[key].tolist()
            for key in (
                "state_time",
                "active_time",
                "phase_time",
                "tempo",
                "durations",
                "reach_gripper",
                "grasp_axial_offset",
                "selected_vial",
                "selected_rack_slot",
                "task_failed",
                "grasp_validated",
                "placement_confirmed",
            )
        }
        result["state"] = [VialsState(value).name for value in snapshot["state"]]
        return result
