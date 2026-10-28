# CODEX

Use Codex throughout today’s workshop to understand the course, find the right command, follow an exercise, and discuss what you observe. The repository includes student skills that connect questions and hands-on work to the actual lesson documents.

Ask in Korean and keep technical names such as Physical AI, GR00T, Co-Training and HG-DAgger in English. A course question can be answered from the documents; physical exercises follow the instructor’s sequence and the readiness of your station.

## Choose your starting point

The same nine course skills support both the ChatGPT desktop app and Codex CLI. Open the workshop folder once, then ask naturally. Skill names are optional; the agent selects relevant instructions from the question and available skills.

| Interface | Start here | Optional skill selection |
|---|---|---|
| ChatGPT app · Codex | Open the local workshop project | `$so101-dli` |
| Codex CLI | Run `codex` in the workshop directory | `/skills` or `$so101-dli` |
| ChatGPT app · Work | Use a project with local file access when available | `@so101-dli` when listed |

The mention syntax follows the [official Skills & Plugins guide](https://learn.chatgpt.com/docs/skills-and-plugins). Natural-language questions work without a mention when the relevant skills are available.

## Option A: ChatGPT app

### Codex in the desktop app

1. Sign in to the prepared ChatGPT desktop app and select **Codex** in the product selector.

2. Open a local project for `~/Sim-to-Real-SO-101-Workshop`. In an existing project, use **Edit project → Add folder**; make this repository the primary folder with **Make primary**. New chats use it to find the course files and skills.

3. For this workshop, choose **Work in → This computer / Local** and use the prepared checkout on branch `aidayseoul2026`. This keeps the chat aligned with the folder mounted in the workshop Container.

4. Open **Skills** in the sidebar to check the course skills, then start a chat in this project. Ask the connection-check question below once, followed by your lesson question.

Folder selection is described in [Projects and chats](https://learn.chatgpt.com/docs/projects); execution choices are described in [Codex environments](https://learn.chatgpt.com/docs/environments/modes). A cloud environment needs its own files and tools; it does not automatically receive the laptop’s USB devices, running Container or GPU.

```text
현재 작업 폴더와 Git branch를 확인해줘.
AGENTS.md, skills/so101-dli/SKILL.md, docs/seoul-workshop-schedule.md를 읽을 수 있는지 확인하고,
앞으로 수업 질문이나 실습 요청에 맞는 스킬을 찾아 적용해줘.
이번에는 파일 접근만 확인해줘.
```

### ChatGPT Work in the app

If you prefer the ChatGPT interface, select **ChatGPT → Work** and use a project that can access the local workshop folder. Availability depends on the account and workspace. Start with the same connection check. See [Use ChatGPT](https://learn.chatgpt.com/docs/use-chatgpt).

Ask naturally after the files are accessible. If `so101-dli` is listed in the skill selector, you can also select it with `@`. If it is missing, ask the agent to read the repository’s skill file directly, or open the same folder in Codex.

For ordinary web/mobile Chat without local folder access, attach the relevant lesson and ask questions about it. A GitHub link alone does not install these repository skills or connect the classroom robot. This course distributes local skill folders; it has no separately published ChatGPT plugin.

## Option B: Codex CLI

Use the prepared CLI, or follow the [official Codex CLI guide](https://learn.chatgpt.com/docs/codex/cli) if installation is needed. In a Host terminal, enter the workshop folder and start Codex.

```bash
cd ~/Sim-to-Real-SO-101-Workshop
git branch --show-current
codex --version
codex
```

Confirm branch `aidayseoul2026` and complete sign-in if prompted. Enter your question at the Codex prompt. For an optional explicit choice, use `/skills` or `$so101-dli`.

## Set up the course skills

The repository stores the instructions in `skills/` and links the nine student skills under `.agents/skills/`. Codex discovers these project skills from the checkout. Keep the folder structure intact so each skill can read its lesson references. No personal-folder copy is needed. See the [official skills guide](https://learn.chatgpt.com/docs/build-skills).

Automatic selection is enabled by default. The repository’s `AGENTS.md` directs ordinary student questions to the relevant course skill; the skill then reads the lesson before answering. A single-topic request uses its specialist, while a comparison across lessons uses course Q&A.

If a skill is missing, check the primary folder and `.agents/skills/` links, then reopen the chat or restart the app/CLI. Use the connection-check prompt to confirm access. Selecting a skill does not grant additional file access or authorize robot motion; those depend on the current environment and request.

## What the course skills cover

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

After opening the workshop folder in the app or CLI, enter this question without a skill name.

```text
오늘의 일정이 뭐야?
```

Codex should read `docs/seoul-workshop-schedule.md` and return a table with the time, topic, duration and instructor. It should include arrival, breaks and lunch, and state that all times are KST. Compare the answer with [Today’s Schedule](seoul-workshop-schedule.md).

### Optional: choose a skill explicitly

Use this only when you want to choose the skill yourself. In the ChatGPT app’s Codex view or Codex CLI:

```text
$so101-dli 오늘의 일정이 뭐야? 시간, 주제, 소요 시간, 진행자를 표로 보여줘.
```

In ChatGPT Work, select the available skill with `@`, then ask:

```text
@so101-dli 오늘의 일정이 뭐야? 시간, 주제, 소요 시간, 진행자를 표로 보여줘.
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
