# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Workshop-local paths for LeRobot datasets."""

from pathlib import Path

WORKSHOP_DATASETS_ROOT = Path(
    "/workspace/Sim-to-Real-SO-101-Workshop/datasets"
)


def dataset_root_from_repo_id(repo_id: str) -> str:
    """Map ``user/dataset`` to its workshop-local dataset directory."""
    parts = repo_id.split("/")
    if len(parts) != 2 or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("--repo_id must have the form user/dataset")
    return str(WORKSHOP_DATASETS_ROOT.joinpath(*parts))
