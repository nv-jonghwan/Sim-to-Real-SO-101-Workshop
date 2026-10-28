# Workshop checks

Run from `/workspace/Sim-to-Real-SO-101-Workshop` inside the workshop container:

```bash
uv pip install -e "source/sim_to_real_so101[dev]"
python -m pytest -q source/sim_to_real_so101/test
```

The suite covers these workshop contracts:

- Joint order, sim/real conversion, and camera selection on real task configs.
- Separate 10-sample follower/teleop calibration statistics, arm selection,
  file-only checks, mocked live reads, and zero-variance range warnings.
- Teleop observation/action timing, recording cadence, and reset boundaries.
- DAgger pause/align/guide/handback transitions, leader holds and faults, taught
  rest return, stale policy replies, browser focus loss, and the streaming writer.
- Scripted recording of applied joint targets and acceptance of successful episodes.
- Background episode encoding, acceptance-order merging, rejection of existing output,
  and decoded two-camera frames with unchanged encoded video files after merge.
- Base/DR/Expanded-DR composition, coordinated layout containment and accessibility,
  rejected-layout termination snapshots, base asset materials, and
  independent camera/tile RGB blur with alpha and depth preserved.
- Procedural motion sampling, actual-pose initialization, calibrated opening
  limits, and selective resets. Selection rejects obstructed approaches under
  rotated, mirrored, and cloned layouts.
- Contact-gated acquisition, insertion, seating, and return; fixed-finger release
  compensation; bounded IK preload and non-finite input isolation. Rotated-base
  checks preserve world-up motion and insertion measurements.
- Gripper overload duration, streaming commands, interruption, reversal, and
  selective resets. The GPU check drives both grippers against a joint stop,
  verifies MJWarp's applied torque at the protected ceiling, resets one gripper,
  and confirms reopening without changing the fitted stiffness or damping.
- Two environments in each of DR and Expanded-DR stepping in Newton, rendering both cameras,
  responding to an arm command, holding each mat at its randomized reset pose
  while stepping, and preserving the unselected environment during a partial reset.
  Camera checks cover DR tilt/zoom limits, partial-reset isolation, and rendered
  external images at the lens and tilt endpoints. An exhausted Expanded-DR layout
  search terminates and recovers only the affected environment.

The simulation test requires an NVIDIA GPU and access to the robot USD assets.
Initial asset downloads and OVRtx shader compilation can take several minutes.
It uses temporary files and does not need a robot, display, dataset, or policy server.
For a quick check without starting the simulator:

```bash
python -m pytest -q source/sim_to_real_so101/test -m unit
```

Browser key handlers, and the control label for every DAgger phase, are tested
with Node on the host (no browser or GPU):

```bash
node --test source/sim_to_real_so101/test/test_browser_controls.cjs
```

Recording timing tests use fake hardware/sensor buffers to make frame ordering
deterministic. The background recorder also encodes and decodes small synthetic
videos through LeRobot; this does not establish encoding throughput during
simulation, training quality, or policy performance.
The simulation check detects missing/blank images; it cannot judge image quality
or reliable grasps. Before a workshop, use the recording and evaluation flows in
[E2E_Workflow.md](../../../E2E_Workflow.md), inspect both camera views, and replay a saved episode.

The tests follow Isaac Lab’s pytest `unit`/`integration` markers and use its
`resolve_task_config`, `launch_simulation`, `reset(env_ids=...)`, and
`scene.get_state()` APIs.

Keep this suite small: add coverage for a workshop failure that these checks
cannot catch. Avoid assertions about private helper structure, copies of
upstream tests, and standalone bug-reproduction scripts in this directory.
