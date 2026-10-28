# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
"""Baseline camera grading and DR film grain for the vial task family."""

from copy import deepcopy

# Fixed appearance approximations for the physical views, not sensor calibration.
BASE_CAMERA_RESPONSES = {
    "/Robot/gripper/wowrobo_2MP_camera": {
        "omni:rtx:post:grade:enabled": True,
        "omni:rtx:post:grade:gain": (1.18, 1.18, 1.182),
        "omni:rtx:post:grade:gamma": (1.12, 1.12, 1.12),
        "omni:rtx:post:grade:saturation": (1.0, 1.0, 1.0),
        # OVRtx defaults to acesApproximation; hand tone mapping to OCIO.
        "omni:rtx:post:tonemap:operator": "none",
    },
    "/ExternalStandaloneCamera": {
        "omni:rtx:post:grade:enabled": True,
        # Saturation is consumed by the color-correction pass.
        "omni:rtx:post:colorcorr:enabled": True,
        "omni:rtx:post:grade:gain": (1.07, 1.07, 1.07),
        "omni:rtx:post:grade:gamma": (1.4, 1.4, 1.4),
        "omni:rtx:post:grade:saturation": (1.2, 1.2, 1.2),
        "omni:rtx:post:grade:whitePoint": (0.95, 0.95, 0.95),
        # OVRtx defaults to acesApproximation; hand tone mapping to OCIO.
        "omni:rtx:post:tonemap:operator": "none",
    },
}

_CAMERA_NOISE = {
    "/Robot/gripper/wowrobo_2MP_camera": {
        "omni:rtx:post:tvNoise:enabled": True,
        "omni:rtx:post:tvNoise:filmGrain:enabled": True,
        "omni:rtx:post:tvNoise:filmGrain:amount": 0.015,
        "omni:rtx:post:tvNoise:filmGrain:size": 0.25,
        "omni:rtx:post:tvNoise:colorAmount": 0.1,
        "omni:rtx:post:tvNoise:lumAmount": 1.0,
    },
    "/ExternalStandaloneCamera": {
        "omni:rtx:post:tvNoise:enabled": True,
        "omni:rtx:post:tvNoise:filmGrain:enabled": True,
        "omni:rtx:post:tvNoise:filmGrain:amount": 0.003,
        "omni:rtx:post:tvNoise:filmGrain:size": 1.0,
        "omni:rtx:post:tvNoise:colorAmount": 0.1,
        "omni:rtx:post:tvNoise:lumAmount": 1.0,
    },
}

DR_CAMERA_RESPONSES = deepcopy(BASE_CAMERA_RESPONSES)
for camera_path, noise_settings in _CAMERA_NOISE.items():
    DR_CAMERA_RESPONSES[camera_path].update(noise_settings)
