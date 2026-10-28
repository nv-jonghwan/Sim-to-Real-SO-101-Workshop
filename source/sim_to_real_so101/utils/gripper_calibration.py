# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
"""Shared percentage-to-jaw-angle mapping for the SO-101 gripper."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GripperCalibration:
    """Encoder span and angle at zero percent, in the simulator jaw frame."""

    span_ticks: float = 1485.0
    zero_degrees: float = -12.505751884817162

    def __post_init__(self):
        if not np.isfinite([self.span_ticks, self.zero_degrees]).all() or not 0 < self.span_ticks <= 4095:
            raise ValueError("Use a finite jaw zero and encoder span in (0, 4095]")

    @property
    def degrees_per_percent(self):
        return self.span_ticks * 360.0 / (4095.0 * 100.0)

    def percent_to_degrees(self, percent):
        return self.zero_degrees + np.asarray(percent) * self.degrees_per_percent

    def degrees_to_percent(self, degrees):
        return (np.asarray(degrees) - self.zero_degrees) / self.degrees_per_percent


# Average encoder span across ten workshop robots, with a fitted jaw-frame zero.
WORKSHOP_GRIPPER_CALIBRATION = GripperCalibration()
