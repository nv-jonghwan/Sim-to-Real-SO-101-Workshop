# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# OVRtx loads USD once, so runtime light and texture randomization must mirror
# USD edits through explicit renderer writes.

import glob
import logging
import math
import os

import isaaclab.sim as sim_utils
import numpy as np
import torch
import warp as wp
import yaml
from isaaclab.cloner import path as cloner_path
from isaaclab.cloner.cloner_cfg import DEFAULT_ENV_TEMPLATE, expand_env_regex_ns
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import CameraCfg
from isaaclab.utils.math import quat_from_euler_xyz, quat_mul
from ovrtx import Semantic
from pxr import Gf, Sdf
from sim_to_real_so101.assets.vial import (
    VIAL_AXIAL_MAX_M as _VIAL_AXIAL_MAX_M,
)
from sim_to_real_so101.assets.vial import (
    VIAL_AXIAL_MIN_M as _VIAL_AXIAL_MIN_M,
)
from sim_to_real_so101.assets.vial import (
    VIAL_GRASP_OFFSET_M as _VIAL_GRASP_OFFSET_M,
)
from sim_to_real_so101.assets.vial import (
    VIAL_RADIUS_M as _VIAL_RADIUS_M,
)
from sim_to_real_so101.utils.ovrtx import SO101OVRTXRenderer
from sim_to_real_so101.utils.warp_bridge import manager_stream

from .reset_kernels import compose_mat_vial_pose, place_in_slot, sample_asset_pose

logger = logging.getLogger(__name__)

_YAW_MAPPING_CACHE: dict[str, dict[str, list[float] | None]] = {}

_VIAL_AXIS_MID_M = 0.5 * (_VIAL_AXIAL_MIN_M + _VIAL_AXIAL_MAX_M)
_VIAL_AXIS_HALF_M = 0.5 * (_VIAL_AXIAL_MAX_M - _VIAL_AXIAL_MIN_M)
# Rack footprint from `assets/usd/Vial_rack_simple.usda`, whose mesh extent
# spans [0, 0.12] on both X and Y: the footprint corner is the rack root.
_RACK_FOOTPRINT_HALF_M = 0.06


def reset_vials_collection_start_pose(env, env_ids, asset_cfg: SceneEntityCfg) -> None:
    """Sample retracted collection poses for the resetting environments only."""
    robot = env.scene[asset_cfg.name]
    joint_ids = asset_cfg.joint_ids
    positions = robot.data.default_joint_pos.torch[env_ids][:, joint_ids].clone()
    # A shared extension varies shoulder, elbow, and wrist without combining extremes.
    extension = torch.rand(len(env_ids), device=env.device)
    jitter = 2.0 * torch.rand((len(env_ids), 5), device=env.device) - 1.0
    angles = torch.stack(
        (
            12.0 * jitter[:, 0],
            -97.0 + 45.0 * extension + 2.0 * jitter[:, 1],
            70.0 - 18.0 * extension + 7.0 * jitter[:, 2],
            50.0 - 12.0 * extension + 9.0 * jitter[:, 3],
            -92.0 + 8.0 * jitter[:, 4],
        ),
        dim=1,
    )
    positions[:, :5] = torch.deg2rad(angles)
    limits = robot.data.soft_joint_pos_limits.torch[env_ids][:, joint_ids]
    positions.clamp_(limits[..., 0], limits[..., 1])
    robot.write_joint_state_to_sim_index(
        position=positions,
        velocity=torch.zeros_like(positions),
        joint_ids=joint_ids,
        env_ids=env_ids,
    )


def randomize_robot_base_tilt(
    env,
    env_ids: torch.Tensor | None,
    asset_cfg: SceneEntityCfg,
    tilt_degrees: tuple[float, float],
) -> None:
    """Tilt the fixed robot base about its nominal mounting position at reset.

    Positive angles lean toward the lightbox opening (world -X), rotating
    about world -Y. Each selected environment samples independently from
    the nominal pose, so repeated resets do not accumulate tilt.
    """
    robot = env.scene[asset_cfg.name]
    if env_ids is None:
        env_ids = torch.arange(env.num_envs, device=env.device)
    if len(env_ids) == 0:
        return

    with manager_stream(env.device):
        tilt = torch.empty(len(env_ids), device=env.device).uniform_(*tilt_degrees).deg2rad()
        zeros = torch.zeros_like(tilt)
        pose = robot.data.default_root_pose.torch[env_ids].clone()
        pose[:, :3] += env.scene.env_origins[env_ids]
        pose[:, 3:] = quat_mul(quat_from_euler_xyz(zeros, -tilt, zeros), pose[:, 3:])
        robot.write_root_pose_to_sim_index(root_pose=pose, env_ids=env_ids)


