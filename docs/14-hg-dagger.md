# Sim-to-Real Strategy 3: Learn From Corrections With HG-DAgger

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/hg-dagger-annotated-header.svg
:alt: Annotated HG-DAgger correction episode showing the vial tip over the solid area between rack slots.
:width: 100%
:class: course-banner annotated-header
```

:::{dropdown} What Do I Need for This Module?
Lecture. No robot or running container required.
:::

A policy may reach the vial, then miss the grasp or stop before lifting. In this session, you’ll learn how human corrections help a policy improve in the situations where it struggles.

## Learning Objectives

- **Explain** how human corrections add useful training examples.

## What Is HG-DAgger?

**HG-DAgger** stands for **Human-Gated Dataset Aggregation**. You watch the policy attempt the task, take over when it needs help, and return control after correcting the motion. These corrections teach the policy what to do in situations it reaches on its own, such as a missed grasp. [HG-DAgger paper](https://arxiv.org/abs/1810.02890)

The workshop tool records your corrections for a separate fine-tuning run. The policy's weights stay the same while you collect data.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/hg-dagger.html"
    title="HG-DAgger workflow: select a step for details" loading="lazy"
    style="display:block; width:100%; height:780px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/hg-dagger.svg
:alt: Watch the policy, pause and align the leader, save a human correction, post-train offline, and reevaluate unaided.

HG-DAgger collects corrections at policy-visited states for a separate training round.
```
````

:::{dropdown} How is HG-DAgger different from reinforcement learning?

Both can improve a policy after its initial training, but they use different feedback.

| Method | Feedback for learning |
|---|---|
| HG-DAgger | A human supplies action targets in states where the policy needs help. Those corrections become supervised training examples. |
| Reinforcement learning (RL) | A reward signal scores behavior. Training seeks actions that earn more reward over time. |

This lesson collects human corrections for a separate training run. It does not run an RL training loop.
:::

## Why Corrections Help

Demonstrations show familiar ways to complete the task. A small error can take the policy into a state it has rarely seen. A human correction adds an example of how to recover from that situation.

Select a label to follow the path from demonstration to recovery. The paths below represent **robot states**, not the arm's physical motion. Here, **green means human correction**; the recording interface shown later uses its own control-status colors.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/hg-dagger-state-map.html"
    title="HG-DAgger state map: demonstrations, unfamiliar states, and human recovery" loading="lazy"
    style="display:block;width:100%;height:680px;border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/hg-dagger-state-map.svg
:alt: A policy leaves familiar demonstration states; a human correction guides it back and supplies recovery examples for later training.

Corrections add observation–action pairs at states the policy reaches during its own attempts.
```
````

## How It Works

1. **Watch** the policy attempt the task. Look for a repeatable failure, such as grasping without lifting.
2. **Pause** the policy and **align** the leader arm with the follower.
3. **Correct** the motion with the leader. For example, demonstrate lifting the vial clear of the mat.
4. **Save** the correction and **return** control to the policy. You can repeat this several times in one rollout.
5. **Mix** the corrections with a sample of the original demonstrations and **fine-tune** the policy.
6. **Evaluate** the updated policy without help. Use the remaining failures to plan another collection round.

Watch when the operator takes over in this recording: **green** shows policy control and **red** shows a human correction with the leader arm.

```{raw} html
<figure style="margin: 1.5rem auto;">
  <video controls playsinline preload="metadata" width="1280" height="720" style="width: 100%; height: auto;" aria-label="HG-DAgger policy rollout and human correction on the real SO-101" aria-describedby="hg-dagger-caption">
    <source src="_static/videos/hg-dagger-corrections.mp4" type="video/mp4">
    <a href="_static/videos/hg-dagger-corrections.mp4">Download the HG-DAgger demonstration.</a>
  </video>
  <figcaption id="hg-dagger-caption">Policy control (green) and human corrections (red) during a real SO-101 collection session.</figcaption>
