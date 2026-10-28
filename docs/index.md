# Train an SO-101 Robot From Sim-to-Real With NVIDIA Isaac

```{image} images/lightbox-sim-to-real.gif
:alt: Orbit of the simulated SO-101 workstation, with the rack and vials fading in, transitioning to the real lightbox workspace.
:width: 100%
:class: course-banner simulation-poster
```

::::::::{audience} learner

See [Get the Code](06-get-the-code.md) for setup.

::::::::

::::::::{audience} learner

Welcome to this hands-on learning path. The material is organized into **self-paced sections** you can work through in order. Duration depends on how deeply you run each exercise and whether you collect your own simulation data.

::::::::

::::::::{audience} event

Welcome to this hands-on workshop! This content includes theory presentations, and the hands-on instructions you need to complete this workshop.

::::::::

{{ seoul_lessons }}

## Overview

Today you'll use a vision-language-action (VLA) model to perform **unstructured pick-and-place of centrifuge vials** into a rack using an SO-101 robot arm.

First we start in simulation, where we can iterate quickly and validate behavior, then in reality.

Through this workflow you'll experience the **sim-to-real gap** firsthand and how to apply systematic strategies to close it.

This workshop uses **Isaac Lab 3.0**, **Newton physics**, **ovrtx rendering**, **LeRobot**, and **GR00T 1.7**.


::::{grid} 2
:gutter: 3

:::{grid-item-card}
:img-top: images/full_so101_calibration.gif

Robot Calibration
:::

:::{grid-item-card}
:img-top: images/dr-perception-comparison/dr-external-resets.gif

Domain Randomization
:::

:::{grid-item-card}
:img-top: images/newton-teleop-motion.gif

Sim Teleoperation and Data Capture
:::

:::{grid-item-card}
:img-top: images/cosmos-augment-1.gif

Cosmos Augmentation
:::

:::{grid-item-card}
:img-top: images/so101_vial_to_rack_task.gif

Real Robot Autonomous Tests
:::

::::

## Learning Objectives

By the end of this learning path, you'll be able to:

- **Configure** and calibrate an SO-101 robot for sim-to-real experiments

- **Collect** demonstration data using teleoperation or a scripted controller, with domain randomization

- **Train** vision-language-action (VLA) models using GR00T for robot manipulation

- **Evaluate** trained policies in simulation

- **Deploy** policies to physical robots and observe the sim-to-real gap

- **Explore** five sim-to-real strategies: Domain Randomization, Co-training, HG-DAgger, Cosmos Augmentation, and System Identification with AnchorBench

{{ overview_lessons }}

{{ setup_lessons }}

:::{toctree}
:caption: Setup Your Robot
:maxdepth: 2
:hidden:

07-using-workspace
07-calibrating-so101
08-operating-so101
:::

:::{toctree}
:caption: GR00T
:maxdepth: 2
:hidden:

10-groot
:::

:::{toctree}
:caption: Simulation
:maxdepth: 2
:hidden:

10-domain-randomization
08-simulation-teleoperation
09-code-tour
09-state-machine-learning
11-sim-evaluation
:::

:::{toctree}
:caption: Sim-to-Real Gap
:maxdepth: 2
:hidden:

03-sim-to-real
12-debugging-sim-to-real
:::

:::{toctree}
:caption: Working in Real
:maxdepth: 2
:hidden:

12-real-evaluation
13-strategy2-cotraining
13-cotraining-practice
14-hg-dagger
14-hg-dagger-practice
:::

:::{toctree}
:caption: Cosmos
:maxdepth: 2
:hidden:

14-strategy3-cosmos
:::

:::{toctree}
:caption: System Identification
:maxdepth: 2
:hidden:

15-strategy4-sysid
:::

:::{toctree}
:caption: Explore and Experiment
:maxdepth: 2
:hidden:

15-explore
:::

:::{toctree}
:caption: Conclusion
:maxdepth: 2
:hidden:

16-conclusion
:::

:::{toctree}
:caption: Reference
:maxdepth: 1
:hidden:

quick_reference
datasets-and-models
troubleshooting
Workshop Code <https://github.com/nv-jonghwan/Sim-to-Real-SO-101-Workshop/tree/aidayseoul2026>
Video Tutorials Playlist<https://www.youtube.com/watch?v=3TL3ALQxQX8&list=PL2bKqBZg-pzVQspO8-wieuIFctBdz_Tr_&pp=0gcJCcsEOCosWNin>
Physical AI Learning <https://docs.nvidia.com/learning/physical-ai/>
:::

