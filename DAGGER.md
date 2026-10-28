# DAgger with the SO-101 leader

`lerobot-rollout-dagger` runs a LeRobot policy on the physical follower inside
LeRobot's `lerobot-rollout`; `lerobot_dagger` runs the same session on the
simulated SO-101. When the policy is about to fail, pause it, take over with the
leader arm, correct, and hand back. Only corrections are recorded, one LeRobot
episode each (HG-DAgger). Merge them with the original demonstrations before
fine-tuning, and measure autonomous success separately.

![DAgger data collection on the real SO-101](docs/images/dagger_data_collection.mp4){width=75%}

*Collecting corrections with the round-1 policy on the real SO-101: green while the
policy runs, red while the operator corrects with the leader arm.*

## Setup

- Workshop container ([README](README.md#starting-the-workshop-container)) with
  the calibrated leader; `TELEOP_PORT` and `TELEOP_ID` set in `/root/env`.
- For the real follower: the calibrated follower and cameras; `ROBOT_PORT`,
  `ROBOT_ID` and `ROBOT_CAMERAS` set in `/root/env`.
- A policy checkpoint (Hub id or local path).

## Run

1. Load settings and the checkpoint:

   ```bash
   cd /workspace/Sim-to-Real-SO-101-Workshop && source /root/env && export MODEL_ID=<checkpoint-hub-id-or-path>
   ```

2. Once per calibration, teach the physical rest poses. Neither command moves
   an arm, and torque stays ON.

   - Leader: support it at its bench rest, then run:

     ```bash
     lerobot_dagger --teach-rest
     ```

   - Real follower: with the follower sitting folded, for example right after
     power-on, run:

     ```bash
     lerobot-rollout-dagger --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.disable_torque_on_disconnect=false --strategy.teach_follower_rest=true
     ```

3. Start collection.

   - Real follower. LeRobot loads the policy in-process; no policy server is
     needed:

     ```bash
     lerobot-rollout-dagger --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.disable_torque_on_disconnect=false --robot.cameras="$ROBOT_CAMERAS" --start_pose_dataset=<hf_user>/<training_dataset> --strategy.repo_id=<hf_user>/<real_dataset> --strategy.leader_port="$TELEOP_PORT" --strategy.leader_id="$TELEOP_ID" --device=cuda
     ```

     Set `--start_pose_dataset` to the training dataset used for evaluation;
     `--strategy.repo_id` names the separate output dataset for corrections.
     Add `--resume=true` to append to an existing dataset,
     `--strategy.leader_follows=true` to keep the leader in sync with the arm,
     and `--strategy.demo_video=<path>` to save a session video. Each
     `--policy.n_action_steps` chunk runs open-loop.

   - Simulation. Start a policy server in a second container shell and keep it
     running; use a dedicated port, because a client connection resets the
     server:

     ```bash
     python -m lerobot.async_inference.policy_server --host=127.0.0.1 --port=8081 --fps=30 --inference_latency=0
     ```

     ```bash
     lerobot_dagger --task Newton-So101-Teleop-Vials-To-Rack-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address 127.0.0.1:8081 --pretrained_name_or_path "$MODEL_ID" --port "$TELEOP_PORT" --robot_id "$TELEOP_ID" --repo_id <hf_user>/<sim_dataset> --seed 42
     ```

     Add `--resume` to append to an existing dataset, `--leader_follows` to keep
     the leader in sync with the arm, and `--action_horizon` to match how the
     checkpoint was evaluated.

   Keep sim and real corrections in separate datasets, and collection seeds
   apart from evaluation seeds.

4. Open http://localhost:8090 and keep the page focused; keys only work there.
   The control panel shows who drives the arm: green **POLICY IN CONTROL**, red
   **HUMAN IN CONTROL** (camera frames match), amber during handovers, and it
   flashes when control changes. Below it, the Workflow keys dim when the
   current phase ignores them and mark the expected next key; the Safety keys
   (X, Esc, L) work in every phase.

## Controls

The session moves the leader to the start pose, then waits paused.

| Key | Action |
|---|---|
| Space | Start the policy / pause it. Pausing never moves the leader. |
| Tab (paused) | Align the leader to the arm; wait for `correction_ready`. |
| G | Release leader torque and start your correction. Support the arm. |
| Space (correcting) | Hold the leader, save the correction, resume the policy. |
| X | Freeze and hold; an unfinished correction is kept (G continues, Space saves). |
| C | Discard the unfinished correction and pause. |
| R | Discard the unfinished correction, reset, move the leader to the start pose. |
| Esc / Ctrl+C | Return the leader to its taught rest and exit with torque ON. |
| L | Release torque and exit without moving. Support the arm first. |

Typical loop: **Space (run) → Space (pause) → Tab → G → correct → Space**,
as often as needed in one rollout. An episode end (success, timeout, unsafe
scene) or R resets the scene, moves the leader to the new start pose and pauses.

**`--leader_follows`**: the leader tracks the arm during policy rollouts, so Tab
only closes a small gap (tracking is capped at 30 deg/s and the leader sags
slightly under gravity). Useful while the policy needs frequent corrections; it
keeps the leader powered (see [Safety](#safety)).

## Real follower

- Start and R move both arms together to the mean episode-start pose from
  `--start_pose_dataset`, using the same selector as `lerobot-rollout` and
  `lerobot_eval`. It reports the mean and standard deviation, reuses complete
  local data, and downloads missing data without videos. Omitting the option
  warns and uses the calibrated state-machine fallback.
  **Verify the selected and achieved pose against the actual training data,
  including corrections, before rollout.** A mean alone does not establish
  coverage when episode starts vary.
  Each arm opens its gripper (a held vial drops), moves shoulder, elbow and
  wrist flex in place, then turns the base and wrist roll. Each arm starts from
  its own pose, so the leader never detours
  to where the follower is. Resets glide with a smooth start and stop, arms at
  up to 45 deg/s and grippers faster; duration depends on the selected pose.
  Reset the objects by hand while paused.
- Pausing leaves the follower holding its last target.
- No automatic success, timeout or safety reset: end a rollout with R and note
  the outcome by hand.
- Exit moves both arms together along the same path through the start pose,
  each ending at its own rest; both keep torque ON. The follower ends at its
  taught rest, or at its startup pose until one is taught.

## Recording

- Only frames between G and the end of a correction are recorded; policy steps,
  pauses, alignment and resets are not.
- Space or task success during a correction saves it as one episode; C, R, Esc,
  timeout, unsafe scenes and faults discard it.
- A separate writer process encodes video while you record, so saving never
  stalls the loop. `Episode N saved` confirms the write.
- `--strategy.demo_video=outputs/<name>.mp4` (`--demo_video` with
  `lerobot_dagger`) also saves the whole session as one video: the external and
  wrist views under a green POLICY or red HUMAN TAKEOVER banner, other phases
  in grey. It is for showing the session, not for training.
- Data goes to `datasets/<repo_id>`; nothing is uploaded. Inspect an episode:

  ```bash
  lerobot-dataset-viz --repo-id <hf_user>/<dataset> --root ./datasets/<hf_user>/<dataset> --episode-index 0
  ```

## Training on corrections

Fine-tune the original checkpoint on the corrections plus a sample of its
demonstrations.

1. Download the demonstrations once. Merging needs them locally, because the
   DR500 Hub dataset has no `v3.0` revision tag:

   ```bash
   python -c "from huggingface_hub import snapshot_download; snapshot_download('sreetz-nv/so101_newton_dr500_20260923', repo_type='dataset', local_dir='datasets/sreetz-nv/so101_newton_dr500_20260923')"
   ```

2. Merge the demonstrations with every correction dataset so far. Episodes keep
   this order: the 500 demonstrations first, then each correction dataset.

   ```bash
   lerobot-edit-dataset --new_repo_id <hf_user>/<merged> --new_root datasets/<hf_user>/<merged> --operation.type merge --operation.repo_ids "['sreetz-nv/so101_newton_dr500_20260923', '<hf_user>/<real_dataset>']" --operation.roots "['datasets/sreetz-nv/so101_newton_dr500_20260923', 'datasets/<hf_user>/<real_dataset>']"
   ```

3. Train from the checkpoint with its recipe on every 10th demonstration and all
   corrections, here 40 corrections (episodes 500-539):

   ```bash
   EPISODES=$(python -c "print(list(range(0, 500, 10)) + list(range(500, 540)))")
   ```

   ```bash
   lerobot-train --dataset.repo_id=<hf_user>/<merged> --dataset.root=datasets/<hf_user>/<merged> --dataset.episodes="$EPISODES" --dataset.image_transforms.enable=true --policy.path="$MODEL_ID" --policy.push_to_hub=false --batch_size=32 --seed=42 --steps=5000 --save_freq=2500 --output_dir=outputs/train/<run> --job_name=<run> --wandb.enable=false
   ```

- Batch 32 needs about 70 GB of GPU memory: an RTX PRO 6000 (96 GB) fits it. 5k steps take about 5.4 h there, mostly CPU image
  preprocessing. `groot_fast_train` on branch `perf/groot-fast-train` runs that
  preprocessing on the GPU: about 1.4 h, with the same losses and robot results.
- The fine-tune keeps the checkpoint's normalization statistics.
- Each round starts again from the original checkpoint and keeps every earlier
  correction dataset.
- Choose checkpoints by robot trials.

## Results on the real SO-101

DR500 checkpoint above (simulation only), five trials per model at nearby vial
positions, with every correction placing into the same rack hole:

| Model | Training data | Result |
|---|---|---|
| DR500 checkpoint | 500 simulated demonstrations | Never grasps |
| Round 1 | 50 demonstrations + 40 grasp-and-lift corrections | Grasps and lifts; no placement |
| Round 2 | + 20 placement corrections | Full task 2/5 |
| Round 2 | + 30 placement corrections | Full task 5/5 |

- Grasping needed few corrections; a reliable lift needed about 35, placement 30.
- Without the demonstration sample the policy got worse and forgot its simulated
  behaviour. Training on the sample alone did not improve open-loop scores.
- 2,500 training steps performed as well as 5,000.
- Corrections covered grasp, lift and placement only. Reaching and carrying come
  from the simulation policy, and far vial positions still fail.

## Safety

- The leader moves under power during Tab, resets and exit, and with
  `--leader_follows` during rollouts: at most 30 deg/s, or 45 deg/s during
  `lerobot-rollout-dagger` resets and exit. Keep its path clear. Lifting the
  arm draws the most current; a weak leader supply shows up as
  `Input voltage error` or missing status packets.
- During a correction torque is off and there is no gravity compensation:
  support the arm.
- Leader faults (stale feedback, drift, alignment timeout) or losing browser
  focus freeze the session and hold the leader.
- Motors stay energized after exit; support the arms before switching off
  power. This is a best-effort hold, not an emergency stop.

## Tests

```bash
python -m pytest -q source/sim_to_real_so101/test
node --test source/sim_to_real_so101/test/test_browser_controls.cjs
```

The unit tests use simulated leader hardware; the GPU test records and decodes
correction videos. Neither replaces a supervised check on the physical arms.
