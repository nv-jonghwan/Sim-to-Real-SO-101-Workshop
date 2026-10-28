# Troubleshooting Guide

```{image} images/rerun_viewer.png
:alt: Rerun camera views and joint plots for inspecting robot behavior.
:width: 100%
:class: course-banner
```

This page consolidates troubleshooting information from across this learning path for easy access.

All workshop commands run in the single `so101-workshop` container with its Python environment active. Keep using the terminal started in [Get the Code](06-get-the-code.md#start-the-workshop-container), stopping each exercise before starting the next. Extra shells are optional; see [container shell recovery](container-shell-recovery).

## Hardware Issues

### First Thing to Try

Unplug power, and replug the power cable. Do this 2X if the next command doesn't run. If that doesn't solve, proceed to the next steps.

:::{dropdown} Robot Doesn't Respond

1. **Check** USB connection
2. **Verify** power LED is on
3. **Try** a different USB port
4. Inside the `so101-workshop` container, **run** `lerobot-find-port` to confirm the port is correct.
:::

:::{dropdown} No Ports Found or Permission Denied on /dev/ttyACM*

If `lerobot-find-port` finds no ports, or you see permission denied when accessing the robot:

First, check the USB connection and confirm that the workshop container was started with the documented `/dev` mount and `--privileged` option. Re-run `lerobot-find-port` at the same container prompt after reconnecting the device.

If permissions still fail and a host-side fix is needed:

1. **Stop** the active exercise, then **exit** the main container shell to return to the host prompt. With the documented `--rm` invocation, this stops and removes the container; mounted files persist.
2. On the **host**, **grant** read/write access only to the connected serial ports you identified (the paths below are examples):

```bash
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1
```

Permissions reset when devices are reconnected; re-run these after unplugging/replugging USB if needed.

3. For persistent **host** access, **add** your host user to the `dialout` group (and `video` for cameras), then log out and back in:

```bash
sudo usermod -a -G dialout "$USER"
sudo usermod -a -G video "$USER"
```

4. **Restart** the workshop container using [Get the Code](06-get-the-code.md#start-the-workshop-container), then verify ports and saved settings.
:::

:::{dropdown} Power Not Connected (All Motors Missing)

If you see this error showing all motors missing:

```
Missing motor IDs:
  - 1 (expected model: 777)
  - 2 (expected model: 777)
  - 3 (expected model: 777)
  - 4 (expected model: 777)
  - 5 (expected model: 777)
  - 6 (expected model: 777)

Full expected motor list (id: model_number):
{1: 777, 2: 777, 3: 777, 4: 777, 5: 777, 6: 777}

Full found motor list (id: model_number):
{}
```

This indicates **power is not connected** to the robot. The USB connection allows communication, but the motors need separate power.

**Solution:**
1. **Connect** the 12V power supply to the robot
2. **Verify** the power LED illuminates
3. **Retry** the command
:::

:::{dropdown} Single Motor Disconnected

If you see an error showing one motor missing:

```
Full expected motor list (id: model_number):
{1: 777, 2: 777, 3: 777, 4: 777, 5: 777, 6: 777}

Full found motor list (id: model_number):
{2: 777, 3: 777, 4: 777, 5: 777, 6: 777}
```

This indicates motor 1 is disconnected or not communicating. Sometimes this will happen unexpectedly, in which case a simple repower should solve it.

**Solution:**
1. **Power cycle**: Unplug and replug the power cable
2. If that doesn't work, **inspect motor cables** for loose connections
3. **Check** the cable connecting to the specific missing motor
4. The motor chain is daisy-chained—a loose connection can affect motors downstream
:::

:::{dropdown} Motor Connection Error

If you see this error:

```
ConnectionError: Failed to write 'Torque_Enable' on id_=2 with '1' after 1 tries. [TxRxResult] There is no status packet!
```

This indicates communication failure with a specific motor.

**Solution:**
1. **Check power**: Ensure the 12V power supply is connected and LED is on
2. **Check USB**: Verify the USB cable is securely connected at both ends
3. **Restart motors**: Power cycle the robot (disconnect and reconnect power)
4. **Check motor ID**: The motor with the specified ID may have a loose connection
:::


::::{dropdown} Calibration Fails

1. **Ensure** the robot port matches the robot.id of the real robot
2. **Ensure** robot is in exact calibration pose
3. **Check** that motors can move freely
4. **Verify** no joint is at a limit
5. **True end stops only** — During the range sweep, move each joint **except wrist roll** to its mechanical end stop, not a cable or obstacle. LeRobot sets the wrist-roll range automatically. A cable pinched between links (or the robot hitting a cable) creates a false min/max and wrong calibration. Check cable routing so the arm can reach its real limits.
:::{figure} images/calibration_cable_snag.gif
:alt: SO-101 arm segment showing cable routing near a joint
:width: 400px
:::

6. **Re-run** calibration from step 1
::::

## Camera Issues

:::{dropdown} Dark or No Image

If the camera feed is very dark or black:

1. **Check the lens cap** — Ensure the lens cap is removed from the camera. This is a common cause of dark or missing feed.
2. **Verify** the camera is powered and connected
3. Inside the `so101-workshop` container, **run** `lerobot-find-cameras opencv` to confirm the camera is detected
:::

:::{dropdown} Camera Index Changed

Camera indices may change any time cameras are unplugged or replugged into your computer.

**Solution:**
1. Inside the `so101-workshop` container, **run** `lerobot-find-cameras opencv` to discover current indices
2. **Update** your configuration with the new indices
3. **Verify** by checking the captured test images
:::

:::{dropdown} Blurry or Out-of-Focus Image

If the camera feed is blurry or the policy has trouble with fine visual detail:

1. **Check focus** — Ensure the camera lens is in focus.
2. **Clean** the lens if it is smudged or dusty
3. **Verify** the camera is fixed in place and not vibrating
:::

:::{dropdown} Wrong Camera Feed

If the policy receives incorrect visual input:

1. **Check** camera assignments match expectations
2. **Verify** the wrist camera and external camera are correctly identified
3. **Re-run** `lerobot-find-cameras opencv` to confirm indices
:::

## Policy Deployment Issues

### CUDA Out of Memory

The most likely cause during workshop evaluation is an extra policy server still running and holding GPU memory. Stop the current evaluation with **Ctrl+C**, then run this in the workshop container to stop all matching LeRobot policy servers:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

Wait for the servers to exit and check GPU memory with `nvidia-smi`. Before retrying simulation evaluation, start just one server using the [startup and readiness commands](11-sim-evaluation.md#run-policy-evaluation). Always [stop the server](11-sim-evaluation.md#stop-evaluation) after finishing with a policy and before starting the next one.

### Inference Is Slow

If real-robot inference is slow, check that you stopped the simulation policy server. It can still use GPU resources. In the terminal where you started it, run:

```bash
kill "$POLICY_SERVER_PID"
wait "$POLICY_SERVER_PID" || true
unset POLICY_SERVER_PID
```

Or **stop all policy servers** in the container:

```bash
pkill -f '[l]erobot\.async_inference\.policy_server'
```

If you started the server in a different terminal, stop it there instead.

(so101-wrist-perception-gap)=
### Compare simulated and real camera images

These two unedited 640 × 480 frames show the visual differences a policy can
encounter when moving from a simulated dataset to the physical workstation.

::::::{dropdown} View an illustrative sim/real camera comparison and its limitations

:::{figure} images/perception-gap-sim-wrist-20260924.png
:width: 640px
:alt: Simulated wrist camera showing orange gripper fingers, a yellow rack, and smooth white vials on a dark mat.

**Simulation.** First wrist-camera frame of episode 0 from
[`sreetz-nv/so101_newton_dr500_20260923`](https://huggingface.co/datasets/sreetz-nv/so101_newton_dr500_20260923),
dataset revision `a08882a61870706727c153beec6ae10ec6747146`.
:::

:::{figure} images/perception-gap-real-wrist-20260924.png
:width: 640px
:alt: Physical wrist camera showing brighter orange gripper fingers, a partly visible yellow rack, a blue-gray mat, and a textured white vial near the image edge.

**Real hardware.** SO-101 wrist-camera frame captured on September 24, 2026,
at 640 × 480 with MJPEG capture configured at 30 FPS.
:::

In this pair, the real image has brighter gripper and rack highlights with
less visible detail. The mat appears blue-gray rather than dark gray, and the
real vial has surface texture and folds absent from the smooth simulated vial.
These differences suggest checking lighting, camera exposure, color response,
and object materials when investigating transfer failures.

:::{note}
The arm pose, gripper opening, and vial layout differ between these frames.
This is an illustrative perception-gap comparison, **not a camera calibration
test**. It does not establish a field-of-view error, a sensor dynamic-range
measurement, or the cause of a policy failure.
:::

For a controlled comparison, reproduce the physical arm's measured joint pose
in simulation, match the vial and rack layout, and record the real camera's
exposure and white-balance settings. Compare the resulting camera images before
changing the simulation. Apply any camera-response adjustment to the images
used for both data collection and policy evaluation, then test its effect on
real-robot performance.

::::::

(wrist-image-alignment)=
### Overlay saved wrist images to inspect alignment

Use the [interactive perception-gap comparison in What Is Sim-to-Real?](perception-gap-comparison) to overlay saved wrist images, adjust simulation opacity, or compare the views side by side. The alternate image pair below provides another comparison.

#### Alternate pair: robot confirmed level

::::::{dropdown} Inspect the alternate image pair and its capture conditions

In this second pair, also captured on September 28, 2026, the operator confirmed
that the physical robot base was level and moved the rack to align it by eye.
The simulation uses the encoder pose captured for this comparison, the elbow
asset correction, and measured lens intrinsics and distortion. It retains the
original authored camera mount; no candidate mount offset is applied. The rack
settled under physics before capture. The loose vials were still moving slightly
and are not alignment references.

```{raw} html
:file: _includes/wrist-image-comparison-level.html
```

The rack corners, hole positions, and gripper outlines align much more closely
in this pair. Brightness, highlights, and surface detail still differ. The real
scene also contains a calibration target absent from simulation. This is a
qualitative alignment example: the rack position was not independently measured,
and both the lens parameters and scene alignment differ from the first pair.
It therefore does not isolate the effect of leveling the base or establish that
the camera mount is calibrated.

::::::

### The arm reaches where there is no vial

When the arm reaches where there’s no vial, find the **first place the observation, prediction, and motion disagree**.

1. **Replay one failed pickup.** Compare the camera image, the image actually sent to GR00T, predicted actions, and executed motion. Is the vial visible in the model’s input?
2. **Move only the vial in simulation.** Keep the arm and cameras fixed. Does the predicted reach follow the vial?
   - Same reach despite moving the vial: investigate visual conditioning or learned position bias.
   - Reach follows but consistently misses: check calibration and action conversion.
3. **Check the action pipeline.** Verify joint order, units, normalization, and relative-action decoding. Make sure relative actions aren’t converted twice.
4. **Try more frequent replanning.** Compare executing 16, 8, and 4 actions before requesting a fresh prediction. Keep the model and test scenes unchanged.
5. **Improve data where failures occur.** Add successful demonstrations with varied vial positions, starting poses, and recovery approaches. Test on layouts excluded from training.

**Change one factor at a time.** Repeat the same scenes and record wrong-location reaches as well as successful pickups. Treat each explanation as a hypothesis until a controlled test supports it.

### Test policy inputs with fixed or “dummy” observations

Run this diagnostic offline, without sending predictions to the physical robot.
A useful test observation starts with a saved, valid observation: both camera
images, the measured joint state, and the task instruction. Retain the checkpoint’s
saved preprocessing and action postprocessing so feature names, image conversion,
normalization, and relative-action decoding match deployment.

::::::{dropdown} Show the offline fixed-observation diagnostic procedure

1. Save the raw camera frames, the corresponding joint state, and the actual
   preprocessed input sent to the model. Check camera assignments, image freshness,
   color order, resizing, and cropping. A live viewer alone does not establish
   what the model received.
2. Predict from that fixed observation repeatedly, resetting any queued action
   chunk between trials. Fix the random seed or repeat enough times to measure
   prediction variability before comparing conditions.
3. Change one input at a time. For a meaningful visual test, render the same
   simulated arm and camera pose with the vial in two different positions.
   Hold the joint state and task text fixed and compare the decoded action chunks.
4. As an additional diagnostic, replace one camera image with a constant image
   of the same shape and type. Keep the other inputs unchanged. This deliberately
   unrealistic “dummy” input can reveal sensitivity to a camera, but a similar
   prediction does not by itself prove that the model ignores vision: the other
   camera, joint state, or a learned action prior may dominate.

Compare predictions offline first. For any simulated rollout comparison, reset
both the environment and the policy’s queued actions between conditions. See the
[perception-gap example](#so101-wrist-perception-gap) for why
matching the arm pose and scene layout matters.

::::::

### Replay a recorded episode on the physical arm

Recorded-action replay bypasses policy prediction. It checks whether the stored
joint commands produce a comparable physical trajectory; it does not test the
policy’s visual reasoning or closed-loop recovery.

1. Inspect a short episode with the dataset viewer. Confirm the robot, saved
   calibration, joint order, units, action convention, and recording FPS. Workshop
   arm actions use native degrees for the first five joints and a percentage for
   the gripper. Use the recorded absolute actions directly; do not apply the
   policy’s relative-action decoding to them.
2. Compare the episode’s starting joint state with the real arm’s measured state.
   Prepare the matching start pose with the supervised positioning procedure;
   replay does not provide a general collision-aware move to the start. For an
   initial motion check, clear the workspace of loose objects and remain at the
   stop control.
3. Inside the workshop container, run the installed LeRobot replay command with
   your dataset and calibrated follower identifiers:

```bash
lerobot-replay --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=<follower_id> --robot.use_degrees=true --dataset.repo_id=<hf_user/dataset_name> --dataset.root=./datasets/<hf_user/dataset_name> --dataset.episode=0 --play_sounds=false
```

4. Stop with **Ctrl+C** if the trajectory deviates. Record the actual joint states
   and camera views with a separate logging setup if quantitative comparison is
   needed; this replay command does not itself save those comparison observations.
   Compare against the episode’s **observed joint states**, as well as its commanded
   actions: commands and measured positions can differ because of lag and contact.
5. If the recorded commands reproduce the same motion but a policy rollout
   does not, investigate policy inputs, prediction, or action-chunk execution.
   If replay diverges too, investigate calibration, joint mapping, gripper
   mapping, actuator response, mounting, and contacts before retraining.

A simulation episode also depends on the asset geometry and joint offsets used
when it was collected. Matching numeric joint values alone cannot establish a
matching physical pose. For a stationary camera comparison, read the real arm’s
encoders and reproduce that pose in simulation without moving the real arm.

:::{dropdown} "It worked once but not consistently"

**Likely cause:** Distribution shift

**Solution:**
- Check if initial conditions vary between trials
- Ensure cameras are stable and haven't shifted
:::

:::{dropdown} "Grasp is always off by the same amount"

**Likely cause:** Calibration or camera positioning

**Solution:**
- Re-run robot calibration
- Check camera positioning
- Verify workspace setup matches training
:::

## Simulation and Display Issues

:::{dropdown} No Simulated Camera Images
Use explicit `--cameras all presets=newton,ovrtx_renderer`. `--cameras none` intentionally disables images. The first ovrtx launch can take a few minutes to warm up caches.
:::

:::{dropdown} Browser Is Blank or Controls Do Not Work
Use `--browser-display` and open `http://localhost:8090` on the host. Focus the browser for keyboard controls. In recording mode, **Space** starts/saves, **C** discards, and **R** discards/resets. Use only one browser tab connected to the viewer at a time.

Use the documented host networking. Browser display uses ports 8090, 49100, and 47998. Stop other display sessions using those ports. `--browser-display` and `--rerun` are mutually exclusive; Rerun/headless modes have no recording keyboard controls.
:::

:::{dropdown} Policy Server or Checkpoint Errors
Follow the background-server startup and readiness check in [Sim Evaluation](11-sim-evaluation.md#run-policy-evaluation) using the same container terminal. The sim client uses `--server_address localhost:8080`.

If readiness times out or evaluation cannot connect, run `tail -n 40 outputs/policy-server.log`. Resolve the reported error before retrying; do not launch duplicate servers on the same port. After evaluation, use the documented [server cleanup](11-sim-evaluation.md#stop-evaluation).

Verify that `MODEL_ID` identifies a LeRobot GR00T 1.7 policy with saved configuration and processors, and that the server can access its local path or Hub repository. A rename map handles feature names only. See [Checkpoint Compatibility](datasets-and-models.md#checkpoint-compatibility).
:::

## Dataset and Recording Issues

:::{dropdown} Automated Collection Has Not Exported a Dataset
`vials_state_machine --record` stages successful episodes and assembles the LeRobot dataset after reaching `--num_episodes`. This is a successful-episode target, not an attempt count. Watch the terminal's collection count and wait for final export before running `lerobot-dataset-viz` or uploading. An early interruption can leave staged episodes without a completed dataset.

Use both cameras with `--cameras all presets=newton,ovrtx_renderer` and provide `--repo_id` and `--task_name`. See [Automated Data Collection](08-simulation-teleoperation.md#optional-automated-data-collection).
:::

:::{dropdown} Training Cannot Find a Locally Recorded Dataset
The lesson's `lerobot-train` command selects a dataset by its Hub ID. Inspect and upload `./datasets/<repo_id>` to the same dataset repository before training. In a new shell, set `HF_USER`, `DATASET_NAME`, and the derived training variables again; ordinary `export` assignments do not carry across shells.
:::

:::{dropdown} Dataset Already Exists
Simulation recording derives its path as `datasets/<repo_id>`. Add `--resume` to append to that dataset, or use a different `--repo_id` for a new collection. Real recording uses `--dataset.repo_id` and `--dataset.root`. Inspect and preserve existing episodes before changing paths.
:::

:::{dropdown} Dataset Missing Images or Final Episodes
Record with both cameras and renderer presets. Wait for the saving indicator to clear and the terminal to confirm each episode is saved. Let **Ctrl+C** shutdown finish before stopping the container.

Use `lerobot-dataset-viz` with the matching repo ID and `--root ./datasets/<repo_id>` to inspect saved data.
:::

## Getting Help

If you're stuck:

1. **Check this guide** for your specific error message
2. **Power cycle** the robot (fixes many transient issues)
3. **Re-run camera detection** if visual behavior is unexpected
4. **Re-run** the diagnostic steps above if the issue persists
