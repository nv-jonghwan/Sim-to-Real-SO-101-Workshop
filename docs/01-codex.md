# CODEX

Use Codex throughout the workshop to prepare the environment, understand the course, follow an exercise, and discuss observations. Instructors, TAs and students use the same repository and the same skill files under `skills/`.

Ask in Korean and keep technical names such as Physical AI, GR00T, Co-Training and HG-DAgger in English. A course question can be answered from the documents; physical exercises follow the instructor’s sequence and the readiness of your station.

## Choose your starting point

Open the shared workshop folder and ask naturally. `AGENTS.md` routes the request to the relevant `skills/<name>/SKILL.md` file. Everyone uses the same files.

| Interface | Start here | Common skill file |
|---|---|---|
| ChatGPT app · Codex | Open the local workshop project | `skills/so101-dli/SKILL.md` |
| Codex CLI | Run `codex` in the workshop directory | `skills/so101-dli/SKILL.md` |
| ChatGPT app · Work | Use a project with local file access | `skills/so101-dli/SKILL.md` |

## Option A: ChatGPT app

### Codex in the desktop app

1. Sign in to the prepared ChatGPT desktop app and select **Codex** in the product selector.

2. Open a local project for `~/Sim-to-Real-SO-101-Workshop`. In an existing project, use **Edit project → Add folder**; make this repository the primary folder with **Make primary**. New chats use it to find the course files and skills.

3. For this workshop, choose **Work in → This computer / Local** and use the prepared checkout on branch `aidayseoul2026`. This keeps the chat aligned with the folder mounted in the workshop Container.

4. Start a chat in this project and ask the connection-check question below, followed by your setup or lesson request. The repository instructions read the canonical skill files directly.

Folder selection is described in [Projects and chats](https://learn.chatgpt.com/docs/projects); execution choices are described in [Codex environments](https://learn.chatgpt.com/docs/environments/modes). A cloud environment needs its own files and tools; it does not automatically receive the laptop’s USB devices, running Container or GPU.

```text
현재 작업 폴더와 Git branch를 확인해줘.
AGENTS.md, skills/so101-dli/SKILL.md, docs/seoul-workshop-schedule.md를 읽을 수 있는지 확인하고,
앞으로 수업 질문이나 실습 요청에 맞는 스킬을 찾아 적용해줘.
이번에는 파일 접근만 확인해줘.
```

### ChatGPT Work in the app

If you prefer the ChatGPT interface, select **ChatGPT → Work** and use a project that can access the local workshop folder. Availability depends on the account and workspace. Start with the same connection check. See [Use ChatGPT](https://learn.chatgpt.com/docs/use-chatgpt).

After confirming file access, ask naturally or name the canonical skill file directly. This workflow does not require a role-specific skill installation or a skill-selector entry.

For ordinary web/mobile Chat without local folder access, attach the relevant lesson and ask questions about it. A GitHub link alone does not install these repository skills or connect the classroom robot. This course distributes local skill folders; it has no separately published ChatGPT plugin.

## Option B: Codex CLI

Use the prepared CLI, or follow the [official Codex CLI guide](https://learn.chatgpt.com/docs/codex/cli) if installation is needed. In a Host terminal, enter the workshop folder and start Codex.

```bash
cd ~/Sim-to-Real-SO-101-Workshop
git branch --show-current
codex --version
codex
```

Confirm branch `aidayseoul2026` and complete sign-in if prompted. Enter a natural-language request or ask Codex to read `skills/so101-dli/SKILL.md` first.

## Set up the course skills

All course skills live in `skills/`. `AGENTS.md` tells the agent which canonical file to read for a setup request or lesson question. Keep the folder structure intact so relative lesson references work. No symlinks, personal-folder copies or role-specific activation are needed.

The skill-selector UI may not list these plain folders. Use the connection-check prompt to verify access to `AGENTS.md` and the requested `SKILL.md`; direct file reading is the course workflow.

If files cannot be read, check the selected project folder and local file access. A skill request does not itself grant additional permissions or establish robot readiness.

## What the course skills cover

| Skill | When to use it |
|---|---|
| `so101-dli-prepare` | Environment installation, checks and resume |
| `so101-dli-docs` | Build and serve the course documentation |
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

::::{audience} student

:::{include} _includes/student-environment-setup.md
:::

::::

::::{audience} instructor

:::{include} _includes/instructor-setup-profile.md
:::

::::

## First example: ask for today’s schedule

After opening the workshop folder in the app or CLI, enter this question without a skill name.

```text
오늘의 일정이 뭐야?
```

Codex should read `docs/seoul-workshop-schedule.md` and return a table with the time, topic, duration and instructor. It should include arrival, breaks and lunch, and state that all times are KST. Compare the answer with [Today’s Schedule](seoul-workshop-schedule.md).

### Optional: name the file directly

```text
skills/so101-dli/SKILL.md를 읽고 오늘의 일정을 시간, 주제, 소요 시간, 진행자 표로 보여줘.
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
| 13:45–13:55 | 오후 시작, 오전 내용 정리 및 Q&A | 10분 | Hogun Kee |
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

These examples need no skill names. The agent uses the relevant available course skill and lesson. You can ask which skill and source section it used.

```text
Sim-to-Real Gap과 Domain Randomization의 관계를 오늘 task 기준으로 설명해줘.

VLA의 입력과 action chunk가 뭔지 GR00T 교재를 읽고 설명해줘.

교재의 calibration부터 한 단계씩 진행하자. 현재 연결을 먼저 확인해줘.

State Machine으로 수집한 dataset과 Teleop dataset은 어떻게 달라?

Sim-only와 Co-Training model을 어떤 조건으로 비교해야 해?

HG-DAgger에서 leader가 언제 움직이는지 실습 전에 설명해줘.

원본과 augmented video에서 무엇을 비교해야 해?

AnchorBench와 calibration의 차이가 뭐야?
```

For an error, provide the command, whether it ran on the Host or in the Container, and the relevant error text. Codex can connect it to [Troubleshooting](troubleshooting.md). Before physical motion, follow the instructor’s safety guidance and confirm that the station is ready.
