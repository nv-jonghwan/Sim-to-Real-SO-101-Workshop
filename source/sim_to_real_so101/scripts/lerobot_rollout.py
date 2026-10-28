# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Upstream LeRobot rollout with manually bounded SO-101 trials."""

import logging
import math
import sys
import time
from dataclasses import dataclass, field
from queue import Empty, SimpleQueue
from unittest.mock import patch

from lerobot.configs import parser
from lerobot.configs.dataset import DatasetRecordConfig
from lerobot.datasets import VideoEncodingManager
from lerobot.robots.so_follower import SO101FollowerConfig
from lerobot.rollout import RolloutConfig, create_strategy
from lerobot.rollout.configs import RolloutStrategyConfig
from lerobot.rollout.context import RolloutContext
from lerobot.rollout.inference.rtc import RTCInferenceEngine
from lerobot.rollout.strategies.base import BaseStrategy
from lerobot.rollout.strategies.core import safe_push_to_hub, send_next_action
from lerobot.scripts import lerobot_rollout as upstream_rollout
from lerobot.utils.feature_utils import build_dataset_frame
from lerobot.utils.keyboard_input import TerminalKeyListener
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import init_logging
from sim_to_real_so101.utils.dataset_paths import dataset_root_from_repo_id
from sim_to_real_so101.utils.dataset_start_pose import dataset_start_pose

logger = logging.getLogger(__name__)


@RolloutStrategyConfig.register_subclass("workshop")
@dataclass
class WorkshopStrategyConfig(RolloutStrategyConfig):
    """Manual trials, recorded when a dataset is configured."""


@dataclass
class WorkshopDatasetConfig(DatasetRecordConfig):
    """Record locally under the requested dataset name."""

    push_to_hub: bool = False

    def stamp_repo_id(self) -> None:
        """Preserve the requested repo ID for the workshop dataset layout."""


@dataclass
class WorkshopRolloutConfig(RolloutConfig):
    """LeRobot CLI configuration with the workshop strategy selected by default."""

    strategy: RolloutStrategyConfig = field(default_factory=WorkshopStrategyConfig)
    dataset: WorkshopDatasetConfig | None = None
    start_pose_dataset: str | None = None


