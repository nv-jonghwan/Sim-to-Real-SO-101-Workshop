# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Warp scene sampling and SO-101 grasp geometry."""

import warp as wp
from isaaclab.sim import FrameView
from sim_to_real_so101.assets.vial import (
    VIAL_AXIAL_MAX_M,
    VIAL_AXIAL_MIN_M,
    VIAL_GRASP_OFFSET_M,
    VIAL_RADIUS_M,
)
from sim_to_real_so101.tasks.vials_state_machine_assets import (
    FIXED_JAW_CONTACT_FRAME,
    MOVING_JAW_CONTACT_FRAME,
    VIAL_GRASP_FRAME,
)
from sim_to_real_so101.utils.warp_bridge import manager_stream
from sim_to_real_so101.utils.warp_math import force_on_filter, frame_in_root

from . import parameters as C
from .data import ControllerState, SceneSample

VIAL_COUNT = 3
RACK_SLOT_COUNT = 4
# Sampled vial poses belong to sm_grasp, above the asset root along local +Z.
VIAL_TIP_LOCAL_Z_M = VIAL_AXIAL_MIN_M - VIAL_GRASP_OFFSET_M


@wp.kernel
def gather_frame(
    position: wp.array(dtype=wp.vec3),
    orientation: wp.array(dtype=wp.vec4),
    root_position: wp.array(dtype=wp.vec3),
    root_orientation: wp.array(dtype=wp.quat),
    index: int,
    world: wp.array2d(dtype=wp.transform),
    base: wp.array2d(dtype=wp.transform),
):
    i = wp.tid()
    q = orientation[i]
    pose = wp.transform(position[i], wp.quat(q[0], q[1], q[2], q[3]))
    world[i, index] = pose
    base[i, index] = wp.transform_multiply(
        wp.transform_inverse(wp.transform(root_position[i], root_orientation[i])), pose
    )


@wp.kernel
def capture_scene(
    state: wp.array(dtype=ControllerState),
    world: wp.array2d(dtype=wp.transform),
    base: wp.array2d(dtype=wp.transform),
    root_orientation: wp.array(dtype=wp.quat),
    joint_pos: wp.array2d(dtype=float),
    joint_vel: wp.array2d(dtype=float),
    jacobian: wp.array4d(dtype=float),
    forces: wp.array3d(dtype=wp.vec3),
    fixed_jaw_forces: wp.array3d(dtype=wp.vec3),
    surface_forces: wp.array3d(dtype=wp.vec3),
    body: int,
    flex_joint: int,
    roll_joint: int,
    gripper_joint: int,
    result: wp.array(dtype=SceneSample),
):
    i = wp.tid()
    vial = state[i].selected_vial
    scene = SceneSample()
    scene.up_axis_b = wp.quat_rotate(
        wp.quat_inverse(root_orientation[i]), wp.vec3(0.0, 0.0, 1.0)
    )
    scene.selected_vial_pose_b = base[i, vial]
    scene.selected_vial_position_w = wp.transform_get_translation(world[i, vial])
    scene.selected_vial_axis_b = wp.quat_rotate(
        wp.transform_get_rotation(base[i, vial]), wp.vec3(0.0, 0.0, 1.0)
    )
    scene.selected_vial_axis_z_w = wp.quat_rotate(
        wp.transform_get_rotation(world[i, vial]), wp.vec3(0.0, 0.0, 1.0)
    )[2]
    scene.selected_vial_tip_b = (
        wp.transform_get_translation(base[i, vial])
        + VIAL_TIP_LOCAL_Z_M * scene.selected_vial_axis_b
    )
    # The controller varies grasp position along the body without moving any asset frame.
    scene.selected_vial_pose_b = wp.transform(
        wp.transform_get_translation(scene.selected_vial_pose_b)
        + state[i].grasp_axial_offset * scene.selected_vial_axis_b,
        wp.transform_get_rotation(scene.selected_vial_pose_b),
    )
    scene.grasp_center_b = 0.5 * (
        wp.transform_get_translation(base[i, 7])
        + wp.transform_get_translation(base[i, 8])
    )
    scene.fixed_jaw_center_b = wp.transform_get_translation(base[i, 7])
    scene.wrist_flex = joint_pos[i, flex_joint]
    scene.wrist_roll = joint_pos[i, roll_joint]
    scene.gripper = joint_pos[i, gripper_joint]
    scene.gripper_velocity = joint_vel[i, gripper_joint]
    scene.contact_force = force_on_filter(forces, i, vial)
    scene.jaw_contact_force = scene.contact_force + force_on_filter(
        fixed_jaw_forces, i, vial
    )
    scene.surface_contact_force = force_on_filter(
        surface_forces, i, 0
    ) + force_on_filter(surface_forces, i, 1)
    inverse = wp.quat_inverse(root_orientation[i])
    scene.wrist_flex_axis_b = wp.quat_rotate(
        inverse,
        wp.vec3(
            jacobian[i, body, 3, flex_joint],
            jacobian[i, body, 4, flex_joint],
            jacobian[i, body, 5, flex_joint],
        ),
    )
    scene.wrist_roll_axis_b = wp.quat_rotate(
        inverse,
        wp.vec3(
            jacobian[i, body, 3, roll_joint],
            jacobian[i, body, 4, roll_joint],
            jacobian[i, body, 5, roll_joint],
        ),
    )
    result[i] = scene


