## Environment setup

Ask `환경설정을 해줘` in the shared workshop project. The agent reads `AGENTS.md` and `skills/so101-dli-prepare/SKILL.md`, checks the existing installation, and follows the preparation guide. The same skill files support installation, course questions and exercises.

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

The build prepares both languages and opens the Korean guide first. Check the actual LAN address and choose an available port for the preview:

```bash
python3 skills/so101-dli-docs/scripts/preview.py start --bind <verified-LAN-IP> --port 8095
python3 skills/so101-dli-docs/scripts/preview.py status
```

Use the verified URL reported by the preview. Keep the requested preview running; its PID, command and log are recorded locally. Use `preview.py stop` to stop that owned preview. This is background execution, not boot autostart.

Software preparation and robot operation are separate checks. Confirm the current operator and station readiness before powered robot exercises; a model cache or connection message does not establish successful motion.
