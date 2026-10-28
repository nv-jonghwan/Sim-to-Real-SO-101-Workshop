## Environment setup

Ask `환경설정을 해줘` in the shared workshop project. The agent reads `AGENTS.md` and `skills/so101-dli-prepare/SKILL.md`, checks the existing installation, and follows the preparation guide. The same skill files support installation, course questions and exercises.

To check this computer first, ask `현재 컴퓨터가 DLI를 실행할 수 있는 환경인지 확인해줘`. The preparation skill automatically reports basic Host eligibility, missing tools/assets and unverified capacity/runtime checks. A read-only report does not certify classroom execution or start installation, downloads or robot motion.

```bash
python3 skills/so101-dli-prepare/scripts/preflight.py --format markdown
```

A read-only plan shows the installation checkpoints and commands without executing them:

```bash
python3 skills/so101-dli-prepare/scripts/setup_plan.py
```

Record the agreed source commit, actual model/dataset paths, commands, logs and next action under `runs/setup/<station>/`. Reuse verified installations and downloads when resuming. Permission errors and untested runtime checks remain unknown.

### Build and open the course guide

Run these commands on the Host from the repository root after preparing the locked documentation dependencies and Git LFS media. Documentation does not require the robot Container or GPU.

```bash
uv sync --frozen
bash skills/so101-dli-docs/scripts/build.sh
python3 skills/so101-dli-docs/scripts/verify_html.py
```

The build prepares both languages. When you build and browse on the same Laptop, start a local preview on an available port:

```bash
python3 skills/so101-dli-docs/scripts/preview.py start --bind 127.0.0.1 --port 8095
python3 skills/so101-dli-docs/scripts/preview.py status
```

After the preview starts, open [the course guide](http://localhost:8095/ko/event/html/index.html) or [DLI preparation and delivery](http://localhost:8095/ko/event/html/2026-10-28-seoul-preparation.html) in that Laptop’s browser. The local service uses `http://localhost:8095`; building alone does not start the server or open the browser. If you choose a different port, update the links accordingly.

`localhost` refers to the computer running your browser. For access from another PC, replace `127.0.0.1` in the start command with the server’s verified LAN IP and open the URL reported by the preview on that PC.

Use the verified URL reported by the preview. Keep the requested preview running; its PID, command and log are recorded locally. Use `preview.py stop` to stop that owned preview. This is background execution, not boot autostart.

Software preparation and robot operation are separate checks. Confirm the current operator and station readiness before powered robot exercises; a model cache or connection message does not establish successful motion.
