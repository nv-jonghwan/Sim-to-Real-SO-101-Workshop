# LeRobot and the SO-101

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/teleop_arm_neutral_pose.jpg
:alt: SO-101 leader arm used to demonstrate robot motions.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Nothing — this module is theory-only.
:::

Meet the SO-101 and the Hugging Face LeRobot tools we'll use to collect demonstrations, train policies, and control the robot.

## Learning Objectives

By the end of this session, you'll be able to:

- **Describe** the SO-101 robot and its capabilities

- **Explain** the LeRobot project and its role in the robotics community

- **Identify** community resources for continued learning


## The SO-101 Robot

The SO-101 is a 6-DOF (degrees of freedom) robot arm designed for research and education in manipulation tasks. Play the animation below to get familiar with the axes of motion.

```{raw} html
<figure style="max-width: 720px; margin: 1.5rem auto;">
  <video controls playsinline preload="metadata" width="1280" height="800" style="width: 100%; height: auto;" aria-label="SO-101 assembly and joint layout" aria-describedby="so101-assembly-caption">
    <source src="_static/videos/so101-assembly-orange-15s.mp4" type="video/mp4">
    <a href="_static/videos/so101-assembly-orange-15s.mp4">Download the SO-101 assembly video.</a>
  </video>
  <figcaption id="so101-assembly-caption">SO-101 assembly and joint layout.</figcaption>
</figure>
```

The SO-101 kit has two arms:

- **Leader / Teleop arm**: You move this arm by hand to control the real or simulated follower and record demonstrations.
- **Follower / Robot arm**: This arm performs the task. It follows the leader during teleoperation or a policy during evaluation.

LeRobot commands use `--teleop` for the leader and `--robot` for the follower.

:::::{grid} 1 2 2 2
:gutter: 2

::::{grid-item}
:::{figure} images/SO101_follower.jpg
:width: 300px
:alt: SO-101 Follower Arm

The follower / robot arm performs the task.
:::
::::

::::{grid-item}
:::{figure} images/SO101_leader.jpg
:width: 300px
:alt: SO-101 Leader Arm

The leader / teleop arm has a handle for controlling the gripper by hand.
:::
::::

:::::

### Why SO-101?

The SO-101 is ideal for this learning path because:

- **Accessible**: Affordable for education and research
- **Well-documented**: Strong community support
- **LeRobot integration**: First-class support in the LeRobot ecosystem

What makes it difficult for precision tasks:
- **Significant backlash in the joints**
- **Joints loosen over time:** tightening the fasteners compresses the 3D-printed plastic, so connections between links and motor flanges gradually lose their clamping force

## The LeRobot Project

LeRobot is an open-source library from Hugging Face which includes tools for data collection, training, robot control, and evaluation of robot policies.

### Community Datasets

LeRobot hosts community-contributed datasets on the Hugging Face Hub with the LeRobot Dataset Format.

- Thousands of robot demonstrations
- Multiple robot platforms
- Various manipulation tasks
- Standardized formats for interoperability

## Why LeRobot for This Course

LeRobot is the foundation of this course for several practical reasons:

::::::{dropdown} Preview the collection, training, and evaluation workflow

### Data Flow With Hugging Face Hub

The workshop uses one `so101-workshop` container for LeRobot tools. Simulation recording writes `datasets/<repo_id>`; use the same namespace when uploading:

```bash
export DATASET_ID="${HF_USER}/so101_teleop_vials_newton"
hf upload "$DATASET_ID" "./datasets/$DATASET_ID" . --repo-type dataset
hf repos tag create "$DATASET_ID" v3.0 --repo-type dataset --revision main
hf download "$DATASET_ID" --repo-type dataset --revision v3.0 --local-dir "./datasets/$DATASET_ID"
```

Set `HF_USER` to your Hugging Face username and authenticate with `hf auth login` first.

For later uploads to the same dataset, {ref}`refresh its tag <refresh-dataset-tag>`.

### Post-Training Pipeline

