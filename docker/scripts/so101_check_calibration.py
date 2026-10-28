#!/usr/bin/env python
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Calibration quality check for the SO101 follower or teleop arm.

Verifies two things:
  1. Static check  — each joint's calibrated range (in raw encoder counts) is
                     compared with reference statistics for the selected arm.
  2. Live check    — the current encoder position of each joint is within its
                     calibrated range (requires robot to be connected).

The STS3215 encoder has 4096 counts per full revolution, but joints cannot
physically rotate 360°, so encoder counts are used directly rather than
converting to degrees.

Usage inside the workshop container:
    export ROBOT_PORT=/dev/ttyACM0
    export ROBOT_ID=follower_arm_1
    python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_check_calibration.py

Use --arm teleop to check the leader with TELEOP_ID and TELEOP_PORT.
Use --static-only to skip hardware access, and --calibration to select a JSON file.
"""

import argparse
import json
import logging
import os
from pathlib import Path

import draccus
from lerobot.motors.motors_bus import MotorCalibration
from lerobot.robots import make_robot_from_config
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
from lerobot.teleoperators.so_leader import SOLeader, SOLeaderTeleopConfig
from lerobot.utils.constants import HF_LEROBOT_CALIBRATION
from lerobot.utils.utils import init_logging

# Default path to the stats JSON produced by so101_calibration_stats.py
DEFAULT_STATS_PATH = Path(__file__).parent / "calibration_stats.json"
TELEOP_STATS_PATH = Path(__file__).parent / "teleop_calibration_stats.json"

# Number of standard deviations outside the mean before flagging a WARN
N_STD = 2.0

# Warn if |homing_offset| exceeds this (raw counts).
HOMING_OFFSET_WARN = 2048


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_calibration(path: Path) -> dict[str, MotorCalibration]:
    with open(path) as f, draccus.config_type("json"):
        return draccus.load(dict[str, MotorCalibration], f)


def load_stats(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def static_check(calibration: dict[str, MotorCalibration], stats: dict) -> list[dict]:
    """Check each joint's motion range against mean ± N_STD × std from the stats file."""
    results = []
    for joint, calib in calibration.items():
        motion_range = abs(calib.range_max - calib.range_min)
        s = stats.get(joint)

        issues = []
        deviation_std = None
        if s:
            mean, std = s["mean"], s["std"]
            deviation = motion_range - mean
            deviation_std = deviation / std if std > 0 else None
            if std == 0 and deviation != 0:
                issues.append(
                    f"motion range {motion_range} differs from reference {mean:.0f} "
                    "(all reference samples have the same range)"
                )
            elif std > 0 and abs(deviation_std) > N_STD:
                issues.append(
                    f"motion range {motion_range} deviates {deviation_std:+.1f}σ from mean "
                    f"(mean={mean:.0f}, std={std:.0f}, threshold=±{N_STD}σ)"
                )

        if abs(calib.homing_offset) > HOMING_OFFSET_WARN:
            issues.append(
                f"large homing_offset ({calib.homing_offset}): "
                "arm was likely not near the midpoint during calibration"
            )

        results.append(dict(
            joint=joint,
            motion_range=motion_range,
            mean=s["mean"] if s else None,
            std=s["std"] if s else None,
            deviation_std=deviation_std,
            homing_offset=calib.homing_offset,
            status="PASS" if not issues else "WARN",
            issues=issues,
        ))
    return results


def live_check(robot, calibration: dict[str, MotorCalibration]) -> list[dict]:
    """Read live encoder positions and check they are within the calibrated range."""
    raw = robot.bus.sync_read("Present_Position", normalize=False)
    results = []
    for joint, pos in raw.items():
        calib = calibration.get(joint)
        if calib is None:
            continue
        in_range = calib.range_min <= pos <= calib.range_max
        results.append(dict(
            joint=joint,
            raw_pos=pos,
            range_min=calib.range_min,
            range_max=calib.range_max,
            in_range=in_range,
            margin_min=pos - calib.range_min,
            margin_max=calib.range_max - pos,
        ))
    return results


