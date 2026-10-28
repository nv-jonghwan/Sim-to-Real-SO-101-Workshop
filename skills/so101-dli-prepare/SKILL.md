---
name: so101-dli-prepare
description: Prepare or resume SO-101 DLI environment setup on any station, including Host prerequisites, Container, lesson models and datasets, precision, and demonstrated readiness. Use for checking whether this computer can run the DLI, installation and classroom provisioning; select instructor documents only on an explicit request, otherwise student documents.
---

# Prepare and hand over a DLI station

Read [DLI preparation and operations](../../docs/2026-10-28-seoul-preparation.md),
[asset preparation](../../docs/workshop-preparation.md), [README](../../README.md)
and [Dockerfile](../../docker/Dockerfile). These checkout files define the
installation commands, lesson assets and completion criteria. Read the relevant
section immediately before its step; do not substitute public latest content.
Use Korean explanations and retain technical labels and commands in English.

A setup question needs an explanation or read-only audit. An explicit station
setup request means perform the authorized installation and verification steps,
continuing until complete or a concrete prerequisite is missing. Do not treat a
skill update, guide build or inventory request as authorization to install,
download, restart Docker, run GPU workloads or move robots.

## Assess whether this computer can run the DLI

Route questions such as “이 컴퓨터에서 DLI를 실행할 수 있어?”, “Minimum requirement를
만족해?” and “환경을 확인해줘” here. Run the read-only preflight automatically,
using the intended Host and actual model/dataset mounts. No installation,
download, GPU workload or device operation follows from an eligibility question.

```bash
python3 <repo>/skills/so101-dli-prepare/scripts/preflight.py --repo <repo> --format markdown
```

Requirements come from `docs/_static/dli-requirements.json`, maintained with the
preparation guide: Ubuntu 24.04 native Linux, x86_64, an RTX GPU and R580+ Driver.
Other OS versions are unverified against this course baseline, not automatically
incompatible. The README's tested GPU list is not an exhaustive compatibility list.
Host CUDA Toolkit is not required separately for the Container workflow.
The course has no numeric minimum for RAM, VRAM or free storage; report observed
values and leave capacity qualification unknown. Never invent thresholds or sum
VRAM across GPUs. Hardware eligibility and missing software are separate results.

Use the generated Korean assessment table and summary: `passed` means only the
basic Host conditions were observed and environment preparation can proceed;
`failed` names a concrete mismatch; `unknown` names missing evidence. Report
software, source/assets, capacity and runtime separately. `dli_ready` stays
unknown in this read-only audit, even when every observed file/tool is present.
If sandbox permissions hide GPU or Docker, inspect the actual Host with an
available authorized read-only tool; report a remaining permission limit as
unknown. Do not report that absent sandbox visibility means absent hardware.

To confirm actual classroom execution, follow the preparation guide's runtime
checks and relevant specialists within the user's authorized scope. Verify
physics, both cameras/viewer and policy inference together without OOM, using
the selected image/revisions/mounts; record live evidence. State any remaining
power/display/network and physical station checks separately. Only after those
checks pass can you say “DLI 수업 진행 가능”; a preflight-only answer must say
“기본 실행 조건 충족, 수업 실행 미검증”. Physical motion still requires the
requested exercise and current operator readiness.

## Select the document profile from the request

Every station uses this same skill and installation workflow. For a new setup,
"환경설정을 해줘" or an unqualified installation request selects `student`.
"Instructor용으로 환경설정을 해줘" selects `instructor`. Do not infer the
profile from the operator being a TA/instructor, the day before the event,
existing instructor output or who cloned the repository. State the selected
profile and proceed; do not require a role confirmation for the student default.
Retain that selection when resuming the same setup; change it when requested.

Use the read-only planner to obtain consistent commands (the default is student):

```bash
python3 <repo>/skills/so101-dli-prepare/scripts/setup_plan.py --repo <repo>
python3 <repo>/skills/so101-dli-prepare/scripts/setup_plan.py --repo <repo> --profile instructor
```

Pass the chosen language, baseline commit, verified LAN address and available
port when known. The planner executes nothing. For `student`, build `event`
documents; for `instructor`, build `instructor` documents. The runtime, model
inventory and shared skills are identical. Do not activate, install or copy a
separate skill set for either profile.

## Choose the station and freeze the source

Record the Host, architecture, operator account, intended checkout, image and
mounts. Preserve the chat's working folder; use explicit paths. Use the requested
`aidayseoul2026` revision, resolve its exact commit and keep it for the setup.
A moving branch name is not a shared station baseline. Do not reset existing
changes or advance an already prepared station without the user's request.

Start with the read-only helper (no device opens, network requests or model load):

