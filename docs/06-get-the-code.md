---
orphan: true
---

# Get the Code and Models

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/task.png
:alt: SO-101 vial-to-rack task represented as a simulation scene.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need Ubuntu Linux, Git with Git LFS, Docker, the CUDA Toolkit, the NVIDIA Container Toolkit, and an NVIDIA RTX GPU.

Install Git LFS on the host and initialize it before cloning so the robot assets and course media download correctly:

```bash
git lfs install
```
:::

Build one workshop image for simulation, calibration, teleoperation, recording, GR00T training, and evaluation.

Tested on Ubuntu Linux newer than 22.04 with an NVIDIA RTX 6000 Pro (Blackwell), RTX 5090 (Blackwell), or RTX 6000 (Ada) GPU. Install the host software before building the image.

::::::::{audience} learner

See [Computer Hardware Prerequisites](02-how-to-take-this-course.md#computer-hardware-prerequisites).

::::::::

## Workshop Software

| Component | Workshop configuration |
|-----------|------------------------|
| Isaac Lab | 3.0 development stack, pinned by `ISAACLAB_REF` in `docker/Dockerfile` |
| Physics | Newton with the MJWarp solver |
| Camera rendering | ovrtx; Isaac Lab supplies compatible ovrtx and OVStage versions |
| LeRobot | 0.6.0 with training, GR00T, async inference, and visualization support |
| Policy | GR00T 1.7, using `nvidia/GR00T-N1.7-3B` for post-training |
| Container | CUDA 13, Ubuntu 24.04, Python 3.12 |

The workshop runs without an Isaac Sim or Kit application. Build the pinned stack rather than substituting a separate Isaac Sim installation.

## Clone the Repository

1. **Open a terminal on the host**, **clone** the repository into your home directory, and **enter** its directory:

```bash
cd ~
git clone --branch aidayseoul2026 --single-branch https://github.com/nv-jonghwan/Sim-to-Real-SO-101-Workshop.git
cd Sim-to-Real-SO-101-Workshop
git lfs pull
```

## Build the Workshop Container

2. **Build** the image and **create** the persistent output directories from the repository root on the host:

```bash
docker build -t so101-workshop -f docker/Dockerfile .
mkdir -p outputs datasets models
```

The same image supports simulation and real-robot exercises.

## Start the Workshop Container

3. **Start** the container from the repository root on the host:

```bash
cd ~/Sim-to-Real-SO-101-Workshop
xhost +
docker run --name so101-workshop -it --rm --privileged --runtime=nvidia --network=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v ~/.Xauthority:/root/.Xauthority -v /dev:/dev -v /run/udev:/run/udev:ro -v ~/.cache/huggingface:/root/.cache/huggingface -v ~/.cache/ovrtx:/root/.cache/ovrtx -v ~/.cache/warp:/root/.cache/warp -v ./docker/env:/root/env -v ./source:/workspace/Sim-to-Real-SO-101-Workshop/source -v ./outputs:/workspace/Sim-to-Real-SO-101-Workshop/outputs -v ./datasets:/workspace/Sim-to-Real-SO-101-Workshop/datasets -v ./models:/workspace/Sim-to-Real-SO-101-Workshop/models so101-workshop:latest
```

The shell starts in `/workspace/Sim-to-Real-SO-101-Workshop`. Its shared Python environment, `/workspace/IsaacLab/env_isaaclab`, is active automatically.

4. **Keep** this terminal open and use the container prompt for the following lessons. Finish or stop the current exercise with **Ctrl+C**, wait for shutdown to complete, then run the next command at the same prompt. Closing this main shell stops the container.

All later workshop commands run from `/workspace/Sim-to-Real-SO-101-Workshop` inside this container unless a step explicitly says **host**. Settings in the mounted `docker/env` load when the container shell starts. A plain `export` lasts for the current shell; use the course's `setenv` helper for persistent robot ports and IDs.

(container-shell-recovery)=
:::{dropdown} Reconnect to a running container or open an optional extra shell

From a host terminal, check whether the container is running:

```bash
docker ps --filter name=so101-workshop
```

If it is running and you need a shell, use:

```bash
docker exec -it so101-workshop bash
```

If it has stopped, repeat step 3 from the repository root on the host. Mounted datasets, models, outputs, and settings persist. Re-enter ordinary `export` variables when starting a new shell. An extra shell is optional; simulation evaluation starts its server in the background of the same terminal.

:::

### Persistent Files

::::::{dropdown} Show container mounts and persistent file locations

| Host location | Container location / purpose |
|---------------|------------------------------|
| `docker/env` | `/root/env`; settings such as robot ports and IDs |
| `source/` | Workshop package source under the container repository |
| `datasets/` | Recorded and downloaded datasets under the container repository |
| `outputs/` | Training runs and other outputs under the container repository |
| `models/` | Downloaded checkpoints under the container repository |
| `~/.cache/huggingface/` | `/root/.cache/huggingface/`; Hub cache and robot calibration |
| `~/.cache/ovrtx/`, `~/.cache/warp/` | Renderer and physics caches |

::::::

Edits under the mounted directories persist on the host. The `--rm` option removes the container when its main process exits.

## Check the Simulation

5. Inside the container, **list** the tasks and **run** the physics-only check:

```bash
list_envs
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras none presets=newton --visualizer newton
```

6. **Stop** with **Ctrl+C**, then **run** the camera-rendering check:

```bash
zero_agent --task Newton-So101-Teleop-Vials-To-Rack-v0 --cameras all presets=newton,ovrtx_renderer
```

The first ovrtx run can take a few minutes to warm up shader caches. The interactive camera display is introduced in [Teleoperating in Sim](08-simulation-teleoperation.md).

Camera commands require explicit `--cameras` selection and `presets=newton,ovrtx_renderer`. Physics-only commands use `--cameras none presets=newton`.

### Choose the Task for Each Stage

::::::{dropdown} Show task IDs for collection and evaluation

- **Leader-arm collection:** `Newton-So101-Teleop-Vials-To-Rack-v0`, or `Newton-So101-Teleop-Vials-To-Rack-DR-v0` for domain randomization, with `lerobot_agent`.
- **Scripted collection:** `Newton-So101-Auto-Vials-State-Machine-v0`, or `Newton-So101-Auto-Vials-State-Machine-DR-v0`, with `vials_state_machine`. Follow [Automated Data Collection](08-simulation-teleoperation.md#optional-automated-data-collection).
- **Policy evaluation:** `Newton-So101-Teleop-Vials-To-Rack-Eval-v0`, or `Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0`, with `lerobot_eval` and a LeRobot policy server.

`list_envs` also lists the bare-arm, lightbox, and automatic-reach tasks. Use the vial-to-rack task for the collection method you choose.

::::::

## Get the Models

7. **Stop** the camera check with **Ctrl+C**, then **authenticate** inside the container:

```bash
hf auth login
```

8. **Use** [Datasets and Models](datasets-and-models.md) to select a compatible LeRobot GR00T 1.7 checkpoint, or train one in [GR00T Post-Training](10-groot.md#reference-post-train-your-own-model). Downloads belong under `models/`.

## What's Next?

Continue to [Calibrating the SO-101](07-calibrating-so101.md).
