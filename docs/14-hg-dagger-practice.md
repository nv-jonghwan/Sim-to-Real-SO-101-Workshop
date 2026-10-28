# HG-DAgger: Collect Corrections

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/so101_rack_task.png
:alt: Physical SO-101 holding a vial above the yellow rack.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You’ll need the current Newton workshop container, a calibrated leader arm, a policy checkpoint, and an NVIDIA GPU. For real collection, you also need the calibrated follower and both cameras.
:::

In this session, you’ll pause the policy, guide it through a correction with the leader arm, and save that correction for training.

:::{important} The leader arm will move
In this lesson, the **physical leader (teleop) arm moves under motor power** during startup, alignment, resets, and normal exit—even when the follower is simulated. Keep its path clear. Support the leader before pressing **G** or **L** to release its torque.
:::

## Learning Objectives

- **Align** the leader, collect a correction, and return control to the policy.
- **Compare** assisted collection with autonomous evaluation.

## Prepare the Workshop Container

Use the instructor-prepared container or the image built in [Get the Code](06-get-the-code.md).

1. **Stop** any teleoperation or evaluation session using the arms or cameras.
2. **Continue** in your workshop container terminal; saved settings load when the shell starts.

Check the saved `TELEOP_PORT` and `TELEOP_ID` for the leader, and `ROBOT_PORT` and `ROBOT_ID` for the real follower. For real collection, verify `CAMERA_GRIPPER` and `CAMERA_EXTERNAL` as in [Camera Setup](08-operating-so101.md#camera-setup), then build the camera configuration in this shell:

```bash
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

Repeat this export after opening a new shell. It uses the `wrist` and `external` camera keys expected by the policy below.

3. **Select** the co-trained checkpoint you want to improve:

```bash
export MODEL_ID=sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011
export HF_USER=your_hf_username
```

```{raw} html
:file: _includes/model-cards/sim75-real10.html
```

### What to Expect

This model was trained on 75 simulated teleoperation demonstrations and 10 real demonstrations. In our real-robot trials, it succeeded in **10 of 20 episodes (50%)**. Watch for a placement that misses the rack slot; those failures are opportunities to pause and collect a correction.

Keep `your_hf_username` for local-only collection, or replace it with your Hugging Face username if you plan to upload. The correction dataset stays local until you upload it.

## Teach the Rest Poses

1. **Support** the leader in its resting position on the bench.
2. **Run** this once per leader calibration:

```bash
lerobot_dagger --teach-rest
```

3. For real collection, **leave** the follower sitting folded, for example right after power-on, and **run** this once per follower calibration:

```bash
lerobot-rollout-dagger --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.disable_torque_on_disconnect=false --strategy.teach_follower_rest=true
```

Both commands save the current position without moving the arm or releasing its torque. Normal exit will return each arm here. Until the follower's rest is taught, exit returns the follower to its pose at startup.

:::{important}
The leader moves under power during startup, alignment, resets, and normal exit. Keep its path clear. Support it before pressing **G** or **L**, which release its torque; there is no gravity compensation. Follow the [robot safety guidance](08-operating-so101.md#safety).
:::

## Start Collection

For the **real follower**, run `lerobot-rollout-dagger`. It runs the collection session inside LeRobot's `lerobot-rollout`, which loads the policy in this process, so no policy server is needed:

```bash
export CORRECTION_ID="$HF_USER/so101_dagger_real_round1"
lerobot-rollout-dagger --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.disable_torque_on_disconnect=false --robot.cameras="$ROBOT_CAMERAS" --strategy.repo_id="$CORRECTION_ID" --strategy.leader_port="$TELEOP_PORT" --strategy.leader_id="$TELEOP_ID" --device=cuda --start_pose_dataset=sreetz-nv/so101_sim_manual_perception_newton_20261008
```

For this exercise, the starting pose comes from the 75 sim-teleoperation demonstrations used in co-training, rather than averaging the entire merged dataset. Startup moves both arms to the mean episode-start pose from that sim dataset. Check the printed starting-pose values before beginning policy execution. Each arm opens its gripper first, then moves its shoulder, elbow, and wrist before turning its base and wrist roll. Remove any held vial before starting or resetting; opening the gripper will drop it.

:::{dropdown} Try collection in simulation instead

The current `lerobot_dagger` simulation command does not support `--start_pose_dataset`; it uses the task's default starting pose. This is not a matched-start comparison with the real collection command above.

Simulation uses `lerobot_dagger` with a policy server. Run these **instead of** the real-follower command. The leader is still a physical arm, but it controls the simulated follower.

1. **Start** a dedicated policy server in the background of this terminal:

```bash
mkdir -p outputs
python -m lerobot.async_inference.policy_server --host=127.0.0.1 --port=8081 --fps=30 --inference_latency=0 > outputs/dagger-policy-server.log 2>&1 & DAGGER_SERVER_PID=$!
python -c "import grpc; grpc.channel_ready_future(grpc.insecure_channel('127.0.0.1:8081')).result(timeout=60); print('Policy server ready')"
```

Wait for `Policy server ready`. If it times out, check `tail -n 40 outputs/dagger-policy-server.log` before continuing. Keep this server dedicated to DAgger: another client connection resets its state.

2. **Start** collection:

```bash
export CORRECTION_ID="$HF_USER/so101_dagger_sim_round1"
lerobot_dagger --task Newton-So101-Teleop-Vials-To-Rack-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address 127.0.0.1:8081 --pretrained_name_or_path "$MODEL_ID" --port "$TELEOP_PORT" --robot_id "$TELEOP_ID" --repo_id "$CORRECTION_ID" --action_horizon 16 --seed 76000
```

3. When finished, **stop** the policy server from the same shell:

```bash
kill "$DAGGER_SERVER_PID"
wait "$DAGGER_SERVER_PID" || true
unset DAGGER_SERVER_PID
```

Keep sim and real corrections in separate datasets, and use different seeds for collection and evaluation.
:::

Open [http://localhost:8090](http://localhost:8090). The session starts **paused** after alignment to the start pose. Keep the page focused for the keyboard controls. Use only one browser tab connected to the viewer at a time.

## Align, Correct, and Hand Back

1. **Press Space** to let the policy run. Watch for the failure you want to correct.
2. **Press Space again** to pause. The follower holds its last command; pausing does not move the leader.
3. **Press Tab** while paused. Let the leader move to match the follower, and **wait for `correction_ready`**. Do not force the powered arm into position.
4. **Support the leader, then press G**. Its torque releases and your correction begins recording.
5. **Guide the leader** through a useful correction—for example, finish the grasp and lift the vial clear of the mat.
6. **Press Space** to hold the leader, save the correction, and return control to the policy. Look for `Episode N saved` to confirm the write.

Repeat as needed within the same rollout:

**Space → Space → Tab → wait → G → correct → Space**

| Key | What it does |
|-----|--------------|
| **Space** | Start or pause the policy; while correcting, save and resume the policy. |
| **Tab**, while paused | Move the leader to match the follower; wait for `correction_ready`. |
| **G** | Release leader torque and begin or continue a correction. |
| **X** | Freeze and hold, keeping the unfinished correction. **G** continues it; **Space** saves it. |
| **C** | Discard the unfinished correction and pause. |
| **R** | Discard the unfinished correction and reset the arms to the start pose. |
| **Esc / Ctrl+C (terminal)** | Exit and return the leader to its taught rest, with torque on. |
| **L** | Release leader torque and exit without moving it. Support the leader first. |

On the **real robot**, use **R** to end a rollout, then reset the objects by hand while paused. Record the outcome yourself: there is no automatic success, timeout, or safety reset. In **simulation**, success, timeout, or an unsafe scene also resets the environment and pauses for the next rollout.

:::{dropdown} Keep the leader near the follower during policy control

Add `--strategy.leader_follows=true` to the real collection command, or `--leader_follows` in simulation. The powered leader tracks the follower during policy motion, which can help when you need frequent corrections. Still pause, press **Tab**, and wait for `correction_ready` before **G**. Tracking is speed-limited, so the leader may lag behind.
:::

## Review and Finish

Save a useful correction with **Space**, or discard it with **C**, before exiting. Normal exit returns the leader to its taught rest. On real hardware, both arms move together through the start pose, each to its own taught rest; both keep torque on. Support them before switching off power.

At the container prompt, **inspect** a saved correction:

```bash
lerobot-dataset-viz --repo-id "$CORRECTION_ID" --root "./datasets/$CORRECTION_ID" --episode-index 0
```

Add `--resume=true` to the real collection command, or `--resume` in simulation, to append more corrections to the same dataset. To start another round separately, change `CORRECTION_ID`.

## What Gets Recorded?

| Part of the session | Recorded? |
|---------------------|-----------|
| Policy rollout | No |
| Pause, alignment, or reset | No |
| Human correction with the leader | Yes, when you save it |

Each saved correction becomes one LeRobot episode. A short grasp, lift, or placement is enough; you do not need to repeat the whole task. Review the episodes before training, and keep simulation and real corrections in separate datasets.

## Evaluate the Updated Policy

Use this provided checkpoint to try a policy trained with corrections. It was trained from GR00T 1.7 base weights on 75 sim demonstrations, 10 real demonstrations, and 29 correction segments. Your newly collected corrections are not included in this checkpoint.

1. **Exit** the correction session and wait for both arms to finish returning to rest.
2. **Select** the corrected model. Keep your verified camera configuration:

```bash
export MODEL_ID=sreetz-nv/so101_real10_sim75_hgdagger29_vision_h16_b64_20k_20261013
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/hg-dagger-20k.html
```

### What to Expect

This model was trained on 75 simulated teleoperation demonstrations, 10 real demonstrations, and 29 human correction segments. In our real-robot trials, it succeeded in **14 of 20 episodes (70%)**. Look for changes in slot alignment and placement, and check that grasping and lifting still work.

Use the sim-teleoperation demonstrations for the starting pose, as in the collection command above. Correction segments begin partway through the task, so their initial frames are not full-task starting poses. Before starting policy actions, verify the achieved pose against the sim demonstrations.

::::{dropdown} Optional: Try This Policy in Simulation First

1. **Stop** the real rollout and continue in the same container terminal. Keep the selected `MODEL_ID` and task instruction.
2. **Start** the simulation policy server below, or reuse it if it is already running.

```bash
mkdir -p outputs
python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080 --fps=30 --inference_latency=0 > outputs/policy-server.log 2>&1 & POLICY_SERVER_PID=$!
python -c "import grpc; grpc.channel_ready_future(grpc.insecure_channel('localhost:8080')).result(timeout=60); print('Policy server ready')"
```

3. **Wait** for `Policy server ready`, then **run** the evaluation:

```bash
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_sim_manual_perception_newton_20261008 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "$TASK_INSTRUCTION"
```

4. **Open** [http://localhost:8090](http://localhost:8090). Use only one browser tab connected to the viewer at a time.

5. **Stop** the background server before running the real policy. If evaluation is still running, press **Ctrl+C** first:

```bash
kill "$POLICY_SERVER_PID"
wait "$POLICY_SERVER_PID" || true
unset POLICY_SERVER_PID
```

Or **stop all policy servers** in the container:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

If reusing a server from another terminal, stop it there instead. Continue with the real rollout below; it loads the policy directly.

::::

3. **Run** the corrected policy on the real robot without intervening:

```bash
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=sreetz-nv/so101_sim_manual_perception_newton_20261008
```

```{include} _includes/rollout-shortcuts.md
```

4. **Compare** with the original co-trained policy under the same starting conditions. Does the vial still miss the slot? Check that any improvement in placement also preserves grasping, lifting, and the return motion. Record your successes and failures, and compare them with the workshop results above.

## Key Takeaways

- Collect corrections where the policy needs help.
- Mix corrections with compatible demonstrations before fine-tuning.
- Test the updated policy without human assistance.

## Resources


- [HG-DAgger: Interactive Imitation Learning with Human Experts](https://arxiv.org/abs/1810.02890) — the original method. This workshop prototype demonstrates manual takeovers, however the paper also explores an uncertainty-based risk measure for deciding when the expert should take over.
- [Reviewing collected demonstrations](08-simulation-teleoperation.md#review-and-upload-collected-data)
- [GR00T Post-Training](10-groot.md)

## What's Next?

Continue to [Strategy 4: Augmenting Datasets With Cosmos](14-strategy3-cosmos.md) to explore synthetic video augmentation for robot training.