@wp.func
def rack_slot_clearance(
    base: wp.array2d(dtype=wp.transform),
    i: int,
    slot: int,
    held_vial: int,
    occupancy_radius: float,
):
    """Signed clearance of the insertion footprint from other live vial poses.

    The footprint covers the gripper and wrist toward the robot base. Vial
    projections include tilt and cap radius; vials below the descent are excluded.
    All distances use robot-base coordinates so rack yaw and env cloning apply.
    """
    target = wp.transform_get_translation(base[i, 3 + slot])
    xy = wp.vec2(target[0], target[1])
    direction = -wp.normalize(xy)
    lowest_gripper_z = (
        target[2]
        - C.RACK_INSERTION_TARGET_DEPTH_M
        - VIAL_TIP_LOCAL_Z_M
        - C.RACK_GRIPPER_BELOW_GRASP_M
        + C.GRASP_AXIAL_OFFSET_MIN_M
    )
    clearance = float(wp.inf)
    half_length = 0.5 * (VIAL_AXIAL_MAX_M - VIAL_AXIAL_MIN_M)
    midpoint = 0.5 * (VIAL_AXIAL_MAX_M + VIAL_AXIAL_MIN_M) - VIAL_GRASP_OFFSET_M
    for vial in range(VIAL_COUNT):
        if vial != held_vial:
            pose = base[i, vial]
            position = wp.transform_get_translation(pose)
            axis = wp.quat_rotate(
                wp.transform_get_rotation(pose), wp.vec3(0.0, 0.0, 1.0)
            )
            center = position + midpoint * axis
            top = center[2] + half_length * wp.abs(axis[2]) + VIAL_RADIUS_M
            if top >= lowest_gripper_z:
                delta = wp.vec2(center[0], center[1]) - xy
                along = wp.clamp(
                    wp.dot(delta, direction), 0.0, C.RACK_GRIPPER_REACHBACK_M
                )
                projected_radius = VIAL_RADIUS_M + half_length * wp.length(
                    wp.vec2(axis[0], axis[1])
                )
                separation = wp.length(delta - along * direction) - (
                    C.RACK_GRIPPER_HALF_WIDTH_M
                    + projected_radius
                    + C.RACK_OBSTACLE_MARGIN_M
                )
                clearance = wp.min(clearance, separation)
                occupied_distance = wp.length(wp.vec2(position[0], position[1]) - xy)
                clearance = wp.min(clearance, occupied_distance - occupancy_radius)
    return clearance


@wp.func
def select_rack_slot(
    base: wp.array2d(dtype=wp.transform),
    i: int,
    vial: int,
    radius: float,
):
    selected = wp.int32(0)
    best_clearance = float(-wp.inf)
    best_distance = float(wp.inf)
    for slot in range(RACK_SLOT_COUNT):
        clearance = rack_slot_clearance(base, i, slot, vial, radius)
        distance = wp.length(
            wp.transform_get_translation(base[i, 3 + slot])
            - wp.transform_get_translation(base[i, vial])
        )
        target = wp.transform_get_translation(base[i, 3 + slot])
        reachable = wp.length(wp.vec2(target[0], target[1])) <= C.MAX_VIAL_REACH_M
        if (
            reachable
            and clearance > 0.0
            and (
                clearance > best_clearance
                or (clearance == best_clearance and distance < best_distance)
            )
        ):
            selected = slot
            best_clearance = clearance
            best_distance = distance
    return (
        selected,
        wp.transform_get_translation(base[i, 3 + selected]),
        best_clearance > -wp.inf,
    )


@wp.func
def point_segment_distance(point: wp.vec2, start: wp.vec2, end: wp.vec2):
    segment = end - start
    fraction = wp.clamp(
        wp.dot(point - start, segment) / wp.max(wp.dot(segment, segment), 1.0e-12),
        0.0,
        1.0,
    )
    return wp.length(point - start - fraction * segment)


