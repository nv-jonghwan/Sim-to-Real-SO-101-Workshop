# What Is Sim-to-Real?

```{raw} html
:file: _includes/module-types/lecture.html
```

:::{figure} images/sim-and-real.png
:class: course-banner
:alt: Unitree H1 in simulation and in the real world.

Sim-to-Real with Unitree H1
:::

:::{dropdown} What Do I Need for This Module?
Nothing — this module is theory-only.
:::

## Learning Objectives

By the end of this session, you'll be able to:

- **Define** sim-to-real transfer and its goals

- **Identify** the four major categories of sim-to-real gaps

- **Explain** why transfer is difficult even with high-fidelity simulation

## Sim-to-Real Defined

**Sim-to-real** refers to the process of training a policy in simulation and deploying it on real hardware. The goal is a policy that performs well in the real world despite being trained entirely (or primarily) in simulation.

## Simulation Evaluation in Action

Watch this policy attempt the vial-to-rack task across different simulated scenes. The external camera is on the left and the wrist camera is on the right. Notice both the successful placements and the failures.

```{raw} html
<figure>
  <video controls muted playsinline preload="none" width="1280" height="550" poster="_static/videos/sim-evaluation-10x-poster.jpg" aria-label="Simulation policy evaluation at 10 times speed, with external and wrist camera views" aria-describedby="sim-evaluation-example-caption" style="display:block; width:100%; height:auto;">
    <source src="_static/videos/sim-evaluation-10x.mp4" type="video/mp4">
  </video>
  <figcaption id="sim-evaluation-example-caption">Example simulation evaluation. Playback is <strong>10× speed</strong>.</figcaption>
</figure>
```

## The Sim-to-Real Gap

The **sim-to-real gap** is the performance difference between simulation and reality. A policy achieving high success rates in simulation may perform significantly worse on real hardware.

:::{warning}
The sim-to-real gap is often larger than expected. 

And while colloquially we may discuss “the gap” as if it’s a single entity, the gap is a complex combination of gaps in sensing, actuation, physics, and modeling.

Zero-shot transfer is difficult, so avoid assuming a policy will “just work” on real hardware without systematic testing and iteration.
:::

:::{figure} images/workshop-concepts/slide-26.png
:alt: Overlapping circles represent the source domain in simulation and the target domain in reality. Greater coverage of real conditions supports transfer.
:width: 100%

The source domain is where we train; the target domain is where we want the policy to work.
:::

(actuation-gaps)=
(physics-gaps)=
(sensing-gaps)=
(choosing-a-strategy)=
## Sources of the Gap

You can **teach the policy to handle variation**, **make simulation closer to the real setup**, or combine both. Choose a change that addresses an observed failure, then compare under the same test conditions.

