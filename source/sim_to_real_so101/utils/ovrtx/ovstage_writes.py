# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Attribute writes into a renderer-owned OVStage scene."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import numpy as np
import ovstage
from isaaclab.cloner import path as cloner_path
from isaaclab.cloner.cloner_cfg import DEFAULT_ENV_TEMPLATE, expand_env_regex_ns
from isaaclab_ov.stage import xform_tensor_from_numpy
from ovrtx import Semantic


@contextmanager
def ovstage_query(stage, stage_paths, prim_paths: list[str]):
    """Resolve prim paths and release both OVStage query resources."""
    path_list = stage_paths.create_path_list_from_strings(prim_paths)
    try:
        query = stage.query_from_path_list(path_list)
        if query is None:
            raise RuntimeError(f"OVStage query is None for {prim_paths}")
        with query:
            yield query
    finally:
        stage_paths.destroy_path_list(path_list)


def expand_prim_paths(prim_path: str, num_envs: int) -> list[str]:
    """Expand an environment-templated prim path into one path per environment."""
    path_expr = expand_env_regex_ns(prim_path)
    matched = cloner_path.match(path_expr, DEFAULT_ENV_TEMPLATE)
    if matched is None or matched.instance not in (".*", "[^/]*", "[^/]+"):
        return [path_expr]
    return [
        DEFAULT_ENV_TEMPLATE.format(env_id) + matched.suffix
        for env_id in range(num_envs)
    ]


def write_attribute(
    stage,
    stage_paths,
    prim_paths: list[str],
    attribute_name: str,
    tensor: np.ndarray,
    ordinal: int,
    semantic: Semantic | None = None,
) -> None:
    """Write ``tensor`` to every prim; a single row is shared by all of them."""
    values = np.ascontiguousarray(np.atleast_1d(np.asarray(tensor)))
    rows = len(values)
    if rows not in (1, len(prim_paths)):
        raise ValueError(
            f"Expected 1 or {len(prim_paths)} rows for {len(prim_paths)} prims, "
            f"got shape {values.shape}"
        )
    kwargs: dict[str, Any] = {
        "ordinal": ordinal,
        "tensors": values,
        "is_array": False,
        # OVStage gathers source rows, so one row addresses every prim directly.
        "index_map": [0] * len(prim_paths) if rows == 1 else None,
    }
    if semantic == Semantic.XFORM_MAT4x4:
        if values.shape[1:] != (4, 4):
            raise ValueError(
                f"OVStage matrix write requires (rows, 4, 4), got {values.shape}"
            )
        kwargs.update(
            tensors=xform_tensor_from_numpy(values),
            semantic=ovstage.AttributeSemantic.MATRIX,
        )
    with ovstage_query(stage, stage_paths, prim_paths) as query:
        stage.write_attribute(query, attribute_name, **kwargs).wait()


def write_asset_path(
    stage,
    stage_paths,
    prim_paths: list[str],
    attribute_name: str,
    asset_path: str,
    ordinal: int,
) -> None:
    """Write an absolute path to an existing scalar USD asset column."""
    value = np.array([[stage_paths.intern_token(asset_path), 0]], dtype=np.uint64)
    with ovstage_query(stage, stage_paths, prim_paths) as query:
        stage.write_attribute(
            query,
            attribute_name,
            ordinal=ordinal,
            tensors=value,
            is_array=False,
            index_map=[0] * len(prim_paths),
            semantic=ovstage.AttributeSemantic.ASSET_PATH_ID,
        ).wait()
