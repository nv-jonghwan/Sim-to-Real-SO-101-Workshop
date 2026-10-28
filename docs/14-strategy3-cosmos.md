# Sim-to-Real Strategy 4: Augmenting Datasets With Cosmos

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/cosmos-transfer-banner.png
:alt: Cosmos Transfer demo showing an SO-101 input episode beside generated footage in a different environment.
:width: 100%
:class: course-banner cosmos-banner
```

:::{dropdown} What Do I Need for This Module?
Lecture. You do not need a connected robot or a running container. Review the source and generated videos, then discuss which variations would be useful for training.
:::

In this session, you'll explore Cosmos as an omnimodel for physical AI, then focus on one application: creating diverse synthetic training data for robot policies. Source and generated video examples illustrate which variations preserve useful training examples.


## Learning Objectives

By the end of this session, you'll be able to:

- **Explain** how Cosmos connects reasoning, world generation, and action modeling

- **Identify** where synthetic video augmentation fits in robot learning

- **Assess** whether generated videos preserve the original task and motion

- **Explain** how to test whether augmentation helps a policy

## Beyond Domain Randomization and Co-Training

In Strategy 1, you used domain randomization to vary configured simulation parameters. Generative augmentation adds another way to vary scene appearance. 

For example, Cosmos 3 video transfer can use a source video and structural controls such as depth or segmentation to generate visual variations. This complements the variations you create in the simulator. [NVIDIA Cosmos 3 transfer examples](https://github.com/NVIDIA/cosmos/tree/main/cookbooks/cosmos3/generator/transfer)

## What Is Cosmos?

**NVIDIA Cosmos** is a platform of world foundation models and tools for physical AI. **Cosmos 3 is an omnimodel** that brings reasoning, world generation, and action generation into one architecture. [NVIDIA Cosmos overview](https://www.nvidia.com/en-us/ai/cosmos/)

The Cosmos 3 family works across language, images, video, audio, and action sequences. Its Mixture-of-Transformers architecture supports both understanding a scene and generating outputs conditioned on that scene. [NVIDIA Cosmos 3 documentation](https://docs.nvidia.com/cosmos/latest/cosmos3/index.html)

```{figure} images/cosmos-omni-model-architecture.png
:alt: Cosmos 3 omni-model architecture connecting an autoregressive text branch and a diffusion branch for vision, audio, and actions through shared multimodal attention.
:width: 100%

Cosmos 3 omni-model architecture, showing shared multimodal attention across autoregressive and diffusion branches.
```

For robot learning, these capabilities support several uses:

- **Understand demonstrations:** reason about objects, interactions, and events in camera footage.
- **Generate training data:** create video variations and plausible future scenes from prompts and other inputs.
- **Explore outcomes:** predict how a scene could evolve under different actions, supporting planning and evaluation.
- **Build policy models:** post-train a World Action Model (WAM), a model that connects observations of the world to robot actions, using data for a particular robot and its cameras.

These uses follow [NVIDIA's Cosmos 3 capability overview](https://www.nvidia.com/en-us/ai/cosmos/). This lesson focuses on data augmentation; the policy you train and deploy in the workshop is GR00T 1.7.

:::{dropdown} Read more about world prediction and action modeling

**Forward dynamics** predicts what happens next from the current observations and proposed controls. **Inverse dynamics** estimates actions that could explain a change between observed states. A **robot policy** uses observations to choose actions for a task. NVIDIA demonstrates these as different applications of Cosmos 3's shared model. [NVIDIA Cosmos 3 research](https://research.nvidia.com/labs/cosmos-lab/cosmos3/)

For an optional exploration, inspect the research examples and identify which inputs and outputs each application needs. Then compare them with the wrist images, external images, joint states, and actions in a workshop episode.

:::

### How Cosmos Works

Consider the video augmentation workflow below. Cosmos 3 uses a prompt and controls such as edges, blur, depth, or segmentation to guide video generation. [NVIDIA Cosmos 3 transfer examples](https://github.com/NVIDIA/cosmos/tree/main/cookbooks/cosmos3/generator/transfer)

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/cosmos-video-transfer.html" title="Source video, appearance prompt, structural control, and task-consistency review" loading="lazy" style="display:block; width:100%; height:600px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/cosmos-video-transfer.svg
:alt: Source video, appearance prompt, structural control, and task-consistency review
```
````


### How Control Signals Shape the Result

Control signals guide which parts of the source video Cosmos should preserve:

- **Edges** guide object outlines and positions.
- **Segmentation** separates regions such as the arm, rack, and vials.
- **Blur** provides the broad color and layout of the scene with less detail.

```{figure} images/cosmos-control-comparison.png
:alt: Cosmos demo showing edge, segmentation, and blur inputs above a comparison of the real input with edge-only, edge-plus-segmentation, and segmentation-only outputs.
:width: 100%

The bottom row compares the real input with three generated results: edges only, edges plus segmentation, and segmentation only.
```