def randomize_external_camera(
    env,
    env_ids: torch.Tensor | None,
    camera_cfg: SceneEntityCfg,
    tilt_degrees: tuple[float, float],
    focal_length_scale: tuple[float, float],
) -> None:
    """Sample external-camera tilt and zoom relative to its configured pose/lens.

    Tilt is about the camera's local horizontal axis. Tiled OVRtx projections
    require shared intrinsics, so zoom is sampled only on a full reset and
    retained during partial resets. Camera positions stay fixed.
    """
    camera = env.scene[camera_cfg.name]
    if env_ids is None:
        env_ids = torch.arange(env.num_envs, device=env.device)
    count = len(env_ids)
    if count == 0:
        return

    with manager_stream(env.device):
        tilt = torch.empty(count, device=env.device).uniform_(*tilt_degrees).deg2rad()
        zeros = torch.zeros_like(tilt)
        nominal = torch.tensor(camera.cfg.offset.rot, device=env.device)
        nominal = (nominal / nominal.norm()).expand(count, -1)
        orientations = quat_mul(nominal, quat_from_euler_xyz(tilt, zeros, zeros))
        camera.set_world_poses(
            orientations=orientations, env_ids=env_ids, convention="opengl"
        )

        if count == env.num_envs:
            focal_length = camera.cfg.spawn.focal_length * _sample_scalar(focal_length_scale)
            focal_pixels = focal_length / camera.cfg.spawn.horizontal_aperture * camera.cfg.width
            matrices = torch.tensor(
                [[focal_pixels, 0, camera.cfg.width / 2],
                 [0, focal_pixels, camera.cfg.height / 2],
                 [0, 0, 1]],
                dtype=torch.float32, device=env.device,
            ).repeat(env.num_envs, 1, 1)
            camera.set_intrinsic_matrices(matrices, focal_length=focal_length)


def _get_all_ovrtx_renderers(env) -> list[SO101OVRTXRenderer]:
    """Return each active workshop camera renderer once."""
    seen: set[int] = set()
    renderers: list[SO101OVRTXRenderer] = []
    for sensor in env.scene.sensors.values():
        if not isinstance(sensor.cfg, CameraCfg):
            continue
        renderer = env.sim.get_or_create_backend(sensor.cfg.renderer_cfg)
        if isinstance(renderer, SO101OVRTXRenderer) and id(renderer) not in seen:
            seen.add(id(renderer))
            renderers.append(renderer)
    return renderers


def _write_ovrtx_attribute(
    env,
    prim_path_pattern: str,
    attribute_name: str,
    tensor: np.ndarray,
    semantic=None,
) -> bool:
    tensor = np.asarray(tensor)
    wrote = False
    for renderer in _get_all_ovrtx_renderers(env):
        wrote = (
            renderer.write_prim_attribute(
                prim_path=prim_path_pattern,
                attribute_name=attribute_name,
                tensor=tensor,
                semantic=semantic,
            )
            or wrote
        )
    return wrote


def _write_ovrtx_asset_path(
    env,
    prim_path_pattern: str,
    attribute_name: str,
    asset_path: str,
) -> bool:
    """Mirror a USD ``asset`` attribute to every active OVRtx backend."""
    asset_path = os.path.abspath(asset_path)
    wrote = False
    for renderer in _get_all_ovrtx_renderers(env):
        wrote = (
            renderer.write_prim_asset_path(
                prim_path=prim_path_pattern,
                attribute_name=attribute_name,
                asset_path=asset_path,
            )
            or wrote
        )
    return wrote


def _to_search_pattern(prim_path_pattern: str) -> str:
    return cloner_path.rebase(
        expand_env_regex_ns(prim_path_pattern),
        DEFAULT_ENV_TEMPLATE.format(0),
        DEFAULT_ENV_TEMPLATE.format(".*"),
    )


def _find_matching_prims_all_envs(prim_path_pattern: str):
    return sim_utils.find_matching_prims(_to_search_pattern(prim_path_pattern))


