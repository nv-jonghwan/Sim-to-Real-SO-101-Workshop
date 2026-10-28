# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Physical SO-101 follower behind the environment interface used by DAgger collection."""

import threading
import time

import numpy as np
import torch
import yaml
from lerobot.cameras.opencv import OpenCVCameraConfig
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig

# Median first frame of the DR500 simulation dataset (arm degrees, gripper
# percent). DR500 checkpoints only start reliably from this pose.
DR500_START_POSE = np.array([0.0, -34.88, -3.91, 86.86, -91.87, 1.18])
_RESET_SPEED = 30.0  # degrees (gripper percent) per second
_OPEN_GRIPPER = 40.0  # percent; wide enough to drop a held vial


class RealSO101Env:
    """Step a physical follower with simulation-shaped observations.

    Joints are exchanged in simulator radians and camera frames as tensors on
    ``device``, so the DAgger session, recorder, display and policy client are
    shared with the Newton task. The follower holds its last goal whenever the
    session does not step. ``close`` returns it through the start pose to its
    pose at connection and keeps torque ON.
    """

    step_dt = 1 / 30

    def __init__(self, iface, port, robot_id, cameras_spec, device):
        # LeRobot camera dict as a YAML flow mapping (E2E_Workflow.md) or JSON.
        cameras = {
            name: OpenCVCameraConfig(**{key: value for key, value in spec.items() if key != "type"})
            for name, spec in yaml.safe_load(cameras_spec).items()
        }
        self.cameras = {name: {"height": cfg.height, "width": cfg.width} for name, cfg in cameras.items()}
        self.iface, self.device = iface, device
        self.robot = SOFollower(SOFollowerRobotConfig(
            port=port, id=robot_id, use_degrees=True, disable_torque_on_disconnect=False, cameras=cameras,
        ))
        # Never start interactive calibration, which releases torque, from a collection session.
        self.robot.calibrate = _refuse_calibration
        self.robot.connect()
        self._rest = self._raw(self.robot.get_observation())
        self._returning = None
        self._started = False

    @property
    def unwrapped(self):
        return self

    def reset(self, options=None):
        """Move to the DR500 start pose along the safe path (blocking), then observe.

        ``options["on_move"]``, if given, receives each raw waypoint as it is sent.
        """
        self._started = True
        self._move_safely(DR500_START_POSE, (options or {}).get("on_move"))
        return self._observe(), {}

    def step(self, action):
        self._send(self.iface.sim_radians_to_raw(action[0].detach().cpu().numpy()))
        done = torch.zeros(1, dtype=torch.bool)
        return self._observe(), None, done, done, {}

    def start_return(self):
        """Start returning to the pose at connection in the background; ``close`` waits for it."""
        print("[DAGGER]: Returning follower to its starting pose.", flush=True)
        self._returning = threading.Thread(target=self._return, name="follower-return")
        self._returning.start()

    def close(self):
        if not self.robot.is_connected:
            return
        try:
            if self._returning is None:
                self.start_return()
            self._returning.join()
        finally:
            self.robot.disconnect()

    def _return(self):
        if self._started:
            self._move_safely(DR500_START_POSE)
        self._move_to(self._rest)

    def _move_safely(self, target, on_move=None):
        """Open the gripper (a held vial drops), move shoulder lift, elbow and wrist
        flex in place, then turn the base and wrist roll and set the gripper."""
        pose = self._raw(self.robot.get_observation())
        if pose[5] < _OPEN_GRIPPER:
            pose = self._move_to(np.r_[pose[:5], _OPEN_GRIPPER], on_move, pose)
            # Hold while the vial falls clear; each waypoint renews the leader's lease.
            self._move_to(pose, on_move, pose, min_s=0.5)
        pose = self._move_to(np.r_[pose[0], target[1:4], pose[4:]], on_move, pose)
        self._move_to(target, on_move, pose)

    def _move_to(self, target, on_move=None, start=None, min_s=0.0):
        """Send straight-line waypoints from ``start`` (default: measured pose) to ``target`` over at least ``min_s``."""
        start = self._raw(self.robot.get_observation()) if start is None else start
        steps = max(1, round(np.max(np.abs(target - start)) / _RESET_SPEED / self.step_dt), round(min_s / self.step_dt))
        for alpha in np.linspace(0, 1, steps + 1)[1:]:
            waypoint = start + alpha * (target - start)
            self._send(waypoint)
            if on_move is not None:
                on_move(waypoint)
            time.sleep(self.step_dt)
        return target

    def _raw(self, observation):
        return np.array([observation[name] for name in self.iface.SO101_JOINT_ORDER], dtype=np.float64)

    def _send(self, raw):
        self.robot.send_action(dict(zip(self.iface.SO101_JOINT_ORDER, raw.tolist(), strict=True)))

    def _observe(self):
        observation = self.robot.get_observation()
        joints = self.iface.raw_to_sim_radians(self._raw(observation))
        return {
            "policy": {"joint_pos_obs": torch.as_tensor(joints, dtype=torch.float32, device=self.device)[None]},
            "visual": {
                f"rgb_{name}": torch.from_numpy(observation[name]).to(self.device)[None] for name in self.cameras
            },
        }


def _refuse_calibration():
    raise RuntimeError("Follower calibration is missing or does not match; calibrate the follower first.")
