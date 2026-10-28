# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Coupled five-joint tracking of a grasp point and gripper-axis direction."""

import logging

import torch
from isaaclab.managers.action_manager import ActionTerm, ActionTermCfg
from isaaclab.utils import math as math_utils
from isaaclab.utils.configclass import configclass
from sim_to_real_so101.tasks.vials_state_machine_assets import ROBOT_TASK_FRAMES

logger = logging.getLogger(__name__)


class VialArmAction(ActionTerm):
    """Track base-frame grasp position and local-Y direction with five arm joints.

    Actions contain ``[grasp_xyz, gripper_y_direction_xyz, gripper_radians]``.
    Position and the two observable direction errors share one damped IK solve.
    Rotation about the requested direction follows the continuous joint solution.
    Joint bounds constrain the IK step before physics-rate integration and braking.
    Invalid environments hold finite targets and time out independently of the batch.
    """

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self._dt = env.physics_dt
        self._arm_ids, _ = self._asset.find_joints(cfg.joint_names, preserve_order=True)
        self._gripper_id = self._asset.find_joints("gripper")[0][0]
        self._joint_ids = self._arm_ids + [self._gripper_id]
        self._body_id = self._asset.find_bodies("gripper")[0][0]
        self._jacobian_body = (
            self._body_id - 1 if self._asset.is_fixed_base else self._body_id
        )
        self._jacobian_joints = [j + self._asset.num_base_dofs for j in self._arm_ids]
        self._jaw_body_ids = [
            self._asset.find_bodies(frame.parent_path)[0][0]
            for frame in ROBOT_TASK_FRAMES
        ]
        self._jaw_offsets = torch.tensor(
            [frame.position for frame in ROBOT_TASK_FRAMES], device=self.device
        )
        self._raw_actions = torch.zeros((self.num_envs, 7), device=self.device)
        self._target = torch.zeros((self.num_envs, 6), device=self.device)
        self._velocity = torch.zeros_like(self._target)
        self._initialized = torch.zeros(
            self.num_envs, dtype=torch.bool, device=self.device
        )
        self._failed = torch.zeros_like(self._initialized)
        self._speed_limit = torch.tensor(
            (*cfg.joint_velocity_limits, cfg.gripper_velocity_limit), device=self.device
        )
        self._acceleration_limit = torch.tensor(
            (*cfg.joint_acceleration_limits, cfg.gripper_acceleration_limit),
            device=self.device,
        )
        self._identity = torch.eye(5, device=self.device)

    @property
    def action_dim(self) -> int:
        return 7

    @property
    def raw_actions(self) -> torch.Tensor:
        return self._raw_actions

    @property
    def processed_actions(self) -> torch.Tensor:
        return self._raw_actions

    def process_actions(self, actions: torch.Tensor):
        self._raw_actions[:] = actions

    def _compute_grasp_kinematics(self):
        """Return the actual jaw midpoint, body-Y axis, and its base-frame Jacobian."""
        data = self._asset.data
        root_rotation = math_utils.matrix_from_quat(
            math_utils.quat_inv(data.root_quat_w.torch)
        )
        jaw_rotation = math_utils.matrix_from_quat(
            data.body_quat_w.torch[:, self._jaw_body_ids]
        )
        jaw_points = data.body_pos_w.torch[:, self._jaw_body_ids] + torch.matmul(
            jaw_rotation, self._jaw_offsets[None, :, :, None]
        ).squeeze(-1)
        center_world = jaw_points.mean(dim=1)
        center = torch.bmm(
            root_rotation, (center_world - data.root_pos_w.torch).unsqueeze(-1)
        ).squeeze(-1)
        body_rotation = math_utils.matrix_from_quat(
            data.body_quat_w.torch[:, self._body_id]
        )
        direction = torch.bmm(root_rotation, body_rotation[:, :, 1:2]).squeeze(-1)
        jacobian_world = data.body_link_jacobian_w.torch[
            :, self._jacobian_body, :, self._jacobian_joints
        ]
        angular = torch.bmm(root_rotation, jacobian_world[:, 3:, :])
        linear = torch.bmm(root_rotation, jacobian_world[:, :3, :])
        offset = torch.bmm(
            root_rotation,
            (center_world - data.body_pos_w.torch[:, self._body_id]).unsqueeze(-1),
        ).squeeze(-1)
        # Both jaw points share the first five joints; the jaw angle is held in this solve.
        linear -= torch.bmm(math_utils.skew_symmetric_matrix(offset), angular)
        return center, direction, torch.cat((linear, angular), dim=1)

    def apply_actions(self):
        center, direction, jacobian = self._compute_grasp_kinematics()
        data = self._asset.data
        positions = data.joint_pos.torch[:, self._joint_ids]
        quaternions = torch.cat(
            (
                data.root_quat_w.torch[:, None],
                data.body_quat_w.torch[:, self._jaw_body_ids],
            ),
            dim=1,
        )
        finite_state = (
            torch.isfinite(positions).all(dim=-1)
            & torch.isfinite(data.joint_vel.torch).all(dim=-1)
            & torch.isfinite(quaternions).all(dim=(-2, -1))
            & (quaternions.norm(dim=-1) > 1.0e-6).all(dim=-1)
            & torch.isfinite(center).all(dim=-1)
            & torch.isfinite(direction).all(dim=-1)
            & (direction.norm(dim=-1) > 1.0e-6)
        )
        finite_jacobian = torch.isfinite(jacobian).all(dim=(-2, -1))
        finite_command = torch.isfinite(self._raw_actions).all(dim=-1) & (
            self._raw_actions[:, 3:6].norm(dim=-1) > 1.0e-6
        )
        valid = finite_state & finite_jacobian & finite_command & ~self._failed
        defaults = data.default_joint_pos.torch[:, self._joint_ids]
        measured = torch.where(torch.isfinite(positions), positions, defaults)
        self._target[:] = torch.where(
            self._initialized[:, None], self._target, measured
        )
        self._initialized[:] = True
        fallback_axis = torch.zeros_like(direction)
        fallback_axis[:, 1] = 1.0
        direction = torch.where(valid[:, None], direction, fallback_axis)
        direction /= direction.norm(dim=-1, keepdim=True).clamp_min(1.0e-8)
        desired_axis = torch.where(
            valid[:, None], self._raw_actions[:, 3:6], fallback_axis
        )
        desired_axis /= desired_axis.norm(dim=-1, keepdim=True).clamp_min(1.0e-8)
        jacobian = torch.where(valid[:, None, None], jacobian, 0.0)

        # Two tangent rows constrain pointing without inventing a sixth arm degree of freedom.
        reference = torch.nn.functional.one_hot(direction.abs().argmin(dim=-1), 3).to(
            direction.dtype
        )
        tangent = torch.cross(direction, reference, dim=-1)
        tangent /= tangent.norm(dim=-1, keepdim=True).clamp_min(1.0e-8)
        basis = torch.stack((tangent, torch.cross(direction, tangent, dim=-1)), dim=1)
        cross = torch.cross(direction, desired_axis, dim=-1)
        sine = cross.norm(dim=-1)
        cosine = (direction * desired_axis).sum(dim=-1).clamp(-1.0, 1.0)
        angle = torch.atan2(sine, cosine)
        rotation_error = cross * (angle / sine.clamp_min(1.0e-8))[:, None]
        rotation_error = torch.where(
            ((cosine < 0.0) & (sine < 1.0e-6))[:, None],
            tangent * angle[:, None],
            rotation_error,
        )
        length = self.cfg.direction_length
        task_jacobian = torch.cat(
            (jacobian[:, :3, :], length * torch.bmm(basis, jacobian[:, 3:, :])), dim=1
        )
        position_error = torch.where(
            valid[:, None], self._raw_actions[:, :3] - center, 0.0
        )
        task_error = torch.cat(
            (
                position_error,
                length * torch.bmm(basis, rotation_error.unsqueeze(-1)).squeeze(-1),
            ),
            dim=1,
        )
        transpose = task_jacobian.transpose(1, 2)
        system = (
            torch.bmm(task_jacobian, transpose) + self.cfg.damping**2 * self._identity
        )
        solution, info = torch.linalg.solve_ex(
            system, task_error.unsqueeze(-1), check_errors=False
        )
        delta = torch.bmm(transpose, solution).squeeze(-1)
        physical_limits = data.soft_joint_pos_limits.torch[:, self._joint_ids]
        limits = physical_limits.clone()
        # Bounded target lead retains servo preload without accumulating through blocked contact.
        limits[:, :5, 0] = torch.maximum(
            limits[:, :5, 0], measured[:, :5] - self.cfg.max_target_lead
        )
        limits[:, :5, 1] = torch.minimum(
            limits[:, :5, 1], measured[:, :5] + self.cfg.max_target_lead
        )
        lower = limits[:, :5, 0] - self._target[:, :5]
        upper = limits[:, :5, 1] - self._target[:, :5]
        free = torch.ones_like(delta, dtype=torch.bool)
        fixed = torch.zeros_like(delta)
        # Redistribute the task error when a joint cannot take its requested step.
        for _ in range(5):
            bounded = delta.clamp(min=lower, max=upper)
            violation = (delta - bounded).abs()
            blocked = violation.amax(dim=-1) > 1.0e-6
            if not blocked.any():
                break
            selected = torch.nn.functional.one_hot(violation.argmax(dim=-1), 5).bool()
            selected &= blocked[:, None]
            fixed = torch.where(selected, bounded, fixed)
            free &= ~selected
            reduced = task_jacobian * free[:, None, :]
            residual = task_error - torch.bmm(
                task_jacobian, fixed.unsqueeze(-1)
            ).squeeze(-1)
            system = (
                torch.bmm(reduced, reduced.transpose(1, 2))
                + self.cfg.damping**2 * self._identity
            )
            solution, bounded_info = torch.linalg.solve_ex(
                system, residual.unsqueeze(-1), check_errors=False
            )
            info = torch.where(bounded_info != 0, bounded_info, info)
            delta = fixed + torch.bmm(reduced.transpose(1, 2), solution).squeeze(-1)
        goal = torch.cat(
            (self._target[:, :5] + delta, self._raw_actions[:, 6:7]), dim=1
        )
        failed = ~valid | (info != 0) | ~torch.isfinite(goal).all(dim=-1)
        new_failures = failed & ~self._failed
        if new_failures.any():
            ids = new_failures.nonzero(as_tuple=True)[0]
            logger.warning(
                "Vial pose IK rejected environments %s: finite_state=%s, finite_jacobian=%s, "
                "finite_command=%s, solve_info=%s; requesting isolated timeout resets.",
                ids.tolist(),
                finite_state[ids].tolist(),
                finite_jacobian[ids].tolist(),
                finite_command[ids].tolist(),
                info[ids].tolist(),
            )
        self._failed |= failed
        self._env.episode_length_buf[self._failed] = self._env.max_episode_length
        goal = torch.where(self._failed[:, None], self._target, goal)
        self._velocity[self._failed] = 0.0
        acceleration_step = self._acceleration_limit * self._dt
        distance = torch.stack(
            (self._target - limits[:, :, 0], limits[:, :, 1] - self._target), dim=-1
        ).clamp_min(0.0)
        braking_speed = (
            acceleration_step[None, :, None] ** 2
            + 2.0 * self._acceleration_limit[None, :, None] * distance
        ).sqrt() - acceleration_step[None, :, None]
        speed = torch.minimum(braking_speed, self._speed_limit[None, :, None])
        error = goal - self._target
        goal_speed = (
            acceleration_step**2 + 2.0 * self._acceleration_limit * error.abs()
        ).sqrt() - acceleration_step
        desired_velocity = (error.sign() * goal_speed).clamp(
            min=-speed[:, :, 0], max=speed[:, :, 1]
        )
        # Preserve the coupled IK direction when one arm joint reaches its rate limit.
        arm_velocity = error[:, :5] / self.cfg.target_response_time
        arm_speed = torch.where(arm_velocity >= 0.0, speed[:, :5, 1], speed[:, :5, 0])
        speed_scale = (
            torch.where(
                arm_velocity.abs() > 1.0e-8,
                arm_speed / arm_velocity.abs().clamp_min(1.0e-8),
                1.0,
            )
            .amin(dim=-1)
            .clamp(max=1.0)
        )
        desired_velocity[:, :5] = arm_velocity * speed_scale[:, None]
        velocity_change = desired_velocity - self._velocity
        acceleration_scale = (
            (acceleration_step[:5] / velocity_change[:, :5].abs().clamp_min(1.0e-8))
            .amin(dim=-1)
            .clamp(max=1.0)
        )
        bounded_change = velocity_change.clamp(
            min=-acceleration_step, max=acceleration_step
        )
        bounded_change[:, :5] = velocity_change[:, :5] * acceleration_scale[:, None]
        self._velocity += bounded_change
        self._target += self._velocity * self._dt
        bounded = self._target.clamp(
            min=physical_limits[:, :, 0], max=physical_limits[:, :, 1]
        )
        self._velocity[:] = torch.where(bounded == self._target, self._velocity, 0.0)
        self._target[:] = bounded
        self._asset.set_joint_position_target_index(
            target=self._target, joint_ids=self._joint_ids
        )

    def reset(self, env_ids=None):
        self._raw_actions[env_ids] = 0.0
        self._initialized[env_ids] = False
        self._velocity[env_ids] = 0.0
        self._failed[env_ids] = False


@configclass
class VialArmActionCfg(ActionTermCfg):
    """Pointing IK weights and physics-rate joint safety limits in SI units."""

    class_type: type = VialArmAction
    joint_names: tuple[str, ...] = (
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
    )
    direction_length: float = 0.08
    damping: float = 0.02
    target_response_time: float = 0.08
    max_target_lead: float = 0.20
    joint_velocity_limits: tuple[float, ...] = (1.4, 2.5, 2.3, 3.0, 1.8)
    joint_acceleration_limits: tuple[float, ...] = (8.0, 12.0, 12.0, 14.0, 10.0)
    gripper_velocity_limit: float = 4.0
    gripper_acceleration_limit: float = 30.0
