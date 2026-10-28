# AGENTS.md — Sim-to-Real SO-101 Workshop

Context for AI coding agents working in this repository.

---

## What this project is

NVIDIA workshop for end-to-end **sim-to-real** transfer of an SO-101 robot
arm (a low-cost LeRobot teleop+follower platform). Flagship task:
"vials → rack" — pick a vial off a mat and place it in a yellow tube rack.

Workflow the repo supports:

1. **Teleoperate** in Isaac Lab with the SO-101 leader arm; record
   episodes in LeRobot dataset format (RGB videos + joint state/action).
2. **Push** the dataset to the HuggingFace Hub.
3. Fine-tune a **GR00T N1.x** VLA in the image's Python environment.
4. **Evaluate** the policy in sim against a GR00T inference server, or on the
   real robot using the workshop image.

Companion learning content:
[https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/](https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/index.html)

---

## The module

`source/sim_to_real_so101/` is the workshop package.

- Built against **Isaac Lab develop** (Newton/MJWarp physics + OVRtx renderer,
  no Isaac Sim / Kit), pinned at
  `5d208f81d4f8895b4e564ebebce232031171a3e8`. Isaac Lab supplies OVRtx
  `0.5.0.377615` and OVStage `0.2.0.377349`; `SO101OVRTXRenderer` enables the
  OVStage scene-ownership path with `ISAAC_LAB_OVRTX_USE_OVSTAGE=1`.
- Derives its robot config from `isaaclab_assets.robots.so101.SO101_CFG`, retaining
  its `Robot=robot`, `Sensor=sensors`, and `Physics=physics` selections. A local
  USDA wrapper sublayers the public multiphysics
  `so101_new_calib_SysID/so101_new_calib.usda` asset and authors workshop joint
  calibration overrides. The `physics` variant supplies the AnchorBench
  system-identification actuator fit.
- The CUDA 13 Docker image includes Isaac Lab, LeRobot/GR00T, and the workshop
  package in a Python 3.12 uv environment at
  `/workspace/IsaacLab/env_isaaclab`.
- Console scripts: `list_envs`, `zero_agent`,
  `random_agent`, `lerobot_agent`, `lerobot_eval`.
- Gym IDs: `Newton-So101-*`.

---

## Repository layout

```
sim-to-real-so-101-workshop/
├── docker/
│   ├── Dockerfile                      # CUDA image for Isaac Lab, LeRobot/GR00T, and workshop tools
│   ├── entrypoint.sh                   # Shared container initialization and venv activation
│   ├── lerobot-policy-patch/           # LeRobot policy-server compatibility patch
│   ├── scripts/                        # Real-robot and calibration scripts
│   └── env                             # User env file (mounted to /root/env)
├── source/sim_to_real_so101/
│   ├── pyproject.toml                  # console scripts; `[dev]` extra: ruff + vulture
│   ├── assets/
│   │   ├── so101.py                    # upstream SO101_CFG adapter
│   │   ├── usd/
│   │   │   ├── Vial_opaque.usda, Vial_rack_simple.usda, mat.usda, lightbox-simple.usda
│   │   ├── mdl/Materials/Base/         # local OmniPBR MDL files (neuraylib has no HTTP resolver)
│   │   └── hdri/                       # 24 EXR HDRIs + yaw_mapping.yaml
│   ├── tasks/
│   │   ├── __init__.py                 # registers Newton-So101-* environments
│   │   ├── so101_env_cfg.py            # base teleop + SO101PhysicsCfg (MJWarp + Newton CollisionPipeline)
│   │   ├── task_env_cfg.py             # + lightbox, mat, wrist + standalone external camera, OVRtx renderer
│   │   └── vials_to_rack_env_cfg.py    # production task + DR + Eval variants
│   ├── mdp/
│   │   ├── __init__.py                 # re-exports isaaclab.envs.mdp + local terms
│   │   ├── obs.py, rewards.py
│   │   └── resets.py                   # DR with OVRtx mirror writes
│   ├── utils/
│   │   ├── ovrtx/                      # multi-product OVRtx renderer
│   │   │   ├── renderer.py             # SO101OVRTXRenderer (products, DR mirror)
│   │   │   └── ovstage_writes.py       # OVStage attribute/asset writes
│   │   ├── ovstream/                   # browser display and client assets
│   │   │   ├── display.py
│   │   │   └── browser_client/
│   │   ├── camera_cfg.py               # --cameras / --headless-render / --browser-display flags
│   │   ├── dataset_paths.py             # repo id to workshop-local dataset path
│   │   ├── lerobot_interface.py        # lerobot sim↔real bridge + GR00T policy-server client
│   │   └── lerobot_recorder.py         # RGB LeRobot dataset recorder
│   └── scripts/                        # CLI entry points (console scripts)
├── README.md, CHANGELOG, LICENSE, SECURITY.md, THIRD_PARTY_NOTICES
└── images/
```