@wp.func
def segment_distance(a: wp.vec2, b: wp.vec2, c: wp.vec2, d: wp.vec2):
    first = b - a
    second = d - c
    delta = c - a
    determinant = first[0] * second[1] - first[1] * second[0]
    if wp.abs(determinant) > 1.0e-10:
        t = (delta[0] * second[1] - delta[1] * second[0]) / determinant
        u = (delta[0] * first[1] - delta[1] * first[0]) / determinant
        if t >= 0.0 and t <= 1.0 and u >= 0.0 and u <= 1.0:
            return 0.0
    return wp.min(
        wp.min(point_segment_distance(a, c, d), point_segment_distance(b, c, d)),
        wp.min(point_segment_distance(c, a, b), point_segment_distance(d, a, b)),
    )


@wp.func
def segment_rectangle_distance(start: wp.vec2, end: wp.vec2, extent: wp.vec2):
    """Return the distance from a segment to a centred rectangle in its own axes."""
    if (wp.abs(start[0]) <= extent[0] and wp.abs(start[1]) <= extent[1]) or (
        wp.abs(end[0]) <= extent[0] and wp.abs(end[1]) <= extent[1]
    ):
        return 0.0
    a = wp.vec2(-extent[0], -extent[1])
    b = wp.vec2(extent[0], -extent[1])
    c = wp.vec2(extent[0], extent[1])
    d = wp.vec2(-extent[0], extent[1])
    return wp.min(
        wp.min(segment_distance(start, end, a, b), segment_distance(start, end, b, c)),
        wp.min(segment_distance(start, end, c, d), segment_distance(start, end, d, a)),
    )


@wp.func
def rack_approach_clearance(
    world: wp.array2d(dtype=wp.transform),
    i: int,
    point: wp.vec3,
    along: wp.vec2,
    across: wp.vec2,
    extent: wp.vec2,
):
    """Separate the open-finger footprint from the live rack's outer rectangle."""
    first = wp.transform_get_translation(world[i, 3])
    second = wp.transform_get_translation(world[i, 4])
    fourth = wp.transform_get_translation(world[i, 6])
    center = wp.vec3(0.0, 0.0, 0.0)
    for slot in range(4):
        center += 0.25 * wp.transform_get_translation(world[i, 3 + slot])
    x_edge = wp.vec2(second[0] - first[0], second[1] - first[1])
    y_edge = wp.vec2(fourth[0] - first[0], fourth[1] - first[1])
    x_axis = wp.normalize(x_edge)
    y_axis = wp.normalize(y_edge)
    # The authored holes are 30 mm inside each edge of the 120 mm rack footprint.
    half_x = 0.5 * wp.length(x_edge) + 0.030
    half_y = 0.5 * wp.length(y_edge) + 0.030
    delta = wp.vec2(point[0] - center[0], point[1] - center[1])
    separation = float(-wp.inf)
    for k in range(4):
        normal = along
        if k == 1:
            normal = across
        elif k == 2:
            normal = x_axis
        elif k == 3:
            normal = y_axis
        jaw_radius = extent[0] * wp.abs(wp.dot(along, normal)) + extent[1] * wp.abs(
            wp.dot(across, normal)
        )
        rack_radius = half_x * wp.abs(wp.dot(x_axis, normal)) + half_y * wp.abs(
            wp.dot(y_axis, normal)
        )
        separation = wp.max(
            separation, wp.abs(wp.dot(delta, normal)) - jaw_radius - rack_radius
        )
    return separation


