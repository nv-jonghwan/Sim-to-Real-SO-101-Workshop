---
name: so101-dli
description: Guide a student through today's AI Day Seoul SO-101 workshop, show the timetable, choose the next lesson or exercise, and route course questions to the relevant student skill.
---

# Follow the workshop as a student

Start with the current checkout, [course contents](../../docs/index.md),
[today's schedule](../../docs/seoul-workshop-schedule.md), and
[CODEX guide](../../docs/01-codex.md). Use the selected `aidayseoul2026` revision.
Read the requested lesson before answering or executing; do not substitute the
public latest course or remembered model IDs for this checkout.

Use the table below to route ordinary Korean or English requests without
requiring a skill mention. For one lesson, read the relevant specialist; for
cross-lesson explanations, read `so101-dli-qa`. Read only the material needed for
the request. Automatic selection depends on skill/file availability in the
current app or CLI project; if discovery is missing, use the canonical skill
file when accessible. Do not ask students to install a personal copy by default.

## Schedule and course navigation

For “오늘의 일정이 뭐야?” or a similar agenda question, read the schedule file
and return a Korean Markdown table with time, topic, duration and instructor.
Include arrival 08:30–09:00, all AM/PM sessions, breaks, lunch and the 17:15 end;
times are KST. Use detailed timetable rows for individual session assignments.
Keep the user-edited instructor-summary wording distinct from those rows.
Use the lesson topic labels, preserving names such as Robot setup, calibration,
Real Teleop, Software stack and Sim Evaluation in English; explain around them
in Korean. Link the schedule source. This question needs no container, GPU, robot or setup.

Explain one meaningful next step at a time: lesson purpose, Host or Container
context, command/action, observed result, and what comes next. A concept question
only needs an explanation; a request to do an exercise means execute it within
the ready course environment and verify the result. If the station is not ready,
identify the specific missing requirement and direct the student to the TA.

| Student task | Skill |
|---|---|
| Questions about any lesson, terminology, architecture or troubleshooting | [so101-dli-qa](../so101-dli-qa/SKILL.md) |
| Workspace, calibration, two cameras and Real Teleop | [so101-dli-hardware](../so101-dli-hardware/SKILL.md) |
| Sim Teleop, Domain Randomization, State Machine, datasets and replay | [so101-dli-collect](../so101-dli-collect/SKILL.md) |
| VLA, GR00T, training and Co-Training concepts | [so101-dli-gr00t](../so101-dli-gr00t/SKILL.md) |
| Sim/real evaluation and Co-Training model comparisons | [so101-dli-evaluate](../so101-dli-evaluate/SKILL.md) |
| HG-DAgger corrections | [so101-dli-dagger](../so101-dli-dagger/SKILL.md) |
| Cosmos video augmentation | [so101-dli-cosmos](../so101-dli-cosmos/SKILL.md) |
| Actuation gap, SysID and AnchorBench | [so101-dli-sysid](../so101-dli-sysid/SKILL.md) |

For open experiments and wrap-up, read [Explore](../../docs/15-explore.md)
and [Conclusion](../../docs/16-conclusion.md), then use the skill for the chosen
experiment. Do not invent certification requirements or completion records.

Answer in natural Korean; preserve Physical AI, Sim-to-Real, GR00T, VLA,
Co-Training, HG-DAgger, product names, CLI flags and code. Use the Korean catalogs
under `docs/locale/ko/LC_MESSAGES/` when terminology or translated prose matters.
For performed exercises, keep concise local results with source/model revision,
conditions, evidence and the next step under ignored `runs/`. Never mark a task
passed from a historical result or from connection messages alone.

For computer eligibility, minimum-requirement checks, or any station installation, setup or provisioning request, read
[so101-dli-prepare](../so101-dli-prepare/SKILL.md). Everyone uses that same skill.
Default new setups to student documents; use instructor documents only when
explicitly requested. Use [so101-dli-docs](../so101-dli-docs/SKILL.md) for the
selected guide. Read canonical skill files through AGENTS.md; no extra
activation or role-specific skill installation is needed.
