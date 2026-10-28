# Co-Training in Practice

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/so101_rack_task.png
:alt: Physical SO-101 holding a vial above the yellow rack.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need the calibrated SO-101 robot, leader arm, both cameras, the assembled workspace, and the `so101-workshop` container.
:::

In this session, you'll compare a co-trained policy with the sim-only baseline on the physical robot.

## Learning Objectives

By the end of this session, you'll be able to:

- **Deploy** trained policies safely to the physical SO-101 robot

- **Observe** and document real-world policy behavior

- **Identify** initial sim-to-real gap symptoms

## Example Results

These real-robot sessions show a policy trained on **75 simulated teleoperation demonstrations and 10 real demonstrations**. The exercise below uses this Sim75 + Real10 checkpoint.

As you watch, notice the failure modes—most commonly **missing the vial slot in the rack**. Compare them with your own setup: do you see the same misses?

```{raw} html
<figure style="margin: 1.5rem auto;">
  <video controls muted playsinline preload="none" width="1280" height="592" poster="_static/videos/cotraining-sim75-real10-poster.jpg" aria-label="Co-trained policy evaluation on a black SO-101, with external and wrist camera views" aria-describedby="cotraining-sim75-real10-caption" style="display: block; width: 100%; max-width: 56rem; height: auto; margin: 0 auto;">
    <source src="_static/videos/cotraining-sim75-real10.mp4" type="video/mp4">
    <a href="_static/videos/cotraining-sim75-real10.mp4">Watch the evaluation with external and wrist camera views.</a>
  </video>
  <figcaption id="cotraining-sim75-real10-caption">Black SO-101: 10 trials, shown through the external and wrist cameras.</figcaption>
</figure>

<figure style="margin: 1.5rem auto;">
  <video controls muted playsinline preload="none" width="1280" height="720" poster="_static/videos/cotraining-train009-poster.jpg" aria-label="Co-trained policy evaluation on an orange SO-101, with annotated attempt outcomes" aria-describedby="cotraining-train009-caption" style="display: block; width: 100%; max-width: 56rem; height: auto; margin: 0 auto;">
    <source src="_static/videos/cotraining-train009.mp4" type="video/mp4">
    <a href="_static/videos/cotraining-train009.mp4">Watch the annotated evaluation on the orange robot.</a>
  </video>
  <figcaption id="cotraining-train009-caption">Orange SO-101: 11 attempts with outcomes marked in the video.</figcaption>
</figure>
```

In these small-sample tests, changing the robot color and using slightly different vials had **no measurable impact on policy performance**.

## (Optional) Collecting Real Demonstrations With LeRobot

::::::::{audience} learner

Historical datasets are listed in [Datasets and Models](datasets-and-models.md). For this stack, collect compatible real demonstrations and train GR00T 1.7 on your mixed dataset.

::::::::

::::::::{audience} event

