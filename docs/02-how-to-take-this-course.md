# How to Take This Course

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/newton-teleop-motion.gif
:alt: SO-101 simulation teleoperation through the browser camera display.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Nothing — this module is theory-only.
:::

::::::::{audience} learner

## Learning Strategies

Choose based on the amount of time you want to invest, and how much of a challenge you want to take on.

Think of this workshop as a platform for you to practice and build your skills in sim-to-real transfer.

### Option 1: As-Is

If you’re not sure, just take the course as-is!

Buy the workspace materials from the Bill of Materials, use our pre-trained checkpoints and pre-collected datasets, and follow the course as-is.

:::{admonition} Tip
:class: tip
This is the fastest way to experience the full sim-to-real workflow end-to-end.
:::

### Option 2: Use Your Own Data

Same as option 1, except you collect your own data and train your own models on the same vial-to-rack task. Use leader-arm teleoperation or the optional [automated collection workflow](08-simulation-teleoperation.md#optional-automated-data-collection), then inspect the dataset and post-train GR00T 1.7. Scripted collection does not need a leader arm; real-robot evaluation still needs a calibrated follower and cameras.

### Option 3: Bring Your Own Task

Get more creative with this learning path as a base for your own exploration.

Buy the workspace, but swap out the props and task. Define a new manipulation problem, collect data for it, and apply the same sim-to-real strategies covered in this course.

:::{admonition} Tip
:class: tip
This will take some creativity, or maybe you already have a task in mind. But it will ultimately teach you the most, to build and apply the process to a new task.
:::

### Option 4: Going Further

Train a robust enough model that you can completely remove the lightbox enclosure and run the task in an uncontrolled environment.

::::::::

::::::::{audience} event

## Working at the Event

Use the prepared workstation, robot workspace, and workshop container. Follow your instructor's exercise sequence and use the supplied datasets and checkpoints where directed. You can revisit the workspace and software setup guides under **Setup References** when repeating the course on your own equipment.

::::::::

## Computer Hardware Prerequisites

::::::::{audience} learner

Tested configurations:

- **OS:** Ubuntu Linux newer than 22.04
- **GPU:** NVIDIA RTX 6000 Pro (Blackwell), RTX 5090 (Blackwell), or RTX 6000 (Ada)
- **Software:** Git with Git LFS, Docker, the CUDA Toolkit, and the NVIDIA Container Toolkit

Install the software before [Get the Code](06-get-the-code.md).

Details on the robot and workspace requirements can be found in [Building the Workspace](05-building-workspace.md).

::::::::

::::::::{audience} event

The event workstation provides the required software and GPU. To see the hardware and installation requirements in [Get the Code](06-get-the-code.md), under **Setup References**.

::::::::

## What's Next?

Continue to [LeRobot and the SO-101](04-lerobot.md).
