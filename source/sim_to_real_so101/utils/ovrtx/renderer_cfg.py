# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0
"""Shared workshop renderer configuration."""

from dataclasses import field

from isaaclab.utils import configclass
from isaaclab_ov.renderers import OVRTXRendererCfg

from .renderer import SO101OVRTXRenderer


@configclass
class SO101OVRTXRendererCfg(OVRTXRendererCfg):
    """Optional render-product attributes keyed by environment-relative camera path.

    Empty responses retain native camera processing. Both cameras must carry
    the same mapping to share one renderer backend.
    """

    class_type: type = SO101OVRTXRenderer
    camera_responses: dict[str, dict[str, bool | str | float | tuple]] = field(default_factory=dict)
