# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Batched frame conversion and contact reduction for native Newton arrays."""

import warp as wp


@wp.kernel
def frame_in_root(
    root_pos: wp.array(dtype=wp.vec3),
    root_quat: wp.array(dtype=wp.quat),
    positions: wp.array2d(dtype=wp.vec3),
    orientations: wp.array2d(dtype=wp.quat),
    frame: int,
    result: wp.array(dtype=wp.transform),
):
    i = wp.tid()
    result[i] = wp.transform_multiply(
        wp.transform_inverse(wp.transform(root_pos[i], root_quat[i])),
        wp.transform(positions[i, frame], orientations[i, frame]),
    )


@wp.func
def force_on_filter(forces: wp.array3d(dtype=wp.vec3), i: int, filter_index: int):
    total = wp.float32(0.0)
    for body in range(forces.shape[1]):
        total += wp.length(forces[i, body, filter_index])
    return total