def _selected_env_ids(env, env_ids: torch.Tensor | None) -> set[int]:
    return (
        set(range(env.scene.num_envs))
        if env_ids is None
        else {int(env_id) for env_id in env_ids.detach().cpu().tolist()}
    )


def _select_env_prims(prims, env, env_ids: torch.Tensor | None):
    selected_env_ids = _selected_env_ids(env, env_ids)
    return [
        prim
        for prim in prims
        if any(
            str(prim.GetPath()).startswith(f"/World/envs/env_{env_id}/")
            for env_id in selected_env_ids
        )
    ]


def _sample_scalar(value_range: tuple[float, float]) -> float:
    return float(np.random.uniform(*value_range))


def _quat_xyzw_to_gf_quatd(quat_xyzw: tuple[float, float, float, float]) -> Gf.Quatd:
    return Gf.Quatd(quat_xyzw[3], quat_xyzw[0], quat_xyzw[1], quat_xyzw[2])


def _write_ovrtx_xform(
    env,
    prim_path_pattern: str,
    position_xyz: tuple[float, float, float],
    quat_xyzw: tuple[float, float, float, float],
) -> bool:
    # Gf's row-vector matrix layout matches the column-major OVRtx payload.
    matrix = Gf.Matrix4d().SetRotate(_quat_xyzw_to_gf_quatd(quat_xyzw))
    matrix.SetTranslateOnly(Gf.Vec3d(*position_xyz))
    return _write_ovrtx_attribute(
        env=env,
        prim_path_pattern=prim_path_pattern,
        attribute_name="omni:xform",
        tensor=np.array([matrix], dtype=np.float64),
        semantic=Semantic.XFORM_MAT4x4,
    )


def randomize_light_exposure(
    env,
    env_ids: torch.Tensor | None,
    exposure_range: tuple[float, float],
    asset_cfg: SceneEntityCfg | None = None,
):
    if asset_cfg is None:
        return

    asset = env.scene[asset_cfg.name]
    prim_path_pattern = asset.cfg.prim_path
    prims = _find_matching_prims_all_envs(prim_path_pattern)
    selected_prims = _select_env_prims(prims, env, env_ids)

    for prim in selected_prims:
        exposure = _sample_scalar(exposure_range)
        with Sdf.ChangeBlock():
            if not prim.IsValid():
                continue
            attr = prim.GetAttribute("inputs:exposure")
            if attr.IsValid():
                attr.Set(exposure)

        _write_ovrtx_attribute(
            env=env,
            prim_path_pattern=str(prim.GetPath()),
            attribute_name="inputs:exposure",
            tensor=np.array([exposure], dtype=np.float32),
        )


def _random_asset_pose(env, env_ids, asset, pose_range):
    """Sample partial native world poses and write them to the selected bodies."""
    ranges = wp.array(
        [
            pose_range.get(key, (0.0, 0.0))
            for key in ("x", "y", "z", "roll", "pitch", "yaw")
        ],
        dtype=wp.vec2,
        device=asset.device,
    )
    result = wp.empty(env_ids.size, dtype=wp.transform, device=asset.device)
    wp.launch(
        sample_asset_pose,
        env_ids.size,
        [
            asset.data.default_root_pose.warp,
            wp.from_torch(env.scene.env_origins, dtype=wp.vec3),
            env_ids,
            ranges,
            int(np.random.randint(0, 2**31)),
            result,
        ],
        device=asset.device,
    )
    asset.write_root_pose_to_sim_index(root_pose=result, env_ids=env_ids)
    return result


def _read_slot_local_poses(
    rack_prim_path: str,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float, float]]]:
    """Read local translate/orient for all `top_*` slot prims under the rack.

    Reads only from env_0; slot transforms are local to the rack and
    identical across clones.
    """
    slot_pattern = f"{rack_prim_path}/Body1/Mesh/top_.*".replace(
        "{ENV_REGEX_NS}", "/World/envs/env_0"
    )
    slot_prims = sim_utils.find_matching_prims(slot_pattern)

    pos_list: list[tuple[float, float, float]] = []
    quat_list: list[tuple[float, float, float, float]] = []
    for prim in slot_prims:
        if not prim.IsValid():
            continue
        translate_attr = prim.GetAttribute("xformOp:translate")
        if translate_attr.IsValid() and translate_attr.Get() is not None:
            t = translate_attr.Get()
            pos = (float(t[0]), float(t[1]), float(t[2]))
        else:
            pos = (0.0, 0.0, 0.0)
        orient_attr = prim.GetAttribute("xformOp:orient")
        if orient_attr.IsValid() and orient_attr.Get() is not None:
            q = orient_attr.Get()
            imag = q.GetImaginary()
            quat = (
                float(imag[0]),
                float(imag[1]),
                float(imag[2]),
                float(q.GetReal()),
            )
        else:
            quat = (0.0, 0.0, 0.0, 1.0)
        pos_list.append(pos)
        quat_list.append(quat)
    return pos_list, quat_list


