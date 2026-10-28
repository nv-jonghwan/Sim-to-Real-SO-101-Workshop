# Calibrating the SO-101

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/teleop-calibration-pose.png
:alt: Positioning the SO-101 leader arm for calibration.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need the SO-101 leader and follower arms, USB cables, and the assembled workspace from [Using the Workspace](07-using-workspace.md).
:::

You'll power on and calibrate both arms, then check their joint ranges. The **leader / teleop arm** is the arm you move by hand; the **follower / robot arm** performs the task.

:::{tip}
If you encounter hardware issues during this session, see the [Troubleshooting Guide](troubleshooting.md) for solutions to common problems.
:::

## Learning Objectives

By the end of this session, you'll be able to:

- **Power on** both arms safely
- **Calibrate** the leader and follower for accurate positioning

## Safety Guidelines

Review the [Safety](08-operating-so101.md#safety) protocol before powering on the robot.

## Powering On the Robot

### Physical Inspection

Before powering on:

1. **Inspect** the robot for any visible damage

:::{warning}
The **leader uses 5V** and the **follower uses 12V**. Do not swap their power supplies.
:::

2. **Connect** the power and USB cables.

3. **Verify** the **power LED** illuminates on the control board at the back of the robot.

4. **Connect** both arms to your computer with USB cables.

### Run the Docker Container for This Course

USB port assignments can change when you reconnect the arms. Usually reconnecting just one won't reassign the value. Use LeRobot's port finder to identify each one, then save the ports for later commands.

1. **Open a terminal on the host** and **change into the workshop folder in your home directory**:

```bash
cd ~/Sim-to-Real-SO-101-Workshop
```

2. **Start** the container from this folder if you haven't already:

```bash
xhost +
docker run --name so101-workshop -it --rm --privileged --runtime=nvidia --network=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v ~/.Xauthority:/root/.Xauthority -v /dev:/dev -v /run/udev:/run/udev:ro -v ~/.cache/huggingface:/root/.cache/huggingface -v ~/.cache/ovrtx:/root/.cache/ovrtx -v ~/.cache/warp:/root/.cache/warp -v ./docker/env:/root/env -v ./source:/workspace/Sim-to-Real-SO-101-Workshop/source -v ./outputs:/workspace/Sim-to-Real-SO-101-Workshop/outputs -v ./datasets:/workspace/Sim-to-Real-SO-101-Workshop/datasets -v ./models:/workspace/Sim-to-Real-SO-101-Workshop/models so101-workshop:latest
```

:::{dropdown} Connect to an Already-Running Container

If the container is already running and you need another terminal, run this on the host. If you are already at the container prompt, skip this step.

```bash
docker exec -it so101-workshop bash
```

:::

The workshop's Python environment and saved settings load automatically.

(identify-the-teleop-arm-port)=
### Identify the Leader Arm Port

3. **Run** this command to start port identification:
```bash
lerobot-find-port
```

4. When prompted, **unplug the leader's USB cable**.

```text
Finding all available ports for the MotorBus.
['/dev/ttyACM0', '/dev/ttyACM1']
Remove the usb cable from your MotorsBus and press Enter when done.
```
5. After removing the cable, **press** **Enter**.

```
The port of this MotorsBus is '/dev/ttyACM2'
Reconnect the USB cable.
```

In this example, `/dev/ttyACM2` is the port assigned by the host computer. It's discovered by a simple diff of connected devices.

6. **Reconnect** the leader and **save** its port. Replace `/dev/ttyACM2` with the port the tool found.
```bash
setenv TELEOP_PORT=/dev/ttyACM2 # replace with the detected leader port
setenv TELEOP_ID=orange_teleop # use this line as-is
```

:::{note}
`setenv` saves these settings in the repository's `docker/env` file so they load in future container sessions.
:::

(identify-the-robot-arm-port)=
### Identify the Follower Arm Port
7. **Repeat** for the **follower**, unplugging and reconnecting its USB cable when prompted.
```bash
lerobot-find-port
```

8. **Save** the follower's port, replacing `/dev/ttyACM0` with the port the tool found.
```bash
setenv ROBOT_PORT=/dev/ttyACM0 # replace with the detected follower port
setenv ROBOT_ID=orange_robot # use this as-is
```

:::{note}
The ID names the arm's calibration file. Use the same ID for that arm in every session.
:::

9. **Check** the saved ports and IDs:

```bash
echo "Teleop port is ${TELEOP_PORT} with id ${TELEOP_ID}"
echo "Robot port is ${ROBOT_PORT} with id ${ROBOT_ID}"
```

10. **Continue** calibration in this terminal.

:::{important}
After reconnecting USB devices, run the port finder again if the assignments have changed. These commands are also on the [Quick Reference](quick_reference.md) page.
:::

## Calibration Process

Calibration aligns encoder readings with the physical positions of each link. The policy relies on these joint positions, so incorrect calibration can cause unintended motion, task failures, or collisions.

Follow the same process for both arms: calibrate, then check.

(calibrate-the-teleop-arm-leader)=
### Calibrate the Leader Arm

1. **Run** the leader calibration command using the port and ID you saved:

```bash
lerobot-calibrate --teleop.type=so101_leader --teleop.port=$TELEOP_PORT --teleop.id=$TELEOP_ID
```

2. When prompted, **move each joint to the middle of its range**. That ends up looking like this pose, which you can simply match:

::::{figure} images/teleop_arm_neutral_pose.jpg
:alt: Leader arm in its calibration pose.
:width: 350px

Leader calibration pose
::::

3. **Press Enter** once the arm matches the pose.

4. **Move** each joint **except wrist roll** through its full range, one at a time.

::::{figure} images/teleop_calibration.gif
:alt: Moving the leader joints through their calibration ranges.
:width: 350px

*Example calibration motion. Start in the calibration pose, then sweep the other joints one by one; wrist roll does not need a sweep.*
::::

:::{tip}

- You can sweep a joint more than once if needed. The script records its minimum and maximum positions. If you miss a joint, run calibration again.
- **Reach the mechanical end stops.** Keep cables and other obstacles clear so they don't stop a joint early and produce an incorrect calibration.
- In these newer versions of LeRobot, **wrist roll does not need a range sweep** on either arm. Its range is assigned automatically, but you must still place it in the initial calibration pose shown below. It's fine if you do move it.
:::

5. **Press Enter** when done.

(check-the-teleop-arm-leader)=
(check-the-leader-arm)=
6. **Check the leader calibration** before moving on to the follower. The checker uses your saved `TELEOP_ID` and `TELEOP_PORT`.

```bash
python docker/scripts/so101_check_calibration.py --arm teleop
```

7. **Check** that the report says `Arm: teleop` and names your calibration file. For any `WARN` or live `OUT OF RANGE` result, check the arm ID and joint travel. Correct any problems, then recalibrate and run the check again.

:::{dropdown} Optional: how the calibration check works

The reference data comes from WowRobo robots calibrated for a live version of this workshop. The checker compares each arm against its own reference dataset: 10 teleop calibrations or 10 follower calibrations. It flags motion ranges outside the mean ±2 population standard deviations. When all reference ranges are identical, a different range produces a warning. These are statistical comparisons, not proof that a calibration is correct or incorrect; even a reference sample can fall outside ±2σ.

The checker also reads live encoder positions when the selected arm connects. Look for the “Live Encoder Positions” section and review any `OUT OF RANGE` results. Add `--static-only` to check the saved file without connecting to hardware; a file-only PASS does not verify live positions.

To check a specific file with either arm's command, add `--calibration /path/to/arm.json`. The `STATS_JSON` environment variable can override the selected arm's reference statistics.
:::

(calibrate-the-follower-arm-robot)=
### Calibrate the Follower Arm

1. **Run** the follower calibration command:

```bash
lerobot-calibrate --robot.type=so101_follower --robot.port=$ROBOT_PORT --robot.id=$ROBOT_ID
```

2. **Move** the follower to the calibration pose, with each joint in the middle of its range:
::::{grid} 2
:gutter: 3

:::{grid-item-card}
:img-top: images/calibration_pose.jpg

Calibration Pose Example
:::

:::{grid-item-card}
:img-top: images/wrist_center.jpg

Match this wrist-roll position carefully to prevent its readings from wrapping around.
:::

::::


3. **Press Enter** to begin calibration.

4. **Move** each joint **except wrist roll** through its full range, one at a time.

:::{figure} images/full_so101_calibration.gif
:alt: Full SO-101 Calibration Sequence
:width: 60%

Example calibration motion on the SO-101; skip the wrist-roll sweep.
:::

5. **Press Enter** when done.

(check-the-follower-arm-robot)=
(check-the-follower-arm-calibration)=
6. **Check the follower calibration** before teleoperation. The checker uses your saved `ROBOT_ID` and `ROBOT_PORT`.

```bash
python docker/scripts/so101_check_calibration.py
```

7. **Check** that the report says `Arm: follower` and names your calibration file. Investigate any `WARN` or live `OUT OF RANGE` result before teleoperation. Correct any problems, then recalibrate and run the check again.

LeRobot saves the calibration under `~/.cache/huggingface/lerobot/calibration`, organized by arm type and ID.

::::::{dropdown} Show an example calibration check report

Example follower output from a file-only check:
```
============================================================================
  SO101 CALIBRATION CHECK REPORT
  Arm:   follower
  File:  /root/.cache/huggingface/lerobot/calibration/robots/so_follower/so-r-003.json
  Stats: /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/calibration_stats.json
============================================================================

[1] Motion Range vs Stats (threshold ±2.0σ)

  Joint               Range     Mean    Std  Deviation    Offset  Status
  --------------------------------------------------------------------------
  shoulder_pan         2724     2735     11     -1.03σ       467  ✓ PASS
  shoulder_lift        2390     2367     15     +1.51σ       766  ✓ PASS
  elbow_flex           2226     2222      8     +0.51σ       614  ✓ PASS
  wrist_flex           2340     2323     12     +1.47σ      -564  ✓ PASS
  wrist_roll           4095     4095      0          —     -1457  ✓ PASS
  gripper              1475     1485     18     -0.57σ     -1331  ✓ PASS

[2] Live check skipped (file-only check or arm not connected)

============================================================================
  Overall: ✓ PASS — calibration looks good.
============================================================================
```

::::::

## Match the External Camera Tilt to Simulation

Camera mounts vary between stations. Adjust the real camera to match the view used to train the provided policies.

The simulated camera looks about **54° downward from horizontal**. Use a phone level app to set a similar tilt:

1. **Rest the phone's long edge on the tabletop** and check for a reading near **0°**.
2. **Place that edge against the camera's front face**, running from top to bottom beside the lens.
3. **Adjust the mount** until the edge is about **54° downward**, within a few degrees.
4. In the next lesson, [compare the live view](08-operating-so101.md#teleoperation-with-cameras) with simulation. The robot, rack, and vials should be framed similarly; camera position and field of view matter too.

::::::{grid} 1 2 2 2
:gutter: 3

:::::{grid-item}
::::{figure} images/camera-level-tabletop.jpg
:alt: Phone level resting on the tabletop with a zero-degree reading.
:width: 100%

Set zero on the tabletop.
::::
:::::

:::::{grid-item}
::::{figure} images/camera-level-front-face.jpg
:alt: Phone held against the external camera to check its tilt.
:width: 100%

Check the camera tilt with the phone.
::::
:::::

::::::

## Key Takeaways

- Keep each arm's port, ID, and calibration file together.
- Center wrist roll for calibration, but skip its range sweep.
- Check both calibrations and the camera view before collecting data or running a policy.