`outputs/`, `datasets/`, and `models/` are mounted from the host at runtime.
The tracked `docker/env` template is mounted at `/root/env` for user settings.
Recording commands derive the local dataset path as `datasets/<repo_id>`; do
not add a separate `--repo_root` argument.

---

## Registered Gym environments

All registered in `sim_to_real_so101/tasks/__init__.py`. All use
`isaaclab.envs:ManagerBasedRLEnv` with `num_envs = 1`, `decimation = 2`,
`sim.dt = 1/60`, `num_substeps = 6`. With `sim.render_interval = decimation`
that gives 60 Hz physics and 30 Hz control and camera rendering.

| ID                                              | Cfg class                  | Purpose                                                |
|-------------------------------------------------|----------------------------|--------------------------------------------------------|
| `Newton-So101-Teleop-Base-v0`                   | `SO101TeleopEnvCfg`        | Bare arm + ground only                                 |
| `Newton-So101-Teleop-Task-v0`                   | `SO101TaskEnvCfg`          | + lightbox + wrist + standalone external camera        |
| `Newton-So101-Teleop-Vials-To-Rack-v0`          | `VialsToRackEnvCfg`        | Production task: 3 vials + rack (no DR)                |
| `Newton-So101-Teleop-Vials-To-Rack-DR-v0`       | `VialsToRackDREnvCfg`      | + sky-light/mat/robot-color DR                         |
| `Newton-So101-Teleop-Vials-To-Rack-Eval-v0`     | `VialsToRackEvalEnvCfg`    | Vials-to-rack + success termination (GR00T eval)       |
| `Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0`  | `VialsToRackEvalDREnvCfg`  | DR + success termination                               |
| `Newton-So101-Auto-Reach-v0`                    | `AutoReachEnvCfg`          | Per-env Cartesian targets + differential IK            |

---

## Sim↔real joint contract (DO NOT change)

The first five joints are LeRobot degrees converted directly to simulator
radians without range rescaling. The gripper is a calibrated percentage with a
measured angle scale and jaw-frame zero. Preserve joint order and apply the same
calibration in both action and observation conversions.

```python
SO101_JOINT_ORDER = [
    "shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos",
    "wrist_flex.pos",   "wrist_roll.pos",    "gripper.pos",
]
from sim_to_real_so101.utils.gripper_calibration import WORKSHOP_GRIPPER_CALIBRATION
```

Keep the mapping and its conversion formulas in `utils/gripper_calibration.py`;
collection and inference must import it rather than define separate tick spans.

The workshop USD sublayer sets gripper limits to the calibrated 0–100% interval,
about -12.51 to 118.04 degrees. The 1485-tick span is the average of calibrations
from 10 different WowRobo robots. Conversion is unclipped; joint-limit enforcement
belongs to the simulator. Robot self-collision is disabled upstream; the visual
jaws overlap slightly at calibrated 0%. The jaw-frame zero is fitted near vial
width; full endpoint geometric alignment and other physical grippers remain
unvalidated.
Do not rescale the state machine's radian targets. See `CHANGELOG` for the
dataset/checkpoint coordinate break.

Corresponding USD joint names: `shoulder_pan, shoulder_lift, elbow_flex,
wrist_flex, wrist_roll, gripper`.

---

## Running things

The image exposes the shared venv through `VIRTUAL_ENV` and `PATH`. The
entrypoint activates it for direct commands, while `/root/.bashrc` activates it
for interactive shells so the `(env_isaaclab)` prompt appears in both the
initial shell and later `docker exec` shells.

Common run commands:

