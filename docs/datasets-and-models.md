# Datasets and Models

```{image} images/lerobot_dataset_visualize_teleop_vials_rack_left.png
:alt: LeRobot dataset viewer showing synchronized camera observations and joint trajectories.
:width: 100%
:class: course-banner
```

The current workflow trains **GR00T 1.7** through LeRobot and records data with **Isaac Lab 3.0, Newton physics, and ovrtx**.

## Current Model Selection

The base model is [nvidia/GR00T-N1.7-3B](https://huggingface.co/nvidia/GR00T-N1.7-3B). Post-train it for the SO-101 task using [GR00T Post-Training](10-groot.md); the base weights alone are not a task policy.

The selected policies below provide three starting points for the lessons. All use GR00T 1.7; their training data and camera names differ. All three checkpoints are public; access was checked on October 8, 2026.

The icons show the data used to post-train each policy. Green means used; gray means not used.

The sim-only policy recorded **94/100 simulation successes** at an execution horizon of 16 actions, 30 Hz, and a 30-second simulated time limit, with scene seeds 76000–76099 and workshop source `f892b1a08c088e55156a389b3f1e42ab5eaa1049`. This is a recorded benchmark, not an expected score from the ten-episode lesson on a later source revision. It does not measure real-robot success or reliable return-and-restart behavior. The selected co-trained checkpoint has no published success rate; compare it on your station.

### Johnny42: Real-to-Real Reference

Trained on [50 real demonstrations](https://huggingface.co/datasets/sreetz-nv/so101-clean-up-vials-into-rack-50_20260628_131121), with camera keys `wrist` and `front`. Its saved action chunk and execution horizon are both 16. Use the training instruction: **Pick up the vials and put them in the yellow rack**. See the pinned [configuration](https://huggingface.co/sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42/blob/981f41e4f5b4dda47c6583de502dcac258bf5312/config.json) and [model card](https://huggingface.co/sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42/blob/981f41e4f5b4dda47c6583de502dcac258bf5312/README.md).

:::{dropdown} Select or download Johnny42

To load from the Hub:

```bash
export MODEL_ID=sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42
```

```{raw} html
:file: _includes/model-cards/johnny42.html
```

To download the reviewed revision and use its local files instead:

```bash
hf download "$MODEL_ID" --revision 981f41e4f5b4dda47c6583de502dcac258bf5312 --local-dir ./models/johnny42
export MODEL_ID=/workspace/Sim-to-Real-SO-101-Workshop/models/johnny42
```

Follow the [Johnny42 camera and instruction settings](johnny42-real-rollout) before running it.

:::

### Vision-Trainable 20k: Sim-Only Reference

This policy starts from the GR00T base and trains for 20,000 updates on [500 scripted Newton demonstrations](https://huggingface.co/datasets/sreetz-nv/so101_newton_dr500_20260923). It uses `wrist` and `external`, with 32 supervised action steps; the reported evaluation executes 16 actions per prediction. The [model card](https://huggingface.co/sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929/blob/bbfef9eaecc7a7654f42aaa4ceb95245bb140a53/README.md) reports 94/100 successes (Wilson 95% interval: 87.5–97.2%). Physical screening found promising behavior with gripper hesitation and no return-to-start behavior; no counted real success rate is available.

:::{dropdown} Select or download the 94% simulation policy

To load from the Hub:

```bash
export MODEL_ID=sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929
```

```{raw} html
:file: _includes/model-cards/sim-vision-20k.html
```

To download the reviewed revision and use its local files instead:

```bash
hf download "$MODEL_ID" --revision bbfef9eaecc7a7654f42aaa4ceb95245bb140a53 --local-dir ./models/sim-vision-20k
export MODEL_ID=/workspace/Sim-to-Real-SO-101-Workshop/models/sim-vision-20k
```

:::

(cotrained-reference)=
### Sim75 + Real10: Co-Trained Reference

This policy combines [75 simulated teleoperation episodes](https://huggingface.co/datasets/sreetz-nv/so101_sim_manual_perception_newton_20261008) with [10 real demonstrations](https://huggingface.co/datasets/sreetz-nv/so101_real_manual). All 85 episodes are used together throughout training. The simulated demonstrations use the Perception-DR environment; both sources use `wrist` and `external` cameras.

Training runs for 20,000 updates with vision trainable, language frozen, and an effective batch of 64 (microbatch 16, accumulated over four steps). The policy uses a 16-action window and relative arm actions. See the [published training recipe](https://huggingface.co/sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011/blob/c7e8049753be5629e73eda69b57a358146bbeb5d/README.md).

A matched simulation evaluation is still pending, and preliminary real trials are not a benchmark. Compare its sim and real behavior using the same rollout settings.

:::{dropdown} Select or download the co-trained teleoperation policy

To load from the Hub:

```bash
export MODEL_ID=sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011
```

```{raw} html
:file: _includes/model-cards/sim75-real10.html
```

To download the reviewed revision and use its local files instead:

```bash
hf download "$MODEL_ID" --revision c7e8049753be5629e73eda69b57a358146bbeb5d --local-dir ./models/sim75-real10
export MODEL_ID=/workspace/Sim-to-Real-SO-101-Workshop/models/sim75-real10
```

:::

Sim + Cosmos GR00T 1.7 checkpoints remain to be prepared for both augmentation mixes. For source data and validation requirements, see [Augmenting Datasets With Cosmos](14-strategy3-cosmos.md).

## Download Models for the Workshop Container

Preparing event stations? Use the [Workshop Preparation Reference](workshop-preparation.md) to cache the models used by the lesson commands.

On the **host**, run these commands from the cloned repository directory with the `hf` CLI installed. Create the `outputs/`, `datasets/`, and `models/` directories before starting the container. Each download goes into `models/`, which the workshop container mounts automatically.

```bash
cd ~/Sim-to-Real-SO-101-Workshop
mkdir -p outputs datasets models
hf download sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42 --revision 981f41e4f5b4dda47c6583de502dcac258bf5312 --local-dir ./models/johnny42
hf download sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929 --revision bbfef9eaecc7a7654f42aaa4ceb95245bb140a53 --local-dir ./models/sim-vision-20k
hf download sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011 --revision c7e8049753be5629e73eda69b57a358146bbeb5d --local-dir ./models/sim75-real10
```

If `hf` is only installed in your workshop container, run the three `hf download` commands from `/workspace/Sim-to-Real-SO-101-Workshop` inside it instead. They write to the same mounted host folder.

The [container launch command](06-get-the-code.md#start-the-workshop-container) mounts `./models` at `/workspace/Sim-to-Real-SO-101-Workshop/models`. No image rebuild is needed. Inside the container, select one downloaded model before evaluation:

| Model | Container setting |
|-------|-------------------|
| Johnny42 | `export MODEL_ID=/workspace/Sim-to-Real-SO-101-Workshop/models/johnny42` |
| Sim-only | `export MODEL_ID=/workspace/Sim-to-Real-SO-101-Workshop/models/sim-vision-20k` |
| Co-trained | `export MODEL_ID=/workspace/Sim-to-Real-SO-101-Workshop/models/sim75-real10` |

Use this local `MODEL_ID` in the evaluation command in place of the lesson's Hub ID. Keep the full downloaded directory, including its saved processors.

## Create Your Own Dataset and Policy

1. **Collect** leader-arm demonstrations into `<user>/so101_teleop_vials_newton`, or use [Automated Data Collection](08-simulation-teleoperation.md#optional-automated-data-collection) to record `<user>/so101_auto_vials_newton`.
2. **Inspect** episodes with `lerobot-dataset-viz`, using the same repo ID and `--root ./datasets/<repo_id>`, then **upload** the completed dataset to that Hub repository.
3. **Train** using [GR00T Post-Training](10-groot.md#reference-post-train-your-own-model). Set `DATASET_NAME` to the dataset you collected. The examples name the resulting policy `<user>/<dataset_name>_GR00T17` and save local checkpoints under `outputs/train/`.
4. **Evaluate** the same policy first in simulation and then on the real robot.

The README's mount layout preserves datasets, downloaded models, and training outputs on the host when the container exits.

## Checkpoint Compatibility

For the current workflow, use a LeRobot policy repository or a checkpoint's `pretrained_model` directory containing weights, configuration, and processor artifacts.

Verify:

- GR00T 1.7 base model and compatible LeRobot configuration.
- Image features matching the checkpoint: `observation.images.wrist` and `observation.images.external` for the selected sim-only and co-trained policies; `observation.images.wrist` and `observation.images.front` for Johnny42.
- Joint order: shoulder pan, shoulder lift, elbow flex, wrist flex, wrist roll, gripper.
- Matching joint normalization, camera calibration, task geometry, and 30 Hz data.
- Saved relative-action preprocessing/postprocessing, including the gripper exclusion.
- An evaluation action horizon no larger than checkpoint chunk size.

A camera rename map only maps feature names; it cannot repair different camera geometry, joint conventions, or a raw Isaac-GR00T checkpoint format.

## Download a Compatible Policy

1. Inside the workshop container, **authenticate**, **set** the model ID to your trained policy, and **download** it:

```bash
hf auth login
export MODEL_ID=your_hf_username/so101_teleop_vials_newton_GR00T17
hf download "$MODEL_ID" --local-dir "./models/$MODEL_ID"
```

The `models/` mount preserves downloads on the host.

2. If the download contains nested checkpoints, **select** the appropriate `pretrained_model` directory for evaluation.

If the downloaded repository stores the policy configuration, weights, and processors at its root, **set** the local path in the same container shell:

```bash
export MODEL_ID="/workspace/Sim-to-Real-SO-101-Workshop/models/$MODEL_ID"
```

Otherwise, set `MODEL_ID` to the nested `pretrained_model` directory. Pass it as `--pretrained_name_or_path "$MODEL_ID"` for simulation or `--policy.path="$MODEL_ID"` for real rollout. To load directly from the Hub instead, retain the repository ID and skip this local-path assignment.

## System Identification References

[System Identification](15-strategy4-sysid.md) uses [Anchor-Lab's SO-101 telemetry](https://huggingface.co/datasets/nvidia/Anchor-Lab) for measurement inspection and the [AnchorBench paired bundle](https://huggingface.co/VigneshBhavan/so101-newton-actuator-ab-paired-checkpoints) for actuator profiles and training records. Its [paired demonstrations](https://huggingface.co/datasets/VigneshBhavan/so101-newton-actuator-ab-paired-demos) provide the policy-training data for that comparison.

These resources have distinct purposes: Anchor-Lab contains signal-level telemetry; the paired demonstrations contain policy-training episodes. The comparison checkpoints are GR00T N1.6 artifacts, not validated GR00T 1.7 replacements for the course rollout commands.

## Historical Course Artifacts

These links preserve the data and policies associated with the earlier lessons. They are references for studying the strategies, not validated replacements for current Newton/GR00T 1.7 artifacts. Check camera schema and calibration before reusing their data. Do not rename a `grootn16` repository to imply that 1.7 weights exist.

### Historical Datasets

::::::{dropdown} Browse historical demonstration datasets

| Dataset | Description | Used In | Link to Visualizer |
|---------|-------------|---------|--------------|
| [sreetz-nv/so101_teleop_vials_rack_left](https://huggingface.co/datasets/sreetz-nv/so101_teleop_vials_rack_left) | 75 sim-only teleoperation demonstrations | [Teleoperating in Sim](08-simulation-teleoperation.md), [Sim Evaluation](11-sim-evaluation.md), [Real Evaluation](12-real-evaluation.md) | [See episodes](https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fsreetz-nv%2Fso101_teleop_vials_rack_left%2Fepisode_0) |
| [sreetz-nv/so101_teleop_vials_rack_left_sim_and_real](https://huggingface.co/datasets/sreetz-nv/so101_teleop_vials_rack_left_sim_and_real) | 75 sim-only demonstrations (same dataset as above) + 5 real-world teleoperation demonstrations | [Strategy 2](13-strategy2-cotraining.md) | [See episodes](https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fsreetz-nv%2Fso101_teleop_vials_rack_left_sim_and_real%2Fepisode_0) |
| [sreetz-nv/so101_teleop_vials_rack_left_augment_02](https://huggingface.co/datasets/sreetz-nv/so101_teleop_vials_rack_left_augment_02) | 75 sim + 7 Cosmos-augmented episodes | [Strategy 4](14-strategy3-cosmos.md) | [See episodes](https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fsreetz-nv%2Fso101_teleop_vials_rack_left_augment_02%2Fepisode_0) |
| [sreetz-nv/so101_teleop_vials_rack_left_cosmos_70](https://huggingface.co/datasets/sreetz-nv/so101_teleop_vials_rack_left_cosmos_70) | 75 sim + 70 Cosmos-augmented episodes | [Strategy 4](14-strategy3-cosmos.md) | [See episodes](https://huggingface.co/spaces/lerobot/visualize_dataset?path=%2Fsreetz-nv%2Fso101_teleop_vials_rack_left_cosmos_70%2Fepisode_0) |

::::::

### Historical Models

::::::{dropdown} Browse historical policy checkpoints

| Model | Description | Used In |
|-------|-------------|---------|
| [aravindhs-NV/grootn16-finetune_sreetz-so101_teleop_vials_rack_left](https://huggingface.co/aravindhs-NV/grootn16-finetune_sreetz-so101_teleop_vials_rack_left) | Sim-only fine-tuned (75 sim episodes) | [Sim Evaluation](11-sim-evaluation.md), [Real Evaluation](12-real-evaluation.md) |
| [aravindhs-NV/grootn16-finetune_sreetz-so101_teleop_vials_rack_left_sim_and_real](https://huggingface.co/aravindhs-NV/grootn16-finetune_sreetz-so101_teleop_vials_rack_left_sim_and_real) | Sim + real co-trained (episode mix requires verification) | [Strategy 2](13-strategy2-cotraining.md) |
| [aravindhs-NV/sreetz-so101_teleop_vials_rack_left_augment_02](https://huggingface.co/aravindhs-NV/sreetz-so101_teleop_vials_rack_left_augment_02) | Cosmos-augmented (75 sim + 7 Cosmos) | [Strategy 4](14-strategy3-cosmos.md) |
| [aravindhs-NV/so100-orig-groot-vials-rack-left-cosmos-70](https://huggingface.co/aravindhs-NV/so100-orig-groot-vials-rack-left-cosmos-70) | Cosmos-augmented (75 sim + 70 Cosmos) | [Strategy 4](14-strategy3-cosmos.md) |

::::::