Compare the rack holes, vial positions, and gripper shape. Which controls keep these details closest to the source while still changing the appearance?

::::::{dropdown} Reference: reproduce a Cosmos 3 augmentation

Start with [NVIDIA's Cosmos 3 transfer notebook for Diffusers](https://github.com/NVIDIA/cosmos/blob/main/cookbooks/cosmos3/generator/transfer/run_video_transfer_with_diffusers.ipynb) for setup and control-video examples.

In one SO-101 trial, we prepared an edge-control video from an external-camera clip and prompted Cosmos to change the surrounding laboratory. We used `nvidia/Cosmos3-Nano`, 121 frames at 640 × 480 and 30 FPS, 50 diffusion steps, prompt guidance 3.0, control guidance 1.5, and seed 2026. The result also changed unintended objects, so compare each generated clip with its source before using it for training.

::::::

:::{figure} images/cosmos-augment-1.gif
:alt: Cosmos Augmentation Example 1
:width: 600px

Cosmos Augmentation Example 1
:::

```{figure} images/cosmos-dramatic-restyling.png
:alt: Two Cosmos restylings of the same robot episode: Pink World with a glittery pink mat and robot, and Cartoon Workshop with bold colors and illustrated surroundings.
:width: 100%

Cosmos can also make dramatic appearance changes: the same episode restyled as “Pink World” and “Cartoon Workshop.” Notice how the robot, mat, and background change, then compare the vial and gripper details.
```

## Example Dataset: Cosmos-Augmented Demonstrations

This [Cosmos Transfer dataset](https://huggingface.co/datasets/bdelfino/so101_vials_dr_sts_250ep_20261005_CosmosTransfer) restyles 10 simulation episodes to resemble physical footage, including a felt mat, foam rack, and frosted vials. Both the external and wrist videos are augmented; the recorded states, actions, and timestamps stay unchanged.

```{raw} html
:file: _includes/dataset-cards/cosmos-transfer.html
```

```{figure} images/cosmos-dataset-examples.gif
:alt: External-camera excerpts from augmented dataset episodes 0, 4, and 9, showing the SO-101 moving vials toward the rack.
:width: 640px

Excerpts from augmented episodes 0, 4, and 9, at normal speed.
```

Notice the vial caps, rack color, and gripper contact. Do they stay consistent as the arm moves? The dataset author notes color drift and small geometry differences, and has not tested whether these episodes improve a trained policy. See the [dataset notes](https://huggingface.co/datasets/bdelfino/so101_vials_dr_sts_250ep_20261005_CosmosTransfer/blob/11418dc75d705a1d4ef1b8bcb66ea31b1cf386da/README.md) for the source episodes and augmentation settings.

### What to Look for in Augmented Data

**Visual Diversity**
- Photorealistic rendering variations
- Natural lighting changes
- Background and texture diversity

**Scenario Variation**
- Background and surface changes
- Lighting variations
- Appearance changes preserving recorded action labels

**Physical Consistency**
- Check that frames preserve task geometry
- Verify contact timing and motion against the source
- Reject augmentations that invalidate recorded actions

## Discussion: Assess Video Augmentation

Use the source and generated examples above to discuss:

- Which lighting, surface, or background changes would be useful for training?
- Do the vial positions, gripper shape, and contact timing still match the recorded actions?
- Which examples would you keep or reject, and why?
- How would you compare policies trained with and without augmented data to test whether it helps?

Reject examples that move the vial, change a grasp, or alter contact timing in a way that no longer matches the recorded actions. This lecture uses prepared examples; running Cosmos generation is not required.

## Key Takeaways

- Cosmos 3 connects scene understanding, world generation, and action modeling; video augmentation is one application.
- Domain randomization, real demonstrations, and generative augmentation provide different ways to expand training coverage.
- Inspect generated videos against the recorded actions before using them for policy training.
- Compare policies on the same task to measure whether an augmentation mix improves real-world performance.

## Resources

- [NVIDIA Cosmos](https://www.nvidia.com/en-us/ai/cosmos/) — Omnimodel overview and use cases
- [Cosmos 3 documentation](https://docs.nvidia.com/cosmos/latest/cosmos3/index.html) — Model family, installation, and inference guides
- [Cosmos 3 research](https://research.nvidia.com/labs/cosmos-lab/cosmos3/) — Examples of reasoning, world prediction, and action modeling
- [Cosmos 3 video transfer](https://github.com/NVIDIA/cosmos/tree/main/cookbooks/cosmos3/generator/transfer) — Controlled video generation for augmentation
- [Cosmos Cookbook](https://nvidia-cosmos.github.io/cosmos-cookbook/) — Recipes and examples for Cosmos world foundation models