_Box = tuple[tuple[float, float], tuple[float, float]]


def _vial_xy_aabb(x: float, y: float, yaw: float) -> _Box:
    """Return the XY (centre, half-extent) box of a vial lying flat at ``yaw``.

    Axial spin does not appear here: the vial is a body of revolution about its
    own long axis, so only the cap heading changes its footprint.
    """
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    centre = (
        x + _VIAL_AXIS_MID_M * cos_yaw,
        y + _VIAL_AXIS_MID_M * sin_yaw,
    )
    half = (
        _VIAL_AXIS_HALF_M * abs(cos_yaw) + _VIAL_RADIUS_M * abs(sin_yaw),
        _VIAL_AXIS_HALF_M * abs(sin_yaw) + _VIAL_RADIUS_M * abs(cos_yaw),
    )
    return centre, half


def _rack_xy_aabb(x: float, y: float, yaw: float) -> _Box:
    """Return the XY (centre, half-extent) box of the rack at ``yaw``."""
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    offset = _RACK_FOOTPRINT_HALF_M
    centre = (
        x + offset * (cos_yaw - sin_yaw),
        y + offset * (sin_yaw + cos_yaw),
    )
    half = offset * (abs(cos_yaw) + abs(sin_yaw))
    return centre, (half, half)


def _aabb_overlap_xy(box_a: _Box, box_b: _Box, clearance: float) -> bool:
    """True when two XY boxes come within ``clearance`` of each other."""
    (centre_a, half_a), (centre_b, half_b) = box_a, box_b
    return all(
        abs(centre_a[axis] - centre_b[axis]) - (half_a[axis] + half_b[axis]) < clearance
        for axis in (0, 1)
    )


def _aabb_inside_xy(box: _Box, bounds: dict[str, tuple[float, float]]) -> bool:
    """True when an XY box lies wholly inside ``bounds``."""
    centre, half = box
    return all(
        centre[axis] - half[axis] >= limits[0]
        and centre[axis] + half[axis] <= limits[1]
        for axis, limits in enumerate(
            (bounds.get("x", (0.0, 0.0)), bounds.get("y", (0.0, 0.0)))
        )
    )


def _sample_mat_vial_poses(
    num_vials: int,
    *,
    pose_range: dict[str, tuple[float, float]],
    mat_bounds: dict[str, tuple[float, float]],
    rack_box: _Box,
    robot_xy: tuple[float, float],
    reach_range: tuple[float, float],
    clearance: float,
    max_sample_tries: int,
) -> list[tuple[float, float, float, float]] | None:
    """Lay one environment's mat vials out so their footprints stay clear.

    Each vial is rejection-sampled until its XY box lies inside ``mat_bounds``,
    its ``sm_grasp`` frame falls within ``reach_range`` of the robot root, and
    it keeps ``clearance`` from the rack and from every vial already placed.
    Returns ``(x, y, yaw, spin)`` per vial, or ``None`` if the sampling budget
    is exhausted before all vials have a valid placement.
    """
    x_range = pose_range.get("x", (0.0, 0.0))
    y_range = pose_range.get("y", (0.0, 0.0))
    yaw_range = pose_range.get("yaw", (0.0, 0.0))
    spin_range = pose_range.get("spin", (0.0, 0.0))

    poses: list[tuple[float, float, float, float]] = []
    boxes: list[_Box] = []
    for _ in range(num_vials):
        for _ in range(max_sample_tries):
            x = _sample_scalar(x_range)
            y = _sample_scalar(y_range)
            yaw = _sample_scalar(yaw_range)

            box = _vial_xy_aabb(x, y, yaw)
            if not _aabb_inside_xy(box, mat_bounds):
                continue
            reach = math.hypot(
                x + _VIAL_GRASP_OFFSET_M * math.cos(yaw) - robot_xy[0],
                y + _VIAL_GRASP_OFFSET_M * math.sin(yaw) - robot_xy[1],
            )
            if not reach_range[0] <= reach <= reach_range[1]:
                continue
            if _aabb_overlap_xy(box, rack_box, clearance):
                continue
            if any(_aabb_overlap_xy(box, other, clearance) for other in boxes):
                continue

            # Spin is free of every constraint above, so it is only drawn once
            # the placement is accepted.
            poses.append((x, y, yaw, _sample_scalar(spin_range)))
            boxes.append(box)
            break
        else:
            return None
    return poses


