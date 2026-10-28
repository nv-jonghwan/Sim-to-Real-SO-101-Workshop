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
#
# This file contains code derived from Isaac Lab
# (https://github.com/isaac-sim/IsaacLab)
# Copyright (c) 2022-2026, The Isaac Lab Project Developers. All rights reserved.
# Licensed under the BSD-3-Clause License.

"""Script to print all environments registered by ``sim_to_real_so101``."""

import argparse

import gymnasium as gym
from prettytable import PrettyTable

import sim_to_real_so101.tasks  # noqa: F401

# Prefix of the gym IDs this module registers (all Newton-So101-*).
MODULE_PREFIXES = ("Newton-",)

parser = argparse.ArgumentParser(description="List sim_to_real_so101 environments.")
parser.add_argument(
    "--keyword",
    type=str,
    default=None,
    help="Substring to filter task IDs by. Defaults to this module's own environments.",
)
args_cli = parser.parse_args()


def main():
    """Print all environments registered by ``sim_to_real_so101``."""
    table = PrettyTable(["S. No.", "Task Name", "Entry Point", "Config"])
    table.title = "Available Environments in sim_to_real_so101"
    table.align["Task Name"] = "l"
    table.align["Entry Point"] = "l"
    table.align["Config"] = "l"

    index = 0
    for task_spec in gym.registry.values():
        if args_cli.keyword is not None:
            match = args_cli.keyword in task_spec.id
        else:
            match = task_spec.id.startswith(MODULE_PREFIXES)
        if match:
            table.add_row(
                [
                    index + 1,
                    task_spec.id,
                    task_spec.entry_point,
                    task_spec.kwargs.get("env_cfg_entry_point", ""),
                ]
            )
            index += 1

    print(table)


if __name__ == "__main__":
    main()
