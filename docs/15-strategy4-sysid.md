# Sim-to-Real Strategy 5: System Identification With AnchorBench

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/sysid-actuator-comparison-banner.png
:alt: SO-101 paired trial with SysID actuators on the left and original actuators on the right. Both trials failed: the SysID trial missed the rack, and the original-actuator trial missed the vial grasp.
:width: 100%
```

:::{dropdown} What Do I Need for This Module?
This module uses videos and published comparisons to explain system identification. You do not need a connected robot or a running workshop container.
:::

The same joint command can produce different motion in simulation and on hardware. **System identification (SysId)** estimates model parameters from measured behavior so that simulation better represents the physical system. Here, you'll compare SO-101 motion with and without an [AnchorBench](https://github.com/NVIDIA/anchor-bench) SysID layer and see how model differences can affect policy behavior.

## Learning Objectives

- Explain how measured robot motion informs system identification.
- Recognize differences between baseline, fitted, and measured motion.
- Explain why matched actions and initial conditions matter in an experiment.
- Distinguish actuator-model validation from downstream policy evaluation.

## From Measurements to a Simulation Model

A position-controlled joint's response depends on more than its target angle. Drive stiffness and damping, actuator effort limits, armature, and friction affect tracking and settling. A SysId workflow adjusts these parameters to reduce disagreement between simulated motion and physical measurements.

The basic process is to record informative motions, fit a model on a chosen subset, and test it on motions excluded from fitting. A good fit should explain behavior beyond the motions used to tune it. Policy success is a further test: improved motion tracking does not by itself establish better pick-and-place performance.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/system-identification.html" title="Measure physical motion, fit a simulation model, then validate motion and policy behavior" loading="lazy" style="display:block; width:100%; height:600px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/system-identification.svg
:alt: Measure physical motion, fit a simulation model, then validate motion and policy behavior
```
````

## Anchor-Lab and AnchorBench