def _sample_coordinated_vials_rack(
    num_vials: int,
    *,
    rack_centers: tuple[tuple[float, float], ...],
    rack_min_center_distance: float,
    rack_pose_range: dict[str, tuple[float, float]],
    vial_pose_range: dict[str, tuple[float, float]],
    mat_bounds: dict[str, tuple[float, float]],
    robot_xy: tuple[float, float],
    reach_range: tuple[float, float],
    clearance: float,
    max_sample_tries: int,
    is_accessible,
) -> tuple[tuple[float, float, float], list[tuple[float, float, float, float]]] | None:
    """Sample a contained rack and reachable mat vials on their assigned side.

    Layout and vial-side choices persist across rejection retries, so crowded
    layouts are not silently replaced by an easier side. Rack centers refer to
    the footprint; its USD root is a corner. Return None on sampling exhaustion.
    """
    center_x, center_y = rack_centers[int(np.random.randint(len(rack_centers)))]
    vial_side = -1 if center_y > 0.0 else 1
    if center_y == 0.0:
        vial_side = int(np.random.choice((-1, 1)))
    pose_range = dict(vial_pose_range)
    side_bounds = dict(mat_bounds)
    if vial_side > 0:
        lo, hi = pose_range["y"]
        pose_range["y"] = (-hi, -lo)
        side_bounds["y"] = (0.0, mat_bounds["y"][1])
    else:
        side_bounds["y"] = (mat_bounds["y"][0], 0.0)

    for _ in range(100):
        yaw = _sample_scalar(rack_pose_range.get("yaw", (0.0, 0.0)))
        x = center_x + _sample_scalar(rack_pose_range.get("x", (0.0, 0.0)))
        y = center_y + _sample_scalar(rack_pose_range.get("y", (0.0, 0.0)))
        # Near-base racks require tightly folded insertion postures at the wrist limit.
        if math.hypot(x - robot_xy[0], y - robot_xy[1]) < rack_min_center_distance:
            continue
        x -= _RACK_FOOTPRINT_HALF_M * (math.cos(yaw) - math.sin(yaw))
        y -= _RACK_FOOTPRINT_HALF_M * (math.sin(yaw) + math.cos(yaw))
        rack_box = _rack_xy_aabb(x, y, yaw)
        if not _aabb_inside_xy(rack_box, mat_bounds):
            continue
        layout = _sample_mat_vial_poses(
            num_vials,
            pose_range=pose_range,
            mat_bounds=side_bounds,
            rack_box=rack_box,
            robot_xy=robot_xy,
            reach_range=reach_range,
            clearance=clearance,
            max_sample_tries=max_sample_tries,
        )
        if layout is not None and is_accessible((x, y, yaw), layout):
            return (x, y, yaw), layout
    return None


