# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Smooth scene-relative curves with bounded, endpoint-flat motion variation."""

import warp as wp


@wp.func
def smooth_fraction(x: float):
    u = wp.clamp(x, 0.0, 1.0)
    return u * u * u * (10.0 + u * (-15.0 + 6.0 * u))


@wp.func
def interpolate_axis(start: wp.vec3, end: wp.vec3, fraction: float):
    rotation = between_axes(start, end)
    return wp.quat_rotate(
        wp.quat_slerp(wp.quat_identity(), rotation, smooth_fraction(fraction)), start
    )


@wp.func
def path_variation(
    start: wp.vec3,
    end: wp.vec3,
    up: wp.vec3,
    u: float,
    bend: float,
    noise: float,
    phase: float,
):
    chord = end - start
    side = wp.cross(up, chord)
    if wp.length(side) > 1.0e-6:
        side = wp.normalize(side)
    envelope = 64.0 * u * u * u * (1.0 - u) * (1.0 - u) * (1.0 - u)
    return side * envelope * (bend + noise * wp.sin(2.0 * wp.pi * u + phase))


@wp.func
def between_axes(a: wp.vec3, b: wp.vec3):
    dot = wp.clamp(wp.dot(a, b), -1.0, 1.0)
    cross = wp.cross(a, b)
    if dot < -0.9999:
        cross = wp.cross(a, wp.vec3(1.0, 0.0, 0.0))
        if wp.length(cross) < 0.01:
            cross = wp.cross(a, wp.vec3(0.0, 1.0, 0.0))
        return wp.quat_from_axis_angle(wp.normalize(cross), wp.pi)
    return wp.normalize(wp.quat(cross[0], cross[1], cross[2], 1.0 + dot))
