# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Collect real-follower DAgger corrections on the LeRobot rollout stack.

``lerobot-rollout`` owns the command line, loads the policy in-process and
connects the follower. The ``lerobot_dagger --real`` session runs on top of it
unchanged: browser controls, leader alignment and takeover, corrections-only
recording, safe resets and exit. Resets use the evaluation dataset-start selector;
verify training-data start coverage before a physical rollout.
"""

import argparse
import math
import os
import queue
import signal
import time
from collections import deque
from dataclasses import dataclass, field
from unittest.mock import patch

import numpy as np
import torch
from lerobot.configs import parser
from lerobot.policies.rtc.configuration_rtc import RTCConfig
from lerobot.policies.utils import prepare_observation_for_inference
from lerobot.robots.so_follower import SO101FollowerConfig
from lerobot.rollout import RolloutConfig, create_strategy
from lerobot.rollout import context as rollout_context
from lerobot.rollout.configs import RolloutStrategyConfig
from lerobot.rollout.inference.factory import InferenceEngineConfig, RTCInferenceConfig
from lerobot.rollout.strategies.core import RolloutStrategy
from lerobot.scripts import lerobot_rollout as upstream_rollout
from lerobot.teleoperators.so_leader import SOLeader
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig
from lerobot.utils.constants import OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame
from sim_to_real_so101.scripts import lerobot_dagger
from sim_to_real_so101.utils.dagger import dagger_leader
from sim_to_real_so101.utils.dagger.dagger_leader import (
    DaggerLeader,
    physical_rest_pose,
)
from sim_to_real_so101.utils.dagger.real_so101 import (
    _OPEN_GRIPPER,
    RealSO101Env,
    _refuse_calibration,
)
from sim_to_real_so101.utils.dataset_start_pose import dataset_start_pose
from sim_to_real_so101.utils.lerobot_interface import LeRobotSO101Interface

_DEFAULT_INSTRUCTION = "Pick up the vial and place it in the rack"
# Peak speeds of reset and exit moves (cosine profile). Arm joints of both arms
# move at up to 45 deg/s; grippers open and close faster than the arms move.
_ARM_SPEED = 45.0  # deg/s
_GRIPPER_SPEED = 90.0  # percent/s, follower
# The leader's powered-motion cap while it tracks reset and exit waypoints. Tab
# alignment and --strategy.leader_follows keep the session's own cap.
_LEADER_RATE = np.array([_ARM_SPEED] * 5 + [50.0])


@RolloutStrategyConfig.register_subclass("workshop_dagger")
@dataclass
class WorkshopDAggerConfig(RolloutStrategyConfig):
    """``lerobot_dagger --real`` options that the rollout command line does not provide."""

    repo_id: str = ""
    leader_port: str = field(default_factory=lambda: os.getenv("TELEOP_PORT", "/dev/ttyACM0"))
    leader_id: str = field(default_factory=lambda: os.getenv("TELEOP_ID", "leader_bot"))
    leader_follows: bool = False
    demo_video: str | None = None
    signal_port: int = 49100
    http_port: int = 8090
    # Save the follower's current pose as its rest and exit without moving.
    teach_follower_rest: bool = False


@dataclass
class WorkshopDAggerRolloutConfig(RolloutConfig):
    """Rollout configuration with the workshop DAgger strategy selected."""

    strategy: WorkshopDAggerConfig = field(default_factory=WorkshopDAggerConfig)
    # The rollout context refuses its sync engine for GR00T relative-action policies. This
    # engine is built but never started: the session runs policy chunks itself.
    inference: InferenceEngineConfig = field(
        default_factory=lambda: RTCInferenceConfig(rtc=RTCConfig(enabled=False), queue_threshold=0))
    task: str = _DEFAULT_INSTRUCTION
    start_pose_dataset: str | None = None
    # The session returns the follower along its safe path on exit.
    return_to_initial_position: bool = False

    def __post_init__(self):
        # Teaching the follower rest needs only the follower, not a policy.
        if not self.strategy.teach_follower_rest:
            super().__post_init__()


class _ChunkPolicy:
    """The policy-client contract of ``lerobot_dagger``, served in-process by the rollout's policy.

    As with the policy server, a used-up chunk triggers one inference on the
    current observation, and its ``--policy.n_action_steps`` actions then run
    open-loop. ``reset`` drops the rest of the chunk, so control handed back
    after a correction starts from the corrected state. Takes joints in
    simulator radians and ``rgb_<camera>`` tensors; returns the next action in
    simulator radians.
    """

    def __init__(self, ctx, iface, camera_names):
        self._ctx, self._iface, self._camera_names = ctx, iface, camera_names
        self._chunk = deque()

    def connect(self):
        """The rollout context loaded the policy."""

    def reset(self):
        self._chunk.clear()
        for stage in (self._ctx.policy.policy, self._ctx.policy.preprocessor, self._ctx.policy.postprocessor):
            stage.reset()

    def get_action(self, joint_positions, visual_obs):
        if not self._chunk:
            self._chunk.extend(self._predict_chunk(joint_positions, visual_obs))
        return self._chunk.popleft()

    def _predict_chunk(self, joint_positions, visual_obs):
        ctx, iface = self._ctx, self._iface
        raw = iface.sim_radians_to_raw(joint_positions.detach().cpu().numpy().astype(np.float32))
        observation = {name: float(raw[i]) for i, name in enumerate(iface.SO101_JOINT_ORDER)}
        for camera in self._camera_names:
            observation[camera] = visual_obs[f"rgb_{camera}"][0].cpu().numpy()
        cfg = ctx.runtime.cfg
        batch = build_dataset_frame(ctx.data.hw_features, ctx.processors.robot_observation_processor(observation),
                                    prefix=OBS_STR)
        batch = prepare_observation_for_inference(batch, torch.device(cfg.device or "cpu"), cfg.task,
                                                  ctx.hardware.robot_wrapper.robot_type)
        batch["task"] = [cfg.task]
        with torch.inference_mode():
            chunk = ctx.policy.postprocessor(ctx.policy.policy.predict_action_chunk(ctx.policy.preprocessor(batch)))
        actions = []
        for row in chunk.squeeze(0).cpu():
            action = dict(zip(ctx.data.ordered_action_keys, row.tolist(), strict=True))
            action = ctx.processors.robot_action_processor((action, observation))
            raw_action = np.array([action[name] for name in iface.SO101_JOINT_ORDER], dtype=np.float32)
            actions.append(torch.from_numpy(iface.raw_to_sim_radians(raw_action)).to(iface.sim_device))
        return actions

    def close(self):
        """The rollout teardown releases the policy."""


class _RolloutFollowerEnv(RealSO101Env):
    """``RealSO101Env`` around the follower that the rollout context connected.

    Resets use the mean episode-start pose from ``start_pose_dataset``, or the
    calibrated state-machine fallback when omitted. Exit returns to ``rest`` (its
    pose at startup when ``None``) through the start pose. Both arms take the
    safe path in step, each from its own pose: ``on_move`` and ``return_path``
    receive the leader's waypoints, so the leader heads for the target from
    wherever it is rather than first to the follower. On exit the leader ends
    at its own rest; ``return_path`` then receives ``None``.
    """

    def __init__(self, iface, robot, device, rest=None, *, start_pose_dataset=None):
        # The base initializer connects a follower of its own; this one is connected.
        self.cameras = {name: {"height": cfg.height, "width": cfg.width} for name, cfg in robot.config.cameras.items()}
        self.iface, self.device = iface, device
        self.robot = robot
        self._rest = self._raw(self.robot.get_observation()) if rest is None else np.asarray(rest, dtype=np.float64)
        start_pose = dataset_start_pose(start_pose_dataset, iface.calibration)
        self._start = np.array([start_pose[name] for name in iface.SO101_JOINT_ORDER])
        self._returning = None
        self._started = False
        self.return_path = queue.SimpleQueue()
        # The session's leader, once created; its pose starts the leader's waypoints.
        self.leader = None

    def reset(self, options=None):
        """Move to the workshop start pose along the safe path (blocking), then observe.

        ``options["on_move"]``, if given, receives the leader's waypoint for each follower waypoint sent.
        """
        self._started = True
        self._move_safely(self._start, (options or {}).get("on_move"))
        return self._observe(), {}

    def _move_safely(self, target, on_move=None):
        follower = self._raw(self.robot.get_observation())
        leader = self._leader_pose() if on_move is not None else None
        self._glide(follower, leader, _safe_segments(follower, target, leader, target), on_move)

    def _return(self):
        try:
            follower, leader = self._raw(self.robot.get_observation()), self._leader_pose()
            segments = _safe_segments(follower, self._start, leader, self._start) if self._started else []
            leader_rest = None
            if leader is not None:
                leader_rest = self._rest if self.leader.rest_pose is None else self.leader.rest_pose
            self._glide(follower, leader, [*segments, (self._rest, leader_rest, 0.0)], self.return_path.put)
        finally:
            self.return_path.put(None)

    def _leader_pose(self):
        """The leader's measured pose, or ``None`` without a leader or live feedback (it then mirrors the follower)."""
        state = None if self.leader is None else self.leader.snapshot()
        if state is None or state["error"] or state["position"] is None:
            return None
        pose = np.array(state["position"], dtype=np.float64)
        pose[5] = np.clip(pose[5], 0, 100)
        return pose

    def _glide(self, follower, leader, segments, on_move):
        """Send follower waypoints through ``segments`` of (follower end, leader end, minimum seconds).

        Each segment follows a cosine speed profile, long enough that every arm
        joint of both arms stays within ``_ARM_SPEED`` and each gripper within
        its own cap, so a tracking leader is not jerked into motion while it
        lifts its own weight. ``on_move`` receives the leader's matching
        waypoint from ``leader``, or the follower's own when ``leader`` is
        ``None``. The leader tracks them at ``_LEADER_RATE`` meanwhile.
        """
        with patch.object(dagger_leader, "_RATE", _LEADER_RATE):
            for follower_end, leader_end, min_s in segments:
                seconds = _cosine_seconds(follower, follower_end, _GRIPPER_SPEED)
                if leader is not None:
                    seconds = max(seconds, _cosine_seconds(leader, leader_end, _LEADER_RATE[5]))
                steps = max(1, math.ceil(seconds / self.step_dt), round(min_s / self.step_dt))
                for i in range(1, steps + 1):
                    alpha = (1 - math.cos(math.pi * i / steps)) / 2
                    waypoint = follower + alpha * (follower_end - follower)
                    self._send(waypoint)
                    if on_move is not None:
                        on_move(waypoint if leader is None else leader + alpha * (leader_end - leader))
                    time.sleep(self.step_dt)
                follower = follower_end
                if leader is not None:
                    leader = leader_end


