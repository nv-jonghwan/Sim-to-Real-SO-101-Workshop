---
name: so101-dli-dagger
description: Conduct the SO-101 DLI HG-DAgger lesson with powered leader alignment, taught rests, correction collection, replay and separate autonomous evaluation.
---

# HG-DAgger with explicit physical behavior

Read [the practical lesson](../../docs/14-hg-dagger-practice.md) and
[DAGGER.md](../../DAGGER.md); follow the selected runtime's exact controls.
Use [hardware qualification](../so101-dli-hardware/SKILL.md) first.

## Before starting

Have the student observe the instructor demonstration before operating.
Move laptops and loose objects outside the leader's sweep, clear clamps/cables
and retain room behind attendees. Explain that **the physical teleop arm moves
under power even when the follower is simulated**, including startup, alignment,
reset and normal exit. G/L release torque with no gravity compensation;
the operator must support the leader first.

Establish current operator readiness and one owner per serial/camera device.
Stop or hand off only the owned prior teleop session. Do not reuse an earlier
chat's operator readiness as unattended authorization now.

Teach leader rest via `lerobot_dagger --teach-rest`, and follower rest via
the lesson's `lerobot-rollout-dagger --strategy.teach_follower_rest=true`
recipe, once for the current calibration. These save current positions, but
still require exclusive device ownership. Check actual saved rests and clear
held vials; startup opens grippers and can drop them.

## Choose one execution path

- Real follower: `lerobot-rollout-dagger` loads policy in-process, so it needs
  no policy server. Use the co-trained policy, verified cameras/IDs and
  `--start_pose_dataset=sreetz-nv/so101_sim_manual_perception_newton_20261008`
  exactly as in the lesson.
- Sim follower: `lerobot_dagger` uses its dedicated localhost:8081 policy
  server and a physical leader. This tag does **not** support
  `--start_pose_dataset` for sim DAgger, so its default pose is not a matched
  start with real collection. Another client resets server state; do not
  share this server with evaluation.

Use distinct local sim/real correction IDs and collection/evaluation seeds.
A new correction round is a new ID unless intentional resume is requested.
No automatic upload.

## Conduct a single correction

Keep the browser focused and only one viewer tab connected:

1. Space: run policy, then Space: pause.
2. Tab while paused: let the powered leader align; wait for `correction_ready`.
3. Support leader, then G: release torque and begin correction.
4. Guide a useful segment. Space saves the segment and returns to policy.
5. Verify `Episode N saved` and replay the actual local episode.

X holds with the unfinished correction retained; C discards and pauses.
R discards the unfinished correction and resets; real completion/reset is
manually assessed. Esc/Ctrl+C perform normal return-to-rest motion with torque
on. L releases leader torque and exits without moving it: support it first.
Do not describe ordinary exit as immediate motor power-off.

## Close and evaluate

Inspect both videos, timestamps, state/action features and number of saved
correction segments. Only human corrections are saved; policy rollout,
alignment and reset are not full demonstration episodes.

Stop the owned sim server when done; wait for return motion and cleanup.
The supplied HG-DAgger checkpoint contains historical 29 corrections, not the
ones just collected. Evaluate it autonomously using the evaluation skill and
separate scored trials. Improvement from new corrections requires an actual
training run and a held-out comparison; assisted completion is not that evidence.
