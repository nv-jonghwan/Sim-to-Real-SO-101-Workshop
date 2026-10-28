# Quick Reference

```{image} images/so101_workspace.jpg
:alt: The workshop SO-101 robot and its lightbox workspace.
:width: 100%
:class: course-banner
```

Use one terminal in one `so101-workshop` container for the full workflow. Finish or stop each exercise before running the next. Commands below run inside it unless labeled **host**. See [Get the Code](06-get-the-code.md) for build requirements and mounts.

## Build and Start — Host

Open a terminal on the host and change into the workshop folder in your home directory before building or starting the container:

```bash
cd ~/Sim-to-Real-SO-101-Workshop
docker build -t so101-workshop -f docker/Dockerfile .
mkdir -p outputs datasets models
xhost +
docker run --name so101-workshop -it --rm --privileged --runtime=nvidia --network=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v ~/.Xauthority:/root/.Xauthority -v /dev:/dev -v /run/udev:/run/udev:ro -v ~/.cache/huggingface:/root/.cache/huggingface -v ~/.cache/ovrtx:/root/.cache/ovrtx -v ~/.cache/warp:/root/.cache/warp -v ./docker/env:/root/env -v ./source:/workspace/Sim-to-Real-SO-101-Workshop/source -v ./outputs:/workspace/Sim-to-Real-SO-101-Workshop/outputs -v ./datasets:/workspace/Sim-to-Real-SO-101-Workshop/datasets -v ./models:/workspace/Sim-to-Real-SO-101-Workshop/models so101-workshop:latest
```

Keep the resulting container prompt open for all commands below. An extra shell is optional; see [container shell recovery](container-shell-recovery) if you need to reconnect.

## Connect to a Running Container — Host

If the workshop container is already running, open a shell from a **host terminal**:

```bash
docker exec -it so101-workshop bash
```

To check whether it is running, optionally list running containers and look for `so101-workshop` in the `NAMES` column:

```bash
docker ps
```

## Identify and Calibrate Hardware

```bash
lerobot-find-port
lerobot-find-cameras opencv
```

Inspect camera previews under `outputs/captured_images`. Replace these example assignments with your station's values:

```bash
setenv ROBOT_PORT=/dev/ttyACM0
setenv TELEOP_PORT=/dev/ttyACM1
setenv ROBOT_ID=orange_robot
setenv TELEOP_ID=orange_teleop
setenv CAMERA_GRIPPER=2
setenv CAMERA_EXTERNAL=0
```

`setenv` persists settings in mounted `docker/env`. New container shells load them automatically.

```bash
lerobot-calibrate --teleop.type=so101_leader --teleop.port="$TELEOP_PORT" --teleop.id="$TELEOP_ID"
lerobot-calibrate --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID"
python docker/scripts/so101_check_calibration.py
lerobot-teleoperate --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --teleop.type=so101_leader --teleop.port="$TELEOP_PORT" --teleop.id="$TELEOP_ID"
```