def _cosine_seconds(start, end, gripper_speed):
    """Duration of a cosine move whose fastest arm joint peaks at ``_ARM_SPEED`` and gripper at ``gripper_speed``."""
    travel = np.abs(np.asarray(end) - np.asarray(start))
    return math.pi / 2 * max(travel[:5].max() / _ARM_SPEED, travel[5] / gripper_speed)


def _safe_segments(follower, target, leader, leader_target):
    """Safe-path segments as (follower end, leader end, minimum seconds); leader ends are ``None`` without ``leader``.

    Each arm opens its gripper to at least ``_OPEN_GRIPPER`` (a held vial
    drops, and the follower waits while it falls clear), moves shoulder lift,
    elbow and wrist flex in place, then turns the base and wrist roll and sets
    the gripper.
    """
    def ends(pose, goal):
        opened = np.r_[pose[:5], max(pose[5], _OPEN_GRIPPER)]
        return [opened, opened, np.r_[opened[0], goal[1:4], opened[4:]], goal]

    leader_ends = [None] * 4 if leader is None else ends(leader, leader_target)
    wait = 0.5 if follower[5] < _OPEN_GRIPPER else 0.0
    return list(zip(ends(follower, target), leader_ends, (0.0, wait, 0.0, 0.0), strict=True))


