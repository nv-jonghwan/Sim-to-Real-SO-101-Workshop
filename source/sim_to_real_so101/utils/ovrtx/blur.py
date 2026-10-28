# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Episode-fixed Gaussian RGB softness on independent camera tiles."""

import numpy as np
import warp as wp


@wp.kernel
def _blur_horizontal(
    rgba: wp.array4d(dtype=wp.uint8),
    weights: wp.array2d(dtype=float),
    scratch: wp.array4d(dtype=float),
):
    env, y, x, channel = wp.tid()
    value = 0.0
    for offset in range(-6, 7):
        source_x = wp.clamp(x + offset, 0, rgba.shape[2] - 1)
        value += float(rgba[env, y, source_x, channel]) * weights[env, offset + 6]
    scratch[env, y, x, channel] = value


@wp.kernel
def _blur_vertical(
    scratch: wp.array4d(dtype=float),
    weights: wp.array2d(dtype=float),
    rgba: wp.array4d(dtype=wp.uint8),
):
    env, y, x, channel = wp.tid()
    value = 0.0
    for offset in range(-6, 7):
        source_y = wp.clamp(y + offset, 0, rgba.shape[1] - 1)
        value += scratch[env, source_y, x, channel] * weights[env, offset + 6]
    rgba[env, y, x, channel] = wp.uint8(wp.clamp(wp.floor(value + 0.5), 0.0, 255.0))


class CameraGaussianBlur:
    """Hold one 0–2.0 pixel sigma per environment; preserve RGBA allocation and alpha."""

    def __init__(self, num_envs: int, device):
        self._sigma_px = np.zeros(num_envs, dtype=np.float32)
        self._weights = wp.zeros((num_envs, 13), dtype=float, device=device)
        self._scratch = None

    def set_sigma(self, env_ids, sigma_px) -> None:
        """Set selected episode sigmas from CPU arrays without changing other environments."""
        ids = np.asarray(env_ids, dtype=np.int64).reshape(-1)
        values = np.asarray(sigma_px, dtype=np.float32).reshape(-1)
        if (
            len(ids) != len(values)
            or np.any(ids < 0)
            or np.any(ids >= len(self._sigma_px))
            or not np.isfinite(values).all()
            or np.any(values < 0.0)
            or np.any(values > 2.0)
        ):
            raise ValueError("Blur requires one finite sigma in [0, 2.0] per selected environment.")
        self._sigma_px[ids] = values
        weights = np.zeros((len(self._sigma_px), 13), dtype=np.float32)
        weights[:, 6] = 1.0
        active = self._sigma_px > 0.0
        offsets = np.arange(-6, 7, dtype=np.float32)
        weights[active] = np.exp(-0.5 * (offsets / self._sigma_px[active, None]) ** 2)
        weights /= weights.sum(axis=1, keepdims=True)
        self._weights.assign(weights)

    def apply(self, rgba: wp.array) -> None:
        """Filter fresh native RGB in place, independently per tile, leaving alpha untouched."""
        shape = (*rgba.shape[:3], 3)
        if self._scratch is None:
            self._scratch = wp.empty(shape, dtype=float, device=rgba.device)
        wp.launch(
            _blur_horizontal, dim=shape,
            inputs=[rgba, self._weights, self._scratch], device=rgba.device,
        )
        wp.launch(
            _blur_vertical, dim=shape,
            inputs=[self._scratch, self._weights, rgba], device=rgba.device,
        )
