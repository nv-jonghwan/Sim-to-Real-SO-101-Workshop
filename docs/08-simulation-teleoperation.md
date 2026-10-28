# Teleoperating in Sim

```{raw} html
:file: _includes/module-types/hands-on.html
```

```{image} images/newton-teleop-motion.gif
:alt: SO-101 teleoperation in the Newton browser display, with external and wrist cameras.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Hands-on. You'll need the `so101-workshop` container, your calibrated SO-101 leader arm, and an NVIDIA GPU for Isaac Lab simulation.
:::

Now that you've done teleoperation on a real robot, let's try it in _simulation_ with Isaac Lab.

In this module, you'll use the leader arm to drive a simulated SO-101 robot, allowing us to collect demonstrations with Isaac Lab.

Because it's simulation, we have control of the world and can manipulate it in interesting ways, like using **domain randomization** to ensure our dataset will be sufficiently varied.

## Learning Objectives

- Drive the simulated SO-101 with the leader arm.
- Practice vial placement using the wrist and external camera views.
- Record, review, and optionally upload demonstrations.
- Explore optional scripted collection with the state machine.

## Teleoperation: Collecting Human Demonstrations

In this lesson we'll apply domain randomization during teleoperation. We will use these to perform a kind of robot learning known as _imitation learning_.

::::{dropdown} Why Imitation Learning? (expand to read)
:animate: fade-in

Teleoperation enables us to capture human expertise in action, allowing the system to benefit from the natural, intuitive motions people provide when performing tasks.

Humans instinctively know what matters for task success, leading to demonstrations that reflect important aspects of the job.

This process also brings in diversity, as different individuals may approach the same task in unique ways. Review teleoperated demonstrations for successful task completion and clear, purposeful motion before using them for imitation learning.
::::

## Launch the Workshop Container

1. **Use** your existing `so101-workshop` container terminal from previous modules. Stop any real teleoperation session with **Ctrl+C** and wait for shutdown before starting simulation.

:::{dropdown} Start or Reconnect to the Workshop Container

If the container is not running, **start** it from a host terminal using your workshop checkout:

```bash
cd ~/Sim-to-Real-SO-101-Workshop
xhost +
docker run --name so101-workshop -it --rm --privileged --runtime=nvidia --network=host -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v ~/.Xauthority:/root/.Xauthority -v /dev:/dev -v /run/udev:/run/udev:ro -v ~/.cache/huggingface:/root/.cache/huggingface -v ~/.cache/ovrtx:/root/.cache/ovrtx -v ~/.cache/warp:/root/.cache/warp -v ./docker/env:/root/env -v ./source:/workspace/Sim-to-Real-SO-101-Workshop/source -v ./outputs:/workspace/Sim-to-Real-SO-101-Workshop/outputs -v ./datasets:/workspace/Sim-to-Real-SO-101-Workshop/datasets -v ./models:/workspace/Sim-to-Real-SO-101-Workshop/models so101-workshop:latest
```

If the container is already running but you need to reconnect, use this from a host terminal:

```bash
docker exec -it so101-workshop bash
```

:::

**Continue** in the container terminal for the commands below. Its Python environment and saved settings load automatically.

## Practice Teleoperation in Simulation

We’ll use `Newton-So101-Teleop-Vials-To-Rack-DR-v0` for practice and recording.

1. **Confirm** that `TELEOP_PORT` and `TELEOP_ID` match your calibrated leader. The agent reads these settings automatically.
2. **Move** the leader arm to a compact pose clear of the simulated props.
3. Inside the container, **launch** the simulation:

```bash
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --browser-display presets=newton,ovrtx_renderer
```

(choose-a-simulation-environment)=
::::{dropdown} Compare all simulation environment choices

The task ID passed to `--task` selects the scene and its randomization. Use the collection variants with `lerobot_agent` or `vials_state_machine`, and the evaluation variants with `lerobot_eval`.

| Environment | What it changes | When to use it |
|---|---|---|
| `Newton-So101-Teleop-Vials-To-Rack-v0` | Base vial-to-rack scene with randomized object placement. | Practice teleoperation and establish a collection baseline. |
| `Newton-So101-Teleop-Vials-To-Rack-DR-v0` | Adds material and lighting variation, film grain, wrist blur, and broader mat variation. | Collect demonstrations across varied simulation conditions. |
| `Newton-So101-Teleop-Vials-To-Rack-Eval-v0` | Base scene with evaluation success termination. | Measure baseline policy behavior in simulation. |
| `Newton-So101-Teleop-Vials-To-Rack-DR-Eval-v0` | Standard DR scene with evaluation success termination. | Test robustness to the standard randomization. |

**Appearance components:** all vial tasks use matte foam, paper-like vial bodies, and blue-gray walls, and baseline camera grading/tone mapping. DR adds material and lighting variation, per-camera film grain, and wrist-only blur. Display, recordings, and policy observations share the processed RGB. These settings approximate camera appearance; compare policy behavior in simulation and reality to measure transfer.

::::

The first ovrtx launch can take a few minutes to warm up shader caches. If startup fails, read the terminal error and verify the leader connection.

4. **Keep** the simulation running for the next step.

## Set Up the Camera Display

1. **Open** [http://localhost:8090](http://localhost:8090) in a browser on the host. Use only one browser tab connected to the viewer at a time.

2. **Practice** picking up a vial and placing it in a rack slot using only the camera feeds.
3. **Focus** the browser and **press R** to reset the environment.
4. **Watch** the terminal for grasp and placement status as you practice.
5. **Stop** with **Ctrl+C** in the terminal before starting a recording session.

`--rerun` is an alternative to `--browser-display` for telemetry. The flags are mutually exclusive. Recording/reset keyboard controls require the browser; they are unavailable in Rerun, headless, and Newton-only modes.

:::{figure} images/newton-teleop-pick-place.gif
:width: 100%
:alt: Picking up and placing a vial while the external and wrist camera feeds and joint plots update in the Newton browser display.

Use both camera feeds to guide the vial into the rack. The browser also shows recording controls and joint observations and actions.
:::

## Recording Demonstrations

Explore an example dataset with the [Dataset Visualizer](https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fsreetz-nv%2Fso101_teleop_vials_rack_left%2Fepisode_29%3Ft%3D0)

:::{tip}
Having trouble with cameras or robot connection? See the [Troubleshooting Guide](troubleshooting.md).
:::

### Inside a Demonstration

An **episode** records a continuous task sequence, such as a full attempt or a saved correction. It keeps the wrist and external images, joint state, actions, task instruction, and timing together. State describes where the robot was; an action describes what it was commanded to do next.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/lerobot-episode.html" title="A LeRobot episode combines images, joint state, actions, and timing" loading="lazy" style="display:block; width:100%; height:600px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/lerobot-episode.svg
:alt: A LeRobot episode combines images, joint state, actions, and timing
```
````