class _MirroringLeader(DaggerLeader):
    """Leader that parks along the path the follower env publishes for it, then settles at its own rest.

    ``path`` yields leader waypoints in step with the follower's return and
    ends with ``None``; without a waypoint for two seconds the leader parks
    directly.
    """

    def __init__(self, *args, path, **kwargs):
        super().__init__(*args, **kwargs)
        self._path = path

    def park(self):
        while self.rest_pose is not None and not self.snapshot()["error"]:
            try:
                waypoint = self._path.get(timeout=2.0)
            except queue.Empty:
                break
            if waypoint is None:
                break
            target = np.array(waypoint, dtype=np.float64)
            target[5] = np.clip(target[5], 0, 100)
            self.renew()
            self.follow(target)
        return super().park()


class WorkshopDAggerStrategy(RolloutStrategy):
    """Run the ``lerobot_dagger --real`` session with the rollout's policy and follower."""

    def __init__(self, config, rest_pose):
        super().__init__(config)
        self._rest_pose = rest_pose

    def setup(self, ctx):
        """Nothing to start: the session runs policy chunks in its own worker."""

    def run(self, ctx):
        cfg, options = ctx.runtime.cfg, self.config
        device = torch.device(cfg.device or "cuda")
        device = f"cuda:{device.index or 0}" if device.type == "cuda" else str(device)
        iface = LeRobotSO101Interface(port=options.leader_port, robot_id=options.leader_id, sim_device=device)
        robot = ctx.hardware.robot_wrapper.inner
        env = _RolloutFollowerEnv(
            iface, robot, device, rest=_follower_rest(robot), start_pose_dataset=cfg.start_pose_dataset,
        )
        args = argparse.Namespace(
            repo_id=options.repo_id, resume=cfg.resume, lang_instruction=cfg.task, task=cfg.task,
            leader_follows=options.leader_follows, demo_video=options.demo_video, browser_display=True,
            signal_port=options.signal_port, http_port=options.http_port,
            # Consumed only by the policy client, which _ChunkPolicy replaces.
            pretrained_name_or_path=None, policy_type=None, policy_device=None, server_address=None, action_horizon=None,
        )
        def make_leader(*args, **kwargs):
            # Resets and exit move both arms in step, the leader from its own pose.
            env.leader = _MirroringLeader(*args, path=env.return_path, **kwargs)
            return env.leader

        # The rollout turns Ctrl+C into a shutdown flag; the session handles KeyboardInterrupt itself.
        interrupt = signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            with (
                patch.object(lerobot_dagger, "LeRobotPolicyServerClient",
                             lambda **_: _ChunkPolicy(ctx, iface, list(env.cameras))),
                patch.object(lerobot_dagger, "DaggerLeader", make_leader),
            ):
                lerobot_dagger._collect(args, env, iface, env.cameras, self._rest_pose, reset_cameras=set())
        finally:
            signal.signal(signal.SIGINT, interrupt)

    def teardown(self, ctx):
        self._teardown_hardware(ctx.hardware, return_to_initial_position=False)


