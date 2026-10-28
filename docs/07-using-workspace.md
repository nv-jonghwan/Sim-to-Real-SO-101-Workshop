# Using the Workspace

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{figure} images/so101_workspace.jpg
:alt: Workshop lightbox viewed through its opening, with the robot at the front, yellow rack on the left, black mat on the right, and light overhead.
:width: 100%

Use this layout as your reference: rack on the left, pickup area on the right.
```

Your station is already assembled. Before calibration, teleoperation, or a policy rollout, take a moment to prepare the light and props.

## Turn On the Light

1. **Press the power button** on the light.
2. If the travel lock appears, **press and hold the power button again** until the progress bar completes and the light stays on.
3. Once the lock screen is gone, **press the center button** to increase brightness in 25% increments. Set it to roughly **50–100%** and keep it consistent during collection and evaluation.
4. **Connect the light to power** for a full workshop session.

```{figure} images/light-operation.gif
:alt: Turning on the workshop light and adjusting its brightness.
:width: 400px

The power and brightness controls on the workshop light.
```

## Place the Rack and Vials

**Left and right here mean looking into the lightbox through its open front**, as in the photo above.

- **Keep the rack on the left.** Our workshop policies were trained with this general layout. Moving it to the other side can make the task unfamiliar to the policy.
- **Lay the black mat flat** across the pickup area to the right of the rack.
- **Scatter 1–3 vials on the mat**, with space between them for the gripper to approach. Vary their positions and directions within that pickup area; avoid piles or placing them against the walls.
- **Point the caps roughly toward the back wall.** Caps facing the other way can require the robot to twist sharply to grasp the vial. This is a known limitation of the current task.
- **Leave empty slots in the rack** for the robot to fill.

## Check Before Moving

- Make sure the robot clamp is secure and cables are clear of the arm's motion.
- When you open the camera preview, check that the **external camera** can see the rack and pickup area, and the **wrist camera** has a clear image.
- Pause the robot before reaching in to reset the props. Between trials, return the rack and loose vials to the same general areas.
