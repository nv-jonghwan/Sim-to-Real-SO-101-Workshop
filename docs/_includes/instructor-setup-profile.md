## Choose the setup document profile

For a new setup, an unqualified request selects student documents (`event`). Select `instructor` documents only when explicitly requested. The operator being an Instructor or TA does not change this default. Both profiles use the same installation workflow, models, datasets and skills.

| Request | Document profile |
|---|---|
| `환경설정을 해줘` | Student (`event`) |
| `Instructor용으로 환경설정을 해줘` | Instructor (`instructor`) |

The agent reads `skills/so101-dli-prepare/SKILL.md`, records the selected profile and proceeds through installation, document build and preview. Asking for an explanation or a plan does not execute those steps.