@wp.func
def grasp_access_clearance(
    world: wp.array2d(dtype=wp.transform),
    i: int,
    selected: int,
    grasp_offset: float,
    approach_half_width: float,
):
    """Measure open-finger access against the rack and all other vial footprints.

    The approach envelope covers a 40 mm axial band at the desired grasp point.
    Its supplied half-width includes the open-jaw spread and finger margin.
    """
    pose = world[i, selected]
    axis = wp.quat_rotate(wp.transform_get_rotation(pose), wp.vec3(0.0, 0.0, 1.0))
    point = wp.transform_get_translation(pose) + grasp_offset * axis
    along = wp.normalize(wp.vec2(axis[0], axis[1]))
    across = wp.vec2(-along[1], along[0])
    extent = wp.vec2(0.020, approach_half_width)
    # The rack reaches the wider fixed-claw body above the fingertip band.
    # Its envelope extends 20 mm farther on the fixed side and 30 mm toward the palm.
    rack_point = point + wp.vec3(
        -0.015 * along[0] + 0.010 * across[0],
        -0.015 * along[1] + 0.010 * across[1],
        0.0,
    )
    rack_extent = wp.vec2(extent[0] + 0.015, extent[1] + 0.010)
    clearance = rack_approach_clearance(world, i, rack_point, along, across, rack_extent)
    for other in range(VIAL_COUNT):
        if other != selected:
            other_pose = world[i, other]
            other_axis = wp.quat_rotate(
                wp.transform_get_rotation(other_pose), wp.vec3(0.0, 0.0, 1.0)
            )
            center = wp.transform_get_translation(other_pose)
            tip_delta = center + VIAL_TIP_LOCAL_Z_M * other_axis - point
            cap_delta = (
                center + (VIAL_AXIAL_MAX_M - VIAL_GRASP_OFFSET_M) * other_axis - point
            )
            tip_xy = wp.vec2(tip_delta[0], tip_delta[1])
            cap_xy = wp.vec2(cap_delta[0], cap_delta[1])
            start = wp.vec2(wp.dot(tip_xy, along), wp.dot(tip_xy, across))
            end = wp.vec2(wp.dot(cap_xy, along), wp.dot(cap_xy, across))
            clearance = wp.min(
                clearance,
                segment_rectangle_distance(start, end, extent) - VIAL_RADIUS_M,
            )
    return clearance


@wp.func
def select_vial(
    world: wp.array2d(dtype=wp.transform),
    base: wp.array2d(dtype=wp.transform),
    i: int,
    start_position: wp.vec3,
    grasp_offset: float,
    approach_half_width: float,
):
    """Select an accessible mat grasp with a short path from the current robot pose."""
    selected = wp.int32(0)
    best_cost = float(wp.inf)
    for vial in range(VIAL_COUNT):
        on_mat = (
            wp.abs(
                wp.quat_rotate(
                    wp.transform_get_rotation(world[i, vial]), wp.vec3(0.0, 0.0, 1.0)
                )[2]
            )
            < 0.7
        )
        position = wp.transform_get_translation(base[i, vial])
        radius = wp.length(wp.vec2(position[0], position[1]))
        if on_mat and radius <= C.MAX_VIAL_REACH_M:
            access = grasp_access_clearance(
                world, i, vial, grasp_offset, approach_half_width
            )
            _slot, _position, available = select_rack_slot(
                base, i, vial, C.RACK_SLOT_OCCUPANCY_RADIUS_M
            )
            if available and access > 0.002:
                axis = wp.quat_rotate(
                    wp.transform_get_rotation(base[i, vial]), wp.vec3(0.0, 0.0, 1.0)
                )
                point = position + grasp_offset * axis
                cost = wp.length(point - start_position) + 0.4 * wp.length(
                    _position - point
                )
                if cost < best_cost:
                    selected = vial
                    best_cost = cost
    return selected, best_cost < wp.inf


@wp.kernel
def _check_spawn_access(
    world: wp.array2d(dtype=wp.transform),
    base: wp.array2d(dtype=wp.transform),
    robot_pose: wp.transform,
    result: wp.array(dtype=wp.bool),
):
    for frame in range(VIAL_COUNT + RACK_SLOT_COUNT):
        base[0, frame] = wp.transform_multiply(
            wp.transform_inverse(robot_pose), world[0, frame]
        )
    available = bool(False)  # noqa: UP018 - Warp loop-carried variable.
    for vial in range(VIAL_COUNT):
        axis = wp.quat_rotate(
            wp.transform_get_rotation(world[0, vial]), wp.vec3(0.0, 0.0, 1.0)
        )
        position = wp.transform_get_translation(base[0, vial])
        # Leave room for the sampled grasp offset and reset-time base tilt.
        if (
            wp.abs(axis[2]) < 0.7
            and wp.length(wp.vec2(position[0], position[1])) <= C.MAX_VIAL_REACH_M - 0.02
        ):
            accessible = bool(True)  # noqa: UP018 - Warp loop-carried variable.
            for sample in range(3):
                fraction = C.GRASP_FRACTION_MIN + 0.5 * float(sample) * (
                    C.GRASP_FRACTION_MAX - C.GRASP_FRACTION_MIN
                )
                offset = (
                    VIAL_AXIAL_MIN_M
                    + fraction * (VIAL_AXIAL_MAX_M - VIAL_AXIAL_MIN_M)
                    - VIAL_GRASP_OFFSET_M
                    + C.GRASP_AXIAL_LEAD_M
                )
                accessible = accessible and (
                    grasp_access_clearance(
                        world, 0, vial, offset, C.GRASP_APPROACH_HALF_WIDTH_MAX_M
                    ) > 0.002
                )
            slot_available = bool(False)  # noqa: UP018 - Warp loop-carried variable.
            for slot in range(RACK_SLOT_COUNT):
                target = wp.transform_get_translation(base[0, VIAL_COUNT + slot])
                if wp.length(wp.vec2(target[0], target[1])) <= C.MAX_VIAL_REACH_M - 0.02:
                    slot_available = slot_available or (
                        rack_slot_clearance(
                            base, 0, slot, vial, C.RACK_SLOT_OCCUPANCY_RADIUS_M
                        ) > 0.0
                    )
            available = available or (accessible and slot_available)
    result[0] = available


