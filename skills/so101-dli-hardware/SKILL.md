---
name: so101-dli-hardware
description: Help students check the prepared SO-101 station, identify leader/follower and cameras, follow calibration, and complete supervised Real Teleop.
---

# Follow calibration and Real Teleop

Read [workspace](../../docs/07-using-workspace.md),
[calibration](../../docs/07-calibrating-so101.md),
[operation and safety](../../docs/08-operating-so101.md).
Use current device identity and calibration, not the defaults in `docker/env`
(which assign both arms to ttyACM0 and are only a template).

## Use the prepared student station

Start with the assembled classroom station. Follow the workspace lesson to
check light, rack/vial placement, camera view, clamps and cable clearance. Keep
the laptop outside the leader movement area. Refer assembly or PC deployment
issues to the TA; guide the student through calibration and Teleop themselves.

Before powered robot operation establish the operator's presence, clear motion
area, identified arms, reachable power-off and current task readiness.
Reuse explicit readiness while it remains current; recheck after device/pose
changes or a later session. Do not start motion merely because an earlier
chat's experiment was authorized.

## Identity and ownership

1. Inspect /dev/serial/by-id and /dev/v4l/by-id, USB identities and container
   device mounts. Record leader and follower separately.
2. Identify the process currently owning each arm/camera. A second reader can
   disrupt teleop: do not open an occupied port just to check it.
3. Record each arm's serial identity locally and resolve its port afresh after
   reboot; ttyACM numbers can change.
4. Preserve saved calibration and motor-register evidence. Verify six motors,
   zero pose, positive/negative direction, range and deliberate gripper opening
   before policy use. Inspect with read-only methods first; do not force a
   recalibration or “fix” offsets to hide a mismatch.

Five arm joints use LeRobot degrees and simulator radians; gripper uses a
calibrated percentage with this repository's shared conversion. Keep joint
order and `--robot.use_degrees=true` for real policy workflows. Use the course's motion settings; an experimental station's custom speed
setting is not a classroom default.

## Cameras and manual acceptance

Use the course camera procedure to identify **two independent images**:
wrist and external, each at the expected orientation, focus, framing and
640×480/30 Hz settings for policy input. Two /dev/video nodes can belong to one
USB camera. A viewer showing one stream does not establish both policy cameras.

For an authorized supervised teleop step, transfer device ownership cleanly,
hold current pose before torque where the runtime requires it, and observe
actual input and follower motion. Record position/direction and gripper checks,
both camera frame progression, calibration IDs, scoped stop and operator result.
Port access and “connected” messages alone do not pass this checkpoint.

Real rollout homes **before P**. HG-DAgger powers the **leader even in sim**,
including startup/alignment/reset/normal exit; route to
[the HG-DAgger skill](../so101-dli-dagger/SKILL.md) before launching it.
