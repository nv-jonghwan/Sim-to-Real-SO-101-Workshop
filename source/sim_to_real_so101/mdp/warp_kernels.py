# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Native Warp rack safety, grasp and placement checks."""

import warp as wp
from sim_to_real_so101.utils.warp_math import force_on_filter


@wp.kernel
def unsafe_rack(
    position: wp.array(dtype=wp.vec3),
    orientation: wp.array(dtype=wp.quat),
    linear: wp.array(dtype=wp.vec3),
    angular: wp.array(dtype=wp.vec3),
    origins: wp.array(dtype=wp.vec3),
    lower: wp.vec3,
    upper: wp.vec3,
    max_linear: float,
    max_angular: float,
    result: wp.array(dtype=bool),
):
    i = wp.tid()
    p = position[i] - origins[i]
    outside = wp.bool(False)
    for j in range(3):
        outside = outside or p[j] < lower[j] or p[j] > upper[j]
    result[i] = (
        not wp.isfinite(position[i])
        or not wp.isfinite(orientation[i])
        or not wp.isfinite(linear[i])
        or not wp.isfinite(angular[i])
        or outside
        or wp.length(linear[i]) > max_linear
        or wp.length(angular[i]) > max_angular
    )


@wp.kernel
def vial_outside_radius(
    position: wp.array(dtype=wp.vec3),
    origins: wp.array(dtype=wp.vec3),
    max_distance_squared: float,
    result: wp.array(dtype=bool),
):
    i = wp.tid()
    p = position[i] - origins[i]
    result[i] = (
        result[i]
        or not wp.isfinite(position[i])
        or wp.dot(p, p) > max_distance_squared
    )


@wp.kernel
def gather_pose(
    position: wp.array(dtype=wp.vec3),
    orientation: wp.array(dtype=wp.quat),
    index: int,
    result: wp.array2d(dtype=wp.transform),
):
    i = wp.tid()
    result[i, index] = wp.transform(position[i], orientation[i])


@wp.kernel
def grasped(
    forces: wp.array3d(dtype=wp.vec3),
    vials: wp.array2d(dtype=wp.transform),
    steps: wp.array(dtype=wp.int64),
    warmup: int,
    min_height: float,
    threshold: float,
    holding: wp.array(dtype=bool),
    result: wp.array2d(dtype=float),
):
    i = wp.tid()
    previous = holding[i]
    if steps[i] <= wp.int64(1):
        previous = False
    any_contact = wp.bool(False)
    new_grasp = wp.bool(False)
    for vial in range(vials.shape[1]):
        contact = force_on_filter(forces, i, vial) > threshold
        lifted = wp.transform_get_translation(vials[i, vial])[2] > min_height
        any_contact = any_contact or contact
        new_grasp = new_grasp or (contact and lifted and not previous)
    holding[i] = (previous and any_contact) or new_grasp
    result[i, 0] = float(holding[i] and steps[i] >= wp.int64(warmup))


@wp.struct
class PlacementBuffers:
    history: wp.array3d(dtype=bool)
    flags: wp.array2d(dtype=bool)
    counter: wp.array(dtype=int)
    active: wp.array(dtype=bool)
    last_step: wp.array(dtype=wp.int64)
    placed: wp.array2d(dtype=float)
    confirmed: wp.array(dtype=bool)


@wp.kernel
def placement(
    forces: wp.array3d(dtype=wp.vec3),
    vials: wp.array2d(dtype=wp.transform),
    rack_position: wp.array(dtype=wp.vec3),
    rack_orientation: wp.array(dtype=wp.quat),
    steps: wp.array(dtype=wp.int64),
    warmup: int,
    threshold: float,
    xy_lower: wp.vec2,
    xy_upper: wp.vec2,
    z_max: float,
    vertical_threshold: float,
    confirm_steps: int,
    buffers: PlacementBuffers,
):
    i = wp.tid()
    step = steps[i]
    if step == buffers.last_step[i]:
        return
    buffers.last_step[i] = step
    if step <= wp.int64(1):
        buffers.counter[i] = 0
        buffers.active[i] = False
        for vial in range(vials.shape[1]):
            buffers.flags[i, vial] = False
            for h in range(buffers.history.shape[2]):
                buffers.history[i, vial, h] = False
    history_index = int(step % wp.int64(buffers.history.shape[2]))
    any_placed = wp.bool(False)
    still_valid = wp.bool(False)
    inverse = wp.transform_inverse(wp.transform(rack_position[i], rack_orientation[i]))
    for vial in range(vials.shape[1]):
        contact = force_on_filter(forces, i, vial) > threshold
        buffers.history[i, vial, history_index] = contact
        recent = wp.bool(False)
        for h in range(buffers.history.shape[2]):
            recent = recent or buffers.history[i, vial, h]
        pose = vials[i, vial]
        up = wp.quat_rotate(wp.transform_get_rotation(pose), wp.vec3(0.0, 0.0, 1.0))
        p = wp.transform_point(inverse, wp.transform_get_translation(pose))
        valid = (
            wp.abs(up[2]) > vertical_threshold
            and p[0] >= xy_lower[0]
            and p[0] <= xy_upper[0]
            and p[1] >= xy_lower[1]
            and p[1] <= xy_upper[1]
            and p[2] < z_max
            and not contact
        )
        if valid and recent and step >= wp.int64(warmup):
            buffers.flags[i, vial] = True
        any_placed = any_placed or buffers.flags[i, vial]
        still_valid = still_valid or (buffers.flags[i, vial] and valid)
    trigger = any_placed and step >= wp.int64(warmup)
    if trigger and not buffers.active[i]:
        buffers.active[i] = True
        buffers.counter[i] = 0
    if buffers.active[i] and still_valid:
        buffers.counter[i] += 1
    else:
        buffers.counter[i] = 0
        buffers.active[i] = False
    buffers.placed[i, 0] = float(trigger)
    buffers.confirmed[i] = buffers.counter[i] >= confirm_steps