Collect demonstrations with `lerobot_agent` and a leader arm, or use `vials_state_machine` for [automated simulation collection](08-simulation-teleoperation.md#optional-automated-data-collection). Both workflows produce LeRobot datasets under `datasets/<repo_id>`. Inspect episodes with `lerobot-dataset-viz` before uploading and training.

Use `lerobot-train` with `--policy.type=groot` and `--policy.base_model_path=nvidia/GR00T-N1.7-3B`. [GR00T Post-Training](10-groot.md#reference-post-train-your-own-model) provides the full configuration.

### Simulation Evaluation

Use the same container terminal: start `python -m lerobot.async_inference.policy_server` in the background, then run `lerobot_eval` at the prompt. The client selects the checkpoint and executes the policy in Isaac Lab. [Sim Evaluation](11-sim-evaluation.md) provides the complete commands and camera requirements.

### Real Robot Evaluation

Use `lerobot-rollout` with the trained LeRobot policy and the follower's calibrated robot and camera configuration. Follow [Real Evaluation](12-real-evaluation.md) for the command.

The workflow is collect → inspect → train → evaluate → iterate, using the shared workshop environment.

::::::

## Community Resources

### Dataset Visualizer

LeRobot provides an interactive dataset visualizer on Hugging Face Spaces:

- [LeRobot Dataset Visualizer](https://huggingface.co/spaces/lerobot/visualize_dataset)

Use this tool to explore any LeRobot dataset on the Hub. You can scrub through episodes, view camera feeds, and inspect action/state trajectories—useful for debugging data quality issues or understanding what a dataset contains before training.

To view an example, enter `lerobot/FineART` in the Dataset Visualizer input field, then click **GO**.

### Documentation

- [LeRobot Documentation](https://huggingface.co/docs/lerobot)
- [SO-101 Getting Started Guide](https://huggingface.co/docs/lerobot/en/so101)

### Examples and Tutorials

- Community notebooks and examples

## Hugging Face Hub Integration

LeRobot leverages the Hugging Face Hub for:

::::::{dropdown} Read more about how this course uses Hugging Face

### How We Used Hugging Face in This Course

**1. Dataset format for gathering demonstrations**

We used the LeRobot dataset format for all teleoperation and state machine (procedurally generated) data. Episodes are stored with observations (e.g. camera images), robot state, and actions in a consistent schema. Simulation recording uses `lerobot_agent --repo_id` and derives the local path as `datasets/<repo_id>`. Real recording uses `lerobot-record` with `--dataset.repo_id` and an explicit `--dataset.root`.

**2. Sharing datasets**

Datasets were pushed to the Hugging Face Hub so they could be reused for training, shared with others, and versioned. We used `--dataset.repo_id=${HF_USER}/dataset_name` and `--dataset.push_to_hub=true` when recording, or `hf upload` for existing local datasets. The [LeRobot Dataset Visualizer](https://huggingface.co/spaces/lerobot/visualize_dataset) on the Hub was used to inspect episodes and verify quality before training.

**3. Merging datasets for co-training (sim + real, sim + Cosmos)**

For co-training we combined multiple data sources into a single training dataset or ran multiple passesof training.

**4. Sharing evaluations**

Evaluation results and policy checkpoints were shared via the Hub. Trained models were uploaded (e.g. as GR00T checkpoints or LeRobot policy repos) so others could reproduce evaluations or run the same policy in sim and on the real robot. Links to specific datasets and model repos were used in this learning path to align everyone on the same baselines and co-trained models.

::::::

## Key Takeaways

- SO-101 is an accessible, well-supported robot for learning sim-to-real
- LeRobot provides open-source tools, datasets, and models
- The Hugging Face community offers ongoing support and resources
- You're joining a growing community of robot learners and practitioners

## What's Next?

::::::::{audience} learner

Next, [Building the Workspace](05-building-workspace.md) walks through assembling and lighting the physical lightbox and task props. After that, [Calibrating the SO-101](07-calibrating-so101.md) covers power-on and calibration, and [Teleoperating](08-operating-so101.md) covers teleoperation and camera setup.

::::::::

::::::::{audience} event

Continue to [Calibrating the SO-101](07-calibrating-so101.md) with the prepared event workspace. Follow your instructor's directions about calibration, then continue to [Teleoperating](08-operating-so101.md).

::::::::

::::
