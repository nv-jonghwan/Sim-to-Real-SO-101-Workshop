# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Native Warp task conditions with Torch outputs for Isaac Lab managers."""

import torch
import warp as wp
from sim_to_real_so101.utils.warp_bridge import manager_stream

from .warp_kernels import (
    PlacementBuffers,
    gather_pose,
    grasped,
    placement,
    unsafe_rack,
    vial_outside_radius,
)


def vial_layout_sampling_failed(env):
    """Snapshot rejected layouts so automatic reset cannot erase the termination."""
    failed = getattr(env, "_vials_layout_sampling_failed", None)
    if failed is None:
        return torch.zeros(env.num_envs, dtype=torch.bool, device=env.device)
    return failed.clone()


def rack_state_is_unsafe(
    env,
    asset_cfg,
    max_linear_speed: float,
    max_angular_speed: float,
    position_lower: tuple[float, float, float],
    position_upper: tuple[float, float, float],
):
    """Flag non-finite, out-of-bounds or excessively fast rack states."""
    rack = env.scene[asset_cfg.name].data
    with manager_stream(env.device):
        result = wp.empty(env.num_envs, dtype=bool, device=env.device)
        wp.launch(
            unsafe_rack,
            env.num_envs,
            [
                rack.root_pos_w.warp,
                rack.root_quat_w.warp,
                rack.root_lin_vel_w.warp,
                rack.root_ang_vel_w.warp,
                wp.from_torch(env.scene.env_origins, dtype=wp.vec3),
                wp.vec3(*position_lower),
                wp.vec3(*position_upper),
                max_linear_speed,
                max_angular_speed,
                result,
            ],
            device=env.device,
        )
    return wp.to_torch(result)


def any_vial_outside_radius(env, vials: list[str], max_distance: float):
    """Flag environments containing a vial beyond an environment-local radius."""
    with manager_stream(env.device):
        result = wp.zeros(env.num_envs, dtype=bool, device=env.device)
        origins = wp.from_torch(env.scene.env_origins, dtype=wp.vec3)
        for name in vials:
            wp.launch(
                vial_outside_radius,
                env.num_envs,
                [
                    env.scene[name].data.root_pos_w.warp,
                    origins,
                    max_distance * max_distance,
                    result,
                ],
                device=env.device,
            )
    return wp.to_torch(result)


def _vial_poses(env, vials):
    poses = wp.empty((env.num_envs, len(vials)), dtype=wp.transform, device=env.device)
    for index, name in enumerate(vials):
        data = env.scene[name].data
        wp.launch(
            gather_pose,
            env.num_envs,
            [data.root_pos_w.warp, data.root_quat_w.warp, index, poses],
            device=env.device,
        )
    return poses


def any_vial_grasped(
    env,
    contact_sensor_cfg,
    vials: list[str],
    min_height: float = 0.01,
    warmup_steps: int = 30,
    force_threshold: float = 0.1,
):
    """Report grasp acquisition above minimum height, held until contact is lost."""
    key = (
        contact_sensor_cfg.name,
        tuple(vials),
        min_height,
        warmup_steps,
        force_threshold,
    )
    with manager_stream(env.device):
        if not hasattr(env, "_workshop_grasps"):
            env._workshop_grasps = {}
        if key not in env._workshop_grasps:
            env._workshop_grasps[key] = wp.zeros(
                env.num_envs, dtype=bool, device=env.device
            )
        result = wp.empty((env.num_envs, 1), dtype=float, device=env.device)
        wp.launch(
            grasped,
            env.num_envs,
            [
                env.scene[contact_sensor_cfg.name].data.force_matrix_w.warp,
                _vial_poses(env, vials),
                wp.from_torch(env.episode_length_buf),
                warmup_steps,
                min_height,
                force_threshold,
                env._workshop_grasps[key],
                result,
            ],
            device=env.device,
        )
    return wp.to_torch(result)