class _RtcDelayWarningFilter(logging.Filter):
    """Suppress the known queue-delay mismatch warning."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "lerobot.policies.rtc.action_queue"
            and record.levelno == logging.WARNING
            and record.getMessage().startswith("Indexes diff is not equal to real delay")
        )


def _init_logging() -> None:
    """Format console logs and quiet routine inference lifecycle messages."""
    init_logging()
    for handler in logging.getLogger().handlers:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        handler.addFilter(_RtcDelayWarningFilter())
    logging.getLogger("lerobot.rollout.inference").setLevel(logging.WARNING)
    logging.getLogger("lerobot.rollout.strategies").setLevel(logging.WARNING)


def _move_to_initial_pose(
    robot,
    initial_pose: dict[str, float],
    *,
    stop_event,
    duration_s: float = 3.0,
    fps: int = 50,
) -> bool:
    """Move smoothly to the workshop rollout pose before inference starts."""
    observation = robot.get_observation()
    start = {key: float(observation[key]) for key in initial_pose}
    steps = max(int(duration_s * fps), 1)
    for step in range(1, steps + 1):
        if stop_event.is_set():
            return False
        progress = step / steps
        blend = 0.5 - 0.5 * math.cos(math.pi * progress)
        robot.send_action(
            {
                key: start[key] + blend * (target - start[key])
                for key, target in initial_pose.items()
            }
        )
        precise_sleep(1 / fps)
    return True


class WorkshopStrategy(BaseStrategy):
    """Manual trials with smooth reset, optional recording, and trial scores."""

    def __init__(self, config: WorkshopStrategyConfig) -> None:
        super().__init__(config)
        self._commands: SimpleQueue[str] = SimpleQueue()
        self._listener = None
        self._paused = True
        self._shutdown_event = None
        self._first_action_since = None
        self._episode_frames = 0
        self.successes = 0
        self.failures = 0

    def setup(self, ctx: RolloutContext) -> None:
        """Enable controls and home the arm, then wait for the first trial."""
        self._shutdown_event = ctx.runtime.shutdown_event
        if not sys.stdin.isatty():
            raise RuntimeError("Workshop rollout requires an interactive terminal; use docker exec -it.")
        self.initial_pose = dataset_start_pose(ctx.runtime.cfg.start_pose_dataset)
        self._listener = TerminalKeyListener(self._queue_key)
        self._listener.start()
        logger.info(
            "Controls | keep this terminal focused | S/F score + save + reset | "
            "Right/N discard + reset | P start | Q/Esc discard + exit"
        )
        logger.info("Starting | moving to the rollout pose")
        self._home_and_pause(ctx)

    def _home_and_pause(self, ctx: RolloutContext) -> None:
        if not _move_to_initial_pose(
            ctx.hardware.robot_wrapper, self.initial_pose, stop_event=self._shutdown_event
        ):
            raise KeyboardInterrupt
        # Keys pressed during a reset must not start or score the next trial.
        while not self._commands.empty():
            self._commands.get_nowait()
        logger.info("Paused | arrange the scene, then press P to start")

    def _queue_key(self, key: str) -> None:
        key = key.lower()
        if key in {"s", "f", "right", "n", "p"}:
            self._commands.put(key)
        elif key in {"q", "esc"}:
            logger.info("Stopping | exit requested")
            self._shutdown_event.set()

    def _log_score(self, event: str) -> None:
        total = self.successes + self.failures
        rate = 100.0 * self.successes / total if total else 0.0
        logger.info(
            "%s | %d / %d successful (%.1f%%) | %d failed",
            event,
            self.successes,
            total,
            rate,
            self.failures,
        )

    def _handle_commands(self, ctx: RolloutContext) -> None:
        try:
            command = self._commands.get_nowait()
        except Empty:
            return
        if command in {"s", "f", "right", "n"} and not self._paused:
            # LeRobot 0.6 clears its thread reference even when stop() times out.
            thread = self._engine._rtc_thread if isinstance(self._engine, RTCInferenceEngine) else None
            self._engine.stop()
            if thread is not None and thread.is_alive():
                raise RuntimeError("Inference did not stop; refusing to reset or restart the rollout.")
            self._paused = True
            self._finish_episode(ctx, command)
            logger.info("Resetting | returning to the rollout pose")
            self._home_and_pause(ctx)
        elif command == "p" and self._paused:
            self._init_engine(ctx)
            self._paused = False
            self._resume()

    def _finish_episode(self, ctx: RolloutContext, outcome: str | None = None) -> None:
        """Save and score a nonempty trial on S/F; discard every other outcome."""
        if not self._episode_frames:
            return
        dataset = ctx.data.dataset
        if outcome in {"s", "f"}:
            if dataset is not None:
                dataset.save_episode()
                logger.info("Saved | episode %d | %d frames", dataset.num_episodes - 1, self._episode_frames)
            self.successes += outcome == "s"
            self.failures += outcome == "f"
            self._log_score("Success" if outcome == "s" else "Failure")
        else:
            if dataset is not None:
                dataset.clear_episode_buffer()
            logger.info("Skipped | trial discarded without scoring")
        self._episode_frames = 0

    def _resume(self) -> None:
        self._first_action_since = time.perf_counter()
        self._engine.resume()
        logger.info("Waiting | first policy action")

    def run(self, ctx: RolloutContext) -> None:
        """Service controls between ticks using upstream observation/action helpers."""
        cfg = ctx.runtime.cfg
        robot = ctx.hardware.robot_wrapper
        dataset = ctx.data.dataset
        control_interval = 1 / (cfg.fps * cfg.interpolation_multiplier)
        last_slow_warning = -math.inf

        while not ctx.runtime.shutdown_event.is_set():
            self._handle_commands(ctx)
            if ctx.runtime.shutdown_event.is_set():
                break
            if self._paused:
                pause_start = time.perf_counter()
                if cfg.display_data:
                    obs = robot.get_observation()
                    obs_processed = ctx.processors.robot_observation_processor(obs)
                    self._log_telemetry(obs_processed, None, ctx.runtime)
                precise_sleep(max(0.0, control_interval - (time.perf_counter() - pause_start)))
                continue

            loop_start = time.perf_counter()
            obs = robot.get_observation()
            obs_processed = ctx.processors.robot_observation_processor(obs)
            if self._interpolator.needs_new_action():
                self._engine.notify_observation(obs_processed)

            if self._handle_warmup(cfg.use_torch_compile, loop_start, control_interval):
                continue

            action_dict = send_next_action(obs_processed, obs, ctx, self._interpolator)
            if dataset is not None and action_dict is not None:
                features = ctx.data.dataset_features
                dataset.add_frame({
                    **build_dataset_frame(features, obs_processed, prefix="observation"),
                    **build_dataset_frame(features, action_dict, prefix="action"),
                    "task": cfg.dataset.single_task or cfg.task,
                })
            if action_dict is not None:
                self._episode_frames += 1
            if action_dict is not None and self._first_action_since is not None:
                logger.info(
                    "Running | first policy action after %.2f s",
                    time.perf_counter() - self._first_action_since,
                )
                self._first_action_since = None
            self._log_telemetry(obs_processed, action_dict, ctx.runtime)

            dt = time.perf_counter() - loop_start
            if (sleep_t := control_interval - dt) > 0:
                precise_sleep(sleep_t)
            elif loop_start - last_slow_warning >= 5.0:
                logger.warning(
                    "Control loop behind target | %.1f Hz / %.1f Hz",
                    1 / dt,
                    1 / control_interval,
                )
                last_slow_warning = loop_start

    def teardown(self, ctx: RolloutContext) -> None:
        """Release hardware, discard an unfinished trial, and finalize dataset writers."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        try:
            super().teardown(ctx)
        finally:
            dataset = ctx.data.dataset
            if dataset is not None:
                with VideoEncodingManager(dataset):
                    self._finish_episode(ctx)
                if ctx.runtime.cfg.dataset.push_to_hub:
                    safe_push_to_hub(
                        dataset,
                        tags=ctx.runtime.cfg.dataset.tags,
                        private=ctx.runtime.cfg.dataset.private,
                    )
            self._log_score("Summary")