_make_robot = rollout_context.make_robot_from_config


def _make_follower(config):
    """Build the follower so that it refuses interactive calibration, like ``RealSO101Env``."""
    robot = _make_robot(config)
    robot.calibrate = _refuse_calibration
    return robot


def _follower_rest(robot):
    """The follower's taught rest pose, or ``None`` to return to its startup pose."""
    try:
        return physical_rest_pose(robot, LeRobotSO101Interface.SO101_JOINT_ORDER)
    except ValueError:
        print("[DAGGER]: No taught follower rest for this calibration; exit returns the follower to its startup "
              "pose. Teach one with --strategy.teach_follower_rest=true.", flush=True)
        return None


def _teach_follower_rest(config):
    """Save the follower's current pose as its rest; connecting holds it with torque ON."""
    robot = _make_follower(config)
    robot.connect()
    try:
        observation = robot.get_observation()
        pose = np.array([observation[name] for name in LeRobotSO101Interface.SO101_JOINT_ORDER])
        pose[5] = np.clip(pose[5], 0, 100)
        physical_rest_pose(robot, LeRobotSO101Interface.SO101_JOINT_ORDER, measured=pose)
    finally:
        robot.disconnect()
    print("[DAGGER]: Follower rest taught; motor torque remains ON.", flush=True)


@parser.wrap()
def rollout(cfg: WorkshopDAggerRolloutConfig) -> None:
    """Check the setup, then let LeRobot build the rollout and run the workshop session."""
    robot = cfg.robot
    if not isinstance(robot, SO101FollowerConfig) or not robot.use_degrees or robot.disable_torque_on_disconnect:
        raise ValueError("Use --robot.type=so101_follower --robot.use_degrees=true "
                         "--robot.disable_torque_on_disconnect=false.")
    if cfg.strategy.teach_follower_rest:
        _teach_follower_rest(robot)
        return
    if not cfg.strategy.repo_id:
        raise ValueError("Set the correction dataset with --strategy.repo_id=<hf_user>/<dataset>.")
    if cfg.teleop is not None or cfg.dataset is not None:
        raise ValueError("Set the leader with --strategy.leader_port/leader_id and the dataset with "
                         "--strategy.repo_id, not --teleop.* or --dataset.*.")
    if cfg.fps != round(1 / RealSO101Env.step_dt) or cfg.interpolation_multiplier != 1:
        raise ValueError("The DAgger session runs at --fps=30 with --interpolation_multiplier=1.")
    # Fail before loading the policy when the leader has no taught rest pose.
    leader = SOLeader(SOLeaderTeleopConfig(port=cfg.strategy.leader_port, id=cfg.strategy.leader_id, use_degrees=True))
    rest_pose = physical_rest_pose(leader, LeRobotSO101Interface.SO101_JOINT_ORDER)

    def strategy(config):
        return WorkshopDAggerStrategy(config, rest_pose) if config is cfg.strategy else create_strategy(config)

    with (
        patch.object(upstream_rollout, "create_strategy", strategy),
        patch.object(rollout_context, "make_robot_from_config", _make_follower),
    ):
        upstream_rollout.rollout.__wrapped__(cfg)


def main() -> None:
    """Run ``lerobot-rollout-dagger``."""
    upstream_rollout.register_third_party_plugins()
    rollout()


if __name__ == "__main__":
    main()