```bash
python3 <repo>/skills/so101-dli-prepare/scripts/preflight.py --repo <repo> --expected-revision <agreed-commit> --output <repo>/runs/setup/<station>/preflight.json
```

`--expected-revision` is optional: without it the comparison is unknown, never a
failure against a hard-coded historical commit. `--hub-cache`, `--models-root`,
`--datasets-root` and repeated `--policy-config` select actual station paths.
The report inventories the current lesson's eight model repositories and six
starting-pose datasets from the course source. File presence is not a working
model, complete download, GPU pass or hardware qualification. Permission errors
remain unknown. Inspect existing mounts without dumping environment or tokens.

## Follow the installation checkpoints

Follow the **RTX Laptop과 수업 실행 환경 준비** section in the preparation guide.
For each checkpoint record its result and continue to the next unmet step:

1. **Host prerequisites:** inspect GPU/driver, OS/architecture, RAM, disk,
   network access, power and display. Follow the guide and current official
   installation instructions for missing Git/Git LFS, Docker Engine, NVIDIA
   Container Toolkit and HF CLI. The workshop's CUDA 13 Container does not by
   itself establish a requirement to replace the Host CUDA installation.
   Do not reinstall working prerequisites. A Docker runtime reconfiguration or
   daemon restart affects running containers: inspect ownership and coordinate
   that disruption before performing the authorized change.
2. **Source and Container:** hydrate the required Git LFS runtime assets; build
   the guide's image or qualify an existing one against Dockerfile, entrypoint,
   patches, image digest, Python imports, source and mounts. Do not copy Python
   environments between architectures or prune caches/images. Use the guide's
   Container invocation and persistent model/dataset/output mounts.
3. **Models and datasets:** use the exact base model, seven policies and six
   datasets in the current guide. Before HF calls confirm the effective identity
   in that same environment, including an overriding token, without exposing
   credentials. Reuse complete authorized caches; download missing files to
   the mounted paths. Preserve processor/config files and weight shards; for
   starting poses use `meta/**` and `data/**`, excluding videos. Record resolved
   revisions and verify loading through the actual Container paths. Uploads
   require their own request.
4. **Precision:** audit each selected policy config. Course settings are
   `model_params_fp32: false` and `use_bf16: true`; never edit the GR00T base
   config. Stop only the owned process using a config before changing it,
   retain its original hash/config, and read back the two settings. Shared Hub
   blobs may serve other experiments: use a separate local policy directory or
   overlay with valid processor/base paths rather than rewriting shared blobs.
   Preserve intentionally selected FP32 experiments.
5. **Documentation and preview:** use
   [docs](../so101-dli-docs/SKILL.md) for the selected profile only. Prepare the
   locked documentation environment with `uv sync --frozen`, then run the
   planner's selected build and preview commands.
   The setup-team section belongs only in instructor output. Verify actual
   remote browser URLs and media when requested. Leave requested previews
   running and record lifecycle information; docs do not require the robot
   Container or GPU.
6. **Runtime demonstration:** in the verified Container follow the guide's
   physics-only check, then wrist/external rendering, then use
   [evaluation](../so101-dli-evaluate/SKILL.md) for a bounded policy load and
   inference check. Check GPU memory/port owners before allocation; keep the
   exact owned PID, command, log and scoped cleanup. A socket or import alone
   does not pass inference. Record observed output and failures separately.
7. **Hardware and representative rehearsal:** use
   [hardware](../so101-dli-hardware/SKILL.md) for device identities, two independent
   camera images, calibration and supervised Real Teleop. An environment installation request does not start motor operation. Perform
   powered checks only for a requested hardware exercise with current operator
   readiness; report missing hardware qualification separately from installation. Use
   [HG-DAgger](../so101-dli-dagger/SKILL.md) before its representative rehearsal;
   its leader moves under power even with a simulated follower. A normal exit
   may move arms. Do not infer physical readiness from another chat.

## Keep evidence and resume

Use ignored `runs/setup/<station>/progress.md` with the agreed source commit,
selected document profile/language, Host/image identity, exact paths/revisions,
commands/logs, each checkpoint's
`pending`, `passed`, `failed` or `unknown` state, and the next action. Preserve
previous evidence; use a fresh report filename on each audit. Never store tokens.

On resume read that record, verify current source/image/device ownership and
recheck changed prerequisites. Reuse valid completed work instead of repeating
installs or downloads. Cache presence must not be promoted to runtime success.
Report source, Host prerequisites, assets, runtime/inference, hardware and docs
separately; finish with the first unmet checkpoint, owner and evidence needed.
Installation completion and a fully qualified robot station are separate claims.
