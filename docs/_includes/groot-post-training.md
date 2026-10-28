Run in the same `so101-workshop` container used for recording. The commands below load a LeRobot dataset by its Hugging Face repository ID. Stop the collection process before starting training.

1. **Upload** and **inspect** your dataset as described in [Teleoperating in Sim](08-simulation-teleoperation.md#review-and-upload-collected-data).
2. Inside the container, **authenticate** and **set** the run variables:

```bash
hf auth login
wandb login
export HF_USER=your_hf_username
export DATASET_NAME=so101_teleop_vials_newton
export DATASET="${HF_USER}/${DATASET_NAME}"
export REPO_ID="${DATASET}_GR00T17"
export OUTPUT_DIR="outputs/train/${REPO_ID}"
```

Use your actual username and dataset. For [automated collection](08-simulation-teleoperation.md#optional-automated-data-collection), set `DATASET_NAME=so101_auto_vials_newton` before defining `DATASET`, `REPO_ID`, and `OUTPUT_DIR`. `REPO_ID` names the model repository; `OUTPUT_DIR` is under the host-mounted `outputs/` directory. A dataset saved only under `datasets/` must be uploaded before using the Hub-based command below.

3. **Run** single-GPU post-training with the suggested settings above:

```bash
lerobot-train --dataset.repo_id="$DATASET" --dataset.image_transforms.enable=true --policy.type=groot --policy.device=cuda --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.embodiment_tag=new_embodiment --policy.tune_visual=false --policy.tune_llm=false --policy.chunk_size=16 --policy.n_action_steps=16 --policy.use_relative_actions=true --policy.relative_exclude_joints='["gripper"]' --policy.use_bf16=true --policy.push_to_hub=true --policy.repo_id="$REPO_ID" --seed=42 --batch_size=32 --steps=20000 --save_checkpoint=true --save_freq=5000 --use_policy_training_preset=true --env_eval_freq=0 --eval_steps=0 --log_freq=10 --output_dir="$OUTPUT_DIR" --job_name="$DATASET" --wandb.enable=true --wandb.disable_artifact=true
```

This configuration uses 20,000 steps, checkpoints every 5,000 steps, image augmentation, BF16, and Hub upload. Reduce batch size if GPU memory is insufficient. For local artifacts only, use `--policy.push_to_hub=false`; for training without Weights & Biases, use `--wandb.enable=false`.

### Multi-GPU Training

::::::{dropdown} Show the alternative multi-GPU training command

As an alternative for **step 3** on a machine with multiple visible GPUs, **run** Accelerate with the same training settings. Choose either the single-GPU command or this command for a run. Use a new `OUTPUT_DIR` for a separate training experiment.

```bash
accelerate launch --multi_gpu --num_processes="$(nvidia-smi -L | wc -l)" "$VIRTUAL_ENV/bin/lerobot-train" --dataset.repo_id="$DATASET" --dataset.image_transforms.enable=true --policy.type=groot --policy.device=cuda --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.embodiment_tag=new_embodiment --policy.tune_visual=false --policy.tune_llm=false --policy.chunk_size=16 --policy.n_action_steps=16 --policy.use_relative_actions=true --policy.relative_exclude_joints='["gripper"]' --policy.use_bf16=true --policy.push_to_hub=true --policy.repo_id="$REPO_ID" --seed=42 --batch_size=32 --steps=20000 --save_checkpoint=true --save_freq=5000 --use_policy_training_preset=true --env_eval_freq=0 --eval_steps=0 --log_freq=10 --output_dir="$OUTPUT_DIR" --job_name="$DATASET" --wandb.enable=true --wandb.disable_artifact=true
```

::::::

### Select the Trained Policy

4. After training finishes, **select** the uploaded model repository:

```bash
export MODEL_ID="$REPO_ID"
```

Alternatively, select a local `pretrained_model` directory under `outputs/train/<user>/<model>/checkpoints/`. Use the directory containing the saved policy configuration, weights, and processors, rather than the enclosing training run directory. This local path also works when training with `--policy.push_to_hub=false`.

Local checkpoints must include configuration and processor artifacts, not just weights. See [Checkpoint Compatibility](datasets-and-models.md#checkpoint-compatibility). Continue evaluation in the same container terminal after training finishes. If you reopen the shell, set `MODEL_ID` again; ordinary exported variables do not persist across shells.

### Optional: Unfreeze the Vision Encoder

Use `--policy.tune_visual=true` to train the vision encoder, and `--policy.tune_llm=false` to keep the language backbone frozen. Use `--policy.tune_visual=false` for a frozen-vision training run. These flags control which model parameters training updates; they do not change inference settings.

The selected [94% simulation policy](datasets-and-models.md#vision-trainable-20k-sim-only-reference) used vision trainable, language frozen, batch size 32, and a 32-step action window. The example below starts a new run from the GR00T base using those choices. Consult the model card for the full recorded recipe and benchmark conditions.

:::{dropdown} Show a vision-unfrozen training example

After setting `DATASET`, `DATASET_NAME`, and authenticating above, run this alternative single-GPU experiment. Its separate model name and output directory let you keep the frozen-vision run for comparison.

```bash
export VISION_REPO_ID="${DATASET}_GR00T17_vision"
lerobot-train --dataset.repo_id="$DATASET" --dataset.image_transforms.enable=true --policy.type=groot --policy.device=cuda --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.embodiment_tag=new_embodiment --policy.tune_visual=true --policy.tune_llm=false --policy.chunk_size=32 --policy.n_action_steps=32 --policy.use_relative_actions=true --policy.relative_exclude_joints='["gripper"]' --policy.use_bf16=true --policy.push_to_hub=true --policy.repo_id="$VISION_REPO_ID" --seed=42 --batch_size=32 --steps=20000 --save_checkpoint=true --save_freq=5000 --use_policy_training_preset=true --env_eval_freq=0 --eval_steps=0 --log_freq=10 --output_dir="outputs/train/$VISION_REPO_ID" --job_name="${DATASET_NAME}_vision" --wandb.enable=true --wandb.disable_artifact=true
```

After training, select this model for evaluation with `export MODEL_ID="$VISION_REPO_ID"`. Use the evaluation lessons' 16-action rollout settings even though this example trains with a 32-step window.

This example changes batch size and action window as well as vision training. To isolate the effect of unfreezing, use batch size 32 and a 32-step window for both runs, keeping the dataset, optimizer settings, update budget, and evaluation conditions the same. Unfreezing requires more memory and is not guaranteed to improve performance.

:::
