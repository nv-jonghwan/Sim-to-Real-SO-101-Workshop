---
name: so101-dli-evaluate
description: Run and compare SO-101 DLI policy evaluations in simulation or on qualified real hardware, handling checkpoint contracts, precision, policy-server cleanup and truthful trial scoring.
---

# Evaluate one policy under declared conditions

Read [sim evaluation](../../docs/11-sim-evaluation.md),
[real evaluation](../../docs/12-real-evaluation.md),
[co-training practice](../../docs/13-cotraining-practice.md) and the selected
[model card](../../docs/datasets-and-models.md). Use their current commands,
model IDs, instructions and matching starting-pose datasets.

## Select and freeze

Record source/image, checkpoint revision/config hash, base and processors,
precision, camera mapping, task, action horizon, environment seed, policy RNG
(if controlled), number of trials, actual time limit and start-pose source.
The ordinary course comparison uses horizon 16, ten episodes and env seed
76000. A 10-trial exercise is not proof of deployment reliability.
A previously consumed seed is not a fresh holdout.

Sim500 uses `sreetz-nv/so101_newton_dr500_vision_h32_b32_20k_20260929`;
its dataset-derived start uses `sreetz-nv/so101_newton_dr500_20260923`.
Co-training uses `sreetz-nv/so101_real10_sim75_vision_h16_b64_20k_20261011`
and `sreetz-nv/so101_real10_sim75_20261011`.
Use the model card for i1/i5/manual/HG-DAgger/Johnny42; Johnny42's camera key
and instruction differ. Renaming camera keys cannot repair geometry, units or
checkpoint-format mismatch.

## Simulation and server lifecycle

Inside the verified workshop container:
1. Check GPU memory and port ownership before launching. Use one fresh policy
   server per selected policy. Bind localhost for a same-container client.
2. Start the lesson's `python -m lerobot.async_inference.policy_server`,
   retaining the PID and log in the same shell; set cleanup for that exact child.
   If the port is occupied, identify its owner; never start a second server
   blindly or kill the owner to free it.
3. Wait for gRPC readiness, then inspect actual checkpoint load and first
   inference. A listening socket only verifies transport.
4. Run `lerobot_eval` with a single environment, an `*-Eval-v0` task,
   both cameras and `presets=newton,ovrtx_renderer`. Compare default/OOD start
   against the matching dataset-derived mean with all other conditions fixed.
5. Record complete success/failure counts and review actual videos/frames.
6. Stop the client, then the same shell's owned server:
   `kill "$POLICY_SERVER_PID"`, `wait "$POLICY_SERVER_PID" || true`,
   `unset POLICY_SERVER_PID`. Verify the port and owned GPU allocation clear
   before switching policy, real rollout or training.

The troubleshooting page's broad `pkill` is for a dedicated workshop container.
On a shared workstation, identify exact owned PIDs/container first and scope
cleanup. A stale PID file needs process identity verification before any signal.
Do not kill all Python/Docker/GPU processes.

For OOM inspect duplicate servers, actual config precision and free memory
before tuning batches/horizons. See
[precision settings](../../docs/workshop-preparation.md#configure-model-precision). Preserve deliberate FP32
experiments and avoid attributing a restart's freed VRAM to BF16 alone.

## Real policy and comparisons

Require [hardware qualification](../so101-dli-hardware/SKILL.md) and operator
readiness. Real `lerobot-rollout` loads the model locally; stop the sim server
first. Use an interactive terminal, the verified follower/cameras and
`--robot.use_degrees=true`. The arm homes on startup **before P**.

Use P to run, S/F to score and return, N to discard, Q/Esc to exit.
Wait for Paused before touching props; cleanup can include return motion.
Match props, light, camera, starting pose, trial count and instruction across
sim-only/co-trained/corrected models. Report first-action delay when available.

Score autonomous sim and autonomous real separately. Human-assisted completion,
manual reset, discarded trial and technical failure are separate categories.
Report successes/scored denominator plus all exclusions; retain failure modes.
Do not report another run's historical results as the student's new result.
