---
name: so101-dli-qa
description: Answer student questions across the entire SO-101 Sim-to-Real course using this checkout's lessons, Korean explanations, code and troubleshooting; explain concepts, commands and observed errors without starting exercises for a question.
---

# Answer from the course

Read [contents](../../docs/index.md) to identify the lesson, then read that
lesson's relevant section. For schedule questions use
[today's schedule](../../docs/seoul-workshop-schedule.md) and its detailed rows.
Use `docs/locale/ko/LC_MESSAGES/<page>.po` for Korean terminology and
`docs/locale/ko/interactive.json` for interactive explanations. Inspect the
associated HTML diagram or code when a question concerns a visual or command.
Do not assume the student has seen presenter preparation or a private handoff.

| Topic | Primary reading |
|---|---|
| Physical AI and today's task | [Overview](../../docs/01-overview.md) |
| LeRobot, SO-101, Dataset Visualizer | [LeRobot](../../docs/04-lerobot.md) |
| Workspace and calibration | [Workspace](../../docs/07-using-workspace.md), [calibration](../../docs/07-calibrating-so101.md) |
| Real Teleop and camera assignment | [Teleoperating](../../docs/08-operating-so101.md) |
| Sim Teleop and Domain Randomization | [Sim Teleop](../../docs/08-simulation-teleoperation.md), [DR](../../docs/10-domain-randomization.md) |
| Software architecture and automated collection | [Code tour](../../docs/09-code-tour.md), [State Machine](../../docs/09-state-machine-learning.md) |
| GR00T and Vision-Language-Action | [GR00T](../../docs/10-groot.md) |
| Reality gap and failure diagnosis | [Sim-to-Real](../../docs/03-sim-to-real.md), [debugging](../../docs/12-debugging-sim-to-real.md) |
| Evaluation and checkpoint differences | [Sim](../../docs/11-sim-evaluation.md), [real](../../docs/12-real-evaluation.md), [models](../../docs/datasets-and-models.md) |
| Co-Training | [Theory](../../docs/13-strategy2-cotraining.md), [practice](../../docs/13-cotraining-practice.md) |
| HG-DAgger | [Theory](../../docs/14-hg-dagger.md), [practice](../../docs/14-hg-dagger-practice.md) |
| Cosmos | [Augmentation](../../docs/14-strategy3-cosmos.md) |
| SysID / AnchorBench | [Actuation gap](../../docs/15-strategy4-sysid.md) |
| Exploration, wrap-up and errors | [Explore](../../docs/15-explore.md), [Conclusion](../../docs/16-conclusion.md), [Troubleshooting](../../docs/troubleshooting.md) |

Lead with the answer, explain how it applies to the vial-to-rack exercise, and
link the specific lesson/section. Use a table for comparisons. Preserve English
technical labels, shaded code, units and model IDs. Distinguish documented course
behavior, actual observations, and an explanation/inference of a failure.

If the course does not answer a question, say what is missing and use current
primary product documentation when needed. Do not invent a command or claim to
have run it. For an observed error, read the log and the matching troubleshooting
section; start with read-only inspection. An explanation request does not start
GPU jobs, robot motion, training, uploads, station provisioning or docs builds.