See [Calibration](07-calibrating-so101.md) and [Camera Setup](08-operating-so101.md#camera-setup).

For both arms, **skip wrist roll during the range sweep**; LeRobot sets its range automatically. Still match the initial calibration pose.

## Manual Follower Control

Stop other robot-control processes first. Normal control moves to the initial pose and returns home on exit:

```bash
python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_control.py --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID"
```

Add `--passive_mode=true` for hand-guiding with torque disabled, or `--rerun=true` for telemetry. For individual joint control:

```bash
python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_manual_control.py --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID"
```

Up/Down selects a joint, Left/Right moves it, Z commands zero, and Q/Escape exits.

## Simulation and Recording

Physics-only check:

```bash
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras none presets=newton --visualizer newton
```

Teleoperation with both cameras:

```bash
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --browser-display presets=newton,ovrtx_renderer
```

Record (keep the username placeholder for local-only collection; use your own username if uploading):

```bash
export HF_USER=your_hf_username
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --repo_id "${HF_USER}/so101_teleop_vials_newton" --task_name "Pick up the vial and place it in the rack"
```

Focus [http://localhost:8090](http://localhost:8090): **Space** starts/saves, **C** discards, **R** discards and resets. Wait for saving to finish before exiting. Add `--resume` to append to the same dataset. Use only one browser tab connected to the viewer at a time.

```bash
lerobot-dataset-viz --repo-id "${HF_USER}/so101_teleop_vials_newton" --root "./datasets/${HF_USER}/so101_teleop_vials_newton" --episode-index 0
hf auth login
export DATASET_ID="${HF_USER}/so101_teleop_vials_newton"
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

For later uploads to the same dataset, {ref}`refresh its tag <refresh-dataset-tag>`.

## Automated Simulation Collection

Stop any running simulation client before starting another. Preview without recording:

```bash
vials_state_machine --task Newton-So101-Auto-Vials-State-Machine-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --visualizer newton
```

Stop the preview with **Ctrl+C**, then collect 100 successful episodes with domain randomization. Keep the username placeholder if you do not plan to upload:

```bash
export HF_USER=your_hf_username
vials_state_machine --task Newton-So101-Auto-Vials-State-Machine-DR-v0 --record --num_episodes 100 --repo_id "${HF_USER}/so101_auto_vials_newton" --task_name "Pick up the vial and place it in the rack" --cameras all --browser-display presets=newton,ovrtx_renderer --visualizer newton
```

Wait for the target and final dataset export; this recorder stages episodes before assembling the dataset. Then inspect and upload:

```bash
lerobot-dataset-viz --repo-id "${HF_USER}/so101_auto_vials_newton" --root "./datasets/${HF_USER}/so101_auto_vials_newton" --episode-index 0
hf auth login
export DATASET_ID="${HF_USER}/so101_auto_vials_newton"
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

See [Automated Data Collection](08-simulation-teleoperation.md#optional-automated-data-collection) for the complete sequence.

## GR00T 1.7 Training and Evaluation

Use the complete [training command](10-groot.md#reference-post-train-your-own-model), with `--policy.type=groot` and `--policy.base_model_path=nvidia/GR00T-N1.7-3B`.

Set `DATASET_NAME=so101_teleop_vials_newton` for the teleoperation example or `DATASET_NAME=so101_auto_vials_newton` for automated collection. Define the model and output variables after choosing the dataset. Training uses 20,000 steps, saves every 5,000 steps, and writes under `outputs/train/<user>/<model>`; choose the single-GPU or multi-GPU command for your machine.

For sim evaluation, start the policy server once in the background of the same container terminal:

```bash
mkdir -p outputs
python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080 --fps=30 --inference_latency=0 > outputs/policy-server.log 2>&1 & POLICY_SERVER_PID=$!
python -c "import grpc; grpc.channel_ready_future(grpc.insecure_channel('localhost:8080')).result(timeout=60); print('Policy server ready')"
```

After `Policy server ready`, select the course sim-only policy at the same prompt, or replace it with your own checkpoint:

```bash
export MODEL_ID=sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_newton_dr500_20260923 --action_horizon 16 --num_episodes 10 --lang_instruction "Pick up the vial and place it in the rack" --seed 76000
```

```{raw} html
:file: _includes/model-cards/sim-vision-20k.html
```

Use `your_hf_username/so101_auto_vials_newton_GR00T17` for the automated-data example, or set `MODEL_ID` to the absolute path of a local `pretrained_model` directory. Keep using this container shell.

See [Selected Policies](datasets-and-models.md#current-model-selection) for Johnny42, the 94% simulation policy, and the co-trained checkpoint. See [Sim Evaluation](11-sim-evaluation.md) for scoring and camera compatibility. For the physical robot, follow [Real Evaluation](run-the-policy), which uses `lerobot-rollout` in this same container.

`lerobot-rollout` moves to the dataset-derived starting pose specified in the evaluation command, then waits for **P**. When changing models, also change `--start_pose_dataset` to the matching training dataset.

```{include} _includes/rollout-shortcuts.md
```

Wait for `Paused` before resetting props. Scored trials are saved when recording is enabled. The default `workshop` strategy ignores `--duration`; end trials manually. See the [real rollout instructions and controls](run-the-policy).

After evaluation returns to the prompt, stop the background server before real rollout or training:

```bash
kill "$POLICY_SERVER_PID"
wait "$POLICY_SERVER_PID" || true
unset POLICY_SERVER_PID
```

Or **stop all policy servers** in the container:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

If server readiness fails, inspect `tail -n 40 outputs/policy-server.log` before retrying. See [Sim Evaluation](11-sim-evaluation.md#run-policy-evaluation) for the full startup and cleanup sequence.

## Common Issues

| Symptom | Check |
|---------|-------|
| All motors missing | Correct arm power supply and connection |
| One motor missing | Motor cable and power cycle |
| Camera or serial index changed | Repeat detection and update saved settings |
| No simulated images | Explicit `--cameras all presets=newton,ovrtx_renderer` |
| Browser controls inactive | Focus browser; use `--browser-display` |
| Policy cannot connect | Confirm background server readiness on port 8080; inspect `outputs/policy-server.log` |
| Dataset already exists | Use `--resume` or a different `--repo_id` |

See [Troubleshooting](troubleshooting.md).
