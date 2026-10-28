#!/usr/bin/env python3
"""Serve only generated course pages and track the preview's exact process."""
import argparse
import fcntl
import functools
import http.server
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "docs/_build"
STATE = REPO / ".local/docs-preview.json"


def identity(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        start = stat[stat.rfind(")") + 2:].split()[19]
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        return start, cmd
    except OSError:
        return None, []


def owned(state):
    if not state:
        return False
    start, cmd = identity(state["pid"])
    return start == state["start_ticks"] and str(Path(__file__).resolve()).encode() in cmd and b"_serve" in cmd


def guide_names(profile):
    if profile == "all":
        return ("learner", "event", "instructor", "ko/learner", "ko/event", "ko/instructor")
    audience = "instructor" if profile == "instructor" else "event"
    return (audience, "ko/" + audience)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, profile="student", **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)

    def translate_path(self, path):
        candidate = Path(super().translate_path(path)).resolve()
        requested = unquote(urlsplit(path).path)
        selected = any(candidate.is_relative_to((ROOT / name / "html").resolve())
                       for name in guide_names(self.profile))
        if not selected or not candidate.is_relative_to(ROOT.resolve()) or any(p.startswith(".") for p in Path(requested).parts if p not in ("/", ".")):
            return str(ROOT / "__forbidden__")
        return str(candidate)

    def list_directory(self, path):
        self.send_error(403, "Directory listing disabled")
        return None


def preview_urls(bind, port, profile="student"):
    return {name: f"http://{bind}:{port}/{name}/html/index.html"
            for name in guide_names(profile)
            if (ROOT / name / "html/index.html").is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop", "_serve"])
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8095)
    parser.add_argument("--profile", choices=["student", "instructor", "all"], default="student")
    args = parser.parse_args()
    if args.action == "_serve":
        handler = functools.partial(Handler, directory=str(ROOT), profile=args.profile)
        with http.server.ThreadingHTTPServer((args.bind, args.port), handler) as server:
            server.serve_forever()
        return
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with (STATE.parent / "docs-preview.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(STATE.read_text()) if STATE.exists() else None
        active = owned(state)
        if state:
            state["profile"] = state.get("profile", "all")
            state["urls"] = preview_urls(state["bind"], state["port"], state["profile"])
        if args.action == "status":
            print(json.dumps({"active": active, "state": state}, indent=2))
            return
        if args.action == "stop":
            if active:
                os.kill(state["pid"], signal.SIGTERM)
                for _ in range(30):
                    if not owned(state):
                        break
                    time.sleep(.1)
                if owned(state):
                    sys.exit("Owned preview did not exit; state retained.")
                STATE.unlink()
                print("Owned preview stopped.")
            else:
                print("No matching live preview; no process signaled.")
            return
        if active:
            if (state["profile"], state["bind"], state["port"]) != (args.profile, args.bind, args.port):
                sys.exit("An owned preview uses a different profile/address; coordinate its scoped stop before replacement.")
            print(json.dumps({"already_running": True, **state}, indent=2))
            return
        if not preview_urls(args.bind, args.port, args.profile):
            sys.exit("Build a course guide before serving.")
        with (STATE.parent / "docs-preview.log").open("ab") as log:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_serve", "--bind", args.bind, "--port", str(args.port), "--profile", args.profile],
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        time.sleep(.5)
        if proc.poll() is not None:
            sys.exit("Preview failed to bind; inspect .local/docs-preview.log. Existing service left unchanged.")
        start, _ = identity(proc.pid)
        state = {"pid": proc.pid, "start_ticks": start, "bind": args.bind, "port": args.port, "root": str(ROOT), "profile": args.profile,
                 "urls": preview_urls(args.bind, args.port, args.profile)}
        STATE.write_text(json.dumps(state, indent=2) + "\n")
        print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
