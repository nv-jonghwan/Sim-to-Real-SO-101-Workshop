# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

"""Estimated STS overload protection for the native Newton/MJWarp gripper drive."""

import math
import re

import numpy as np
import torch
import warp as wp
from isaaclab.managers import ManagerTermBase
from isaaclab_newton.physics import NewtonManager
from sim_to_real_so101.utils.warp_bridge import manager_stream


@wp.struct
class ProtectionState:
    blocked_steps: int
    direction: float
    protected_direction: float


@wp.kernel
def _update_protection(
    q: wp.array2d[float], qd: wp.array2d[float],
    target: wp.array2d[float], target_velocity: wp.array2d[float], feedforward: wp.array2d[float],
    stiffness: wp.array2d[float], damping: wp.array2d[float], peak: wp.array2d[float],
    gripper: int, trip_steps: int,
    history: wp.array[ProtectionState], limits: wp.array2d[float],
):
    e = wp.tid()
    s = history[e]
    error = target[e, gripper] - q[e, gripper]
    direction = 0.0
    if wp.abs(error) > 0.02:
        direction = wp.sign(error)
    demand = stiffness[e, gripper] * error + damping[e, gripper] * (
        target_velocity[e, gripper] - qd[e, gripper]
    ) + feedforward[e, gripper]
    if direction * s.protected_direction <= 0.0:
        s.protected_direction = 0.0
    blocked = (
        direction != 0.0 and wp.abs(qd[e, gripper]) < 0.1
        and demand * direction >= 0.25 * peak[e, gripper]
    )
    if blocked:
        if direction != s.direction:
            s.blocked_steps = 0
        s.blocked_steps = wp.min(s.blocked_steps + 1, trip_steps)
    else:
        s.blocked_steps = 0
    s.direction = direction
    if s.blocked_steps >= trip_steps:
        s.protected_direction = direction
    fraction = 0.5
    if s.protected_direction != 0.0:
        fraction = 0.2
    limits[e, gripper] = peak[e, gripper] * fraction
    history[e] = s


@wp.kernel
def _reset_protection(
    mask: wp.array[wp.bool], gripper: int, peak: wp.array2d[float],
    history: wp.array[ProtectionState], limits: wp.array2d[float],
):
    e = wp.tid()
    if mask[e]:
        history[e] = ProtectionState()
        limits[e, gripper] = peak[e, gripper] * 0.5


@wp.kernel
def _publish_limits(
    limits: wp.array2d[float], gripper: int, mj_joints: wp.array[int],
    joint_limits: wp.array2d[float], mj_ranges: wp.array2d[wp.vec2],
):
    e = wp.tid()
    cap = limits[e, gripper]
    joint_limits[e, gripper] = cap
    mj_ranges[e, mj_joints[e]] = wp.vec2(-cap, cap)


class STSGripperProtection:
    """Track continuous blockage and a directional protection latch per environment.

    Limits are estimated fractions of the immutable USD peak: 50% normally,
    20% after 100 ms of blocked PD demand above 25%. Reaching the target,
    reversing direction, or resetting releases protection. These percentages
    approximate servo output settings, not a calibrated electrical model.
    """

    def __init__(self, peak_effort: wp.array, gripper: int, dt: float):
        self.peak = wp.clone(peak_effort)
        self.limits = wp.clone(peak_effort)
        self.gripper = gripper
        self.trip_steps = math.ceil(0.1 / dt)
        self.history = wp.zeros(peak_effort.shape[0], dtype=ProtectionState, device=peak_effort.device)
        self.reset(wp.ones(len(self.history), dtype=wp.bool, device=peak_effort.device))

    def step(self, q, qd, target, target_velocity, feedforward, stiffness, damping):
        """Update the torque ceiling once per physics interval; leave the PD drive implicit."""
        wp.launch(
            _update_protection, dim=len(self.history), device=self.peak.device,
            inputs=[q, qd, target, target_velocity, feedforward, stiffness, damping,
                    self.peak, self.gripper, self.trip_steps, self.history, self.limits],
        )

    def reset(self, mask):
        """Clear only the environments selected by the Boolean mask."""
        wp.launch(
            _reset_protection, dim=len(self.history), device=self.peak.device,
            inputs=[mask, self.gripper, self.peak, self.history, self.limits],
        )


class GripperProtectionTerm(ManagerTermBase):
    """Install a physics-step callback and reset its history with each episode.

    MJWarp keeps a solver copy of Newton's joint effort limit. Both arrays must
    be written before the solver substeps; updating only articulation telemetry
    does not limit contact forces. The solver handle and mapping are specific to
    the pinned Isaac Lab/Newton backend. No gains or passive dynamics are changed.
    """

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self.robot = env.scene["robot"]
        self.gripper = self.robot.joint_names.index("gripper")
        self.protection = STSGripperProtection(
            self.robot.data.joint_effort_limits.warp, self.gripper, env.physics_dt,
        )
        self.reset_mask = torch.ones(env.num_envs, dtype=torch.bool, device=env.device)

    def __call__(self, env, env_ids):
        """Bind the solver and install protection after simulation initialization."""
        model = NewtonManager.get_model()
        solver = NewtonManager._solver
        # Resolve the backend joint map once; no scene queries or host readbacks occur in a step.
        labels = model.joint_label
        worlds = model.joint_world.numpy()
        dof_starts = model.joint_qd_start.numpy()
        joint_map = solver.mjc_jnt_to_newton_dof.numpy()
        pattern = self.robot.cfg.prim_path + r"/joints/gripper"
        mj_joints = np.full(env.num_envs, -1, dtype=np.int32)
        for index, label in enumerate(labels):
            if re.fullmatch(pattern, label):
                world = int(worlds[index])
                matches = np.flatnonzero(joint_map[world] == dof_starts[index])
                if len(matches) != 1:
                    raise ValueError(f"Expected one MJWarp gripper joint for {label}")
                mj_joints[world] = matches[0]
        if np.any(mj_joints < 0):
            raise ValueError("Missing SO-101 gripper in the MJWarp joint map")
        self.mj_joints = wp.array(mj_joints, dtype=int, device=env.device)
        self.mj_ranges = solver.mjw_model.jnt_actfrcrange
        NewtonManager.register_post_actuator_callback(self.step)
        self.reset()

    def _publish(self):
        wp.launch(
            _publish_limits, dim=self.num_envs, device=self.device,
            inputs=[self.protection.limits, self.gripper, self.mj_joints,
                    self.robot.data.joint_effort_limits.warp, self.mj_ranges],
        )

    def step(self):
        """Apply the ceiling on the Newton stream before each physics interval."""
        data = self.robot.data
        command = self.robot.actuators.target_command
        self.protection.step(
            data.joint_pos.warp, data.joint_vel.warp,
            command.position.warp, command.velocity.warp, command.effort.warp,
            data.joint_stiffness.warp, data.joint_damping.warp,
        )
        self._publish()

    def reset(self, env_ids=None):
        """Restore the selected grippers' normal ceiling at an episode boundary."""
        self.reset_mask.zero_()
        self.reset_mask[slice(None) if env_ids is None else env_ids] = True
        with manager_stream(self.device):
            self.protection.reset(wp.from_torch(self.reset_mask))
            self._publish()