def _create_strategy(config: RolloutStrategyConfig):
    return WorkshopStrategy(config) if isinstance(config, WorkshopStrategyConfig) else create_strategy(config)


@parser.wrap()
def rollout(cfg: WorkshopRolloutConfig) -> None:
    """Delegate setup and dataset creation to LeRobot with the workshop strategy."""
    if cfg.dataset is not None and cfg.dataset.root is None:
        cfg.dataset.root = dataset_root_from_repo_id(cfg.dataset.repo_id)
    if isinstance(cfg.strategy, WorkshopStrategyConfig):
        if not isinstance(cfg.robot, SO101FollowerConfig) or not cfg.robot.use_degrees:
            raise ValueError("Workshop strategy requires --robot.type=so101_follower and --robot.use_degrees=true")
        cfg.duration = 0.0
        if cfg.dataset is not None:
            recording_fps = cfg.fps * cfg.interpolation_multiplier
            if recording_fps != int(recording_fps):
                raise ValueError("Recording requires a whole-number control rate (fps * interpolation_multiplier)")
            cfg.dataset.fps = int(recording_fps)
    # LeRobot 0.6 dispatches strategies through a fixed factory, without a registry.
    with (
        patch.object(upstream_rollout, "create_strategy", _create_strategy),
        patch.object(upstream_rollout, "init_logging", _init_logging),
    ):
        upstream_rollout.rollout.__wrapped__(cfg)


def main() -> None:
    """Run ``lerobot-rollout``."""
    upstream_rollout.register_third_party_plugins()
    rollout()


if __name__ == "__main__":
    main()