def reset_vials_rack(
    env,
    env_ids: torch.Tensor,
    vials: list[str],
    rack: str,
    rack_pose_range: dict[str, tuple[float, float]],
    vial_pose_range: dict[str, tuple[float, float]],
    mat_bounds: dict[str, tuple[float, float]],
    vial_reach_range: tuple[float, float],
    fixed_vial_z: float,
    clearance: float = 0.004,
    max_sample_tries: int = 1000,
    rack_placement_prob: float = 0.33,
    rack_centers: tuple[tuple[float, float], ...] | None = None,
    rack_min_center_distance: float = 0.0,
):
    """Reset the selected environments' rack and vials, zeroing their velocities.

    Mat vials are rejection-sampled over ``vial_pose_range`` so that each vial's
    XY bounding box stays inside ``mat_bounds`` and keeps ``clearance`` from the
    rack and from every other vial, while its ``sm_grasp`` frame stays within
    ``vial_reach_range`` of the robot root. The ``x``/``y`` keys are the
    vial-root position in metres relative to the environment origin, ``yaw`` the
    world heading of the cap and ``spin`` the rotation about the vial's own long
    axis.

    With ``rack_centers``, choose a rack footprint center uniformly and apply
    ``rack_pose_range`` about it. Mat vials occupy the opposite Y half of the
    mat; a centered rack chooses that half randomly. The vial Y range mirrors
    for the positive half. The footprint center stays at least
    ``rack_min_center_distance`` horizontally from the robot root.
    Joint rack/vial sampling enforces rack containment
    and a reachable floor grasp/slot pair with open-finger clearance. It retries
    the same layout choice. Exhaustion marks only that environment's episode
    invalid and restores its authored object poses for the automatic reset.
    Other floor vials retain the wider ``vial_reach_range``.

    Without ``rack_centers``, an exhausted vial search uses authored XY poses.
    All mat poses use ``fixed_vial_z`` relative to the environment origin.

    With probability ``rack_placement_prob`` one randomly chosen vial is
    pre-placed in a randomly chosen rack slot instead of on the mat.
    """
    vial_objects = [env.scene[name] for name in vials]
    rack_obj = env.scene[rack]
    slot_pos_list, slot_quat_list = _read_slot_local_poses(rack_obj.cfg.prim_path)
    total_slots = len(slot_pos_list)

    with manager_stream(env.device):
        ids = wp.from_torch(env_ids)
        count = ids.size
        if count == 0:
            return
        if not hasattr(env, "_vials_layout_sampling_failed"):
            env._vials_layout_sampling_failed = torch.zeros(
                env.num_envs, dtype=torch.bool, device=env.device
            )
        env._vials_layout_sampling_failed[env_ids] = False
        if rack_centers is None:
            rack_pose = _random_asset_pose(env, ids, rack_obj, rack_pose_range)
        zero_velocity = wp.zeros(count, dtype=wp.spatial_vector, device=env.device)
        rack_obj.write_root_velocity_to_sim_index(
            root_velocity=zero_velocity, env_ids=ids
        )

        placed_vial = -1
        if total_slots > 0 and np.random.uniform() < rack_placement_prob:
            placed_vial = int(np.random.randint(len(vial_objects)))
        mat_indices = [i for i in range(len(vial_objects)) if i != placed_vial]

        # The rejection sampler uses host-side environment-local coordinates;
        # the pose kernel adds the environment origin exactly once.
        origins = wp.from_torch(env.scene.env_origins, dtype=wp.vec3)
        selected_ids = ids.numpy()
        selected_origins = origins.numpy()[selected_ids]
        robot_local_xy = (
            env.scene["robot"].data.root_pos_w.warp.numpy()[selected_ids, :2]
            - selected_origins[:, :2]
        )
        if rack_centers is not None:
            from sim_to_real_so101.utils.vials_state_machine.scene import (
                layout_has_grasp_access,
            )

            rack_snapshot = rack_obj.data.default_root_pose.warp.numpy()[
                selected_ids
            ].copy()
            rack_snapshot[:, :3] += selected_origins
            robot_defaults = env.scene["robot"].data.default_root_pose.warp.numpy()[
                selected_ids
            ]
            vial_defaults = [
                vial.data.default_root_pose.warp.numpy()[selected_ids]
                for vial in vial_objects
            ]
            slots = [
                wp.transform(wp.vec3(*pos), wp.quat(*quat))
                for pos, quat in zip(slot_pos_list, slot_quat_list, strict=True)
            ]
            placed_slot_index = (
                int(np.random.randint(total_slots)) if placed_vial >= 0 else -1
            )
            layouts = []
            for row in range(count):
                def is_accessible(rack_sample, layout, row=row):
                    x, y, yaw = rack_sample
                    rack_frame = wp.transform(
                        wp.vec3(
                            x, y, float(rack_snapshot[row, 2] - selected_origins[row, 2])
                        ),
                        wp.quat_rpy(0.0, 0.0, yaw),
                    )
                    frames = []
                    for index in range(len(vial_objects)):
                        if index == placed_vial:
                            pose = wp.transform_multiply(
                                rack_frame, slots[placed_slot_index]
                            )
                        else:
                            vx, vy, heading, spin = layout[mat_indices.index(index)]
                            orientation = (
                                wp.quat_rpy(0.0, 0.0, heading)
                                * wp.quat(*vial_defaults[index][row, 3:])
                                * wp.quat_rpy(0.0, 0.0, spin)
                            )
                            pose = wp.transform(wp.vec3(vx, vy, fixed_vial_z), orientation)
                        grasp = wp.transform_multiply(
                            pose,
                            wp.transform(
                                wp.vec3(0.0, 0.0, _VIAL_GRASP_OFFSET_M), wp.quat_identity()
                            ),
                        )
                        frames.append(tuple(grasp))
                    frames.extend(
                        tuple(wp.transform_multiply(rack_frame, slot)) for slot in slots
                    )
                    root = robot_defaults[row]
                    return layout_has_grasp_access(
                        frames, wp.transform(wp.vec3(*root[:3]), wp.quat(*root[3:]))
                    )

                sample = _sample_coordinated_vials_rack(
                    len(mat_indices),
                    rack_centers=rack_centers,
                    rack_min_center_distance=rack_min_center_distance,
                    rack_pose_range=rack_pose_range,
                    vial_pose_range=vial_pose_range,
                    mat_bounds=mat_bounds,
                    robot_xy=robot_local_xy[row],
                    reach_range=vial_reach_range,
                    clearance=clearance,
                    max_sample_tries=max_sample_tries,
                    is_accessible=is_accessible,
                )
                if sample is None:
                    layouts.append(None)
                    continue
                rack_sample, layout = sample
                x, y, yaw = rack_sample
                rack_snapshot[row, :2] = (x, y) + selected_origins[row, :2]
                rack_snapshot[row, 3:] = tuple(wp.quat_rpy(0.0, 0.0, yaw))
                layouts.append(layout)
            rack_pose = wp.array(rack_snapshot, dtype=wp.transform, device=env.device)
            rack_obj.write_root_pose_to_sim_index(root_pose=rack_pose, env_ids=ids)
        else:
            rack_snapshot = rack_pose.numpy()
            rack_local_xy = rack_snapshot[:, :2] - selected_origins[:, :2]
            layouts = [
                _sample_mat_vial_poses(
                    len(mat_indices),
                    pose_range=vial_pose_range,
                    mat_bounds=mat_bounds,
                    rack_box=_rack_xy_aabb(
                        rack_local_xy[row, 0],
                        rack_local_xy[row, 1],
                        wp.quat_to_rpy(wp.quat(*rack_snapshot[row, 3:]))[2],
                    ),
                    robot_xy=robot_local_xy[row],
                    reach_range=vial_reach_range,
                    clearance=clearance,
                    max_sample_tries=max_sample_tries,
                )
                for row in range(count)
            ]
        exhausted = [row for row, layout in enumerate(layouts) if layout is None]
        if exhausted:
            if rack_centers is not None:
                env._vials_layout_sampling_failed[env_ids[exhausted]] = True
                logger.warning(
                    "Vial layout search exhausted for env ids %s; rejecting these "
                    "episodes and restoring authored object poses until automatic reset.",
                    selected_ids[exhausted].tolist(),
                )
            else:
                logger.warning(
                    "Vial layout search exhausted for env ids %s; keeping the authored "
                    "spawn grid there.",
                    selected_ids[exhausted].tolist(),
                )
        resolved = wp.array(
            [layout is not None for layout in layouts],
            dtype=wp.bool,
            device=env.device,
        )

        for index, vial in enumerate(vial_objects):
            pose = wp.empty(count, dtype=wp.transform, device=env.device)
            if index == placed_vial:
                slot_index = (
                    int(np.random.randint(total_slots))
                    if rack_centers is None
                    else placed_slot_index
                )
                slot = wp.transform(
                    wp.vec3(*slot_pos_list[slot_index]),
                    wp.quat(*slot_quat_list[slot_index]),
                )
                wp.launch(
                    place_in_slot, count, [rack_pose, slot, pose], device=env.device
                )
                if rack_centers is not None and exhausted:
                    # Failed episodes use the complete authored grid, including this vial.
                    snapshot = pose.numpy()
                    snapshot[exhausted] = vial_defaults[index][exhausted]
                    snapshot[exhausted, :3] += selected_origins[exhausted]
                    snapshot[exhausted, 2] = selected_origins[exhausted, 2] + fixed_vial_z
                    pose = wp.array(snapshot, dtype=wp.transform, device=env.device)
            else:
                layout_index = mat_indices.index(index)
                samples = wp.array(
                    [
                        (0.0, 0.0, 0.0, 0.0) if layout is None else layout[layout_index]
                        for layout in layouts
                    ],
                    dtype=wp.vec4,
                    device=env.device,
                )
                wp.launch(
                    compose_mat_vial_pose,
                    count,
                    [
                        vial.data.default_root_pose.warp,
                        origins,
                        ids,
                        samples,
                        resolved,
                        fixed_vial_z,
                        pose,
                    ],
                    device=env.device,
                )
            vial.write_root_pose_to_sim_index(root_pose=pose, env_ids=ids)
            vial.write_root_velocity_to_sim_index(
                root_velocity=zero_velocity, env_ids=ids
            )