[NVIDIA Anchor-Lab](https://huggingface.co/datasets/nvidia/Anchor-Lab) is a collection of timestamped measurements from physical robot experiments. It covers SO-101 arms and H1/G1 humanoids. The SO-101 recordings include frequency sweeps, backlash-detection motions, and workspace sweeps: different motions reveal different aspects of a robot's response. These measurements provide a reference for calibrating and validating simulation models.

The [SO-101 AnchorBench comparison](https://huggingface.co/VigneshBhavan/so101-newton-actuator-ab-paired-checkpoints) shows how fitted actuator parameters can be studied in a policy-learning workflow. Its Hugging Face page brings together baseline and fitted actuator profiles, paired policy checkpoints, reproduction notes, and comparison videos. The accompanying [paired demonstrations](https://huggingface.co/datasets/VigneshBhavan/so101-newton-actuator-ab-paired-demos) use matched commands and scenes to help isolate the effect of the actuator model.

The published bundle supplies a fitted profile and reproduction records, but not a complete command sequence for fitting a new AnchorBench model from Anchor-Lab telemetry.

## Teleop Comparison: Default and SysID Assets

A poorly tuned robot asset can move differently from the physical robot it represents. This teleoperation comparison overlays the default SO-101 asset, the asset with a fitted SysID layer, and the measured hardware motion. The separation between them illustrates the actuation gap.

| Color | What it shows |
|-------|---------------|
| **Yellow** | Default USD asset. |
| **Red** | SysID USD layer applied on top of the default USD asset. |
| **Light blue** | Joint values read back from the physical SO-101 being driven. This readback adds a little more delay. |

Compare how closely the simulated motion follows the light-blue hardware readback. Account for the readback delay when interpreting timing differences; not every visible lag comes from the actuator model.

```{raw} html
<figure style="margin: 1.5rem auto;">
  <video controls playsinline preload="metadata" width="1280" height="720" style="width: 100%; height: auto;" aria-label="SO-101 teleop comparison of default USD, SysID USD layer, and measured hardware motion" aria-describedby="teleop-sysid-comparison-caption">
    <source src="_static/videos/so101-teleop-sysid-comparison.mp4" type="video/mp4">
    <a href="_static/videos/so101-teleop-sysid-comparison.mp4">Download the SO-101 teleop and SysID comparison.</a>
  </video>
  <figcaption id="teleop-sysid-comparison-caption">Yellow: default USD. Red: SysID USD layer over the default asset. Light blue: measured hardware readback, with additional delay.</figcaption>
</figure>
```

## Example SysID Motion: Chirp Sweep

A chirp sweep gradually changes the frequency of an oscillating command. Watch the lag, amplitude, and settling of the measured motion as the sweep progresses. A single static pose would not reveal these response differences.

```{raw} html
<figure style="margin: 1.5rem auto;">
  <video controls playsinline preload="metadata" width="1280" height="720" style="width: 100%; height: auto;" aria-label="Chirp Sweep: SO-101 system identification motion">
    <source src="_static/videos/chirp-sweep.mp4" type="video/mp4">
    <a href="_static/videos/chirp-sweep.mp4">Download the Chirp Sweep SysID motion example.</a>
  </video>
</figure>
```

```{figure} images/chirp-sweep-joint-response.png
:alt: Six joint-response plots for the chirp sweep, comparing dashed commanded trajectories with solid motor encoder measurements as frequency increases. Arm positions are in degrees; gripper opening is in percent.
:width: 100%

Joint responses from the chirp sweep above. Dashed lines show the commanded motion; solid lines show motor encoder measurements. Notice where the measured motion lags or has a smaller amplitude as the oscillations get faster.
```

## Workshop Comparison: SysId and Original Actuators

Watch these 10 paired trials with SysId actuators on the left and original actuators on the right. The video plays at 5× speed.

The policy used here was not trained to robust task performance, but the comparison makes failures while moving toward the vial visible. Focus on the approach: does the gripper reach the vial in a position where it can grasp it? Use these observations to distinguish approach failures from problems during grasping or placement.

```{raw} html
<figure style="margin: 1.5rem auto;">
  <video controls playsinline preload="metadata" width="1920" height="610" style="width: 100%; height: auto;" aria-label="SO-101 comparison with SysId and original actuators" aria-describedby="sysid-comparison-caption">
    <source src="_static/videos/sysid_vs_original_10_pairs_5x.mp4" type="video/mp4">
    <a href="_static/videos/sysid_vs_original_10_pairs_5x.mp4">Download the SysId and original actuator comparison.</a>
  </video>
  <figcaption id="sysid-comparison-caption">SysId actuators (left) and original actuators (right).</figcaption>
</figure>
```

### Simulation Evaluation Results

In a separate simulation comparison, we evaluated two policies with both actuator profiles. Each cell below reports successful placements out of **100 trials**, using the same scene resets, a 16-action execution horizon, and a 30-second trial limit.

| Policy training data | Evaluated with SysID actuators | Evaluated with original actuators |
|---|---|---|
| Collected with SysID actuators | **96/100 (96%)** | **86/100 (86%)** |
| Collected with original actuators | **57/100 (57%)** | **49/100 (49%)** |

The SysID-trained policy performed better with either actuator profile. For that same policy, switching evaluation from original to SysID actuators improved success by **10 percentage points**.

This isn't always the case with SysID, and likely points to poor tuning with the original model to have such a delta in simulation.

## Key Takeaways

- SysId uses physical measurements to estimate simulation parameters.
- Timing, units, and motion coverage determine whether a fit is meaningful.
- Matched demonstrations help isolate the effect of actuator profiles.
- Verify both motion-model accuracy and downstream task performance.

## Resources

- [Anchor-Lab measurements](https://huggingface.co/datasets/nvidia/Anchor-Lab)
- [SO-101 profiles and reproduction notes](https://huggingface.co/VigneshBhavan/so101-newton-actuator-ab-paired-checkpoints/blob/123b6cbc48f7bb948397cb0ad5b9dac8a4ab38d8/reproduction/README.md)
- [Paired demonstrations](https://huggingface.co/datasets/VigneshBhavan/so101-newton-actuator-ab-paired-demos)

## What's Next?

Continue to [Explore and Experiment](15-explore.md) to choose a follow-up experiment and find further resources.