```bash
# Physics-only baseline (no cameras, no OVRtx)
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras none presets=newton --visualizer newton

# Full task with both cameras (OVRtx required)
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras all presets=newton,ovrtx_renderer

# Teleop with leader arm + browser display (open http://localhost:8090; docker-only)
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras all --browser-display --port /dev/ttyACM0 --robot_id leader_bot presets=newton,ovrtx_renderer

# Same with Rerun streaming instead (joint plots + camera RGB)
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --rerun --port /dev/ttyACM0 --robot_id leader_bot presets=newton,ovrtx_renderer

# Teleop + record a LeRobot dataset to disk (push its derived local path to the Hub afterwards)
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --browser-display --repo_id <your-hf-user>/so101_teleop_vials_newton --task_name "Pick up the vial and place it in the rack" presets=newton,ovrtx_renderer
```

### Required runtime flags for camera tasks

Camera tasks need **both** preset tokens **and** an explicit `--cameras`
selection. Forgetting any of these is the #1 way to get a silent
no-images run:

| Flag                                  | Required when                                     |
|---------------------------------------|---------------------------------------------------|
| `presets=newton,ovrtx_renderer`       | OVRtx renderer is in use (both tokens — newton physics + ovrtx rendering) |
| `--cameras CAMS`                      | Always set explicitly — `none`, `wrist`, `external`, or `all` |
| `--visualizer newton` or `viser`      | Optional local visualization. Newton manager live plots are disabled. |
| `--browser-display` xor `--rerun`     | Optional, mutually exclusive (lerobot_agent only). `--browser-display` streams cameras, plots, and FPS to `http://localhost:8090`; its keyboard controls work only while the page is focused. Rerun, headless, and Newton-only modes have no application keyboard controls. Docker-only. |
| `--headless-render`                   | Benchmark cameras with no display (lerobot_agent only) |

See `README.md` for the Docker invocation and `E2E_Workflow.md` for recording,
training, and inference workflows.

---

## Active-development policy

- **Avoid overengineering.** Implement the current contract with the smallest
  clear solution. Do not add abstractions, metadata, validation layers, or
  configurability for hypothetical future needs.
- **Do not preserve workshop artifacts.** Do not add backward-compatibility code
  for generated datasets, staged episodes, checkpoints, cached outputs, or
  generated configuration. Artifacts produced by earlier code may be invalidated
  and regenerated as the project evolves.
- Do not add legacy readers, migrations, format-version markers, dual behavior,
  or compatibility fallbacks unless the user explicitly requests support for a
  specific existing artifact or external interface.
- Record artifact-breaking changes in `CHANGELOG`; keep the implementation
  focused on the current format and behavior.

---

## Pre-commit policy

Before committing, review every added or modified comment and docstring against
the policy below. For workshop code, test, configuration, asset, or runtime-dependency
changes, run from `/workspace/Sim-to-Real-SO-101-Workshop` inside the workshop container:

```bash
uv pip install -e "source/sim_to_real_so101[dev]"
python -m pytest -q source/sim_to_real_so101/test -m unit
ruff check source/sim_to_real_so101
( cd source/sim_to_real_so101 && vulture --min-confidence 80 . )
```

Vulture's `[tool.vulture] ignore_names` allowlist lives in
`source/sim_to_real_so101/pyproject.toml`. Vulture only discovers
its config from the current working directory, so it has to be invoked
from inside the package dir (or that allowlist will appear to be
missing — see `pyproject.toml` for the rationale).

All three tools are declared in the module's `[dev]` extra.
Documentation-only changes do not require these commands.

### Before pushing

For the changes covered above, run the full suite, including the GPU simulation
smoke test, before pushing. Use the same container and working directory:

```bash
python -m pytest -q source/sim_to_real_so101/test
```

The GPU test is required at the pre-push stage. Report which checks ran and any
failures or unavailable prerequisites; do not imply skipped checks passed.

---

## Tests

Use the small suite in `source/sim_to_real_so101/test/`; see its
[README](source/sim_to_real_so101/test/README.md) for coverage and limitations.

- Keep the suite small. Extend an existing test for a concrete workshop failure
  before adding another file. Avoid tests that mirror private implementation
  details and standalone bug-reproduction scripts.
- Follow Isaac Lab's pytest `unit`/`integration` markers and reuse its public
  configuration, launch, scene-state, and reset APIs.
- Passing tests do not establish image quality, grasp reliability, video
  encoding, or policy performance. Validate the affected workflow manually
  when changing those behaviors.

---