def print_report(
    calib_path: Path,
    stats_path: Path,
    static_results: list[dict],
    live_results: list[dict],
    arm: str = "follower",
) -> None:
    W = 76
    print("\n" + "=" * W)
    print("  SO101 CALIBRATION CHECK REPORT")
    print(f"  Arm:   {arm}")
    print(f"  File:  {calib_path}")
    print(f"  Stats: {stats_path}")
    print("=" * W)

    # --- Static check ---
    print(f"\n[1] Motion Range vs Stats (threshold ±{N_STD}σ)\n")
    header = (
        f"  {'Joint':<18} {'Range':>6}  {'Mean':>7} {'Std':>6} {'Deviation':>10}  "
        f"{'Offset':>8}  Status"
    )
    print(header)
    print("  " + "-" * (W - 2))

    all_pass = True
    for r in static_results:
        status = r["status"]
        if status != "PASS":
            all_pass = False
        flag = "✓" if status == "PASS" else "⚠"
        mean_str = f"{r['mean']:.0f}" if r["mean"] is not None else "—"
        std_str  = f"{r['std']:.0f}"  if r["std"]  is not None else "—"
        dev_str  = f"{r['deviation_std']:+.2f}σ" if r["deviation_std"] is not None else "—"
        print(
            f"  {r['joint']:<18} {r['motion_range']:>6}  {mean_str:>7} {std_str:>6} {dev_str:>10}  "
            f"{r['homing_offset']:>8}  {flag} {status}"
        )
        for issue in r["issues"]:
            print(f"    {'':18}  → {issue}")

    # --- Live check ---
    if live_results:
        print("\n[2] Live Encoder Positions\n")
        header2 = f"  {'Joint':<18} {'Position':>9}  {'Calibrated Range':^20}  {'In Range':>9}"
        print(header2)
        print("  " + "-" * (W - 2))
        for r in live_results:
            flag = "✓" if r["in_range"] else "✗"
            if not r["in_range"]:
                all_pass = False
            rng = f"{r['range_min']} – {r['range_max']}"
            print(
                f"  {r['joint']:<18} {r['raw_pos']:>9}  {rng:^20}  "
                f"{flag} {'OK' if r['in_range'] else 'OUT OF RANGE'}"
            )
    else:
        print("\n[2] Live check skipped (file-only check or arm not connected)\n")

    print("\n" + "=" * W)
    verdict = "✓ PASS — calibration looks good." if all_pass else "⚠ WARN — review the issues above."
    print(f"  Overall: {verdict}")
    print("=" * W + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm", choices=("follower", "teleop"), default="follower",
        help="Use ROBOT_ID/ROBOT_PORT or TELEOP_ID/TELEOP_PORT and matching reference statistics.",
    )
    parser.add_argument("--calibration", type=Path, help="Calibration JSON to check instead of the cached ID.")
    parser.add_argument("--static-only", action="store_true", help="Check the file without connecting to hardware.")
    args = parser.parse_args(argv)
    init_logging()

    if args.arm == "teleop":
        arm_id = os.getenv("TELEOP_ID", "leader_arm_1")
        port = os.getenv("TELEOP_PORT", "/dev/ttyACM0")
        calib_dir = HF_LEROBOT_CALIBRATION / "teleoperators" / SOLeader.name
        default_stats = TELEOP_STATS_PATH
    else:
        arm_id = os.getenv("ROBOT_ID", "follower_arm_1")
        port = os.getenv("ROBOT_PORT", "/dev/ttyACM0")
        calib_dir = HF_LEROBOT_CALIBRATION / "robots" / SOFollower.name
        default_stats = DEFAULT_STATS_PATH
    calib_path = args.calibration or calib_dir / f"{arm_id}.json"

    if not calib_path.exists():
        logging.error(f"Calibration file not found: {calib_path}")
        logging.error("Run `lerobot-calibrate` first, or check the selected arm ID / --calibration path.")
        return 1

    stats_path = Path(os.getenv("STATS_JSON", default_stats))
    if not stats_path.exists():
        logging.error(f"Stats file not found: {stats_path}")
        logging.error("Run so101_calibration_stats.py first, or set STATS_JSON env var.")
        return 1

    logging.info(f"Loading calibration: {calib_path}")
    logging.info(f"Loading stats: {stats_path}")
    calibration = load_calibration(calib_path)
    stats = load_stats(stats_path)

    static_results = static_check(calibration, stats)

    live_results = []
    if args.static_only:
        print_report(calib_path, stats_path, static_results, live_results, args.arm)
        return 0

    # The device must load the same calibration file as the static check.
    robot = None
    try:
        if args.arm == "teleop":
            config = SOLeaderTeleopConfig(port=port, id=calib_path.stem, calibration_dir=calib_path.parent)
            robot = SOLeader(config)
        else:
            config = SOFollowerRobotConfig(port=port, id=calib_path.stem, calibration_dir=calib_path.parent)
            robot = make_robot_from_config(config)
        robot.connect(calibrate=False)
        logging.info("Arm connected — reading live encoder positions")
        live_results = live_check(robot, calibration)
    except Exception as e:
        logging.warning(f"Could not connect to arm: {e}")
        logging.warning("Skipping live check — showing file-only report")
    finally:
        if robot is not None and robot.is_connected:
            robot.disconnect()

    print_report(calib_path, stats_path, static_results, live_results, args.arm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
