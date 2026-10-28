---
name: so101-dli-docs
description: Build, verify and serve this SO-101 DLI repository's English and Korean learner, event and instructor Sphinx documentation, including Git LFS media and a private workstation preview.
---

# Build and preview the course

Read [README's build instructions](../../README.md) and
[docs/conf.py](../../docs/conf.py). This is host-only documentation work;
the robot container, GPU, HF login and physical hardware are unnecessary.

## Prepare and build

1. Confirm requested source/tag and current changes.
2. Hydrate documentation images/videos with `git lfs pull --include="docs/**,images/**"`.
   Verify files are actual bytes, not LFS pointer text. Do not fetch model assets.
3. Use the repository lock with `uv sync --frozen` in a separate project
   environment. The internal sphinx-nvlearning extension requires authorized
   GitLab access. Prefer existing SSH credentials without copying private keys
   or weakening host-key checks. Do not replace the extension with dummy directives.
4. Run from any cwd:

```bash
bash <repo>/skills/so101-dli-docs/scripts/build.sh all all
```

The helper uses the repo's .venv and builds both languages and audiences separately with
`-W --keep-going`. Do not suppress warnings to claim a successful build.
Do not remove an unrelated build directory or edit upstream content merely to
hide failures.

## Serve and verify

Serve **only docs/_build**, never the repository, models, docker/env or raw
planning/handoff records. Use a free port and a single owned process:

```bash
python3 <repo>/skills/so101-dli-docs/scripts/preview.py start --bind 127.0.0.1 --port 8095
python3 <repo>/skills/so101-dli-docs/scripts/preview.py status
python3 <repo>/skills/so101-dli-docs/scripts/preview.py stop
```

For requested LAN access, bind the station's verified interface address and
report the access scope. A local preview is not public publication. Avoid changing
firewall rules or existing web services. The helper records owned PID/start time,
serves no symlinks outside the built tree, and refuses to overwrite an active
preview. Leave a verified preview running when requested; no boot autostart.

Verify HTTP from the intended access path, navigation, local image decode,
iframe loading and actual video frame progression in an isolated browser.
Check event and learner pages; a successful Sphinx build alone does not prove
media playback. Report external-media limitations separately.

Return the exact verified event/learner/Seoul preparation URLs, source commit,
build result and scoped restart/stop commands. The event version hides assembly
from the main lesson flow but keeps instructor setup accessible.

The Seoul preparation page is available in `event` and `instructor`, placed
above Today's Schedule. Its setup-team section is instructor-only. The `learner`
variant includes only the schedule in that category. Verify the preparation page is absent from learner navigation,
search and generated HTML/source/doctree files, including incremental builds.
`docs/conf.py` excludes the source and removes its stale learner outputs.

Keep `DLI준비와 진행` focused on day-before setup, the setup team, class
operations and repository skills. External TAs use this page: omit internal
Planning links and personal workstation details. Use the selected course source
for setup values; the public `latest` page can differ (for example, camera tilt).
When a title changes, rewrite all HTML pages so cached sidebars are updated.
The build helper uses `-a` for this; check the title on other lesson pages too.


## Korean documentation

For localization, read [Korean terminology and maintenance](references/2026-10-28-korean-localization.md). Preserve slide terminology and shaded inline-code strings in English. Translate interactive explanatory prose too, including hidden panels and JavaScript updates. Keep English Markdown/assets as the source; edit Korean PO catalogs and `docs/locale/ko/interactive.json`. Validate both languages, exercise every interactive selection/control, and retain per-page language navigation.

## Instructor and student guides

`build.sh event ko` builds the student classroom guide; `build.sh instructor ko`
builds the instructor guide. `both` builds learner and event only; `all` builds
learner, event and instructor. The default remains `both`. Instructor output is
`docs/_build/instructor/html` or `docs/_build/ko/instructor/html`.
The instructor uses the event lesson flow and adds `-t instructor`.

Keep **셋업 담당과 진행 순서** in `_includes/seoul-setup-team.md`, included
through `{audience} instructor`. Other preparation sections remain in event.
Verify the section and staff names are absent from student HTML, navigation,
search, copied sources and parsed doctrees, and present in instructor HTML and
search. Verify language links retain the instructor directory. Keep all outputs
separate; do not reuse the event output directory for an instructor build.

For Host/Container installation or lesson-cache provisioning, use
[so101-dli-prepare](../so101-dli-prepare/SKILL.md); documentation work does not
require that runtime. The same optional `instructor_skills.py` activation adds
both instructor skill links without changing the nine student links.
