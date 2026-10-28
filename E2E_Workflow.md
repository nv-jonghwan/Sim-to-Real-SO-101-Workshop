# Model Training

## Environment setup

Build and start the workshop container as described in
[README.md](README.md#installation).

Run the following commands in the same container terminal. Stop each exercise
before starting the next.

---

## Record in simulation

```bash
lerobot_agent \
    --task Newton-So101-Teleop-Vials-To-Rack-v0 \
    --cameras all presets=newton,ovrtx_renderer --browser-display \
    --repo_id user/so101_vials_dataset \
    --task_name "Pick up the vial and place it in the rack" \
    --resume
```

Keep the browser page focused while using `Space` to start or save a take, `C` to
discard it, or `R` to discard it and reset the environment.

### Visualize the dataset

```bash
lerobot-dataset-viz \
    --repo-id user/so101_vials_dataset \
    --root ./datasets/user/so101_vials_dataset \
    --episode-index 0
```

### Upload the dataset

After recording and reviewing your episodes, upload and tag the completed
dataset. Replace the example ID with the one used for collection.

```bash
hf auth login
export DATASET_ID=user/so101_vials_dataset
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

Use this same dataset ID for `DATASET` below. For automated collection, wait for
the final dataset export before uploading.

For later uploads to the same dataset, replace the existing tag after the upload
finishes:

```bash
hf repos tag delete "$DATASET_ID" v3.0 --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

## Human corrections during policy rollout

Run a policy in simulation or on the real follower and record corrections made
with the leader arm (HG-DAgger); see [DAGGER.md](DAGGER.md). Merge corrections
with the original demonstrations before fine-tuning, and measure autonomous
success separately.

## Training

```bash
hf auth login
wandb login

export DATASET_NAME=your_data_set
export HF_USER=your_hf_username
export DATASET=$HF_USER/$DATASET_NAME
export REPO_ID="${DATASET}_GR00T17" #this is the model that will be uploaded to huggingface
export OUTPUT_DIR=outputs/train/$REPO_ID

lerobot-train \
  --dataset.repo_id=$DATASET \
  --dataset.image_transforms.enable=true \
  --policy.type=groot \
  --policy.device=cuda \
  --policy.base_model_path=nvidia/GR00T-N1.7-3B \
  --policy.embodiment_tag=new_embodiment \
  --policy.tune_visual=true \
  --policy.tune_llm=false \
  --policy.chunk_size=16 \
  --policy.n_action_steps=16 \
  --policy.use_relative_actions=true \
  --policy.relative_exclude_joints='["gripper"]' \
  --policy.use_bf16=true \
  --policy.push_to_hub=true \
  --policy.repo_id=$REPO_ID \
  --seed=42 \
  --batch_size=64 \
  --steps=20000 \
  --save_checkpoint=true \
  --save_freq=5000 \
  --use_policy_training_preset=true \
  --env_eval_freq=0 \
  --eval_steps=0 \
  --log_freq=10 \
  --output_dir=$OUTPUT_DIR \
  --job_name=$DATASET \
  --wandb.enable=true \
  --wandb.disable_artifact=true

# Multi-GPU:
accelerate launch \
  --multi_gpu \
  --num_processes="$(nvidia-smi -L | wc -l)" \
  "$VIRTUAL_ENV/bin/lerobot-train" \
  --dataset.repo_id=$DATASET \
  --dataset.image_transforms.enable=true \
  --policy.type=groot \
  --policy.device=cuda \
  --policy.base_model_path=nvidia/GR00T-N1.7-3B \
  --policy.embodiment_tag=new_embodiment \
  --policy.tune_visual=true \
  --policy.tune_llm=false \
  --policy.chunk_size=16 \
  --policy.n_action_steps=16 \
  --policy.use_relative_actions=true \
  --policy.relative_exclude_joints='["gripper"]' \
  --policy.use_bf16=true \
  --policy.push_to_hub=true \
  --policy.repo_id=$REPO_ID \
  --seed=42 \
  --batch_size=64 \
  --steps=20000 \
  --save_checkpoint=true \
  --save_freq=5000 \
  --use_policy_training_preset=true \
  --env_eval_freq=0 \
  --eval_steps=0 \
  --log_freq=10 \
  --output_dir=$OUTPUT_DIR \
  --job_name=$DATASET \
  --wandb.enable=true \
  --wandb.disable_artifact=true

```

## Deployment

### In Simulation

#### Start the LeRobot Inference Server in the Background
```bash
mkdir -p outputs
python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080 --fps=30 --inference_latency=0 > outputs/policy-server.log 2>&1 & POLICY_SERVER_PID=$!
python -c "import grpc; grpc.channel_ready_future(grpc.insecure_channel('localhost:8080')).result(timeout=60); print('Policy server ready')"
```

Use the same container terminal for the commands below. Wait for the readiness
message; if it times out, inspect `tail -n 40 outputs/policy-server.log` before
continuing. Start the server only once for a sequence of simulation evaluations.

GR00T is sensitive to the starting pose. Evaluation commands accept an optional
`--start_pose_dataset` pointing to a training dataset. If omitted, they log a
warning and use the state-machine starting pose.

#### Inference in Isaac Lab

```bash
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --pretrained_name_or_path your-hf-user/your-trained-model --start_pose_dataset user/so101_vials_dataset
```

If a checkpoint names the external camera `front`, add
`--rename_map '{"external":"front"}'`. The client sends both images and feature
descriptions under the checkpoint names. Fully qualified names also work:
`--rename_map '{"observation.images.external":"observation.images.front"}'`.

After the evaluation ends, stop the background server from the same shell:

```bash
kill "$POLICY_SERVER_PID"
wait "$POLICY_SERVER_PID" || true
unset POLICY_SERVER_PID
```

Or **stop all policy servers** in the container:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

Keep the container terminal open for real-robot rollout.

### In Real Robot, using `lerobot-rollout`

```bash
export MODEL_ID=your-hf-user/your-trained-model
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"

# Use the same robot ID as calibration, and verify the port and camera indices.
# Find camera indices using `lerobot-find-cameras opencv`.
WRIST_CAM='wrist: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, fourcc: "MJPG"}'
EXTERNAL_CAM='external: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, fourcc: "MJPG"}'
export ROBOT_CAMERAS="{ $WRIST_CAM, $EXTERNAL_CAM }"
# Keep the ROBOT_ID and ROBOT_PORT set during calibration.

lerobot-rollout \
  --strategy.type=workshop \
  --policy.path="$MODEL_ID" \
  --policy.base_model_path=nvidia/GR00T-N1.7-3B \
  --policy.n_action_steps=16 \
  --robot.type=so101_follower \
  --robot.port="$ROBOT_PORT" \
  --robot.id="$ROBOT_ID" \
  --robot.use_degrees=true \
  --robot.cameras="$ROBOT_CAMERAS" \
  --task="$TASK_INSTRUCTION" \
  --device=cuda \
  --display_data=true \
  --inference.type=rtc \
  --inference.rtc.enabled=false \
  --inference.rtc.execution_horizon=16 \
  --inference.queue_threshold=0 \
  --start_pose_dataset=user/so101_vials_dataset \
  --dataset.repo_id=your-hf-user/rollout_recording
```

Both `--dataset.repo_id` (recording) and `--start_pose_dataset` are optional.

The arm homes on startup, then waits for **P**. End trials manually; the default
`workshop` strategy ignores `--duration`. Wait for `Paused` before resetting props.

Keep the rollout terminal focused; keys typed in other applications do not
control the robot. An interactive terminal is required (`docker exec -it`).
Keys are case-insensitive.

| Key | Action |
|-----|--------|
| **P** | Start a trial. |
| **S / F** | Score success/failure, return to the start pose, and pause. |
| **N / →** | Discard the trial, return to the start pose, and pause. |
| **Q / Esc** | Exit and discard any unfinished trial. |



## Automated data collection

Run the vials-to-rack state machine without recording:

```bash
vials_state_machine \
  --task Newton-So101-Auto-Vials-State-Machine-v0 \
  --cameras all \
  --browser-display \
  presets=newton,ovrtx_renderer \
  --visualizer newton
```

Run the domain-randomized state machine and record 100 successful episodes:

```bash
export HF_USER=your_hf_username
vials_state_machine \
  --task Newton-So101-Auto-Vials-State-Machine-DR-v0 \
  --record \
  --num_episodes 100 \
  --repo_id "${HF_USER}/so101_auto_vials_newton" \
  --task_name "Pick up the vial and place it in the rack" \
  --cameras all \
  --browser-display \
  presets=newton,ovrtx_renderer \
  --visualizer newton
```

For left, center, and right rack layouts with the same DR appearance, replace
the collection task above with `Newton-So101-Auto-Vials-State-Machine-Expanded-DR-v0`.
Use `Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-Eval-v0` for matching policy
evaluation, or `Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-v0` for teleoperation.
