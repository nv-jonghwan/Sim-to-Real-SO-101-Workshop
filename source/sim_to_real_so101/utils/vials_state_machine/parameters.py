# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Physical limits and pooled motion ranges from ten successful demonstrations.

Dataset sreetz-nv/so101_real_manual, revision 975f14991f6d944f8ae418512998a66a0151e40a.
Phase medians in seconds: 3.50, .80, 1.83, 1.77, .63, .47, 2.22.
FK-derived positions are estimates; contact offsets require simulation validation.
"""

import math

from sim_to_real_so101.utils.gripper_calibration import WORKSHOP_GRIPPER_CALIBRATION


def jaw_radians(percent):
    return math.radians(float(WORKSHOP_GRIPPER_CALIBRATION.percent_to_degrees(percent)))


MAX_OPENING_RAD = jaw_radians(50.0)
REACH_OPEN_MIN_RAD = jaw_radians(28.0)
REACH_OPEN_MAX_RAD = jaw_radians(43.0)
PINCH_MIN_RAD = jaw_radians(1.0)
PINCH_MAX_RAD = jaw_radians(3.0)
RELEASE_MIN_RAD = jaw_radians(38.0)
RELEASE_MAX_RAD = jaw_radians(46.0)

WARMUP_SETTLE_STEPS = 30
WARMUP_STEPS = WARMUP_SETTLE_STEPS
MAX_VIAL_REACH_M = 0.40
RACK_SLOT_OCCUPANCY_RADIUS_M = 0.025
RACK_GRIPPER_REACHBACK_M = 0.14
RACK_GRIPPER_HALF_WIDTH_M = 0.03
RACK_GRIPPER_BELOW_GRASP_M = 0.035
RACK_OBSTACLE_MARGIN_M = 0.004
# The spherical vial tip enters the opening before the fingers transfer support.
TIP_ENGAGEMENT_M = 0.003
GRASP_AXIAL_OFFSET_MIN_M = -0.035
RACK_INSERTION_TARGET_DEPTH_M = TIP_ENGAGEMENT_M

TIP_CENTER_TOLERANCE_M = 0.012
UPRIGHT_AXIS_Z = 0.98
MIN_GRASP_FORCE_N = 1.5
MAX_GRASP_FORCE_N = 16.0
MAX_PHASE_OVERRUN_S = 3.0
MAX_ACTIVE_DURATION_RATIO = 1.60

WARMUP = 0
REACH = 1
PINCH = 2
LIFT_TURN = 3
GUIDE_IN = 4
OPEN = 5
SETTLE = 6
RETURN = 7

# Grasp sampling and reset-time clearance checks share the controller envelope.
GRASP_FRACTION_MIN = 0.52
GRASP_FRACTION_MAX = 0.62
GRASP_AXIAL_LEAD_M = 0.005
GRASP_APPROACH_HALF_WIDTH_MIN_M = 0.028
GRASP_APPROACH_HALF_WIDTH_MAX_M = 0.046
