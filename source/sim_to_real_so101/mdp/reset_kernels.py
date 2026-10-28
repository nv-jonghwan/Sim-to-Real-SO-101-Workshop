# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Warp sampling and pose composition for selected reset environments."""

from typing import Any

import warp as wp


@wp.kernel
def sample_asset_pose(
    defaults: wp.array(dtype=wp.transform),
    origins: wp.array(dtype=wp.vec3),
    ids: wp.array(dtype=Any),
    ranges: wp.array(dtype=wp.vec2),
    seed: int,
    result: wp.array(dtype=wp.transform),
):
    k = wp.tid()
    i = int(ids[k])
    rng = wp.rand_init(seed, i)
    position = wp.transform_get_translation(defaults[i]) + origins[i]
    angles = wp.vec3(0.0)
    for j in range(3):
        position[j] += wp.randf(rng, ranges[j][0], ranges[j][1])
        angles[j] = wp.randf(rng, ranges[j + 3][0], ranges[j + 3][1])
    orientation = wp.transform_get_rotation(defaults[i]) * wp.quat_rpy(
        angles[0], angles[1], angles[2]
    )
    result[k] = wp.transform(position, orientation)


@wp.kernel
def place_in_slot(
    rack: wp.array(dtype=wp.transform),
    slot: wp.transform,
    result: wp.array(dtype=wp.transform),
):
    i = wp.tid()
    result[i] = wp.transform_multiply(rack[i], slot)


@wp.kernel
def compose_mat_vial_pose(
    defaults: wp.array(dtype=wp.transform),
    origins: wp.array(dtype=wp.vec3),
    ids: wp.array(dtype=Any),
    samples: wp.array(dtype=wp.vec4),
    resolved: wp.array(dtype=wp.bool),
    height: float,
    result: wp.array(dtype=wp.transform),
):
    k = wp.tid()
    i = int(ids[k])
    position = wp.transform_get_translation(defaults[i])
    orientation = wp.transform_get_rotation(defaults[i])
    if resolved[k]:
        sample = samples[k]
        position = wp.vec3(sample[0], sample[1], height)
        # Cap heading is a world-Z rotation; axial spin is vial-local.
        orientation = (
            wp.quat_rpy(0.0, 0.0, sample[2])
            * orientation
            * wp.quat_rpy(0.0, 0.0, sample[3])
        )
    position[2] = height
    result[k] = wp.transform(position + origins[i], orientation)
