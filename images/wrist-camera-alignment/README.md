# Wrist-camera alignment comparison

## Live viewer reference

| Real wrist camera | Simulation with the approved settings |
|---|---|
| ![Real wrist-camera reference](viewer-real.jpg) | ![Matched simulated wrist-camera view](viewer-sim.jpg) |

These frames come from the live comparison at the matched robot pose, using the
settings in this MR. The camera housing is hidden in the tuning viewer;
collection renders it at the corrected mount pose.

## Seeded collection

[Watch the wrist-camera comparison](wrist-seed42.mp4) · [Watch the external-camera comparison](external-seed42.mp4)

![Original USD camera on the left, fitted fisheye lens and mount on the right](wrist-seed42.jpg)

The left side uses the original `newton` USD camera lens and mount. The right
side uses this MR's fitted fisheye lens and mount, including the matching camera
housing transform. Both recordings use
`Newton-So101-Auto-Vials-State-Machine-Perception-DR-v0`, seed **42**, one
environment, both cameras, and the same state-machine and randomization settings.

Each configuration completed its first episode successfully: **325 frames** with
the original camera and **326 frames** with the fitted camera, at **30 fps**.
The videos align episode timestamps; the original's final frame is held for
one frame (1/30 second). These are independent simulation runs, so joint trajectories are
not numerically identical. Their initial recorded joint states differ by less
than 0.000001 degrees, and their first ten recorded actions are identical.

This compares the camera views during scripted collection. It does not measure
VLA performance or establish calibration accuracy at other poses.

The recordings use source commit `ed9bf08751c03cf4202f9c1448bc9a7689b88af2`;
the original-camera wrapper is unchanged from `newton` commit
`33f56e38a2edaf73f7cef6ea32f03597b84b33ee`.
