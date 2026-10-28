# Teleoperating

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/rerun_viewer_teleop_hq.gif
:alt: Camera views and joint signals from SO-101 teleoperation in Rerun.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need the calibrated SO-101 robot, leader arm, both cameras, and the Docker container running from [Calibrating the SO-101](07-calibrating-so101.md).
:::

In this session, you'll teleoperate the SO-101 using the leader arm. 

This will give you a sense of the task difficulty by doing it yourself, and also understand how demonstrations can be collected by operators.

We'll also configure cameras, and run teleoperation with live camera views in Rerun.

Make sure you have completed [Calibrating the SO-101](07-calibrating-so101.md) first. You'll need a calibrated robot and the Docker container running with environment variables set.

:::{tip}
If you encounter hardware issues during this session, see the [Troubleshooting Guide](troubleshooting.md) for solutions to common problems.
:::

## Learning Objectives

By the end of this session, you'll be able to:

- **Teleoperate** the robot using the leader arm

- **Configure** cameras so you can teleoperate using the same camera views our AI models will use, and Rerun for debugging


(safety)=
## Safety

Before powering on or running policies:

- **Pinch hazard:** The gripper and moving joints can trap fingers. Keep hands clear of the follower arm while motors are enabled, and keep fingers away from the leader arm’s joints as you guide it.
- Verify cables are routed to avoid snagging during motion.
- Be ready to stop execution with **CTRL+C** or unplug power cables if needed.
- Re-check workspace placement after moving any equipment.

## Teleoperation (no cameras)

Now that both arms are calibrated, we're ready to begin teleoperating!

First, let's just use our eyes - no cameras.

1. **Position both arms in similar poses before starting teleoperation.** The follower will move to match the leader arm.

2. **Begin** the teleoperation process.
```bash
lerobot-teleoperate --robot.type=so101_follower --robot.port=$ROBOT_PORT --robot.id=$ROBOT_ID --teleop.type=so101_leader --teleop.port=$TELEOP_PORT --teleop.id=$TELEOP_ID
```

3. **Move** the leader arm and watch how the follower arm moves to match.

4. **Try** to pick up a vial and place it in the rack!

5. **Press Ctrl+C** in the terminal to stop the teleoperation.

## Camera Setup

The teleoperation you just did used an incredible vision system: your human perception system.

Our AI model will not have this information, so we need to use the cameras instead when we collect demonstrations.

Each robot workspace today is equipped with **two cameras**:
- **Gripper camera**: Mounted on the robot's wrist, just before the gripper
- **External camera**: Stationary camera viewing the workspace from the side

Because the policy works off of these visual images, camera assignment is critical to policy performance. If they are swapped, the policy will fail.

:::{dropdown} Why Two Cameras?
The gripper camera becomes partially occluded after the robot grasps an object like a vial.

And to place the vial vertically into the rack, the camera is pointed more at the walls of the lightbox than the target rack.

The external camera provides continuous visibility of the workspace throughout the entire manipulation sequence, ensuring the policy always has usable visual input even when the gripper camera is blocked.
:::


### Finding Available Cameras

Similar to the port finder, LeRobot has a tool for identifying available cameras.

We need to determine the id of both the camera on the robot, and the external stationary camera.

1. **Make sure** the two cameras' USB cables are plugged into your computer.

2. **Run** the command:

```bash
lerobot-find-cameras opencv
```

This command captures an image from each available camera, allowing you to determine the index of each camera.

The command reports camera indices and saves preview images under `outputs/captured_images`. Use the printed paths to inspect the images.

3. **Open the captured images** by running this command **outside the container**, in a host terminal at the repository directory:

```bash
open ./outputs/captured_images/
```

The container's `outputs/` directory is mounted there, so these are the images you just captured.

4. **Open** each image and **note** which index corresponds to the wrist and stationary camera. For instance, `opencv__dev_video0.png` indicates an index of `0`.

```{figure} images/camera-identification-indices.png
:alt: Camera preview windows with index 0 circled in the wrist image filename and index 4 circled in the external image filename.
:width: 100%

In this example, camera **0** is the wrist view and camera **4** is the external view. Use the indices from your own captured images.
```

5. At the same container prompt, **assign** these environment variables using the indices you verified:

```bash
setenv CAMERA_GRIPPER=4 # make sure to update to your values
setenv CAMERA_EXTERNAL=6 # make sure to update to your values
```

:::{important}
**Camera Index Warning**

Camera indices may change any time cameras are unplugged or replugged into your computer, typically when more than one is unplugged at a time.

If you see unexpected behavior during policy execution, camera index reassignment is a common cause.
:::

:::{tip}
Having camera or hardware issues? 
See the [Troubleshooting Guide](troubleshooting.md), also available on the sidebar, for common solutions and detailed diagnostic steps. 

See the [Quick Reference](quick_reference.md) for common commands.
:::

## Teleoperation With Cameras

Now that we have the camera indices, we can run teleoperation with the real cameras in your workspace.

1. **Put both arms in similar positions before starting.** The follower arm will move to match the leader when teleoperation starts, so keep clear of its path.

2. **Run** the command:

```bash
lerobot-teleoperate --robot.type=so101_follower --robot.port=$ROBOT_PORT --robot.id=$ROBOT_ID --teleop.type=so101_leader --teleop.port=$TELEOP_PORT --teleop.id=$TELEOP_ID --display_data=true --robot.cameras='{ "wrist": { "type": "opencv", "index_or_path": '"$CAMERA_GRIPPER"', "width": 640, "height": 480, "fps": 30 }, "external": { "type": "opencv", "index_or_path": '"$CAMERA_EXTERNAL"', "width": 640, "height": 480, "fps": 30 } }'
```

::::{figure} images/rerun_viewer_teleop_hq.gif
:alt: Rerun Viewer Teleop Example
:width: 650px

Rerun Viewer Teleop Example
::::

This will launch the teleoperation interface. You should see two cameras, one on the wrist and one externally mounted on the lightbox. Make sure your camera views and props roughly match this setup. 

This is a valuable tool for both teleoperation and debugging.

3. Now using the **Rerun** viewer that opened, **try** picking up vials and placing them in the rack **only using the camera views**, not your eyes. See if you can perform the task a few times.

We'll spend some time here - try to do several picks. Emphasize smooth, direct movements. Don't hesitate, move with intention.

:::{note}
Notice what makes this task challenging: 
- the gripper camera becomes partially occluded after grasp
- the rack requires precise placement
- lack of depth data makes rack alignment difficult
:::

4. **Press Ctrl+C** to stop the teleoperation.

5. **Close** the Rerun viewer if it's still open.

## Key Takeaways

- Camera assignment directly affects policy performance
- Task difficulty - gripper camera becomes occluded after grasp, external camera provides continuous visibility
- The Rerun viewer is a valuable debugging tool for verifying camera views and robot state

## Resources

- [SO-101 Getting Started Guide](https://huggingface.co/docs/lerobot/en/so101) — Full assembly, motor setup, and calibration instructions
- [Rerun](https://rerun.io/) — A tool for visualizing camera views and robot actions
