# Train an SO-101 Robot From Sim-to-Real With NVIDIA Isaac

![SO-101 Vial to Rack Task](images/so101_banner.png)

Welcome to this workshop on sim-to-real transfer for the SO-101 robot!

This repository contains the assets and code to accompany this [learning content](https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/index.html).

This fork’s `aidayseoul2026` branch contains the AI Day Seoul 2026 course snapshot, Korean documentation, schedule and shared setup and course skills for environment preparation, hands-on exercises and whole-course Q&A. Students can start with [CODEX](docs/01-codex.md) and [Today’s Schedule](docs/seoul-workshop-schedule.md). Instructor setup is covered separately in [DLI preparation and RTX Laptop setup](docs/2026-10-28-seoul-preparation.md). The public upstream repository remains available at [isaac-sim/Sim-to-Real-SO-101-Workshop](https://github.com/isaac-sim/Sim-to-Real-SO-101-Workshop).

Documentation builds use the `sphinx-nvlearning` extension from NVIDIA’s internal GitLab and require authorized access. This documentation dependency is separate from the workshop Docker runtime.

The rest of this README will help you setup the environment and ensure everything is installed correctly.

You can also use this repo as a basis for trying out your own tasks.

## Requirements

This content was tested on the following GPUs:

- NVIDIA RTX 6000 Pro (Blackwell)
- NVIDIA RTX 5090 (Blackwell)
- NVIDIA RTX 6000 (Ada)

OS and Software tested:
- Ubuntu Linux >22.04
- Docker
- CUDA Toolkit
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)


## Installation