Select a gap in the diagram to explore its examples.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/reality-gap-strategies.html" title="Connect sensing, actuation, physics, and modeling gaps to transfer strategies" loading="lazy" style="display:block; width:100%; height:600px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/reality-gap-strategies.svg
:alt: Connect sensing, actuation, physics, and modeling gaps to transfer strategies
```

**Sensing Gaps**

- Camera models lack real sensor noise, blur, and distortion
- Depth sensors have idealized measurements without artifacts
- Simulated lighting differs from real lighting conditions

**Actuation Gaps**

- Motor models lack friction, backlash, and thermal effects
- Joint dynamics are simplified
- Control loop timing differs between simulation and hardware

**Physics Gaps**

- Contact dynamics (friction, restitution) are approximations
- Deformable objects can be challenging to simulate accurately, especially if they change over time
- Fluid dynamics and granular materials are computationally expensive

**Modeling Gaps**

- CAD models differ from as-built hardware
- Mass and inertia properties are estimates
- Joint reference frames and zero positions may differ from the calibrated robot

````

(modeling-gaps)=
### Modeling Gap Examples

:::::{grid} 1 2 2 2
:gutter: 2

::::{grid-item}
:::{figure} images/so101-modeling-gap.png
:width: 300px
:alt: Close-up of the simulated SO-101 arm, showing its links, joints, and gripper.

**Robot geometry.** Differences in link dimensions or joint placement can change the robot's pose.
:::
::::

::::{grid-item}
:::{figure} images/elbow-reference-frame-offset.svg
:width: 300px
:alt: Elbow diagram comparing the calibrated LeRobot zero direction in green with the USD joint-frame zero in orange.

**Joint reference frames.** Different definitions of zero can produce different poses for the same joint angle. The limits shown are an example, not calibration targets.
:::
::::

:::::

Select either image to view it at full size.

(perception-gap-comparison)=
### Explore the Perception Gap

Appearance differences can contribute to missed grasps or reaches toward empty
space. Similar symptoms can also come from calibration or action execution.

Use the comparison below to inspect rack edges, hole shapes, and fixed gripper
features. Adjust **Sim opacity**, switch to **Side by side**, or use
**Toggle real / sim** to alternate between the images. You can also load your
own saved image pair; the files stay in your browser. No camera stream or robot
connection is needed.

```{raw} html
:file: _includes/wrist-image-comparison.html
```

Here’s the real wrist view beside our perception-tuned simulation. Compare the lighting, textures, and edges.

::::{dropdown} How we adjust the ovrtx camera response

The base vial scene configures grading and tone mapping through
`SO101OVRTXRendererCfg.camera_responses`; DR adds film grain. The profiles live in
`source/sim_to_real_so101/tasks/camera_profiles.py`. The renderer in
`source/sim_to_real_so101/utils/ovrtx/renderer.py` authors response
attributes on each camera's **render product**, so wrist and external views
can use different settings. These are appearance approximations designed to close the perception gap. Consider how you might tune or randomize parameters like this for other tasks.

| Setting | Wrist camera | External camera | What it controls |
|---|---|---|---|
| `grade:gain` | `(1.18, 1.18, 1.182)` | `(1.07, 1.07, 1.07)` | Per-channel image gain. |
| `grade:gamma` | `(1.12, 1.12, 1.12)` | `(1.4, 1.4, 1.4)` | Midtone response. |
| `grade:saturation` | `(1.0, 1.0, 1.0)` | `(1.2, 1.2, 1.2)` | Color intensity; the external profile also enables `colorcorr:enabled`. |
| `grade:whitePoint` | No override | `(0.95, 0.95, 0.95)` | White-point adjustment for the external view. |
| `tvNoise:filmGrain:amount` / `size` | `0.015` / `0.25` | `0.003` / `1.0` | Grain strength and scale. |
| `tonemap:operator` | `"none"` | `"none"` | Bypasses the default `acesApproximation` renderer operator and hands tone mapping to OCIO. |
| Gaussian blur sigma | `0.9` pixels in this example; task default `0.7–1.1` | No added blur | Wrist softness, sampled independently per environment at reset. |

All ovrtx keys in the table have the prefix `omni:rtx:post:`. For example,
these entries from the wrist profile enable grading and a small amount of grain:

```python
# Excerpt from the wrist render-product response profile.
{
    "omni:rtx:post:grade:enabled": True,
    "omni:rtx:post:grade:gain": (1.18, 1.18, 1.182),
    "omni:rtx:post:grade:gamma": (1.12, 1.12, 1.12),
    "omni:rtx:post:tvNoise:enabled": True,
    "omni:rtx:post:tvNoise:filmGrain:enabled": True,
    "omni:rtx:post:tvNoise:filmGrain:amount": 0.015,
    "omni:rtx:post:tvNoise:filmGrain:size": 0.25,
    "omni:rtx:post:tonemap:operator": "none",
}
```

**Blur is separate from those ovrtx attributes.** The workshop applies Gaussian
blur to the wrist camera after rendering, through the Isaac Lab API. Its reset event in
`source/sim_to_real_so101/tasks/vials_to_rack_env_cfg.py` uses:

```python
reset_wrist_blur = EventTerm(
    func=randomize_camera_blur,
    mode="reset",
    params={
        "sensor_cfg": SceneEntityCfg("camera_wrist"),
        "sigma_range": (0.7, 1.1),
    },
)
```

The sampled blur stays fixed until that environment resets. The processed RGB
feeds **display, recording, and policy observations**.
When doing this in practice, check parameters likehighlights and texture as well as overall brightness, then evaluate the
policy to determine whether the adjustment helps transfer.

::::

For an alternate image pair, see the
[wrist-image comparison in the troubleshooting guide](wrist-image-alignment).

## What Makes Transfer Hard?

The sim-to-real gap isn't just about simulation fidelity. Even with perfect simulation, transfer is challenging because:

1. **Distribution shift**: Real-world conditions vary from training
2. **Compounding errors**: Small perception errors lead to large action errors
3. **Unmodeled dynamics**: Real physics has effects that may not be represented in simulation. For example, bearings or linear slides can wear, grease can dry out, and screws can loosen over time, changing friction or alignment.
4. **Temporal differences**: Real-time constraints affect behavior

Before attributing a failure to the policy, check camera assignments, joint order and units, calibration, action conventions, and starting pose. A policy needs compatible inputs and commands as well as a plausible scene.

## Summary

| Gap Category | Examples |
|--------------|----------|
| Sensing | Camera noise, lighting, depth artifacts |
| Actuation | Friction, backlash, thermal effects |
| Physics | Contact dynamics, deformables |
| Modeling | CAD errors, mass/inertia estimates |

Understanding these gaps is essential—throughout this learning path, you'll learn strategies to address each category.
