# Explore and Experiment

```{image} images/laboratory-simulation-poster.png
:alt: SO-101 simulated workstation in a laboratory environment.
:width: 100%
:class: course-banner simulation-poster
```

Use this time to revisit a result, try another supplied model, or investigate a failure from your own setup. Choose one question and change one factor at a time.

## Choose an Experiment

- **Compare environments.** Use [Sim Evaluation](11-sim-evaluation.md) to compare a policy in the base and DR tasks.
- **Compare data sources.** Revisit [Co-Training in Practice](13-cotraining-practice.md) and compare with your sim-only results using matched starting conditions.
- **Investigate a failure.** Use [Debugging Sim-to-Real Issues](12-debugging-sim-to-real.md) to narrow down what to test next.
- **Change the scene.** Try the exercise below: adjust domain randomization or add a prop, then test an existing policy.

## Try It: Change the Scene

What might change in the robot's real workspace? Use the [Architecture Tour](09-code-tour.md) and [Domain Randomization](10-domain-randomization.md) to choose one variation to explore.

1. **Choose a change:** widen a lighting or object-position range, vary a material or orientation, or add a lab prop such as a beaker or sample tray. You can ask Astra to design a prop for you.
2. **Make the change on a new branch.** Start with one variation so you can see its effect. Keep the rack reachable and leave room for the arm to move.
3. **Reset the simulation a few times.** Check both camera views. Does the variation look plausible? Does it hide the vial or rack?
4. **Evaluate the same supplied policy** using [Sim Evaluation](11-sim-evaluation.md). Compare its behavior with the original scene, keeping the checkpoint, starting conditions, and rollout settings the same.

Where does the policy still work, and where does it struggle? Changing the scene tests the policy's robustness; it does not train the policy to handle the new variation.

:::{dropdown} Sample prompt: create and randomize a lab prop

```text
On a new branch called experiment/lab-prop, create a USD prop for a laboratory
that handles centrifuge vials—for example, a beaker or sample tray. Use realistic
scale and materials. Add it beside the robot's work area without blocking the
rack or arm. Randomize its position and appearance within a small, plausible
range on each reset. Show me which files and parameters you changed.
```

:::

## Create a Workspace With Astra

We used **Astra** to generate this laboratory workspace around our SO-101 task. The lightbox panels are removed, the external camera sits on a stand, and lab benches, equipment, and overhead lighting surround the robot.

:::{figure} images/astra-laboratory-workspace.png
:alt: SO-101 workstation in an Astra-generated laboratory, with a tripod-mounted external camera, benches, glassware, a centrifuge, and overhead fluorescent lights.
:width: 100%

The vial-to-rack workstation in a laboratory environment generated with Astra.
:::

Try describing a setting for your own task. How might its lighting and background change what the policy sees?

::::{dropdown} Sample prompt: build a laboratory environment

```text
On a new branch called experiment/laboratory-env, remove the lightbox's side,
top, and back panels. Place the entire workstation inside a laboratory with
benches, beakers, and common lab equipment, including a centrifuge.

Add bright room lighting with overhead fluorescent fixtures. Mount the external
camera on a tripod or monopod. Give the laboratory a technical appearance and
use higher-fidelity assets.
```

::::

## Further Resources


### Courses
- [Getting Started with Isaac Lab - Transferring Robot Learning Policies from Simulation to Reality](https://docs.nvidia.com/learning/physical-ai/getting-started-with-isaac-lab/latest/transferring-robot-learning-policies-from-simulation-to-reality/index.html)

### Documentation
- [LeRobot Documentation](https://huggingface.co/docs/lerobot)
- [Isaac Lab Documentation](https://isaac-sim.github.io/IsaacLab/main/index.html)
- [GR00T Developer Guide](https://developer.nvidia.com/isaac/gr00t)
- [Anchor-Lab Dataset](https://huggingface.co/datasets/nvidia/Anchor-Lab)
- [SO-101 AnchorBench Comparison](https://huggingface.co/VigneshBhavan/so101-newton-actuator-ab-paired-checkpoints)

### Community
- [Hugging Face Discord](https://discord.gg/huggingface)
- [NVIDIA Developer Forums](https://forums.developer.nvidia.com/)
- [LeRobot GitHub](https://github.com/huggingface/lerobot)

### Papers
- [The Reality Gap in Robotics: Challenges, Solutions, and Best Practices](https://arxiv.org/pdf/2510.20808)

## What's Next?

Continue to the [Conclusion](16-conclusion.md) for the recap, workshop availability, and feedback.