def _placement_state(
    env,
    contact_sensor_cfg,
    vials,
    rack_name,
    warmup_steps,
    grasp_history_window,
    force_threshold,
    rack_local_x_min,
    rack_local_x_max,
    rack_local_y_min,
    rack_local_y_max,
    rack_local_z_max,
    vertical_threshold,
    confirm_steps,
):
    if grasp_history_window <= 0:
        raise ValueError("grasp_history_window must be positive")
    key = (
        contact_sensor_cfg.name,
        tuple(vials),
        rack_name,
        warmup_steps,
        grasp_history_window,
        force_threshold,
        rack_local_x_min,
        rack_local_x_max,
        rack_local_y_min,
        rack_local_y_max,
        rack_local_z_max,
        vertical_threshold,
        confirm_steps,
    )
    with manager_stream(env.device):
        if not hasattr(env, "_workshop_placements"):
            env._workshop_placements = {}
        if key not in env._workshop_placements:
            buffers = PlacementBuffers()
            buffers.history = wp.zeros(
                (env.num_envs, len(vials), grasp_history_window),
                dtype=bool,
                device=env.device,
            )
            buffers.flags = wp.zeros(
                (env.num_envs, len(vials)), dtype=bool, device=env.device
            )
            buffers.counter = wp.zeros(env.num_envs, dtype=int, device=env.device)
            buffers.active = wp.zeros(env.num_envs, dtype=bool, device=env.device)
            buffers.last_step = wp.full(
                env.num_envs, -1, dtype=wp.int64, device=env.device
            )
            buffers.placed = wp.zeros((env.num_envs, 1), dtype=float, device=env.device)
            buffers.confirmed = wp.zeros(env.num_envs, dtype=bool, device=env.device)
            env._workshop_placements[key] = buffers
        buffers = env._workshop_placements[key]
        rack = env.scene[rack_name].data
        wp.launch(
            placement,
            env.num_envs,
            [
                env.scene[contact_sensor_cfg.name].data.force_matrix_w.warp,
                _vial_poses(env, vials),
                rack.root_pos_w.warp,
                rack.root_quat_w.warp,
                wp.from_torch(env.episode_length_buf),
                warmup_steps,
                force_threshold,
                wp.vec2(rack_local_x_min, rack_local_y_min),
                wp.vec2(rack_local_x_max, rack_local_y_max),
                rack_local_z_max,
                vertical_threshold,
                confirm_steps,
                buffers,
            ],
            device=env.device,
        )
    return buffers


def vial_placed_on_rack(
    env,
    contact_sensor_cfg,
    vials: list[str],
    rack_name: str,
    warmup_steps: int = 30,
    grasp_history_window: int = 20,
    force_threshold: float = 2.0,
    rack_local_x_min: float = 0.0,
    rack_local_x_max: float = 0.12,
    rack_local_y_min: float = 0.0,
    rack_local_y_max: float = 0.12,
    rack_local_z_max: float = 0.1,
    vertical_threshold: float = 0.7,
):
    """Latch placement after recent grasp, upright release inside the rack, and warmup."""
    buffers = _placement_state(
        env,
        contact_sensor_cfg,
        vials,
        rack_name,
        warmup_steps,
        grasp_history_window,
        force_threshold,
        rack_local_x_min,
        rack_local_x_max,
        rack_local_y_min,
        rack_local_y_max,
        rack_local_z_max,
        vertical_threshold,
        25,
    )
    return wp.to_torch(buffers.placed)


def vial_placed_on_rack_termination(
    env,
    contact_sensor_cfg,
    vials: list[str],
    rack_name: str,
    warmup_steps: int = 30,
    grasp_history_window: int = 20,
    force_threshold: float = 2.0,
    rack_local_x_min: float = 0.0,
    rack_local_x_max: float = 0.12,
    rack_local_y_min: float = 0.0,
    rack_local_y_max: float = 0.12,
    rack_local_z_max: float = 0.1,
    vertical_threshold: float = 0.7,
    confirm_steps: int = 25,
):
    """Require valid upright, released placement for consecutive confirmation steps."""
    buffers = _placement_state(
        env,
        contact_sensor_cfg,
        vials,
        rack_name,
        warmup_steps,
        grasp_history_window,
        force_threshold,
        rack_local_x_min,
        rack_local_x_max,
        rack_local_y_min,
        rack_local_y_max,
        rack_local_z_max,
        vertical_threshold,
        confirm_steps,
    )
    return wp.to_torch(buffers.confirmed)


def state_machine_vial_placed_on_rack_termination(
    env,
    contact_sensor_cfg,
    vials: list[str],
    rack_name: str,
    warmup_steps: int = 30,
    grasp_history_window: int = 20,
    force_threshold: float = 2.0,
    rack_local_x_min: float = 0.0,
    rack_local_x_max: float = 0.12,
    rack_local_y_min: float = 0.0,
    rack_local_y_max: float = 0.12,
    rack_local_z_max: float = 0.1,
    vertical_threshold: float = 0.7,
    confirm_steps: int = 25,
):
    """Require current confirmed placement and the controller's completed return."""
    confirmed = vial_placed_on_rack_termination(
        env,
        contact_sensor_cfg,
        vials,
        rack_name,
        warmup_steps,
        grasp_history_window,
        force_threshold,
        rack_local_x_min,
        rack_local_x_max,
        rack_local_y_min,
        rack_local_y_max,
        rack_local_z_max,
        vertical_threshold,
        confirm_steps,
    )
    env._vials_state_machine_placement_success = confirmed
    retreat_complete = getattr(
        env, "_vials_state_machine_retreat_complete", None
    )
    if retreat_complete is None:
        return confirmed & False
    return retreat_complete & confirmed