**Already prepared for you:** The event datasets and trained models are provided. You do not need to collect, merge, upload, or train data for this exercise. Continue to [Deploy a Co-Trained Policy](#hands-on-deploy-a-co-trained-policy). The dropdown below is a reference for trying the preparation workflow later.

::::::::

:::{note}
Use the same camera names, joint order, normalization, frame rate, and task instruction in simulation and real demonstrations.
:::

::::::{dropdown} Reference: collect and prepare your own co-training data

This recording workflow starts with five new real episodes; this is a separate collection, not the selected checkpoint's training dataset.

1. Use the existing container terminal after stopping any active rollout.

2. If you plan to upload, **log in** with `hf auth login`. Skip this for local-only collection (recommended).

3. **Set** the dataset namespace. Keep the placeholder for local-only collection, or use your Hugging Face username if you plan to upload.
```bash
export HF_USER=your-hf-username
```

4. Run the following command - make sure to set the `dataset.repo_id` argument.


```bash
lerobot-record --robot.type=so101_follower --robot.port=$ROBOT_PORT --robot.id=$ROBOT_ID --robot.cameras='{ "wrist": { "type": "opencv", "index_or_path": '"$CAMERA_GRIPPER"', "width": 640, "height": 480, "fps": 30 }, "external": { "type": "opencv", "index_or_path": '"$CAMERA_EXTERNAL"', "width": 640, "height": 480, "fps": 30 } }' --teleop.type=so101_leader --teleop.port=$TELEOP_PORT --teleop.id=$TELEOP_ID --display_data=true --dataset.repo_id=${HF_USER}/so101-teleop-vials-to-rack-real --dataset.root="./datasets/${HF_USER}/so101-teleop-vials-to-rack-real" --dataset.push_to_hub=false --dataset.num_episodes=5 --dataset.single_task="Pick up the vial and place it in the rack" --play_sounds=false
```

5. Use these controls to control recording:

- **Press Right Arrow (→):** Early stop the current episode or reset time and move to the next.
- **Press Left Arrow (←):** Cancel the current episode and re-record it.
- **Press Escape (ESC):** Stop the session and allow video encoding and saving to finish.

Read more about LeRobot Record here: [lerobot-record](https://huggingface.co/docs/lerobot/il_robots#record-function)

6. **Upload** and **tag** the completed dataset:

```bash
export DATASET_ID="${HF_USER}/so101-teleop-vials-to-rack-real"
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

For later uploads to the same dataset, {ref}`refresh its tag <refresh-dataset-tag>`.

7. **Merge** the local simulation dataset from [Teleoperating in Sim](08-simulation-teleoperation.md#review-and-upload-collected-data) with the real episodes you just recorded:

```bash
export SIM_DATASET_ID="${HF_USER}/so101_teleop_vials_newton"
export REAL_DATASET_ID="${HF_USER}/so101-teleop-vials-to-rack-real"
export DATASET_NAME=so101_vials_sim_real_round1
export MERGED_DATASET_ID="${HF_USER}/${DATASET_NAME}"
lerobot-edit-dataset --new_repo_id "$MERGED_DATASET_ID" --new_root "./datasets/$MERGED_DATASET_ID" --operation.type merge --operation.repo_ids "['$SIM_DATASET_ID', '$REAL_DATASET_ID']" --operation.roots "['./datasets/$SIM_DATASET_ID', './datasets/$REAL_DATASET_ID']" --push_to_hub=false
```

Both input folders must contain completed LeRobot datasets. If you used automated collection, set `SIM_DATASET_ID` to `${HF_USER}/so101_auto_vials_newton` before merging. Use a new output dataset name for each merge. Check that the inputs share camera names (`wrist` and `external`), joint units, task instruction, and 30 Hz frame rate.

This example includes all episodes from both sources without balancing or duplicating them. Longer datasets contribute more training frames; merging does not create a 50/50 sampling ratio or reproduce the selected Sim75 + Real10 model.

8. **Inspect** episodes from both sources in the merged dataset. Simulation episodes come first, followed by real episodes:

```bash
lerobot-dataset-viz --repo-id "$MERGED_DATASET_ID" --root "./datasets/$MERGED_DATASET_ID" --episode-index 0
```

Change `--episode-index` to inspect a real episode too; its first index is the number of simulation episodes in your input dataset. Then **upload** the merged dataset:

```bash
hf upload "$MERGED_DATASET_ID" "./datasets/$MERGED_DATASET_ID" . --repo-type dataset
hf repos tag create "$MERGED_DATASET_ID" v3.0 --repo-type dataset --revision main
```

9. Follow [GR00T Post-Training](10-groot.md#reference-post-train-your-own-model), using `DATASET_NAME=so101_vials_sim_real_round1` instead of its teleoperation-only example. Define the training variables after choosing that name so the dataset, model ID, and output directory refer to this new experiment.

::::::

## Hands-On: Deploy a Co-Trained Policy

Use the selected [Sim75 + Real10 policy](cotrained-reference): a GR00T 1.7 checkpoint trained for 20,000 updates on 75 simulated teleoperation episodes and 10 real demonstrations. It uses a 16-action window with vision trainable and language frozen. The example videos show preliminary real trials; this exercise measures how it performs on your station.

See [model downloads and benchmark conditions](cotrained-reference).

### Workspace Prep

Review [Safety](08-operating-so101.md#safety) before proceeding.

1. **Verify** the follower connection and calibrated robot ID.
2. **Place** the vials and rack in the [workspace](12-real-evaluation.md#workspace-prep) used for the sim-only baseline.
3. **Check** camera assignments and clear their views.
4. **Turn on** the lightbox with the same settings used for the baseline.

### Run and Compare

1. **Use** the same container terminal after the preceding rollout stops, following [Real Evaluation](run-the-policy).
2. **Set** the selected co-trained model, or use the local path from its download instructions:

```bash
export MODEL_ID=sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/sim75-real10.html
```

### What to Expect

This model was trained on 75 simulated teleoperation demonstrations and 10 real demonstrations. In our real-robot trials, it succeeded in **10 of 20 episodes (50%)**. Compare its grasping and placement with the sim-only policy, especially whether the vial tip misses the rack slot.

Use camera keys `wrist` and `external`, with the camera configuration from [Real Evaluation](run-the-policy).

Both commands below use the [merged training dataset](https://huggingface.co/datasets/sreetz-nv/so101_real10_sim75_20261011) to calculate the starting pose from its 10 real and 75 simulated episodes.

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
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_real10_sim75_20261011 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "$TASK_INSTRUCTION"
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

3. **Run** the policy on the real robot:

```bash
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=sreetz-nv/so101_real10_sim75_20261011
```

```{include} _includes/rollout-shortcuts.md
```

4. **Record** successful grasps/placements, recovery attempts, drops, and overshoot across comparable trials.
5. **Score** or **discard** the trial, then wait for `Paused` before resetting props. Press **P** to try again, or **Q / Esc** to exit before changing checkpoints.

::::::{dropdown} Optional: Try i5: Add State-Machine Variation

1. **Stop** the previous rollout and wait for cleanup, then **select** this model:

```bash
export MODEL_ID=liorbenhorin-nv/so101_vision_dr_i5_GR00T17_20261013
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/i5.html
```

### What to Expect

This model first trained on 75 sim-teleoperation and 10 real demonstrations, then trained further on 125 state-machine demonstrations with broader rack layouts. In our real-robot trials, it succeeded in **9 of 20 trials (45%)**. The state-machine variation lets it support some evaluations with the rack on the other side of the workspace. Try that layout and compare grasping and slot alignment with your usual setup.

The command uses the initial poses from this model's second-stage state-machine dataset. Verify the achieved starting pose before pressing **P**.

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
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset liorbenhorin-nv/so101_vials_procedural_all_125ep_20261013 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "$TASK_INSTRUCTION"
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

2. **Run** the policy on the real robot:

```bash
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=liorbenhorin-nv/so101_vials_procedural_all_125ep_20261013
```

```{include} _includes/rollout-shortcuts.md
```

::::::

## Key Takeaways

- Co-training combines sim and real data for better policies
- Document observations systematically—they guide improvement
- The sim-to-real gap is real and often significant
- Different policies exhibit different failure modes

## Resources

- [Isaac-GR00T Repository](https://github.com/NVIDIA/Isaac-GR00T) — Source code for GR00T deployment including SO-101 evaluation scripts
- [SO-101 Finetuning Guide](https://github.com/NVIDIA/Isaac-GR00T/blob/main/examples/SO100/README.md) — Full instructions for finetuning and evaluation
- [Sim-and-Real Co-Training: A Simple Recipe for Vision-Based Robotic Manipulation](https://co-training.github.io/) — RSS 2025 paper on co-training strategies

## What's Next?

Continue to [Strategy 3: HG-DAgger](14-hg-dagger.md) to learn how human corrections can target the failures you observed during real evaluation.
