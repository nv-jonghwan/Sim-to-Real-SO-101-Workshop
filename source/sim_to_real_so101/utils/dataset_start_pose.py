# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compute the mean SO-101 starting pose across all dataset episodes."""

import logging
from pathlib import Path

import numpy as np
from huggingface_hub import snapshot_download
from lerobot.datasets.io_utils import load_nested_dataset
from lerobot.datasets.lerobot_dataset import LeRobotDatasetMetadata
from sim_to_real_so101.utils.dataset_paths import dataset_root_from_repo_id
from sim_to_real_so101.utils.gripper_calibration import (
    WORKSHOP_GRIPPER_CALIBRATION,
    GripperCalibration,
)


def dataset_start_pose(
    repo_id: str | None, calibration: GripperCalibration = WORKSHOP_GRIPPER_CALIBRATION,
) -> dict[str, float]:
    """Average all episode starts, in arm degrees and gripper percent.

    Print the mean and standard deviation. Reuse local data offline and fetch
    missing data without videos. With no repo ID, warn and return the calibrated
    state-machine pose. Empty datasets and non-finite states raise ValueError.
    """
    if repo_id is None:
        from sim_to_real_so101.tasks.vials_state_machine_env_cfg import (
            vials_start_pose_in_lerobot_units,
        )

        logging.getLogger(__name__).warning(
            "No --start_pose_dataset supplied; using the state-machine starting pose."
        )
        return vials_start_pose_in_lerobot_units(calibration)

    metadata, frames = _load_dataset_frames(repo_id)
    start_frames = frames.select(metadata.episodes["dataset_from_index"])
    joint_states = np.asarray(start_frames["observation.state"], dtype=np.float64)
    joint_names = metadata.features["observation.state"]["names"]
    if not np.isfinite(joint_states).all():
        raise ValueError("Starting joint states must be finite")

    mean_values = joint_states.mean(axis=0).tolist()
    std_values = joint_states.std(axis=0).tolist()
    mean_pose = dict(zip(joint_names, mean_values, strict=True))
    standard_deviation = dict(zip(joint_names, std_values, strict=True))
    print(f"[Start pose] {repo_id}: {metadata.total_episodes} episode starts")
    print(f"[Start pose] Mean (arm degrees, gripper %): {mean_pose}")
    print(f"[Start pose] Std: {standard_deviation}")
    return mean_pose


def _load_dataset_frames(repo_id: str):
    """Reuse local LeRobot metadata and frames; fetch missing files without videos."""
    root = Path(dataset_root_from_repo_id(repo_id))
    metadata = LeRobotDatasetMetadata(repo_id, root=root)
    if metadata.total_episodes == 0:
        raise ValueError(f"Dataset {repo_id} has no episodes")
    for episode_index in range(metadata.total_episodes):
        data_file = root / metadata.get_data_file_path(episode_index)
        if not data_file.is_file():
            snapshot_download(
                repo_id,
                repo_type="dataset",
                revision=metadata.revision,
                local_dir=root,
                allow_patterns=["data/**"],
            )
            break
    return metadata, load_nested_dataset(root / "data")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id", help="LeRobot dataset user/dataset")
    dataset_start_pose(parser.parse_args().repo_id)
