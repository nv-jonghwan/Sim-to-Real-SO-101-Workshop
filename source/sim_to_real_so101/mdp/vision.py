# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

"""Episode-level camera softness for the DR tasks."""

import torch
from isaaclab.managers import SceneEntityCfg

from .resets import _get_all_ovrtx_renderers


def randomize_camera_blur(
    env,
    env_ids: torch.Tensor | slice | None,
    sensor_cfg: SceneEntityCfg,
    sigma_range: tuple[float, float],
) -> None:
    """Sample Gaussian sigma in native-image pixels for each resetting camera tile."""
    low, high = sigma_range
    if not 0.0 <= low <= high <= 2.0:
        raise ValueError("Camera blur sigma must satisfy 0 <= low <= high <= 2.0 pixels")
    indices = torch.arange(env.scene.num_envs, device=env.device)
    if env_ids is not None:
        indices = indices[env_ids]
    sigma = torch.empty(len(indices), device=env.device).uniform_(low, high)
    camera_path = env.scene[sensor_cfg.name].cfg.prim_path
    ids, values = indices.cpu().numpy(), sigma.cpu().numpy()
    for renderer in _get_all_ovrtx_renderers(env):
        renderer.set_camera_blur(camera_path, ids, values)
