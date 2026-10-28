---
name: so101-dli-sysid
description: Answer student questions about the actuation gap, System Identification and AnchorBench, explain the course's measured comparisons and guide analysis of supplied traces without starting an unsolicited physical excitation run.
---

# Understand the actuation gap

Read [SysID / AnchorBench](../../docs/15-strategy4-sysid.md),
[Sim-to-Real debugging](../../docs/12-debugging-sim-to-real.md) and their Korean
catalogs. Use the actual figures, videos and conditions in this checkout.

Explain command versus measured motion, position tracking, timing, actuator
response and the effect of fitted simulation parameters. Distinguish visual
domain mismatch from actuation mismatch, and calibration from system
identification. Keep the source's robot, measurement method, units and trial
conditions when discussing a plot or reported improvement.

For the normal lecture/demo, inspect supplied traces or clips and walk the
student through the comparison. Do not interpret a simulation fit as proof of
policy success on every physical robot. For requested new trace analysis,
check joint order, timestamps, units, input/output alignment and the source
conditions before computing errors or comparing runs.

A new physical excitation experiment needs a concrete course procedure and
current hardware/operator readiness; a conceptual question does not authorize
motor commands. If the lesson is demonstrative and does not provide a runnable
experiment for the classroom station, say so and involve the instructor/TA.
Do not change actuator parameters or calibration to hide an observed mismatch.
