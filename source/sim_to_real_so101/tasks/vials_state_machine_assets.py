# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Task-local asset derivatives with semantic manipulation frames."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import isaaclab.sim as sim_utils
from isaaclab.sim.utils import clone
from sim_to_real_so101.assets.vial import VIAL_GRASP_OFFSET_M

FIXED_JAW_CONTACT_FRAME = "sm_fixed_jaw_contact"
MOVING_JAW_CONTACT_FRAME = "sm_moving_jaw_contact"
VIAL_GRASP_FRAME = "sm_grasp"


@dataclass(frozen=True)
class TaskFrame:
    """An empty frame authored relative to an asset prim."""

    parent_path: str
    name: str
    position: tuple[float, float, float]


ROBOT_TASK_FRAMES = (
    TaskFrame(
        parent_path="gripper",
        name=FIXED_JAW_CONTACT_FRAME,
        position=(-0.0079, -0.0002, -0.0981),
    ),
    TaskFrame(
        parent_path="moving_jaw_so101_v1",
        name=MOVING_JAW_CONTACT_FRAME,
        position=(-0.0079, -0.0766, 0.0189),
    ),
)
VIAL_TASK_FRAMES = (
    TaskFrame(
        parent_path="",
        name=VIAL_GRASP_FRAME,
        position=(0.0, 0.0, VIAL_GRASP_OFFSET_M),
    ),
)


def with_task_frames(asset_cfg, frames: Sequence[TaskFrame]):
    """Return an asset-config copy whose spawner authors the supplied frames."""
    cfg = asset_cfg.copy()
    base_spawn = cfg.spawn.func
    cfg.spawn.func = _task_frame_spawner(base_spawn, tuple(frames))
    return cfg


def _task_frame_spawner(
    base_spawn: Callable[..., Any],
    frames: tuple[TaskFrame, ...],
) -> Callable[..., Any]:
    @clone
    def spawn(
        prim_path: str,
        cfg,
        translation: tuple[float, float, float] | None = None,
        orientation: tuple[float, float, float, float] | None = None,
        **kwargs,
    ):
        prim = base_spawn(
            prim_path,
            cfg,
            translation=translation,
            orientation=orientation,
            **kwargs,
        )
        for frame in frames:
            parent_path = "/".join(
                part for part in (prim_path, frame.parent_path) if part
            )
            frame_path = f"{parent_path}/{frame.name}"
            sim_utils.create_prim(
                frame_path,
                prim_type="Xform",
                translation=frame.position,
            )
        return prim

    return spawn