1. Install [Git LFS](#git-lfs) if needed, then clone this repository and build the container:
```bash
git lfs install
cd ~
git clone --branch aidayseoul2026 --single-branch https://github.com/nv-jonghwan/Sim-to-Real-SO-101-Workshop.git
cd Sim-to-Real-SO-101-Workshop
git lfs pull
docker build -t so101-workshop -f docker/Dockerfile .
```

2. Continue with the course instructions [here](https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/datasets-and-models.html).

---

### Starting the workshop container

Open a terminal on the host and change into the workshop folder in your home
directory before starting the container. Its Python environment is active in
the initial shell and in later `docker exec` processes.

_The image enables OVRtx's OVStage scene path. The first OVRtx run may take a
few minutes to warm up shader caches._

```bash
cd ~/Sim-to-Real-SO-101-Workshop
xhost +
docker run --name so101-workshop -it --rm --privileged --runtime=nvidia  --network=host \
   -e DISPLAY \
   -v /tmp/.X11-unix:/tmp/.X11-unix \
   -v ~/.Xauthority:/root/.Xauthority \
   -v /dev:/dev \
   -v /run/udev:/run/udev:ro \
   -v ~/.cache/huggingface:/root/.cache/huggingface \
   -v ~/.cache/ovrtx:/root/.cache/ovrtx \
   -v ~/.cache/warp:/root/.cache/warp \
   -v ./docker/env:/root/env \
   -v ./source:/workspace/Sim-to-Real-SO-101-Workshop/source \
   -v ./outputs:/workspace/Sim-to-Real-SO-101-Workshop/outputs \
   -v ./datasets:/workspace/Sim-to-Real-SO-101-Workshop/datasets \
   -v ./models:/workspace/Sim-to-Real-SO-101-Workshop/models \
   so101-workshop:latest
```

Keep this terminal open and run workshop commands sequentially at the container
prompt. If you need to reconnect or want an optional extra shell, run this on the host:

```bash
docker exec -it so101-workshop bash
```

See [E2E_Workflow.md](E2E_Workflow.md) for recording, training, simulation
inference, and real-robot rollout commands.

## Models and Datasets

Recorded datasets use their Hugging Face repo id as their local path. For
example, `--repo_id user/dataset_1` writes to
`./datasets/user/dataset_1` on the host.

### Downloading model weights

The models used in the course are listed in the course instructions [here](https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/datasets-and-models.html).

You can either download them ahead of time, or as you get to them in the course.

## Tasks

Environments register under the `Newton-So101-*` ids.

#### Teleop
- `Newton-So101-Teleop-Base-v0` — bare arm + ground only
- `Newton-So101-Teleop-Task-v0` — + lightbox + wrist + standalone external camera

#### Production tasks
- `Newton-So101-Teleop-Vials-To-Rack-v0` — main task: pick a vial off the mat and place it in the yellow rack
- `Newton-So101-Teleop-Vials-To-Rack-DR-v0` — same, with domain randomization
- `Newton-So101-Teleop-Vials-To-Rack-Eval-v0` / `-DR-Eval-v0` — success-rate eval against a GR00T policy server

#### Automated collection

- `Newton-So101-Auto-Reach-v0` — 200-step episodes with independent random
  Cartesian targets per environment and differential-IK arm control.
- `Newton-So101-Auto-Vials-State-Machine-v0` — procedural collection with seven
  phases informed by all ten successful
  [real manual demonstrations](https://huggingface.co/datasets/sreetz-nv/so101_real_manual):
  reach, pinch, lift and turn, guide in, open, settle, and return. Each attempt
  generates a path from the actual robot pose, selected vial, and live rack slot.
  Speeds, phase durations, grasp position, opening, and smooth path variation are
  sampled continuously; a shared pace factor coordinates transport and dwell.
- `Newton-So101-Auto-Vials-State-Machine-DR-v0` — the same automated pipeline
  with domain randomization.

The generator uses pooled measurements from dataset revision
`975f14991f6d944f8ae418512998a66a0151e40a` (30 Hz, ten episodes, 8.17–14.70 seconds),
with no stored demonstration trajectories or episode selection. Grasp-point
motion and gripper directions were estimated using robot-model forward
kinematics; contact bands were estimated visually. These measurements provide
motion priors, not exact object poses, contact forces, or guarantees for unseen
layouts.

Targets are computed from current geometry, so vial and rack positions can
change sides and an upright rack can rotate about its vertical axis within the
robot's reachable workspace. Selection excludes distant or obstructed grasps
and occupied rack slots, including open-finger overlap with the rack itself;
joint limits and contact feedback still apply throughout
motion. An attempt without an accessible vial and slot resets before approaching.
Wrist elevation increases with grasp distance using the measured correlation.
Lift targets add 30–55 mm above the insertion pose; lateral carry waits for actual
vial-tip clearance. Gravity directions are expressed in the live robot-base frame.

The first 30 control frames allow the scene to settle while holding the actual
robot pose. This one-second preparation is excluded from recording. Translation
and wrist reorientation begin together in REACH, and the return targets the
saved starting view. Approach opening is sampled between 28% and 43%; every
procedural opening command, including contact clearance, is capped at the
calibrated 50% setting.

Coupled five-joint IK tracks the jaw midpoint and gripper's body-Y direction,
with bounded servo preload and coordinated joint velocity and acceleration limits.
Position and orientation tracking errors slow the phase clock. Contact gates confirm acquisition
and lift; measured vial-tip alignment guides entry before opening permits
seating under gravity. Opening compensates for the moving jaw's contribution to
the midpoint so the arm can hold the fixed finger near its release pose. Contact
must clear before withdrawal advances, and recording requires the selected vial
to remain seated upright through the completed return. Stalled or infeasible
attempts are rejected. Gripper torque follows the shared estimated STS protection
model; invalid IK inputs hold finite targets and reset the affected environment.

Motion generation changes robot commands only. Geometry, cameras, materials,
lighting, render settings, and joint calibration retain the task configuration.
The internal command has seven components (point XYZ, direction XYZ, and jaw
angle); recorded observations and actions retain the canonical six-joint
LeRobot contract and the existing observation-before-action timing.

To request 100 accepted local episodes with both cameras:

```bash
vials_state_machine --num_envs 8 --cameras all --headless-render --visualizer none --record --repo_id user/so101_real_motion --task_name "Pick up the vial and place it in the rack" --num_episodes 100 presets=newton,ovrtx_renderer
```

Use a fresh dataset name for each collection. Data is written under
`datasets/<repo_id>`; existing dataset and staging directories are rejected.

The vials-to-rack DR variants randomize external-camera tilt by ±5° and focal
length between 97% and 100% of nominal at reset, keeping its field of view at
least as wide as the calibrated view. Camera position and wrist-camera
calibration stay fixed. Tiled rendering shares one focal length across
environments, so only full resets resample it; partial resets resample tilt
for the selected environments.

The vials-to-rack DR variants sample robot-base tilt from −3° to +6° at reset.
Positive tilt leans back toward the lightbox opening (world −X), pivoting about
the nominal base position. Each environment keeps its sampled tilt for the
episode; joint calibration and the non-DR base pose stay fixed.

### Wrist-camera alignment

All workshop tasks use the wrist-camera lens and mount in
[`so101_workshop_overrides.usda`](source/sim_to_real_so101/assets/usd/so101_workshop_overrides.usda).
The asset applies a 640 × 480 OpenCV fisheye projection and moves the optical
frame and camera housing together. These settings were visually matched to the
workshop robot; other cameras and mounts need their own checks. Use the same
camera configuration for data collection, training, and evaluation.

[Compare a seeded state-machine episode with the original and fitted cameras](images/wrist-camera-alignment/README.md).

### Base and DR appearance

All vial tasks use matte foam, paper-like vial bodies, and blue-gray lightbox
walls authored directly in the workshop USD assets. Baseline camera profiles
apply gain, gamma, saturation, and external white-point adjustment. They select
`tonemap:operator = "none"` to bypass OVRtx's default ACES approximation and
hand tone mapping to OCIO. DR adds grouped material
brightness/roughness variation, lightbox exposure 1.5–2.25, and sky exposure
−5.5 to −4.5, alongside object placement, mat rotation, robot tilt, and external
camera randomization.

The opt-in `Newton-So101-Teleop-Vials-To-Rack-DR-v0`,
`Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0`, and
`Newton-So101-Auto-Vials-State-Machine-DR-v0` tasks add per-camera
film grain and wrist Gaussian blur sampled at reset
(sigma 0.7–1.1 pixels). External RGB has no added blur. Display, recordings,
and policy observations receive the same processed RGB.

Expanded DR retains all DR appearance settings and samples left, center, and
right rack layouts uniformly, with floor vials on the opposite half of the mat
(a random half for the center layout). Rack and vial XY sampling areas grow by
20%; containment and clearance checks constrain accepted placements. The rack
center stays at least 33 cm from the robot base. Each accepted layout has a
geometrically accessible floor grasp and a clear, reachable rack slot. Exhausted
sampling terminates only the affected environment as unsuccessful.

Use `Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-v0` for teleoperation,
`Newton-So101-Teleop-Vials-To-Rack-Expanded-DR-Eval-v0` for evaluation, or
`Newton-So101-Auto-Vials-State-Machine-Expanded-DR-v0` for scripted collection.
The layout screen does not guarantee IK feasibility or grasp success.

The profiles live in `source/sim_to_real_so101/tasks/camera_profiles.py`.
`SO101OVRTXRendererCfg.camera_responses` exposes render-product attributes
keyed by environment-relative camera path. Its empty default retains native
camera processing; the vial base scene supplies grading and tone mapping,
and DR extends those profiles with `tvNoise`. Both cameras
carry the same mapping so they share one renderer backend.

These profiles approximate camera appearance; they are not sensor calibration.
Use the same task family for collection and evaluation. The base/DR appearance
change invalidates earlier visual training distributions; regenerate datasets
and retrain policies. Use the regular DR task IDs in place of Perception-DR or Vision-DR IDs.

## Commands

- `list_envs` — list registered envs
- `zero_agent` — zero-action debug agent
- `vials_state_machine` — run the automatic vials-to-rack state machine
- `random_agent` — random-action debug agent
- `lerobot_agent` — LeRobot SO101 leader-arm teleop (+ optional dataset recording)
- `lerobot_eval` — success-rate eval against a remote GR00T policy server
- `lerobot_dagger` — collect human corrections during a simulated or real policy rollout;
  see [DAgger](DAGGER.md) for leader handover and recording controls
- `lerobot-rollout-dagger` — collect real-robot corrections inside LeRobot's
  `lerobot-rollout`, with the same controls; see [DAgger](DAGGER.md)
- `lerobot-rollout` — interactive real-robot policy rollout with reset and manual scores

The workshop installs after LeRobot in the image, so its `lerobot-rollout`
command replaces the upstream executable and accepts the upstream arguments. With
the default `--strategy.type=workshop` and `--robot.use_degrees=true`, it moves
the SO-101 to the mean episode-start pose from `--start_pose_dataset=user/dataset`
and waits for **P** to begin. This flag is optional in both this strategy and
`lerobot_eval`: omitting it logs a warning and uses the state-machine starting
pose. With a dataset, they average the first state of every episode and
reuse `datasets/user/dataset` offline when its metadata and data are present.
Missing data is downloaded without videos; existing videos are preserved.

Press **S**/**F** to finish and score a success/failure, or **Right arrow**/**N**
to discard a technical skip without scoring. Both return to the start pose and
pause; **P** starts another trial. With recording enabled, only scored trials
are saved. **Q**/**Esc** exits and discards any unfinished trial.
Inference state is cleared before each trial.
The workshop strategy runs until interrupted (ignoring `--duration`).
Other strategies use upstream behavior.

---

## Simulation and teleoperation

In the active workshop venv, run a physics-only smoke test:

```bash
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras none presets=newton --visualizer newton
```

Camera runs require an explicit camera selection and both renderer presets:

```bash
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras all presets=newton,ovrtx_renderer
```

### Browser sensor display

`--browser-display` streams camera video through WebRTC and joint/action
telemetry through Server-Sent Events. It is mutually exclusive with `--rerun`.
With the container's host networking, open `http://localhost:8090`. While that
page has focus, R resets the environment. When a dataset recorder is configured,
Space starts or stops a take and C discards it. These controls are disabled in
headless, Rerun, and Newton-only modes.

- Port 8090: browser client and telemetry
- Port 49100: WebRTC signaling
- Port 47998: WebRTC media

```bash
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras all --browser-display --port "$TELEOP_PORT" --robot_id "$TELEOP_ID" presets=newton,ovrtx_renderer
```

## Robot setup and utilities

The workshop venv is already active in the container shell. Values such as
`TELEOP_PORT`, `ROBOT_PORT`, `TELEOP_ID`, and `ROBOT_ID` can be stored in
`docker/env`.

### Calibration and direct teleoperation

```bash
lerobot-calibrate --teleop.type=so101_leader --teleop.port="$TELEOP_PORT" --teleop.id="$TELEOP_ID"
lerobot-calibrate --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID"
lerobot-teleoperate --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" --teleop.type=so101_leader --teleop.port="$TELEOP_PORT" --teleop.id="$TELEOP_ID"
```

### Manual robot control

Normal mode moves the follower to its initial pose and returns it home on exit:

```bash
python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_control.py --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID"
```

Add `--passive_mode=true` to disable torque for hand-guiding, or
`--rerun=true` to display live telemetry.

For keyboard joint control, use Left/Right to move the selected joint, Up/Down
to select a joint, `z` to zero all joints, and `q` or Escape to quit:

```bash
python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_manual_control.py --robot.type=so101_follower --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID"
```

Optional flags include `--step-size 5.0` and `--use-degrees`.

### Calibration quality check

The checker compares each joint's calibrated encoder range with the bundled
known-good statistics and, when the robot is connected, verifies its live
position:

```bash
python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_check_calibration.py
```

To regenerate the statistics from the bundled calibration samples:

```bash
python /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/so101_calibration_stats.py --calib-dir /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/sample_callibrations --output-json /workspace/Sim-to-Real-SO-101-Workshop/docker/scripts/calibration_stats.json --output-plot /workspace/Sim-to-Real-SO-101-Workshop/outputs/calibration_stats.png
```

---

## Shared environment setup and course skills

Instructors, TAs and students clone the same `aidayseoul2026` checkout and use
its canonical `skills/<name>/SKILL.md` files. `AGENTS.md` routes natural-language
requests to those files directly. No skill symlinks, personal copies or
role-specific activation are needed; the skill-selector UI is not required.

Use [so101-dli-prepare](skills/so101-dli-prepare/SKILL.md) for the common Host,
Container, models/datasets, precision, runtime checks and handover workflow.
Read [DLI preparation](docs/2026-10-28-seoul-preparation.md) for the current steps.
The requested document profile is the only role selection:

| New setup request | Profile | Documents |
|---|---|---|
| `환경설정을 해줘` without an Instructor request | `student` (default) | Classroom `event` |
| `Instructor용으로 환경설정을 해줘` | `instructor` | Instructor |

Being an Instructor/TA performing day-before installation does not select
instructor documents. Both profiles use the same skills and runtime assets.
State and record the selection; reuse it when continuing the same setup. A
profile change reuses a validated runtime and changes document selection.

```bash
python3 skills/so101-dli-prepare/scripts/setup_plan.py
python3 skills/so101-dli-prepare/scripts/setup_plan.py --profile instructor
```

These commands print plans and execute no installation. The plan builds both languages and initially opens the Korean guide; pass the verified LAN address, available port and agreed commit when
known. Keep source/image/model revisions, selected profile, checkpoint evidence
and the next action in ignored `runs/setup/<station>/progress.md`.

```bash
python3 skills/so101-dli-prepare/scripts/preflight.py --repo . --expected-revision <agreed-commit> --output runs/setup/laptop-01/preflight.json
```

## Building and previewing the learning content

Use the common [documentation skill](skills/so101-dli-docs/SKILL.md) on the Host.
It does not require the robot Container or GPU. Git LFS documentation media must
be hydrated. The locked Sphinx dependency `sphinx-nvlearning` requires authorized
NVIDIA GitLab access; do not replace it with a stub.

From the repository root, prepare the documentation environment and build the
selected profile. The helper defaults to student `event` documents; a plain
Sphinx invocation without course tags remains the optional self-paced learner
build, so use this helper for classroom installation.

```bash
uv sync --frozen
bash skills/so101-dli-docs/scripts/build.sh event all
```

For an explicitly requested Instructor installation, use:

```bash
bash skills/so101-dli-docs/scripts/build.sh instructor all
```

The setup-team and document-profile instructions are included only in
Instructor HTML, navigation and search. Student guides do not advertise the
Instructor build; source copying and source links are disabled for those guides. Outputs are separate: `docs/_build/ko/event/html` and
`docs/_build/ko/instructor/html`. Both languages are built; language switches stay inside the selected guide.

Choose one preview matching the setup profile. Replace `<verified-LAN-IP>` with
the station's actual interface address and use a free port. The preview serves
only its selected guide, even when other build outputs remain on disk.

```bash
python3 skills/so101-dli-docs/scripts/preview.py start --profile student --bind <verified-LAN-IP> --port 8095
python3 skills/so101-dli-docs/scripts/preview.py start --profile instructor --bind <verified-LAN-IP> --port 8095
```

Use only one of these start commands on a given port. An existing owned preview
with a different profile/address is reported instead of being silently reused.
Status reports actual URLs and the PID; its log is `.local/docs-preview.log`.
It remains running after terminal exit and is not configured for boot autostart.

```bash
python3 skills/so101-dli-docs/scripts/preview.py status
python3 skills/so101-dli-docs/scripts/preview.py stop
```

The student URL is `http://<verified-LAN-IP>:8095/ko/event/html/index.html`;
the Instructor URL is `http://<verified-LAN-IP>:8095/ko/instructor/html/index.html`.
Verify the actual HTTP response and desktop browser; keep a requested preview
running. No public tunnel or firewall change is part of setup.

### Explicit maintainer builds

The optional `learner` guide includes self-paced assembly/software lessons.
For document maintenance and verification, explicitly build all six outputs and
use an all-guides preview. These are not the default station setup.

```bash
bash skills/so101-dli-docs/scripts/build.sh all all
python3 skills/so101-dli-docs/scripts/verify_html.py --profile all
python3 skills/so101-dli-docs/scripts/preview.py start --profile all --bind <verified-LAN-IP> --port 8095
```

The MyST `audience` directive supports `learner`, `event`, `student` and `instructor`.
Instructor includes the event lesson flow and the instructor-only setup-team
include. Content outside audience blocks is shared by the selected guides.
