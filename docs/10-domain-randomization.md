# Sim-to-Real Strategy 1: Domain Randomization

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/dr-perception-comparison/dr-external-resets.gif
:alt: Simulation resets showing varied lighting, materials, and object placement.
:width: 100%
:class: course-banner
```

:::{dropdown} What Do I Need for This Module?
Lecture. No robot or running container required.
:::

## Learning Objectives

By the end of this session, you'll be able to:

- **Explain** domain randomization and why it improves sim-to-real transfer

- **Apply** domain randomization to augment demonstrations

## What Is Domain Randomization?

Domain randomization (DR) is a sim-to-real strategy based on this idea: instead of making simulation perfectly match reality, randomize simulation parameters during training so the policy becomes robust to any value in the range, including real-world values.

Put in simple terms: think about how you might learn to catch a ball.

If you always catch it in the same pose, you might not learn to _reach_ and catch the ball, or hold the glove in different orientations. By varying where the ball is thrown to you when you practice, you will likely learn a better "policy" for catching the ball.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/domain-randomization.html"
    title="Domain randomization workflow: select a step for details" loading="lazy"
    style="display:block; width:100%; height:780px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/domain-randomization.svg
:alt: Vary simulation conditions, record successful demonstrations, post-train GR00T, and evaluate in simulation and reality.

Randomization contributes learning examples through collection and post-training; evaluation checks transfer.
```
````

::::{dropdown} What should we randomize?
:animate: fade-in

A useful rule of thumb: **consider what you expect to change in your scene, then vary those parameters**. Think about object mass and scale, positions, and orientations.

For example, we noticed that clamping the robot to the foamcore could tilt its base. To account for this, we randomize base tilt from **−3° to +6°**. We also vary the external camera's tilt by **±5° from its nominal angle** to account for differences in mounting.

The following are possible randomization categories. The code tour below identifies which are enabled for the current SO-101 task.

:::{figure} images/dr-perception-comparison/dr-external-resets.gif
:width: 600px
:alt: Domain Randomization Example

Domain Randomization Example. Each time the scene is reset, a number of parameters are randomized within given ranges.
:::

**Visual Domain Randomization:**
- Object colors, textures, materials
- Lighting intensity, direction, color temperature
- Camera position, orientation, field of view
- Background appearance

Physics and actuation can also be randomized:

**Physics Domain Randomization:**
- Object mass, friction, restitution
- Joint damping, friction, limits
- Actuator delays, noise, offsets
- Sensor noise characteristics

### Strengths and Limitations

**Strengths:**
- No real-world data required for augmentation
- Handles unknown parameters
- Scales to many parameters
- Simple to implement

**Limitations:**
- More art than science (tuning ranges)
- Trades optimality for robustness
- May produce conservative, slow motions
- Doesn't work well for highly dynamic tasks

::::

## Domain Randomization in Simulation

Randomization runs on environment reset. Saving a take alone does not request a reset; press **R** for a fresh setup.

### Test Domain Randomization

These captures predate the DR consolidation and retain their original task labels.

Switch between **External camera** and **Wrist camera** to compare the standard environment, DR, Perception-DR, and real camera images. The DR and Perception-DR GIFs cycle through eight environment resets, showing changes in lighting, materials, and scene placement. The standard environment and real images are still references; their poses and layouts differ from the randomized scenes.

::::::{tab-set}
:::::{tab-item} External camera

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item}
**Standard environment**

```{image} images/dr-perception-comparison/base-external.png
:alt: Standard environment, external view.
:width: 100%
```
:::
:::{grid-item}
**Domain Randomization · resets**

```{image} images/dr-perception-comparison/dr-external-resets.gif
:alt: Domain Randomization, external view.
:width: 100%
```
:::
:::{grid-item}
**Perception-DR · resets**

```{image} images/dr-perception-comparison/perception-external-resets.gif
:alt: Perception-DR, external view.
:width: 100%
```
:::
:::{grid-item}
**Real camera · reference**

```{image} images/dr-perception-comparison/real-external.png
:alt: Real camera · reference, external view.
:width: 100%
```
:::
::::
:::::
:::::{tab-item} Wrist camera

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item}
**Standard environment**

```{image} images/dr-perception-comparison/base-wrist.png
:alt: Standard environment, wrist view.
:width: 100%
```
:::
:::{grid-item}
**Domain Randomization · resets**

```{image} images/dr-perception-comparison/dr-wrist-resets.gif
:alt: Domain Randomization, wrist view.
:width: 100%
```
:::
:::{grid-item}
**Perception-DR · resets**

```{image} images/dr-perception-comparison/perception-wrist-resets.gif
:alt: Perception-DR, wrist view.
:width: 100%
```
:::
:::{grid-item}
**Real camera · reference**

```{image} images/dr-perception-comparison/real-wrist.jpg
:alt: Real camera · reference, wrist view.
:width: 100%
```
:::
::::
:::::
::::::

### Code Tour: Domain Randomization Implementation

::::::{dropdown} Read more about the domain-randomization implementation

Start with `source/sim_to_real_so101/tasks/vials_to_rack_env_cfg.py`. `VialsToRackEventCfg` defines object resets; `VialsToRackEventDRCfg` adds DR settings.

| Parameter | Base task | DR task |
|-----------|-----------|---------|
| Vial and rack placement | Sampled by `mdp.reset_vials_rack` | Same placement sampler |
| Robot base tilt | Nominal pose | −3° to +6° at reset; positive tilt leans back toward the lightbox opening |
| Lightbox exposure | Fixed at 2.0 | 1.0 to 3.0 |
| Sky light | No DR dome light | HDRI swaps, exposure −1.0 to 1.0, temperature 4500–7000 K |
| Mat yaw | −0.1 to 0.1 radians | −0.3 to 0.3 radians |
| Printed robot material | Orange | Orange, consistent across printed parts |
| External camera tilt | Nominal pose | ±5° around nominal, about the camera's local horizontal axis |
| External camera focal length | Nominal | 97–100% of nominal (equal or wider field of view) |
| External camera position and wrist camera calibration | Fixed | Fixed |

These are this checkout's settings. Camera position, robot color, or physics randomization require deliberate configuration changes; the DR task name does not enable every possible randomization.

Reset events use Isaac Lab's `EventTerm` API. For example:

```python
reset_lightbox_light_exposure = EventTerm(
    func=mdp.randomize_light_exposure,
    mode="reset",
    params={
        "exposure_range": (1.0, 3.0),
        "asset_cfg": SceneEntityCfg("lightbox_light"),
    },
)
```

The implementations live in `source/sim_to_real_so101/mdp/resets.py`. ovrtx loads its scene separately, so visual changes must reach the renderer through the workshop's attribute or asset-path write helpers. Editing only the live USD stage will not update rendered images. Global HDRI changes run on full-scene resets; allow a few warmup frames for texture loading.

Edit event parameters in the mounted `source/` directory, restart the simulation, and inspect both camera feeds. Preserve joint ordering, joint normalization, and camera calibration when using existing datasets and policies.

::::::

## Key Takeaways

- Domain randomization makes policies robust by training on varied conditions
- DR augmentation multiplies your dataset with varied conditions
- Combined real demonstrations + DR augmentation is a powerful baseline

## What's Next?

Continue to [Teleoperating in Sim](08-simulation-teleoperation.md) to explore teleoperated and state-machine demonstrations.
