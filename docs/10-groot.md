# Isaac GR00T: Vision-Language-Action Models

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/workshop-concepts/slide-35.png
:alt: GR00T architecture connecting image and language inputs to robot actions.
:width: 100%
```

:::{dropdown} What Do I Need for This Module?
Mostly theory with code examples. No additional hardware is required beyond a computer with the `so101-workshop` container built.
:::

In this session, we'll explore the VLA model called NVIDIA Isaac GR00T, how it works, and see examples of it in action.

## Learning Objectives

By the end of this session, you'll be able to:

- **Explain** what vision-language-action models are and why they're powerful

- **Describe** the GR00T architecture and its components

- **Understand** how VLAs differ from traditional robot learning approaches

- **Explain** how batch size, training steps, and action horizons affect the workflow

- **Design** a checkpoint-continuation experiment, separating optimizer state, learning-rate schedules, and data sampling

## What Is GR00T?

[NVIDIA Isaac GR00T](https://developer.nvidia.com/isaac/gr00t) (Generalist Robot 00 Technology) is a research initiative and development platform for developing general-purpose robot foundation models and data pipelines to accelerate humanoid robotics research and development.

It provides:

- **Pre-trained visual understanding** from large-scale data
- **Language-conditioned behavior** for flexible task specification
- **Action generation** suitable for real-time robot control

In this course, we'll use GR00T 1.7 models post-trained for the SO-101 robot.

:::{note}
**Training time in this course**

Training time depends on hardware and run settings. Train your own policy or use a compatible LeRobot GR00T 1.7 checkpoint supplied for your workshop. See [Datasets and Models](datasets-and-models.md) for compatibility guidance.

:::


## What Is a Vision-Language-Action Model?

**Vision-Language-Action (VLA) models** take visual input, robot state, and language instructions and output low-level or mid-level actions for an embodied agent, such as a robot.

```
Input: Camera image (1 or more) + Robot state + "Pick up the red vial and place it in the rack"
Output: Sequence of joint positions/velocities to execute the task
```

### Modular Pipelines and Learned Policies

A modular robot pipeline might estimate an object's pose, plan a motion, and send that plan to a controller. A VLA learns a mapping from images, task text, and robot state to action targets. For vial placement, the policy learns from examples of what the robot saw and did instead of requiring a hand-written grasp-and-place plan for each observation.

Both approaches still depend on sensing, calibration, and reliable control. A learned policy also depends on demonstration coverage: the instruction alone does not teach it how to recover from an unfamiliar grasp.

### The Data Pyramid

:::{figure} images/workshop-concepts/slide-37.png
:alt: Data pyramid: human videos and web data at the base, simulated and synthetic data in the middle, and real-robot data at the top.
:width: 100%

The pyramid shows complementary data sources, not prescribed proportions. Our workshop focuses on simulation and real-robot demonstrations for post-training.
:::

### Defining Terminology

::::::{dropdown} Read more about model weights, pre-training, post-training, fine-tuning, and inference

#### Model Weights and Parameters

**Model weights**, also called **parameters**, are the learned numbers inside a neural network. This course uses the two terms interchangeably. Training adjusts the weights; inference only reads them. **Hyperparameters**, such as batch size and learning rate, are different: you choose them before training, and they control how the weights are updated.

#### Understanding VLA Training Stages

VLA models are not trained in a single step. They go through distinct phases, each building on the previous one.

Understanding these stages helps explain how a model progresses from broad world knowledge to task-specific robot behavior, and why each phase matters for sim-to-real transfer.

**Pre-training** is the first and largest training phase. The model learns general representations from internet-scale data, including images, text, video, and increasingly, robot demonstrations. 

The model develops reusable visual, language, and action representations before adaptation to your specific robot task. Broad images, language, and human video contribute visual and language knowledge; robot experience connects observations with actions. SO-101 demonstrations then supply the details of this arm, camera setup, and vial-placement task. These are data roles, not fixed dataset proportions or a universal training order.

**Post-training** is the umbrella term for everything that happens after pre-training to make a general model useful for a specific robot, task, or environment. 

This is where a pretrained foundation model is adapted to a specific embodiment and task using demonstrations that map observations and language instructions to robot actions. Post-training is computationally intensive and typically requires several hours on GPU hardware.

:::{note}
This is the stage you run in this course: taking the pretrained GR00T 1.7 foundation model and adapting it to SO-101 data collected in simulation.
:::

**Fine-tuning** is a specific form of post-training where you continue training on a smaller, targeted dataset to improve performance in a specific setting. 

For example, after post-training on simulation data, you might fine-tune on a small set of real-robot demonstrations to reduce the sim-to-real gap. Fine-tuning aims to preserve general capabilities while adapting behavior to new conditions.

**Inference** is when the trained model runs in real time. It receives camera frames and a language instruction, then outputs joint position commands. 

No learning happens during inference because model weights are frozen. Speed matters here. Techniques such as action chunking, where the model predicts multiple timesteps at once, reduce forward passes and produce smoother motion. On modern GPU hardware, this supports real-time closed-loop control.

::::::

### Training and Inference

Training changes selected model weights; inference uses the saved weights with new observations. A **frozen** component still computes features, but its weights do not receive optimizer updates. The base recipe freezes vision and language; the optional vision-unfreezing experiment lets visual features adapt to task images. More trainable parameters require more memory and can overfit a small dataset, so judge the change through matched rollouts.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/gr00t-training-stages.html" title="GR00T training stages: explore frozen and trainable components" loading="lazy" style="display:block; width:100%; height:540px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/gr00t-training-stages.svg
:alt: Pretrained weights initialize post-training, where demonstration targets and an optimizer update selected components; inference uses the saved policy with fixed weights.

Post-training adapts selected weights to SO-101 demonstrations. Inference uses the resulting checkpoint without updating its weights.
```
````

