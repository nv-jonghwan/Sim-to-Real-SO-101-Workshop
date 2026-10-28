# Sim-to-Real Strategy 2: Co-Training With Real Data

```{raw} html
:file: _includes/module-types/lecture.html
```

::::{container} cotraining-banner

:::{container} cotraining-banner-panel
```{image} images/task.png
:alt: Simulated SO-101 and vial rack shown as a wireframe scene.
```

Simulation
:::

:::{container} cotraining-banner-panel
```{image} images/so101_rack_task.png
:alt: Physical SO-101 holding a vial above the yellow rack.
```

Real robot
:::

::::

:::{dropdown} What Do I Need for This Module?
Lecture. No robot or running container required.
:::

In this session, you'll learn how simulated and real demonstrations contribute to co-training.


## Learning Objectives

By the end of this session, you'll be able to:

- **Explain** co-training strategies for mixing sim and real data

## What Is Co-Training?

Co-training combines data from multiple sources—simulation and real-world—during policy training.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/cotraining.html"
    title="Co-training workflow: select a step for details" loading="lazy"
    style="display:block; width:100%; height:780px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/cotraining.svg
:alt: Review simulation and real demonstrations, check sampling exposure, post-train one policy, and evaluate each domain separately.

Simulation and real demonstrations contribute complementary examples. The training sampler controls their exposure.
```
````

The selected course checkpoint combines 10 real demonstrations with 75 simulated teleoperation demonstrations. You'll evaluate it in [Co-Training in Practice](13-cotraining-practice.md).

You'll have a chance to experience policies trained with various mixes of data.

:::{figure} images/real_demos_vial_rack.gif
:alt: Physical demonstration
:width: 600px

Physical demonstration of the task with teleoperation.
:::

:::{tip}
View a dataset of real-only demonstrations using the Hugging Face Dataset Visualizer [here](https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fsreetz-nv%2Fso101_teleop_vials_rack_left_real_50%2Fepisode_0).
:::

### The Data Challenge

| Data Source | Quantity | Quality | Reality Match |
|-------------|----------|---------|---------------|
| **Simulation** | Abundant | Consistent | Approximate |
| **Real teleop** | Limited | Variable | Exact |

Neither source alone is ideal:
- **Sim-only**: Abundant but doesn't match real-world distribution
- **Real-only**: Matches reality but quantity is limited

**Co-training** leverages both.

:::{note}
There isn't one co-training recipe that works for every task. The useful sim/real mix depends on data quality, coverage, and how closely simulation matches your setup. Test on your robot, then adjust the mix and collect examples around its failures.
:::