## Comments and docstrings

Comments and docstrings are documentation, not a record of the editing
process.

- Describe the current behavior, invariant, constraint, or rationale.
- Do not narrate changes with wording such as "previously", "now", "changed",
  "removed", "kept", or "used to".
- Put historical context in the commit message, pull request, `CHANGELOG`, or a
  design document.
- Do not leave commented-out code.
- Write docstrings as contracts: purpose, inputs, outputs, side effects, and
  errors where those details are useful.
- Version-specific compatibility history is allowed when it explains an active
  constraint.
- Before finishing a change, review every added or modified comment and
  docstring for compliance.

---

## Things you (or another agent) are likely to break — read first

1. **Joint order and unit convention.** Preserve `SO101_JOINT_ORDER` and the
   measured gripper zero/scale. Convert arm degrees directly to radians without
   range normalization. Gripper calibration and authored physical limits are
   independent; observations and actions must use inverse conversions.
2. **Articulation joint names** (`shoulder_pan`, `shoulder_lift`,
   `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`) come from the
   multiphysics USD. Its authored articulation order matches the canonical
   LeRobot feature order; changing the asset order can permute dataset values.
3. **Camera key naming convention.** `lerobot_agent` discovers cameras
   by prefix `camera_` and the recorder/interface expects observation
   keys `rgb_<name>`, `depth_<name>`, `instance_id_seg_<name>`. Rename
   one, break all three layers.
