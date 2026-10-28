---
orphan: true
---

# Workshop Preparation Reference

For workshop organizers: build the container and download the lesson models on each station before learners arrive.

## Clone the Repository and Build the Container

Run these commands **on the host**, with Git LFS and Docker installed:

```bash
git lfs install
cd ~
git clone --branch aidayseoul2026 --single-branch https://github.com/nv-jonghwan/Sim-to-Real-SO-101-Workshop.git
cd Sim-to-Real-SO-101-Workshop
git lfs pull
docker build -t so101-workshop -f docker/Dockerfile .
```

## Download the Lesson Models

Run these commands **on the host**, using the Hugging Face CLI (`hf`). They fill the host cache that the container mounts, so the lesson commands can keep using their published model IDs. You can download the models before launching the container.

If the CLI is only available inside the container, you can run the same commands there with the cache mount below in place.

```bash
hf download nvidia/GR00T-N1.7-3B
hf download sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929
hf download sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011
hf download sreetz-nv/so101_real10_sim75_hgdagger29_vision_h16_b64_20k_20261013
hf download liorbenhorin-nv/so101_sim_manual_perception_newton_20261008_GR00T17_20k
hf download liorbenhorin-nv/so101_vision_dr_i1_GR00T17_20261013
hf download liorbenhorin-nv/so101_vision_dr_i5_GR00T17_20261013
hf download sreetz-nv/so101-clean-up-vials-into-rack-50-groot-n17-relact-bs64-20k-20260628_johnny_42
```

| Download | Used for |
|---|---|
| GR00T 1.7 base | Base-model files required by the policy runtime |
| Sim-only 20k | Simulation and first real evaluations |
| Sim75 + Real10 | Co-training comparisons and the HG-DAgger collection policy |
| i1 | State-machine-only evaluation |
| i5 | Co-training plus broader state-machine layouts |
| Johnny42 | Optional real-to-real comparison |
| HG-DAgger 20k | Demonstrations and corrections trained together, for comparison |
| Manual simulation teleoperation 20k | Additional sim-only policy for comparison |

Download the complete repositories, including their configuration and processor files. If access requires authentication, run `hf auth login` and complete any access requirements shown on the model's Hugging Face page, then retry.

## Configure Model Precision

After downloading the models, **manually edit `config.json` for each of the seven lesson policies** and set:

```json
"model_params_fp32": false,
"use_bf16": true
```

Use the policy configuration in the Hugging Face cache mounted into the container, typically `~/.cache/huggingface/hub/models--<owner>--<model>/snapshots/<revision>/config.json` on the host. Choose the revision used for evaluation. If using a local model directory instead, edit its `config.json`.

Repeat this for every lesson policy listed above, leaving all other settings unchanged. **Do not edit the `nvidia/GR00T-N1.7-3B` base model.** Check these settings again after downloading a new model revision, and restart any running policy process after editing.



## Download Starting-Pose Data

Run this from the workshop checkout on the host. It downloads metadata and joint-state data for every dataset used by `--start_pose_dataset`, without videos. The container's `./datasets` mount puts these files where the starting-pose loader expects them.

```bash
for DATASET_ID in \
  sreetz-nv/so101_newton_dr500_20260923 \
  sreetz-nv/so101_sim_manual_perception_newton_20261008 \
  sreetz-nv/so101_real10_sim75_20261011 \
  sreetz-nv/so101-clean-up-vials-into-rack-50_20260628_131121 \
  liorbenhorin-nv/so101_vials_procedural_left_125ep_20261013 \
  liorbenhorin-nv/so101_vials_procedural_all_125ep_20261013
do
  hf download "$DATASET_ID" --repo-type dataset \
    --include "meta/**" "data/**" \
    --local-dir "./datasets/$DATASET_ID" || break
done
```

HG-DAgger uses the sim-teleoperation dataset for its starting pose, not the correction segments.
