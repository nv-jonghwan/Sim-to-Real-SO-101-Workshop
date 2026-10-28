---
name: so101-dli-collect
description: Collect, replay and validate SO-101 simulation or real demonstration datasets, including domain randomization, scripted collection and sim-real merges for this DLI course.
---

# Collect demonstrations with a traceable contract

Read [sim teleoperation](../../docs/08-simulation-teleoperation.md),
[state-machine collection](../../docs/09-state-machine-learning.md) and
[co-training practice](../../docs/13-cotraining-practice.md) as applicable.
Use the prepared classroom station and the hardware skill; if a required asset
or container is missing, identify it for the TA. Do not assume another teleop
process can share the leader with the simulation.

## Choose the exercise

- Practice/record teleop with `lerobot_agent`, a physical calibrated leader,
  `--cameras all --browser-display presets=newton,ovrtx_renderer` and the
  base or DR collection task. Recording keys require the focused browser.
  Rerun/headless modes do not provide these keyboard controls.
- For physical demonstrations use the lesson's `lerobot-record` recipe after
  both cameras and follower are qualified. Set explicit local recording:
  `--dataset.push_to_hub=false`; preserve completed episodes.
- Scripted collection uses `vials_state_machine`. Copy its options from the
  current lesson/source and inspect `--help`; do not invent a legacy CLI.
  It does not require a physical leader. Use a new dataset path and a bounded
  episode/time budget; partial staging is not a finalized LeRobot dataset.

Use a fresh `repo_id` and task instruction in the station's authorized namespace.
Local naming does not itself authorize an upload.
Local paths are `datasets/<repo_id>`; do not add unsupported `--repo_root`.
Use `--resume` only when supported and continuing the intended dataset.

## Validate before expanding

Start with one completed episode. Check metadata, task, fps, episode/frame
counts, monotonic timestamps, six finite joint state/action features, both RGB
videos and actual decode/frame progression. Replay with
`lerobot-dataset-viz --repo-id ... --root ./datasets/... --episode-index 0`.
Review the grasp, placement, release and timing in both cameras.

Preserve canonical joint order, arm-degree/gripper-percentage conventions,
`wrist`/`external` camera keys and 30 Hz cadence. Observation/action timing
is part of the training contract; do not independently decode relative actions.
Task success alone does not prove training data quality.

If the state machine fails with non-finite Jacobians, retain logs and incomplete
episode status. Do not relax contact/success criteria or change camera geometry
to obtain a passing sample.

## Merge and optional training

Use the course's `lerobot-edit-dataset` merge with a **new** output and
`--push_to_hub=false`; input datasets must be finalized and compatible.
Inspect at least one sim and one real episode after merge. Episode concatenation
does not establish balanced sampling or reproduce the provided Sim75+Real10
checkpoint. Record source IDs/revisions, counts and merge ordering.

Training, Cosmos generation and upload are later requested actions. Keep local
datasets and evidence available for the next checkpoint; never infer permission
to publish from a tutorial containing `hf upload`.