### Set the Dataset Namespace

When ready to collect data, we'll add a few extra arguments for where to save the data we collect.

1. **Set** the dataset namespace. Keep `your-hf-username` for local-only collection, or replace it with your Hugging Face username if you plan to upload.

```bash
export HF_USER=your-hf-username
```

You only need to set this once per terminal session. Local collection does not require a Hugging Face login.

### Record Demonstrations

1. **Launch** the recording session inside the container:

```bash
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --repo_id "${HF_USER}/so101_teleop_vials_newton" --task_name "Pick up the vial and place it in the rack"
```

The recorder derives the local path from the repo ID: `datasets/<user>/so101_teleop_vials_newton`.

:::{note} Dataset folder already exists?
If you see `[ERROR]: Dataset root already exists`, add `--resume` to append new episodes to the existing dataset. To start a separate dataset, choose a new `--repo_id` instead.
:::

To append to an existing dataset, run the command below. In a new shell, set `HF_USER` again first:

```bash
lerobot_agent --task Newton-So101-Teleop-Vials-To-Rack-DR-v0 --cameras all --browser-display presets=newton,ovrtx_renderer --repo_id "${HF_USER}/so101_teleop_vials_newton" --task_name "Pick up the vial and place it in the rack" --resume
```

2. **Open** [http://localhost:8090](http://localhost:8090). Use only one browser tab connected to the viewer at a time.
3. **Focus** the browser and **use** **Space** to start/save, **C** to discard, and **R** to discard and reset.
4. **Repeat** until you have collected the desired demonstrations.
5. **Wait** for the saving indicator to clear in the browser, and the terminal to report the episode saved. Completed episodes save in the background. For example:

```text
[INFO]: Episode 1 saved.
```

6. **Stop** with **Ctrl+C** in the terminal and **allow** shutdown to finish.

### Review and Upload Collected Data

1. **Inspect** an episode with the dataset visualizer:

```bash
lerobot-dataset-viz --repo-id "${HF_USER}/so101_teleop_vials_newton" --root "./datasets/${HF_USER}/so101_teleop_vials_newton" --episode-index 0
```

The visualizer opens the episode in **Rerun**. Once it has loaded, press **Spacebar** to play or pause. You can replay it as many times as you like.

2. **Change** `--episode-index` to review more takes and **verify** camera assignments and successful placement before training.

Simulation recording writes to disk.

3. **Optional:** Authenticate and upload the completed dataset to share it or train from its Hub ID:

```bash
hf auth login
export DATASET_ID="${HF_USER}/so101_teleop_vials_newton"
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

(refresh-dataset-tag)=
:::{dropdown} Uploading more episodes to the same dataset?

After `hf upload` finishes, replace the existing `v3.0` tag so it points to the updated data:

```bash
hf repos tag delete "$DATASET_ID" v3.0 --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

`v3.0` is the dataset format used by this workshop. See the [Hugging Face CLI guide](https://huggingface.co/docs/huggingface_hub/en/guides/cli#hf-repos-tag) for more about tags.

:::

## Optional: Automated Data Collection

The workshop also provides `vials_state_machine`, a scripted controller that approaches a vial, grasps it, transfers it to the rack, inserts it, and releases it. This path runs entirely in simulation and does not require a leader arm or a trained policy. It produces demonstrations for the same post-training workflow.

### Preview the Scripted Controller

1. **Stop** any running teleoperation or evaluation client to release the display ports.
2. In the workshop container, **run** the base state-machine task without recording:

```bash
vials_state_machine --task Newton-So101-Auto-Vials-State-Machine-v0 --cameras all --browser-display presets=newton,ovrtx_renderer
```

3. **Open** [http://localhost:8090](http://localhost:8090) and **inspect** both camera feeds while the controller executes. Use only one browser tab connected to the viewer at a time.
4. **Stop** the preview with **Ctrl+C** before starting collection.

### Record Successful Episodes

1. **Run** the domain-randomized task with recording enabled. Keep the `your_hf_username` placeholder for local-only collection, or use your Hugging Face username if you plan to upload:

```bash
export HF_USER=your_hf_username
vials_state_machine --task Newton-So101-Auto-Vials-State-Machine-DR-v0 --record --num_episodes 5 --repo_id "${HF_USER}/so101_auto_vials_newton" --task_name "Pick up the vial and place it in the rack" --cameras all --browser-display presets=newton,ovrtx_renderer
```

The target is **5 successful episodes**, not 5 attempts. The recorder accepts successful episodes and discards unsuccessful attempts. Both cameras are required. Recording is automatic; the teleoperation **Space/C** controls are not part of this collection flow.

2. **Wait** for collection and dataset export to complete. Successful episodes are staged during the run; the LeRobot dataset is assembled when the collection target is reached. Stopping early can leave staged episodes without a completed dataset.
3. **Inspect** the exported data before uploading:

```bash
lerobot-dataset-viz --repo-id "${HF_USER}/so101_auto_vials_newton" --root "./datasets/${HF_USER}/so101_auto_vials_newton" --episode-index 0
```

4. **Optional:** Review several episodes for camera coverage, grasp quality, and placement, then upload the dataset:

```bash
hf auth login
export DATASET_ID="${HF_USER}/so101_auto_vials_newton"
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
```

## Sim vs. Real Teleoperation Comparison

::::::{dropdown} Compare simulation and real teleoperation, and when to use each

| Aspect | Simulation | Real Robot |
|--------|------------|------------|
| Domain randomization | Automatic | Manual, limited to what you can physically change in the environment |
| Data collection speed | Faster reset, parallel envs possible | Real-time only |
| Hardware wear | None | Accumulates over time |
| Visual diversity | Procedural generation | Requires manual variation |
| Physics accuracy | Approximated | Ground truth |

### When to Use Each

**Use simulation when:**
- Building initial dataset with DR
- Hardware is limited or shared
- Exploring task or policy variations quickly and safely
- Real environment isn't ready, accessible, or during development

**Use real robot when:**
- Collecting high-quality ground truth
- Validating sim-trained policies
- Capturing real-world nuances (friction, lighting)

::::::

(mix-teleoperation-with-automated-demonstrations)=
:::{dropdown} Mix Teleoperation With Automated Demonstrations

A mixed dataset can be a useful way to reduce collection effort. Teleoperation takes time and requires people to repeat the task many times (up to 75 in our examples), but it also provides useful variation for task generalization.

Automated data collection can aid in testing and initial pipe-cleaning, or as a supplement to teleoperation. But it can easily result in an overfitted model if not properly randomized.

There is no fixed teleoperation-to-automation ratio for every task. Start with a deliberate mix, evaluate it against a teleoperation-only or automation-only baseline, and add examples where coverage is missing.

:::

## Key Takeaways

- Teleoperation captures human expertise in demonstration form
- Always teleoperate using only camera views—not your eyes