def _load_yaw_mapping(textures_root: str) -> dict[str, list[float] | None]:
    if textures_root in _YAW_MAPPING_CACHE:
        return _YAW_MAPPING_CACHE[textures_root]
    mapping_path = os.path.join(textures_root, "yaw_mapping.yaml")
    try:
        with open(mapping_path, "r") as f:
            mapping = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(
            "yaw_mapping.yaml not found at %s; using zero yaw range", mapping_path
        )
        mapping = {}
    _YAW_MAPPING_CACHE[textures_root] = mapping
    return mapping


def randomize_sky_light(
    env,
    env_ids: torch.Tensor | None,
    exposure_range: tuple[float, float],
    temperature_range: tuple[float, float],
    textures_root: str,
    asset_cfg: SceneEntityCfg | None = None,
):
    """Randomize dome HDRI, exposure, colour temperature, and mapped yaw."""
    if asset_cfg is None:
        return
    if env_ids is not None and len(env_ids) != env.scene.num_envs:
        return

    asset = env.scene[asset_cfg.name]
    prim_path_pattern = asset.cfg.prim_path
    prims = _find_matching_prims_all_envs(prim_path_pattern)
    if not prims:
        return

    textures = sorted(glob.glob(os.path.join(textures_root, "*.exr")))
    if not textures:
        logger.warning("No .exr textures found in %s", textures_root)
        return

    exposure = _sample_scalar(exposure_range)
    temperature = _sample_scalar(temperature_range)
    texture_index = int(np.random.randint(len(textures)))
    texture_path = os.path.abspath(textures[texture_index])

    yaw_mapping = _load_yaw_mapping(textures_root)
    yaw_range = yaw_mapping.get(os.path.basename(texture_path))
    yaw = (
        0.0
        if yaw_range is None
        else math.radians(_sample_scalar((float(yaw_range[0]), float(yaw_range[1]))))
    )
    quat_xyzw_tuple = tuple(wp.quat_rpy(0.0, 0.0, yaw))

    with Sdf.ChangeBlock():
        for prim in prims:
            if not prim.IsValid():
                continue
            texture_attr = prim.GetAttribute("inputs:texture:file")
            if texture_attr.IsValid():
                texture_attr.Set(Sdf.AssetPath(texture_path))
            exp_attr = prim.GetAttribute("inputs:exposure")
            if exp_attr.IsValid():
                exp_attr.Set(exposure)
            temp_attr = prim.GetAttribute("inputs:colorTemperature")
            if temp_attr.IsValid():
                temp_attr.Set(temperature)
            orient_attr = prim.GetAttribute("xformOp:orient")
            if orient_attr.IsValid():
                orient_attr.Set(_quat_xyzw_to_gf_quatd(quat_xyzw_tuple))

    _write_ovrtx_asset_path(
        env=env,
        prim_path_pattern=prim_path_pattern,
        attribute_name="inputs:texture:file",
        asset_path=texture_path,
    )
    _write_ovrtx_attribute(
        env=env,
        prim_path_pattern=prim_path_pattern,
        attribute_name="inputs:exposure",
        tensor=np.array([exposure], dtype=np.float32),
    )
    _write_ovrtx_attribute(
        env=env,
        prim_path_pattern=prim_path_pattern,
        attribute_name="inputs:colorTemperature",
        tensor=np.array([temperature], dtype=np.float32),
    )
    _write_ovrtx_xform(
        env=env,
        prim_path_pattern=prim_path_pattern,
        position_xyz=(0.0, 0.0, 0.0),
        quat_xyzw=quat_xyzw_tuple,
    )
