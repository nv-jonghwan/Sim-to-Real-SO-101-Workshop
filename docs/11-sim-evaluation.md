# Sim Evaluation

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/sim-eval-rollout.gif
:alt: Simulated policy rollout with camera observations and joint signals.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need the running `so101-workshop` container, an NVIDIA RTX GPU, and a compatible LeRobot GR00T 1.7 checkpoint.
:::

Evaluate your policy in Isaac Lab 3.0 with Newton physics and ovrtx cameras before deploying it to the physical robot.

## Learning Objectives

- Run simulation evaluation from one terminal in the workshop container.
- Compare base and domain-randomized evaluation conditions.
- Record grasp, placement, and failure behavior.

:::{important} Success in sim does not guarantee success in real
A strong simulation score is a useful starting point, but a higher sim score does not necessarily mean a better real-world policy. Test the same checkpoint on the physical robot and record the two results separately.
:::

Before running trials, check the starting conditions against the selected checkpoint’s training data. An evaluation task’s default reset is not proof that its starts match that dataset.

## Run Policy Evaluation

1. **Use** the existing `so101-workshop` container terminal. Stop any active exercise with **Ctrl+C** and wait for the prompt.

:::{dropdown} Start the Workshop Container

If the container is not running, run this from a **host terminal**:

```bash
cd ~/Sim-to-Real-SO-101-Workshop
xhost +
docker run --name so101-workshop -it --rm --privileged --runtime=nvidia --network=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v ~/.Xauthority:/root/.Xauthority -v /dev:/dev -v /run/udev:/run/udev:ro -v ~/.cache/huggingface:/root/.cache/huggingface -v ~/.cache/ovrtx:/root/.cache/ovrtx -v ~/.cache/warp:/root/.cache/warp -v ./docker/env:/root/env -v ./source:/workspace/Sim-to-Real-SO-101-Workshop/source -v ./outputs:/workspace/Sim-to-Real-SO-101-Workshop/outputs -v ./datasets:/workspace/Sim-to-Real-SO-101-Workshop/datasets -v ./models:/workspace/Sim-to-Real-SO-101-Workshop/models so101-workshop:latest
```

:::

The current `lerobot_eval` connects to a policy server. Start a fresh server for each policy in the background of this shell, leaving the prompt available for evaluation:

:::{important} Stop the policy server before switching policies
Every time you finish evaluating a policy, use one of the [server shutdown options](#stop-evaluation) below **before starting the next policy**: run `kill`, `wait`, and `unset` in the same shell, or stop all policy servers in the container.
:::

```bash
mkdir -p outputs
python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080 --fps=30 --inference_latency=0 > outputs/policy-server.log 2>&1 & POLICY_SERVER_PID=$!
python -c "import grpc; grpc.channel_ready_future(grpc.insecure_channel('localhost:8080')).result(timeout=60); print('Policy server ready')"
```

Wait for `Policy server ready` before continuing. If readiness times out, inspect `tail -n 40 outputs/policy-server.log` and resolve the error before evaluating. The server log stays in the mounted `outputs/` directory. Keep `POLICY_SERVER_PID` in this shell for cleanup; do not start another server while this one is running.

2. At the same prompt, **set** your model repository or local checkpoint directory:

```bash
export MODEL_ID=sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929
```

```{raw} html
:file: _includes/model-cards/sim-vision-20k.html
```

### What to Expect

This model was trained on 500 state-machine demonstrations in simulation. Those demonstrations did not include returning after placement, so expect it to stop rather than repeat the task. Compare its behavior from the default starting pose with the dataset-derived start in the next run.

For your own teleoperation model, use `your_hf_username/so101_teleop_vials_newton_GR00T17`. For the automated collection example, use `your_hf_username/so101_auto_vials_newton_GR00T17`. To evaluate a local checkpoint, set `MODEL_ID` to the absolute container path of your selected `pretrained_model` directory under `models/` or `outputs/train/`. The background server uses the same container filesystem and can read these mounts. See [Download a Compatible Policy](datasets-and-models.md#download-a-compatible-policy).

3. **Run** ten episodes with both cameras, using the default starting pose:

:::{important} Expect a Low Success Rate on this first run.
This is a deliberate starting-pose comparison, where we start the robot in a pose that's out of distribution. The selected policy is expected to struggle from the default pose.
:::

```bash
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "Pick up the vial and place it in the rack"
```

4. **Open** [http://localhost:8090](http://localhost:8090) to watch camera feeds and telemetry. With the page focused, **R** interrupts the current episode and resets the scene. Use only one browser tab connected to the viewer at a time.

5. **Stop** the evaluation with **Ctrl+C** if it is still running, then **stop the policy server** in the same shell:

```bash
kill "$POLICY_SERVER_PID"
wait "$POLICY_SERVER_PID" || true
unset POLICY_SERVER_PID
```

Or **stop all policy servers** in the container:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

### Compare a Dataset-Derived Starting Pose

6. **Restart** the policy server and wait for `Policy server ready`:

```bash
python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080 --fps=30 --inference_latency=0 > outputs/policy-server.log 2>&1 & POLICY_SERVER_PID=$!
python -c "import grpc; grpc.channel_ready_future(grpc.insecure_channel('localhost:8080')).result(timeout=60); print('Policy server ready')"
```

7. **Run** the same evaluation with `--start_pose_dataset` added. Keep the model, task, seed, and episode count unchanged:

```bash
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_newton_dr500_20260923 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "Pick up the vial and place it in the rack"
```

The flag uses the mean joint positions at the start of episodes in the specified dataset, including gripper opening. Check the terminal's `[Start pose]` lines for the dataset name, mean, and standard deviation. This uses a dataset-derived pose rather than sampling a different recorded start each time; the mean alone does not guarantee coverage for every checkpoint.

8. **Compare** the two runs. For this workshop example, we expect a much higher success rate with the dataset-derived start. Did the grasp approach improve? What changed even though the policy weights stayed the same?

### What Happens After the Release?

Notice that the policy does not return home after releasing the vial. Why might that be?

:::{dropdown} Why Doesn't the Robot Return Home?
The state-machine demonstrations used for this model ended without returning home, so they did not teach the policy that part of the task. To teach a repeatable loop, include the movement after release back to a ready pose in the demonstrations, then train and evaluate that continuation. We'll explore this with the next models.

An evaluation reset is separate from this learned behavior: the simulator can reset after a placement without the policy having learned to move home.
:::

### Evaluate Without a Display

::::::{dropdown} Show the evaluation command without a display

To repeat the dataset-derived-start evaluation without a display, **run** without `--browser-display`. Cameras and both presets remain required:

```bash
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_newton_dr500_20260923 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "Pick up the vial and place it in the rack"
```

::::::

(check-camera-compatibility)=
:::{dropdown} Check Camera Compatibility

Current observations use `wrist` and `external`, corresponding to `observation.images.wrist` and `observation.images.external` in LeRobot. A checkpoint trained with these names needs no rename map.

For a compatible older LeRobot checkpoint whose camera features are `ego` and `external_D455`, add `--rename_map '{"wrist":"ego","external":"external_D455"}'`. The direction is **simulation camera name → checkpoint feature name**. Inspect the checkpoint before using a map. Renaming keys does not correct different camera poses, optics, joint conventions, or model formats.

:::

1. **Stop** any active evaluation client with **Ctrl+C** and **keep** the server running.
2. **Run** the same checkpoint under the DR evaluation task:

```bash
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_newton_dr500_20260923 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "Pick up the vial and place it in the rack"
```

See the [camera comparison](10-domain-randomization.md#test-domain-randomization) and [configured Domain Randomization ranges](10-domain-randomization.md#code-tour-domain-randomization-implementation). Use the same episode count and seed (`--seed`) when comparing checkpoints.

## Watch and Record Results

- The terminal reports progress and grasp/placement events.
- Evaluation tasks reset on placement, timeout, or an unsafe rack state.
- A trial counts as successful only when the task's success condition is met without a timeout.
- Safety resets alone do not count as successes.
- Watch the rollouts as well as the summary to understand how the policy fails.

1. **Record** the model, task ID, seed, episode count, action horizon, successful placements, and failure descriptions. Look for missed grasps, drops, rack collisions, and lighting sensitivity.

**Try another environment:** Run the same checkpoint in the base or DR environment, keeping the seed, episode count, and action horizon the same. How do the results change? Consider how differences from the environment used to collect its training data—such as lighting, materials, camera views, or object placement—might affect what the policy sees and how it behaves.

The workshop control and camera cadence is 30 Hz. GPU contention or inference latency can affect observed rollout rate.

## Stop Evaluation

1. **Press Ctrl+C** to stop a running evaluation and wait for the prompt. If all episodes have finished, the prompt is already available.
2. **Stop** the background server in this same shell to free its GPU memory. Run these commands every time you finish with a policy, before evaluating another policy:

```bash
kill "$POLICY_SERVER_PID"
wait "$POLICY_SERVER_PID" || true
unset POLICY_SERVER_PID
```

Or **stop all policy servers** in the container:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

3. **Keep** this terminal and the workshop container open. Before evaluating the next policy in simulation.