4. **`isaaclab.envs.mdp` star-import** in `mdp/__init__.py` shadows
   anything we define here with the same name. Keep workshop-specific
   names distinct (don't redefine `time_out`, `joint_pos`, etc.).
5. **Quaternion convention.** `init_state.rot` tuples are **XYZW**
   (Isaac Lab convention).
6. **`num_substeps=6` at `sim.dt = 1/60` balances performance and contact
   accuracy.** Primitive vial and rack colliders reduced the solver load, but
   `ke=1.57e5` (a ~446 Hz contact spring for a 20 g vial) remains coupled to
   the substep count. Re-check grasps and the vials state machine after
   changing either value.
7. **OVRtx loads USD once.** Light and texture DR must mirror USD edits through
   `SO101OVRTXRenderer.write_prim_attribute` or `write_prim_asset_path`. The mat
   is a kinematic `RigidObjectCfg`; use the built-in `reset_root_state_uniform`
   event so physics and rendering receive its pose through Isaac Lab.
8. **OVRtx `omni:xform` is column-major.** Row-major matrices place
   objects out of view. See `mdp/resets.py:_write_ovrtx_xform` for light transforms.
9. **Vial mass uses native spawn authoring:**
   `mass_props=[sim_utils.MassCfg(mass=0.02)]`. Newton imports the authored
   mass and computes matching inertia from the collision geometry.
10. **`ArticulationRootPropertiesCfg.solver_*_iteration_count` is a
    PhysX-only schema field.** Newton ignores it. Solver iteration
    counts go on `MJWarpSolverCfg.iterations` / `ls_iterations`.
11. **Vial-task contact tuning is task-local.** Contact stiffness, damping,
    friction, and MuJoCo impedance live in `tasks/vials_to_rack_env_cfg.py`;
    vial colliders use `condim=6`. The SO-101 remains instanceable and uses its
    USD-authored collision materials.
12. **`gr00t_client/`** is a small vendored client compatible with the
    GR00T server's wire format. The serializer expects custom-typed dicts
    (`__ModalityConfig_class__`, `__ndarray_class__`); changes must be
    coordinated with the upstream `Isaac-GR00T` server.
13. **OVRtx 0.5 and OVStage 0.2 own moving-instance and eager camera batching.**
    Isaac Lab prepares due camera poses, submits shared OVRtx products in one
    native step, and uses OVStage GPU hierarchy computation. The workshop
    renderer also coalesces sequential scalar camera reads because reset
    observation computation bypasses eager scene batching. The workshop does
    not override `ISAAC_LAB_OVRTX_READ_GPU_TRANSFORMS`; it retains its
    ambient-fill rewrite and runtime domain-randomization writes. Isaac Lab owns
    the compatible OVRtx and OVStage pins; do not add a second workshop-level
    renderer pin.
14. **Disabling cameras prunes their event/obs terms.**
    `apply_camera_selection` (`utils/camera_cfg.py`) removes a disabled
    camera from the scene cfg and strips any event/obs term that
    references it, so `--cameras none` and single-camera selections stay
    valid. Preserve that pruning if you add camera-referencing terms.
15. **`isaaclab_ov` bakes a full-strength ambient fill** into the OVRtx
    render scope (`omni:rtx:rt:ambientLight:intensity = 1.0`), independent of
    the authored lights — it washes out the scene and blows out the light-box.
    `SO101OVRTXRenderer` zeroes it in the generated render-scope USD; don't
    remove that rewrite or widen light-box exposure DR without re-checking
    for blow-out. The base task fixes `randomize_light_exposure` at
    `(2.0, 2.0)` to preserve the ovrtx 0.3 workshop brightness after 0.4
    corrected RectLight transform-size handling; DR tasks use `(1.5, 2.25)` and a `(0.28, 0.28)` metre RectLight.
16. **The wrist camera comes from the robot asset's `Sensor=sensors` variant.**
    `CameraCfg` binds `/Robot/gripper/wowrobo_2MP_camera` with `spawn=None`;
    the local `so101_workshop_overrides.usda` asset directly supplies the
    `omni:lensdistortion:opencvFisheye:*` parameters and camera-to-gripper pose.
    It applies the same rigid correction to the camera housing. The fit is
    visual alignment for the workshop camera, not a multi-view calibration.
    `GetAppliedSchemas()` is empty in
    the kit-less runtime, but OVRtx consumes these namespaced attributes
    directly. The robot post-spawn callback restores the workshop's
    `(0.001, 5.0)` clipping range before camera initialization.
    Changing the pose or projection changes recorded wrist RGB and invalidates
    existing datasets and policies.
17. **Runtime HDRI swaps use OVStage `ASSET_STRING` writes.** Keep texture
    paths absolute and mirror them to every camera backend; writing only
    `Sdf.AssetPath` on the Isaac stage does not update OVRtx. The dome light is
    global, so partial environment resets must not randomize it. Allow a few
    warmup frames after a full reset because texture loading is asynchronous.
18. **RectLight size is authored through `inputs:width` / `inputs:height`.**
    Keep its transform scale at `(1, 1, 1)`. OVRtx 0.3 handled scale-authored
    light dimensions incorrectly, while 0.4's rect-light fix changed the
    resulting illumination. The light remains at intensity 100 and uses
    exposure 2 (a 4x multiplier) to match the previous appearance.
19. **The SO-101 multiphysics asset requires explicit variants.** Upstream
    `SO101_CFG` selects the public
    `Robots_Multiphysics/RobotStudio/so101_new_calib_SysID/so101_new_calib.usda`
    with `Robot=robot`, `Sensor=sensors`, and `Physics=physics`; the asset's own
    defaults select no robot and PhysX, which is invalid for this Newton
    workshop. The workshop `usd_path` points to a local override layer that
    sublayers that same SysID asset; preserve the inherited variant selections
    and the SysID source when changing it.
20. **The external view is a standalone pinhole camera.** Composing the Isaac 6.0 external camera caused delayed dynamic-geometry
    corruption throughout OVRtx, even when its authored cameras were unused.
    Keep `/ExternalStandaloneCamera` at the calibrated camera world pose and
    preserve its focal length/aperture instead of loading the sensor body.
21. **OVStage owns OVRtx multi-environment cloning.** Runtime material changes
    must use `VisualMaterialCfg`; robot materials must share one sampled color
    per environment. Workshop DR attribute writes must use exact prim paths
    when `env_ids` selects a subset; wildcard writes expand to every clone and
    are only valid for intentional all-environment updates.
    Keep local mat/camera/light transforms parent-relative (do not author
    `omni:resetXformStack=True`). Inspect RGB from every environment when
    adding new cloned assets or material channels.
22. **SO-101 collision meshes use convex hulls.** Convex decomposition expands
    the robot into thousands of pieces without helping this task. The rack
    remains SDF and the vials remain primitives. The SysID asset also fixed a
    broken reference path in `payloads/base.usda`, so ~15 authored convex-hull
    collision proxies (`Cube_02`-`Cube_13`, `Cylinder_01`, `Cylinder_02`) now
    compose that previously did not. Contact count is correspondingly higher —
    re-check `nconmax=512` for overflow (upstream raised its own SO-101 stack
    task to 600) and re-check grasps when changing gripper contact parameters.
23. **Each camera owns one tiled render product ordered by environment.** Any
    per-environment render state must be addressed tile by tile, in every
    product, since the products do not share state.
24. **SO-101 fitted actuator parameters come from the USD.** The upstream
    `usd` actuator group resolves stiffness, damping, armature, friction,
    dynamic friction, viscous friction, velocity limits, and effort limits from
    the asset's `physics` variant. `mdp/gripper_protection.py` applies an estimated
    time-dependent gripper effort ceiling through a Newton callback, shared by
    teleop, scripted collection, and evaluation. Keep the implicit PD drive and
    `use_newton_actuators=True`; both Newton's effort-limit array and MJWarp's
    solver force-range array must receive the ceiling before physics substeps.
    Preserve per-environment overload history and reset isolation. See
    `GRIPPER_PROTECTION.md` for the estimates and backend dependency.
    `soft_joint_pos_limit_factor=1.0` preserves the authored rest pose and teleop range.
25. **Observation-action timing is part of the dataset contract.**
    `lerobot_agent` pairs the current observation with the leader command
    applied next. `vials_state_machine` pairs the preceding observation with
    the post-IK, rate-limited joint target written for the next control interval.
    Preserve capture before the decimated physics interval and preserve
    per-environment episode boundaries.

---

## Known issues to fix

- **The vials state machine can crash in adaptive DLS IK on a non-finite
  Jacobian.** `torch.linalg.solve` may report its regularized matrix as
  singular during `env.step()`, even though `lambda_min=0.05` makes a finite
  `J Jᵀ + λ²I` positive definite. Add finite-state/Jacobian diagnostics and
  make the action path fail or reset only the affected environment instead of
  terminating the rollout. Do not treat ordinary damping or state-machine
  tolerance tuning as the root fix.

---

## Reference files (read before edits)

- `README.md` — user-facing install and run commands.
- `E2E_Workflow.md` — recording, training, and deployment workflow.
- `CHANGELOG` — recent breaking changes.

---

## How to ask, when in doubt

When the user requests a run command, give the command — don't refactor
the underlying script first. Most scripts already accept the flags you
need (`--cameras`, `--browser-display`, `--rerun`, etc.). Match the scope
of action to what was asked.

For run commands, keep them single-line, copy-pasteable, with no leading
indent on shell continuations. Omit args with working defaults
(`--port`, `--robot_id`) unless the user is overriding them.


## AI Days Seoul shared course skills

The same checkout and canonical `skills/<name>/SKILL.md` files are used on every
station. Read the relevant canonical skill directly; this repository does not
require skill symlinks, personal-folder copies or role-specific activation.
Do not claim that the skill-selector UI automatically lists arbitrary folders.
Natural Korean or English requests need no skill mention.

For course navigation read `skills/so101-dli/SKILL.md`; for cross-lesson Q&A use
`skills/so101-dli-qa/SKILL.md`; for one lesson read its specialist as listed in
the router. Read the current lesson before answering or performing an exercise.
For schedule questions read `docs/seoul-workshop-schedule.md` and return its
detailed rows in Korean, including time, topic, duration, instructor, arrival,
breaks, lunch and the 17:15 end in KST. A Q&A request does not start workloads.

For requests such as "환경설정해줘", "설치해줘" or DLI Laptop setup, read
`skills/so101-dli-prepare/SKILL.md` and the preparation guide. Use the same
installation checkpoints and assets on student and instructor computers.
For a new setup, default to profile `student` (classroom docs audience `event`).
Select `instructor` only when the user explicitly asks for Instructor용 setup or
documents. The operator being a TA/instructor does not select that profile.
State the selected profile before executing; no extra confirmation is required
for this default. Record it and retain it while continuing the same setup.
Use `skills/so101-dli-docs/SKILL.md` to build and serve only the selected guide.
An explicit change of profile changes document selection, not the shared skills
or verified runtime installation. Maintainer builds of all guides are explicit.

Use this fork's selected `aidayseoul2026` commit; record the exact baseline,
Host/image identity and checkpoint evidence under ignored `runs/setup/<station>/`.
Preserve current installations and resume valid work. A skill/document update or
setup explanation does not itself authorize an installation or robot motion.
Use the authorized station HF account and organization policy; never print tokens.