</figure>
```

### Watch the Handoff

This short rollout excerpt shows the policy pause, leader alignment, and human correction. Watch the control status and recording indicator as the operator takes over. The clip plays at normal speed.

```{raw} html
<figure>
  <video controls playsinline preload="metadata" style="width:100%;height:auto" aria-label="Rollout excerpt showing a pause and human correction">
    <source src="_static/videos/hg-dagger-takeover-2.mp4" type="video/mp4">
  </video>
  <figcaption>A short intervention before returning control to the policy.</figcaption>
</figure>
```

## Example Dataset: Just the Corrections

This [vial placement dataset](https://huggingface.co/datasets/sreetz-nv/hg_dagger_vial_placement_correction) contains **only the saved human corrections**. Each episode starts when the operator intervenes and ends when that correction is saved. The autonomous parts of the attempt are not included.

```{raw} html
:file: _includes/dataset-cards/hg-dagger-corrections.html
```

### When to Take Over

Look at the vial tip, not just the gripper. These external-camera frames show the start of two saved corrections:

```{figure} images/hg-dagger-takeover-cues.svg
:alt: Episode 0 with the vial tip marked over the solid area between rack slots, and episode 10 with the tip marked outside the rack.
:width: 100%

Placement errors at the start of corrections: between slots (episode 0) and outside the rack (episode 10).
```

- **Tip over the solid part of the rack:** pause before the robot pushes down between slots.
- **Tip outside the rack:** take over to bring the vial back over a slot.
- **Tip touching the rack without entering:** pause rather than letting the robot keep pressing.

Pause the policy, align the leader with the follower, then correct the placement. These stills show misalignment; watch the live motion and both camera views to judge contact.

Watch these three short correction episodes from the external camera. Each plays at normal speed.

::::{grid} 1 2 3 3
:gutter: 2

:::{grid-item}
```{figure} images/hg-dagger-correction-0.gif
:alt: External-camera view of human correction episode 0 during vial placement.
Episode 0
```
:::

:::{grid-item}
```{figure} images/hg-dagger-correction-10.gif
:alt: External-camera view of human correction episode 10 during vial placement.
Episode 10
```
:::

:::{grid-item}
```{figure} images/hg-dagger-correction-20.gif
:alt: External-camera view of human correction episode 20 during vial placement.
Episode 20
```
:::

::::

**Think back to how GR00T trains:** why can a correction lasting just a few seconds still be useful, even though it doesn't show the whole task?

:::{dropdown} Why short corrections can help
GR00T trains on observation/action windows sampled from episodes. An observation supplies the camera images, robot state, and task instruction; the following actions supply the training target. A short correction can provide several such windows showing what to do at a difficult moment, such as lining up a vial with a rack slot.

The model doesn't need every example to start with picking up the vial. These segments add targeted examples of recovery to the broader task demonstrations. Keep episode boundaries intact so training windows don't join unrelated corrections.
:::

## Baseline vs. Learning From Corrections

Compare the baseline policy on the left with the HG-DAgger policy on the right. Watch the approach, grasp, and placement: where does their behavior differ?

```{raw} html
<figure>
  <video controls playsinline preload="none" width="1280" height="480" poster="images/hg-dagger-baseline-vs-corrections.jpg" style="width:100%;height:auto;" aria-label="External-camera comparison of baseline and HG-DAgger policies" aria-describedby="hg-dagger-comparison-caption">
    <source src="_static/videos/hg-dagger-baseline-vs-corrections.mp4" type="video/mp4">
  </video>
  <figcaption id="hg-dagger-comparison-caption">Baseline (left) and policy trained with corrections (right), viewed from the external camera.</figcaption>
</figure>
```

## What's Next?

Continue to [HG-DAgger: Collect Corrections](14-hg-dagger-practice.md) to align the leader arm and collect corrections with the workshop interface.
