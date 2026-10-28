# Real Evaluation

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/so101_vial_to_rack_task.gif
:alt: SO-101 performing the vial-to-rack task on physical hardware.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need the calibrated follower, both cameras, assembled workspace, running `so101-workshop` container, and the checkpoint evaluated in simulation.
:::

## Learning Objectives

- Explore the sim-to-real gap by comparing policies trained on sim-only and real-only data on the physical robot.
- Compare policies trained on different types of simulation data, including state-machine and human-teleoperated demonstrations.
- Recognize how overfitting to state-machine data can limit a policy's robustness and lead it to repeat the demonstrations' motion patterns and stopping behavior.

(workspace-prep)=
## Workspace Prep

Review the [Safety](08-operating-so101.md#safety) protocol before running the robot.

1. **Place** one to three vials on the mat and position the rack in its reference location.
2. **Match** camera views and [lightbox setup](05-building-workspace.md#set-up-the-light) used for collection.

(run-the-policy)=
(run-the-first-policy)=
## Run the First Policy: Trained on Sim-Only Data

1. **Continue** in the same container terminal after [stopping simulation evaluation and its background server](11-sim-evaluation.md#stop-evaluation).

:::{dropdown} Reconnect to the Container Shell

If you need to reconnect to the running workshop container, open a terminal on the **host** and run:

```bash
docker exec -it so101-workshop bash
```

To check whether the container is running, use `docker ps` and look for `so101-workshop` in the `NAMES` column. If you are already at the container prompt, skip this step.

:::

2. Inside the container, **select** the model used in sim. Reuse the camera indices you already identified:

```bash
export MODEL_ID=sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/sim-vision-20k.html
```

### What to Expect

This model was trained on 500 state-machine demonstrations in simulation, with no teleoperation or real demonstrations.

At the end of an episode, it will simply hover at the vial drop-off location, since it did not see a "return to home" demonstration. It suffers from overfitting, being biased toward some vial positions and lacking motion diversity.

:::{important}
This policy overfit to the particular grasps and vial positions in its state-machine demonstrations, so expect a low success rate on the real robot.
:::

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
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_newton_dr500_20260923 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "$TASK_INSTRUCTION"
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

3. **Run** an interactive rollout on the real robot:

```bash
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=sreetz-nv/so101_newton_dr500_20260923
```

```{include} _includes/rollout-shortcuts.md
```

:::{tip} Check camera framing during your first rollouts
Before pressing **P**, check the external-camera preview: it should show **most of the rack and some of the robot**, with the vial pickup area visible. If you've already set the correct camera angle, move the props into frame while the robot is paused. The camera has a fairly narrow field of view, so prop positions are important. If the policy struggles, check this framing before trying another model.
:::

:::{dropdown} Understand the command flags

This command uses `--policy.n_action_steps=16` for the action return limit and the separate real-time chunking (RTC) setting `--inference.rtc.execution_horizon=16`. Use the instruction associated with each model's training data. The asynchronous inference engine is selected with RTC compensation disabled.

`--robot.use_degrees=true` keeps the arm joints in degrees, matching the workshop's recorded states and actions. The gripper uses its percentage convention.

The arm automatically moves toward the mean episode-start pose from `sreetz-nv/so101_newton_dr500_20260923`, then waits for **P**. Keep clear during startup. The terminal prints the dataset-derived mean and standard deviation. **Before pressing P**, verify the achieved pose; computing the mean alone does not establish a matched start.

The starting pose matters because it sets the cameras' initial views, the motions the arm can reach, and the trajectory produced by GR00T's relative actions. A pose outside the training dataset's starting distribution can make a capable policy fail for reasons unrelated to its weights. Verify the achieved pose and current gripper calibration before comparing policies. If the pose requires an offset or does not match the dataset distribution, label the trial as an out-of-distribution test rather than a matched evaluation.

The log shows `Waiting | first policy action`, followed by `Running | first policy action after ... s` when the first action is sent. The default `workshop` strategy runs until **Q**, **Esc**, or **Ctrl+C**; `--duration` is ignored.

:::

## Run the Second Policy

1. **Exit** the first rollout with **Q**, **Esc**, or **Ctrl+C** and wait for cleanup to finish.
2. **Select** the policy trained only on simulated teleoperation. Keep your verified wrist and external camera configuration:

```bash
export MODEL_ID=liorbenhorin-nv/so101_sim_manual_perception_newton_20261008_GR00T17_20k
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/sim-teleop-75.html
```

### What to Expect

This model was trained on 75 human teleoperated demonstrations using simulation. These motions contain enough diversity to train a more robust model, even though there is significantly less demonstration data compared to the first policy. Quality of data is key.

After vial drop-off, the demonstrations return the robot near its start pose. This creates a looping behavior. Notice how the robot will continue to pick vials in a loop. This won't be seen in simulation due to an earlier termination condition when the vial is placed. Compare that behavior with the first policy.

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
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101_sim_manual_perception_newton_20261008 --action_horizon 16 --num_episodes 10 --seed 42 --lang_instruction "$TASK_INSTRUCTION"
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


3. **Run** the second policy on the real robot. Startup moves the arm toward this dataset's mean starting pose; keep clear and verify the achieved pose before pressing **P**.

```bash
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=sreetz-nv/so101_sim_manual_perception_newton_20261008
```

```{include} _includes/rollout-shortcuts.md
```

4. **Watch what happens after placement.** Compare the first policy's lack of a return movement with the second policy's return toward a ready pose and continuation to another vial. Keep clear while it continues, and score or stop the trial using the controls above.

::::::{dropdown} Optional: Try i1: State-Machine-Only Training

1. **Stop** the previous rollout and wait for cleanup, then **select** this model:

```bash
export MODEL_ID=liorbenhorin-nv/so101_vision_dr_i1_GR00T17_20261013
export TASK_INSTRUCTION="Pick up the vial and place it in the rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, external: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/i1.html
```

### What to Expect

This model was trained on 125 state-machine demonstrations in simulation, with the human-emulation state machine built from teleoperation demonstrations. In our real-robot trials, it succeeded in **8 of 20 trials (40%)**. Watch for missed grasps or rack-slot alignment errors, and notice what it does after placement.

The command uses the initial poses from this model's state-machine training dataset. Verify the achieved starting pose before pressing **P**.

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
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset liorbenhorin-nv/so101_vials_procedural_left_125ep_20261013 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "$TASK_INSTRUCTION"
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
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=liorbenhorin-nv/so101_vials_procedural_left_125ep_20261013
```

```{include} _includes/rollout-shortcuts.md
```

::::::

(johnny42-real-rollout)=
## Optional: Compare Johnny42, Trained on Real Data

[Johnny42](datasets-and-models.md#johnny42-real-to-real-reference) was trained on **50 real-robot demonstrations, not simulation data**. Stop the previous rollout and wait for cleanup, then set the model, instruction, and camera configuration below. Reuse your verified camera indices:

```bash
export MODEL_ID=sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42
export TASK_INSTRUCTION="Pick up the vials and put them in the yellow rack"
export ROBOT_CAMERAS="{ wrist: {type: opencv, index_or_path: $CAMERA_GRIPPER, width: 640, height: 480, fps: 30, fourcc: MJPG}, front: {type: opencv, index_or_path: $CAMERA_EXTERNAL, width: 640, height: 480, fps: 30, fourcc: MJPG} }"
```

```{raw} html
:file: _includes/model-cards/johnny42.html
```

### What to Expect

This model was trained on 50 real demonstrations. Use it to compare a real-data policy with the simulation-trained policies on your station.

This model's training data was collected before we standardized camera names, so it uses `front` for the external camera. Switch back to `external` afterward by running the `ROBOT_CAMERAS` export included with the other model rollouts.

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
lerobot_eval --task Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --server_address localhost:8080 --pretrained_name_or_path "$MODEL_ID" --policy_type groot --policy_device cuda --start_pose_dataset sreetz-nv/so101-clean-up-vials-into-rack-50_20260628_131121 --action_horizon 16 --num_episodes 10 --seed 76000 --lang_instruction "$TASK_INSTRUCTION" --rename_map '{"external":"front"}'
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

**Run the real evaluation** with the same model:

```bash
lerobot-rollout --strategy.type=workshop --policy.path="$MODEL_ID" --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.n_action_steps=16 --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --robot.use_degrees=true --robot.cameras="$ROBOT_CAMERAS" --task="$TASK_INSTRUCTION" --device=cuda --display_data=true --inference.type=rtc --inference.rtc.enabled=false --inference.rtc.execution_horizon=16 --inference.queue_threshold=0 --start_pose_dataset=sreetz-nv/so101-clean-up-vials-into-rack-50_20260628_131121
```

```{include} _includes/rollout-shortcuts.md
```

## Key Takeaways

- Overfitting to particular grasps and vial positions can yield high simulation evaluation success rates that do not translate to reliable real-world performance.
- The first policy's state-machine demonstrations did not include a return after release, so it does not learn a complete repeating loop.
- The second policy's teleoperated demonstrations include continuation after placement. Watch how this supports returning to a ready pose and attempting another pickup.
- A learned return is different from the rollout controller's homing after **S/F** or **N**. Compare what the policy does before you end the trial.
- Match the starting pose to each policy's own training data, and record the behavior you observe.

## What's Next?

Continue to [Strategy 2: Co-Training With Real Data](13-strategy2-cotraining.md).