### Architecture Overview

GR00T 1.7 conditions action generation on images, language, and robot state. Its vision-language backbone is Cosmos-Reason2-2B, and its action head uses flow matching to generate action chunks. See the [GR00T 1.7 model card](https://huggingface.co/nvidia/GR00T-N1.7-3B).

The conceptual **System 2** role interprets images and language; the **System 1** role generates actions from those features and the robot state. This terminology comes from the [GR00T dual-system architecture](https://arxiv.org/abs/2503.14734). The controller applies returned actions, then fresh observations close the loop. This schematic describes data flow; it does not imply that the policy returns a human-readable plan.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/gr00t-observation-action.html" title="GR00T observation-to-action workflow: explore inputs, model components, and feedback" loading="lazy" style="display:block; width:100%; height:540px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/gr00t-observation-action.svg
:alt: Images and language enter the GR00T vision-language backbone; its features and robot state condition the action head, which returns action chunks for control and observation feedback.

Images, language, and joint state condition the next action chunk; new observations provide feedback without changing model weights.
```
````

The Cosmos-Reason2-2B backbone inside GR00T is different from the separate [Cosmos 3 video augmentation demo](14-strategy3-cosmos.md). Here it supplies features for action prediction; the later demo generates visual variations of recorded clips.

### Key Components

::::::{dropdown} Read more about the vision, language, and action components

**Vision Encoder**: Processes camera images into feature representations
- Supplies visual evidence about objects and their spatial relationships
- May remain frozen or be trained in the workshop's optional experiment

**Language Encoder**: Processes task instructions
- Maps natural language to task embeddings
- Conditions behavior on the instruction alongside visual observations

**Cross-Modal Fusion**: Combines vision and language
- Attention mechanisms to relate visual features to language
- Grounds language concepts in visual observations

**Action Decoder**: Generates robot actions
- Conditioned on fused visual-language features
- Outputs appropriate action representation (joint positions, velocities, etc.)

::::::

## What Happens in One Step of GR00T Training?

One **training step** is an optimizer update, not an episode or a robot movement. A batch supplies observation/action windows; GR00T computes a loss and uses it to adjust trainable weights.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/groot-training-step.html" title="One GR00T training update: batch size, action horizon, trainable components, and learning rate" loading="lazy" style="display:block;width:100%;height:850px;border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/groot-training-step.svg
:alt: Sample windows, prepare action and noise targets, compute loss and gradients, then update trainable weights.

Batch size counts windows; the training horizon sets targets per window; learning rate scales optimizer updates. Frozen weights do not change.
```
````

The action head uses [flow matching](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/policies/groot/groot_n1_7.py): it learns a flow from noise toward demonstrated action chunks. The **training horizon** sets the target window, starting at the sampled frame; the rollout horizon controls how many actions are used during evaluation.

Our verified sim-only and mixed HG-DAgger 20,000-step runs took about **12½ and 13½ hours**, respectively, on a **single H100 GPU**. These times include checkpoint saving, but exclude dataset preparation, upload, and evaluation. Training time varies with the recipe and implementation.

(hands-on-run-gr00t-post-training-yourself)=
::::::::{audience} learner

## Reference: Post-Train Your Own Model

```{include} _includes/groot-post-training.md
```

::::::::

::::::::{audience} event

## Reference: Post-Train Your Own Model

We won't have time to train during the workshop, so we'll use prepared checkpoints. These instructions are for trying post-training afterward.

:::::::{dropdown} Training instructions for later

```{include} _includes/groot-post-training.md
```

:::::::

::::::::

## Experiment Technique: Continue Training a Checkpoint

You can train an existing policy further without repeating its earlier updates. For example, start from a 50,000-step checkpoint and add 20,000 updates to explore what more training does. Preserve the original checkpoint and compare both policies using the same evaluation conditions. More training can improve behavior, leave it unchanged, or overfit the demonstrations.

::::::{dropdown} Read more about continuing a checkpoint, optimizer state, and data mixtures

### Choose What to Restore

- **Resume the training run:** restore weights, optimizer state, scheduler state, and the update counter. This is useful for an interrupted run. It requires the full training checkpoint, including training state, rather than only an exported policy. In this mode, `--steps=70000` is the total target, so resuming at 50,000 leaves 20,000 updates. Inspect the restored learning-rate schedule before extending a completed run; a rate that has decayed near zero may produce little further learning.
- **Start a new fine-tuning run from saved weights:** load the policy and its saved processors, then create a fresh optimizer and schedule. With `--resume=false`, `--steps=20000` means 20,000 additional updates, counted from zero in the new run. This is useful for testing a new recipe or introducing real demonstrations.

In LeRobot, `--policy.path` selects the trained policy and loads its configuration; the resolved configuration records that location as `pretrained_path`. GR00T's `base_model_path` still identifies the underlying foundation-model assets. Preserve the checkpoint's compatible base-model revision, camera keys, joint order, action representation, horizons, and processors.

### Example: Add 20,000 Updates

Run inside the workshop container. Set `CHECKPOINT` to your actual LeRobot `pretrained_model` directory, containing the weights, policy configuration, processors, and saved `train_config.json`. The example reuses that training configuration and dataset, with a new output directory and a fresh optimizer. Check that its dataset and base-model paths are accessible in this container.

```bash
export CHECKPOINT="outputs/train/your_hf_username/your_model/checkpoints/050000/pretrained_model"
export CONTINUE_OUTPUT="outputs/train/your_hf_username/your_model_continue20k"
lerobot-train --config_path="$CHECKPOINT/train_config.json" --policy.path="$CHECKPOINT" --resume=false --steps=20000 --use_policy_training_preset=true --policy.optimizer_lr=1e-5 --policy.max_steps=20000 --policy.warmup_ratio=0.05 --policy.push_to_hub=false --save_checkpoint_to_hub=false --save_checkpoint=true --save_freq=5000 --output_dir="$CONTINUE_OUTPUT" --job_name=continue20k --wandb.enable=false
```

The example's `1e-5` peak learning rate and 5% warmup are experiment settings, not a proven optimum. With this preset, `policy.max_steps` supplies the warmup calculation; the outer `steps` sets the update budget. The new `020000` checkpoint represents 50,000 earlier updates plus 20,000 additional updates. Batch size, augmentation, and which model components are frozen come from the saved configuration; review the resolved settings before training.

### Example: Match the Gripper Mapping

A gripper percentage can mean a different physical opening when its encoder
calibration differs. Collection and simulation inference share `utils/gripper_calibration.py`, with 1485 ticks as the
default. For a model known to have used the older 1531-tick span, add
`--gripper_span_ticks 1531` to the usual `lerobot_eval` command. Both observation
and action conversions use that span; the five arm coordinates stay unchanged.
This override assumes the same jaw-angle zero.

A measured robot mapping can similarly translate gripper values without changing
model weights. Here is the calculation only; it does not move or connect a robot:

```python
from sim_to_real_so101.utils.gripper_calibration import GripperCalibration

model = GripperCalibration(span_ticks=1531)  # Known training convention.
robot = GripperCalibration()  # Workshop default; replace with measured span/zero.
model_command = 45.0
robot_command = robot.degrees_to_percent(model.percent_to_degrees(model_command))
model_observation = model.degrees_to_percent(robot.percent_to_degrees(robot_command))
print(robot_command, model_observation)  # About 46.39%, then 45%.
```

For deployment, this calculation belongs before policy state normalization and
after action decoding. The example is not automatically installed into
`lerobot-rollout`. Measure the robot's encoder span **and** physical jaw-angle
zero in the same frame; retain the robot driver's limits. Matching gripper
coordinates does not correct other arm offsets or establish real-task success.

### Is a Fresh Optimizer Better?

The model weights store learned behavior. Adam's optimizer state stores running estimates of gradient direction and magnitude that guide future updates. Resetting those estimates preserves the weights.

A reset may help when moving from simulation-only data to a sim/real mixture because the gradient distribution changes. It also discards potentially useful history and can make early updates less stable. Keeping optimizer state can be useful when continuing the same objective and data. Neither choice guarantees better performance.

**An optimizer reset and a learning-rate restart are separate choices.** Continuing with a useful learning rate after a schedule has decayed can matter even without resetting Adam. To test the reset itself, start from identical weights and keep the sampled batches, trainable parameters, update budget, and learning-rate schedule identical; change only whether optimizer state is restored. Extra training plus a reset plus a different schedule tests the whole recipe, not the reset alone.

### Adding Real Data: Control the Sampling Ratio

Two useful experiments are starting from the simulation-trained checkpoint and continuing on mixed sim/real data, or starting from pretrained GR00T and using that mixture from the beginning. The first reuses task-specific learning; the second exposes the policy to real examples earlier. Account for the first stage's training cost and data exposure when comparing them. Continuing on real data alone is a separate experiment and may overfit a small collection.

The sampling ratio controls how often training selects each source, independently of how many demonstrations you store. At batch size 32, a 50% real / 50% sim ratio gives about 16 examples from each source on average; 25% real gives about 8. A weighted sampler produces those proportions over many draws, while a fixed batch composition can enforce exact counts.

For uniform sampling within each source, assign each eligible real training frame weight `p_real / N_real` and each eligible simulated frame weight `(1 - p_real) / N_sim`. Here, `N_real` and `N_sim` count eligible training frames, not episodes. More real-data sampling revisits the limited real demonstrations more often; it does not create new diversity. Log the observed sampling proportions and monitor overfitting.

:::{note}
**Check the trainer before setting a ratio.** The LeRobot `v0.6.0` training path used by this lesson shuffles eligible frames and does not expose a sim/real mixture-ratio flag. Its GR00T `balance_dataset_weights` and `balance_trajectory_weights` fields are unused by this path. Merging datasets alone therefore does not enforce a chosen ratio: longer episodes contribute more frames. Explicit ratios require a trainer or sampler that supports source weighting and retains each frame's source identity. The weights above describe that experiment design, not an additional command-line option for the example.
:::

### Make the Comparison Informative

Keep some demonstrations aside for testing: never use them to train the model or calculate the normalization statistics that scale its inputs and actions. Checking predictions against those unseen demonstrations is called **held-out validation**. A **rollout test** instead lets the model control the arm and measures whether it completes the task. These checks measure different things; prediction error can improve while task success worsens, or vice versa.

Compare the original checkpoint, a continuation with the same data and trainable components, and the proposed change using the same test conditions. This control helps distinguish gains from extra updates from gains due to unfreezing or adding real data. Change one factor at a time, record total updates and sampled examples per source, and test sim-to-real claims on the real task as well as in simulation.

For implementation details, see [LeRobot's training configuration](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/configs/train.py) and [frame sampler](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/datasets/sampler.py). The [Adam paper](https://arxiv.org/abs/1412.6980) explains optimizer state, and [Sim-and-Real Co-Training](https://arxiv.org/abs/2503.24361) studies data-mixture choices. Continue with [Co-Training in Practice](13-cotraining-practice.md#optional-collecting-real-demonstrations-with-lerobot) for the workshop's data workflow.

::::::

## Overfitting

More training is not always better. If training loss keeps falling but performance on held-out demonstrations or new rollout conditions gets worse, that can signal overfitting. Evaluate checkpoints along the way rather than choosing by training loss alone. If gains stall, inspect the failures and improve demonstration coverage before simply adding more steps.

Watch how the policy stalls until the vial is moved into just the right position in the gripper. Too little **domain randomization (DR) around the grasp** can leave a model relying on a narrow set of familiar views.

```{raw} html
<figure style="margin: 1.5rem auto;">
  <video controls muted playsinline preload="none" poster="_static/videos/grasp-overfitting-poster.jpg" aria-label="Overfitting example: the policy waits until the vial is repositioned in the gripper" style="display: block; width: 100%; max-width: 56rem; height: auto; margin: 0 auto;">
    <source src="_static/videos/grasp-overfitting.mp4" type="video/mp4">
    <a href="_static/videos/grasp-overfitting.mp4">Watch the grasp overfitting example.</a>
  </video>
</figure>
```

**Vary** vial positions and grasp angles in your demonstrations, then **test** positions you did not train on. More episodes of the same grasp will not provide that missing variety.

## Key Takeaways

- **Start in distribution.** For best results, use a robot starting pose represented in the checkpoint’s training dataset, including gripper opening. Check the actual demonstrations rather than assuming the default home pose matches. An unfamiliar start changes the camera views and robot state, and can cause failures even with a well-trained policy.
- GR00T uses a **System 2** vision-language backbone to interpret images and instructions, and a **System 1** action head to generate action chunks conditioned on those features and the robot state.
- VLA models combine vision, language, and action in a unified architecture
- GR00T provides pre-trained components for accelerated learning
- Action chunking provides smooth, temporally consistent control
- Pre-trained vision encoders enable visual generalization

## Suggested Training Hyperparameters

The values below are used in this lesson's commands. **Treat them as suggested starting points**, not an optimized configuration or a guarantee of success. Dataset quality, task variation, and GPU capacity can require different settings. The older AnchorBench comparison has its own training recipe; do not mix its settings with this GR00T 1.7 example.

:::{dropdown} Training parameter reference

| Parameter | Workshop example | What it controls and how it interacts |
|-----------|------------------|--------------------------------------|
| `--batch_size` | `32` | Number of sampled observation/action windows per GPU process in an update. Larger batches usually need more memory. With the shown distributed launch, effective batch is this value multiplied by the number of GPU processes. |
| `--steps` | `20000` | Number of optimizer updates, not episodes or robot control steps. Batch size and updates together determine how many training windows are sampled, including repeats. More updates can also overfit a small dataset. |
| `--use_policy_training_preset` | `true` | Selects the GR00T optimizer and learning-rate schedule. The command leaves these to the pinned implementation; inspect the saved run configuration when reproducing a result. |
| `--policy.optimizer_lr` | Not overridden; preset default `1e-4` in LeRobot `v0.6.0` | Sets the peak learning rate used by the preset optimizer. It controls update scale together with the optimizer and schedule. It is not a robot speed setting. |
| `--policy.tune_visual` | `false` in the base example; `true` in the vision-unfreezing example | Controls whether training updates the vision encoder. Unfreezing adds trainable parameters and GPU memory use; test whether it improves rollout performance on your data. |
| `--policy.tune_llm` | `false` | Keeps the language backbone frozen. This is independent of the vision encoder setting. |
| `--dataset.image_transforms.enable` | `true` | Applies training-time image augmentation to vary visual inputs. It complements simulation domain randomization; it does not create additional motion demonstrations. |
| `--policy.chunk_size` / `--policy.n_action_steps` | `16` / `16` | Configures the action window and policy return limit. Longer temporal targets change the learning problem; keep training and deployment configuration compatible. |
| `--policy.use_relative_actions` / `--policy.relative_exclude_joints` | `true` / `'["gripper"]'` | Expresses arm targets relative to the observation state while retaining absolute gripper targets. Deployment must use the matching saved processors. |
| `--policy.embodiment_tag` | `new_embodiment` | Selects the embodiment configuration for this adaptation. This is a model/data configuration choice, not a performance tuning knob. |
| `--policy.use_bf16` | `true` | Enables BF16 autocast for supported computation. It can reduce compute memory and improve throughput; it does not imply every model or optimizer tensor is stored in BF16. |
| `--seed` | `42` | Controls seeded randomness for repeatable comparisons. A fixed seed does not guarantee identical results across GPU counts or software versions. |
| `--save_checkpoint` / `--save_freq` | `true` / `5000` | Saves intermediate models for later comparison. Saving more often uses more storage; it does not add learning updates. |
| `--env_eval_freq` / `--eval_steps` | `0` / `0` | Disables periodic environment evaluation and held-out loss evaluation in this command. Training loss alone does not establish grasp or placement success; run the evaluation lessons separately. |
| `--log_freq` / `--wandb.enable` | `10` / `true` | Controls reporting cadence and experiment tracking. These make runs easier to compare; they do not change the training objective. |

The preset defaults and horizon limits above are checked against [LeRobot's GR00T configuration](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/policies/groot/configuration_groot.py) and [policy implementation](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/policies/groot/modeling_groot.py). Effective batch size follows the [pinned training loop](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/scripts/lerobot_train.py). Record the resolved optimizer and scheduler settings rather than inferring every default from the command line.

:::

## Action Space and Control

### Action Representations

::::::{dropdown} Compare joint actions, end-effector actions, and action chunking

GR00T supports several action representations:

**Joint Position Actions**

- Direct control over robot configuration
- Requires learning full arm coordination

**End-Effector Actions**

- Inverse kinematics computes joint commands
- Abstracts away arm configuration

**Action Chunking**

- Predict multiple future actions at once
- Smoother execution, temporal consistency

::::::

In this course, we use **joint position actions with action chunking**. Arm actions are **relative** to the observed joint positions.

(prediction-and-execution-lengths)=
:::{dropdown} Prediction and Execution Lengths

The **training chunk** describes the future action targets associated with an observation. The **rollout horizon** describes how much of a predicted sequence is used before requesting another chunk.

**Real-time chunking (RTC)** helps join consecutive action chunks while accounting for prediction delay.

| Parameter | Suggested example | What it controls |
|-----------|-------------------|------------------|
| `--policy.chunk_size` | `16` | Length of the future action target window used for training, within the base model's supported horizon. Changing the training window calls for a new training experiment. |
| `--policy.n_action_steps` | `16` in the base training example and all real rollouts | Caps the action sequence returned by this LeRobot policy. It must not exceed `chunk_size`; the base checkpoint can impose a further limit. |
| `lerobot_eval --action_horizon` | `16` | Number of returned actions the simulation server supplies to the client. The synchronous client drains its queue before requesting a fresh prediction. It cannot obtain more actions than the policy returns. |
| `--inference.type` / `--inference.rtc.enabled` | `rtc` / `false` | Uses the real rollout's background chunk-inference engine with RTC compensation disabled. Selecting this engine does not enable compensation by itself. |
| `--inference.rtc.execution_horizon` / `--inference.queue_threshold` | `16` / `0` | RTC overlap-prefix setting and queue refill trigger, matching the current real-rollout recipe. The RTC value does not set the number of actions executed; `policy.n_action_steps=16` sets the policy return limit. RTC compensation is disabled in this recipe. |

Use a **16-action rollout horizon** throughout this workshop, including for the [selected policies](datasets-and-models.md#current-model-selection) and the optional vision-unfrozen training example.

:::

### Explore the Training and Inference Loops

Adjust these diagrams to see the relationships. They are teaching illustrations, not a training run or robot controller. The calculations assume the example's 16-step training window and no gradient accumulation. The rollout timeline uses the workshop's nominal 30 Hz control rate and excludes inference and network delays.

```{raw} html
:file: _includes/groot-hyperparameters.html
```

## Resources

- [NVIDIA Isaac GR00T GitHub](https://github.com/NVIDIA/Isaac-GR00T) — Source code, model weights, and documentation
- [Isaac-GR00T FAQ: Improving Policies](https://github.com/NVIDIA/Isaac-GR00T/blob/main/FAQ.md) — Policy-improvement and troubleshooting guidance from the GR00T repository
