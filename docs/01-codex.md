# CODEX

Use Codex throughout today’s workshop to understand the course, find the right command, follow an exercise, and discuss what you observe. The repository includes student skills that connect questions and hands-on work to the actual lesson documents.

Ask in Korean and keep technical names such as Physical AI, GR00T, Co-Training and HG-DAgger in English. A course question can be answered from the documents; physical exercises follow the instructor’s sequence and the readiness of your station.

## Open the workshop in Codex

Use the prepared Codex installation on your RTX Laptop. If it is not installed, follow the [official Codex CLI guide](https://learn.chatgpt.com/docs/codex/cli). Sign in with the account provided or approved for the course.

In a Host terminal, enter the cloned workshop repository and check its branch.

```bash
cd ~/Sim-to-Real-SO-101-Workshop
git branch --show-current
codex --version
codex
```

The branch should be `aidayseoul2026`. On the first run, complete the sign-in prompts. In the Codex desktop app or IDE extension, open this same repository folder. The workshop container and Codex must refer to the same checkout.

## Set up the course skills

The instructions live in `skills/`. This repository also includes `.agents/skills/` links to those student skills, so Codex can discover them when opened in this repository. No copy into a personal skill folder is required.

```bash
ls .agents/skills
```

In Codex CLI, enter `/skills` or type `$` to find a skill. You can request one explicitly with `$so101-dli`; Codex can also select an appropriate skill from a natural-language question. These discovery locations and invocation methods follow the [official skills guide](https://learn.chatgpt.com/docs/build-skills).

If a skill does not appear, check that the repository root is open and that the links resolve to a `SKILL.md` file, then restart Codex. You can also ask Codex to read `skills/so101-dli/SKILL.md` directly. The repository’s `AGENTS.md` connects course requests to these instructions.

## Choose a skill for your question or exercise

| Skill | When to use it |
|---|---|
| `so101-dli` | Today’s schedule, lesson navigation and the next exercise |
| `so101-dli-qa` | Questions and explanations across the complete course |
| `so101-dli-hardware` | Workspace checks, calibration, cameras and Real Teleop |
| `so101-dli-collect` | Sim Teleop, Domain Randomization, State Machine and datasets |
| `so101-dli-gr00t` | VLA, GR00T, post-training and Co-Training |
| `so101-dli-evaluate` | Sim/real evaluation and comparisons of prepared policies |
| `so101-dli-dagger` | HG-DAgger correction collection and review |
| `so101-dli-cosmos` | Cosmos augmentation and source/generated video comparison |
| `so101-dli-sysid` | Actuation gap, System Identification and AnchorBench |

The skills read the current lesson Markdown, Korean catalogs, interactive explanations and relevant code. Ask for a source section when you want to relate an answer back to the lesson.

## First example: ask for today’s schedule

Enter this short question in Codex.

```text
오늘의 일정이 뭐야?
```

Codex should read `docs/seoul-workshop-schedule.md` and return a table with the time, topic, duration and instructor. It should include arrival, breaks and lunch, and state that all times are KST. Compare the answer with [Today’s Schedule](seoul-workshop-schedule.md).

To request the same workflow explicitly, use:

```text
$so101-dli 오늘의 일정이 뭐야? 시간, 주제, 소요 시간, 진행자를 표로 보여줘.
```

Check that teaching begins at 09:00, lunch is 12:45–13:45 and the conclusion ends at 17:15. Use each detailed session row for its instructor. This exercise reads documents and does not need to start a robot or simulation.

### Verified schedule example

A read-only Codex run with the question above produced the 22-row schedule below. Times, durations and instructors were checked against the lesson. Topic labels are aligned with the course terminology; wording may vary between runs.

| Time | Topic | Duration | Instructor |
|---|---|---|---|
| 08:30–09:00 | 도착 및 착석 | 30분 | — |
| 09:00–09:10 | Physical AI & today’s task | 10분 | Jonghwan Lee |
| 09:10–09:30 | LeRobot | 20분 | Jonghwan Lee |
| 09:30–10:40 | Robot setup · calibration · Real Teleop | 70분 | Jonghwan Lee |
| 10:40–11:05 | Understanding GR00T | 25분 | Jonghwan Lee |
| 11:05–11:25 | Sim Teleop · Domain Randomization | 20분 | Jonghwan Lee |
| 11:25–11:50 | Software stack, architecture | 25분 | Jonghwan Lee |
| 11:50–12:00 | Break | 10분 | — |
| 12:00–12:15 | State Machine | 15분 | Jonghwan Lee |
| 12:15–12:35 | Sim Evaluation | 20분 | Jonghwan Lee |
| 12:35–12:45 | Q&A | 10분 | Jonghwan Lee |
| 12:45–13:45 | Lunch | 60분 | — |
| 13:45–13:55 | 오후 시작, 오전 내용 정리 및 Q&A | 10분 | Jihyeon Ryu |
| 13:55–14:10 | Sim-to-Real Gap | 15분 | Hogun Kee |
| 14:10–14:40 | Real Robot Rollouts with sim-only data | 30분 | Hogun Kee |
| 14:40–15:10 | Co-Training theory and practice | 30분 | Hogun Kee |
| 15:10–15:40 | HG-DAgger | 30분 | Hogun Kee |
| 15:40–15:50 | Break | 10분 | — |
| 15:50–16:10 | Cosmos | 20분 | Jihyeon Ryu |
| 16:10–16:20 | SysID / AnchorBench | 10분 | Jihyeon Ryu |
| 16:20–17:05 | Explore, experiment & wrap up | 45분 | Jihyeon Ryu |
| 17:05–17:15 | Conclusion | 10분 | Jihyeon Ryu |

## Try course questions and hands-on requests

```text
$so101-dli-qa Sim-to-Real Gap과 Domain Randomization의 관계를 오늘 task 기준으로 설명해줘.

$so101-dli-gr00t VLA의 입력과 action chunk가 뭔지 GR00T 교재를 읽고 설명해줘.

$so101-dli-hardware 교재의 calibration부터 한 단계씩 진행하자. 현재 연결을 먼저 확인해줘.

$so101-dli-collect State Machine으로 수집한 dataset과 Teleop dataset은 어떻게 달라?

$so101-dli-evaluate Sim-only와 Co-Training model을 어떤 조건으로 비교해야 해?

$so101-dli-dagger HG-DAgger에서 leader가 언제 움직이는지 실습 전에 설명해줘.

$so101-dli-cosmos 원본과 augmented video에서 무엇을 비교해야 해?

$so101-dli-sysid AnchorBench와 calibration의 차이가 뭐야?
```

For an error, provide the command, whether it ran on the Host or in the Container, and the relevant error text. Codex can connect it to [Troubleshooting](troubleshooting.md). Before physical motion, follow the instructor’s safety guidance and confirm that the station is ready.
