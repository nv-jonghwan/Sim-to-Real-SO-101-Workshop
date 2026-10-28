---
name: so101-dli-gr00t
description: Help students understand GR00T Vision-Language-Action models, model inputs/actions, pre-training, post-training and Co-Training, and follow the course's optional training exercise when explicitly requested.
---

# Learn GR00T and Co-Training

Read [GR00T](../../docs/10-groot.md),
[Co-Training theory](../../docs/13-strategy2-cotraining.md),
[practice](../../docs/13-cotraining-practice.md) and
[model cards](../../docs/datasets-and-models.md) for the student's question.
Use their Korean catalogs and interactive explanations for terminology.

Explain the role of language, wrist/external RGB, joint state, action chunks,
training data and policy execution using the vial-to-rack task. Keep training
batch size, action horizon, inference execution steps and flow steps distinct.
Use the actual interactive control definitions when explaining their effect.
Distinguish pre-training from post-training, sim-only from mixed sim/real data,
and Co-Training from a new architecture. Explain overfitting and evaluation
conditions before comparing supplied checkpoints.

For a practice comparison, route to
[so101-dli-evaluate](../so101-dli-evaluate/SKILL.md) with the lesson's exact model
and matching dataset. Selecting a prepared model does not run training.

For an explicit optional post-training request, first read the current GR00T
reference training section and inspect the selected dataset's schema, cameras,
action units, processor/config and base model. Follow the lesson's current
command and declared resource/time scope; record source, dataset and checkpoint
revisions plus the resulting artifacts. If the classroom station cannot run it,
explain the missing resource and use the supplied checkpoints for the lesson.
Do not provision cloud machines or replace this course with a different model.
A completed training run needs separate evaluation before claiming improvement.
