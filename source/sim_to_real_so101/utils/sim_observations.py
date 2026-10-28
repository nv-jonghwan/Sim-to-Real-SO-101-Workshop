# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Camera observations at simulation reset boundaries."""


def refresh_reset_visuals(env, obs: dict, active_cameras: set[str]) -> None:
    """Refresh reset RGB in place without advancing the observed robot state."""
    if not active_cameras:
        return
    unwrapped = env.unwrapped
    sim = unwrapped.sim
    physics_step = sim.get_physics_step_count()
    # OVRtx material/texture updates need several render-only refreshes.
    for _ in range(4):
        for name in sorted(active_cameras):
            sensor = unwrapped.scene[name]
            sensor.reset()
            sensor.update(0.0, force_recompute=True)
    obs["visual"] = unwrapped.observation_manager.compute_group("visual")
    if sim.get_physics_step_count() != physics_step:
        raise RuntimeError("Reset camera refresh advanced physics.")
