# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
"""Reset-time material variation for the vial task."""

import torch

_VIAL_BODY_NAMES = tuple(f"vial_{i}_body_material" for i in range(1, 4))

# Linear-albedo candidates, not estimates fitted to the cameras' automatic exposure.
_MATERIAL_GROUPS = (
    (("robot_printed_material", "robot_sensor_printed_material"), (0.80, 0.20, 0.025), None, None),
    (("wall_material",), (0.275, 0.365, 0.445), 0.95, 0.05),
    (("mat_material",), (0.95, 0.95, 0.95), 0.97, 0.04),
    (("rack_material",), (0.95, 0.55, 0.06), 0.60, 0.30),
    (_VIAL_BODY_NAMES, (0.86, 0.86, 0.84), 0.78, 0.22),
    (tuple(f"vial_{i}_cap_material" for i in range(1, 4)), (0.025, 0.16, 0.58), 0.60, 0.25),
)


def randomize_task_materials(env, env_ids):
    """Sample each material group once per selected environment and update every camera."""
    if isinstance(env_ids, slice):
        env_ids = torch.arange(env.num_envs, device=env.device)[env_ids]
    count = env.num_envs if env_ids is None else len(env_ids)
    for names, color, roughness, specular in _MATERIAL_GROUPS:
        materials = [env.scene[name] for name in names]
        brightness = torch.empty((count, 1), device=env.device).uniform_(0.95, 1.05)
        colors = (torch.tensor(color, device=env.device) * brightness).clamp(max=1.0)
        channels = {"color": colors.unsqueeze(0).expand(len(materials), -1, -1)}
        if roughness is not None:
            roughnesses = torch.empty(count, device=env.device).uniform_(roughness - 0.03, roughness + 0.03)
            channels["roughness"] = roughnesses.unsqueeze(0).expand(len(materials), -1)
            if specular is not None:
                channels["specular"] = torch.full((len(materials), count), specular, device=env.device)
        env.sim.render_context.write_visual_materials(
            materials, channels, env_ids,
        )