def layout_has_grasp_access(world_poses, robot_pose) -> bool:
    """Check proposed vial/slot frames with the controller's clearance geometry.

    Require one horizontal vial with space for the widest approach opening at
    the low, middle, and high grasp offsets, plus a clear reachable slot. Both endpoints
    retain 2 cm of horizontal reach margin. This is a geometric screen, not an
    IK or dynamics guarantee. Frames are environment-local, ordered as three
    vial grasp frames followed by the four rack slots.
    """
    world = wp.array([world_poses], dtype=wp.transform, device="cpu")
    base = wp.empty_like(world)
    result = wp.empty(1, dtype=wp.bool, device="cpu")
    wp.launch(_check_spawn_access, 1, [world, base, robot_pose, result], device="cpu")
    return bool(result.numpy()[0])


class VialSceneView:
    """Gather live Newton Warp arrays into reusable per-environment scene buffers."""

    def __init__(self, *, num_envs: int, device):
        self.num_envs = num_envs
        self.device = str(device)
        self.world = wp.empty((num_envs, 9), dtype=wp.transform, device=self.device)
        self.base = wp.empty_like(self.world)
        self.samples = wp.empty(num_envs, dtype=SceneSample, device=self.device)
        self.pose = wp.empty(num_envs, dtype=wp.transform, device=self.device)
        self._views = None
        self._body = None
        self._flex = None
        self._roll = None
        self._gripper = None

    def _resolve_robot(self, env):
        if self._body is None:
            robot = env.scene["robot"]
            self._body = robot.find_bodies("gripper")[0][0]
            self._flex = robot.find_joints("wrist_flex")[0][0]
            self._roll = robot.find_joints("wrist_roll")[0][0]
            self._gripper = robot.find_joints("gripper")[0][0]

    def gripper_pose_b(self, env):
        self._resolve_robot(env)
        robot = env.scene["robot"].data
        with manager_stream(self.device):
            wp.launch(
                frame_in_root,
                self.num_envs,
                [
                    robot.root_pos_w.warp,
                    robot.root_quat_w.warp,
                    robot.body_pos_w.warp,
                    robot.body_quat_w.warp,
                    self._body,
                    self.pose,
                ],
                device=self.device,
            )
        return self.pose

    def capture(self, env, state):
        self._resolve_robot(env)
        if self._views is None:
            paths = [
                f"Vial_{index}/{VIAL_GRASP_FRAME}" for index in range(1, VIAL_COUNT + 1)
            ]
            paths += [
                f"Rack_Left/Body1/Mesh/top_{index:02d}"
                for index in range(1, RACK_SLOT_COUNT + 1)
            ]
            paths += [
                f"Robot/gripper/{FIXED_JAW_CONTACT_FRAME}",
                f"Robot/moving_jaw_so101_v1/{MOVING_JAW_CONTACT_FRAME}",
            ]
            self._views = [
                FrameView(f"/World/envs/env_.*/{path}", device=self.device)
                for path in paths
            ]
        robot = env.scene["robot"].data
        for index, view in enumerate(self._views):
            position, orientation = view.get_world_poses()
            wp.launch(
                gather_frame,
                self.num_envs,
                [
                    position.warp,
                    orientation.warp,
                    robot.root_pos_w.warp,
                    robot.root_quat_w.warp,
                    index,
                    self.world,
                    self.base,
                ],
                device=self.device,
            )
        # The fixed root body has no row in Newton's articulation Jacobian.
        wp.launch(
            capture_scene,
            self.num_envs,
            [
                state,
                self.world,
                self.base,
                robot.root_quat_w.warp,
                robot.joint_pos.warp,
                robot.joint_vel.warp,
                robot.body_link_jacobian_w.warp,
                env.scene["contact_grasp"].data.force_matrix_w.warp,
                env.scene["contact_grasp_fixed"].data.force_matrix_w.warp,
                env.scene["contact_grasp_surface"].data.force_matrix_w.warp,
                self._body - 1,
                self._flex,
                self._roll,
                self._gripper,
                self.samples,
            ],
            device=self.device,
        )
        return self.samples
