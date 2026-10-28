#!/usr/bin/env python3
"""Print setup commands for a shared station workflow; execute no installation."""
import argparse
import json
from pathlib import Path


def build_plan(repo, profile="student", language="all", bind=None, port=8095, expected_revision=None):
    if profile not in {"student", "instructor"}:
        raise ValueError("profile must be student or instructor")
    if language not in {"en", "ko", "all"}:
        raise ValueError("language must be en, ko or all")
    repo = Path(repo).expanduser().resolve()
    audience = "instructor" if profile == "instructor" else "event"
    prefix = "" if language == "en" else "ko/"
    tools = repo / "skills/so101-dli-docs/scripts"
    preflight = ["python3", str(repo / "skills/so101-dli-prepare/scripts/preflight.py"), "--repo", str(repo)]
    if expected_revision:
        preflight += ["--expected-revision", expected_revision]
    return {
        "profile": profile, "document_audience": audience, "language": language,
        "repo": str(repo), "expected_revision": expected_revision,
        "guide_path": f"/{prefix}{audience}/html/index.html",
        "document_output": str(repo / f"docs/_build/{prefix}{audience}/html"),
        "preflight_command": preflight,
        "document_environment_command": ["uv", "sync", "--frozen", "--project", str(repo)],
        "document_build_command": ["bash", str(tools / "build.sh"), audience, language],
        "preview_command": ["python3", str(tools / "preview.py"), "start", "--profile", profile,
                            "--bind", bind or "<verified-LAN-IP>", "--port", str(port)],
        "checkpoints": ["Host prerequisites", "Container", "models and datasets", "precision",
                        "selected documents and preview", "simulation and inference", "hardware qualification and handover"],
        "executed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--profile", choices=["student", "instructor"], default="student")
    parser.add_argument("--language", choices=["en", "ko", "all"], default="all")
    parser.add_argument("--bind", help="verified interface IP for the preview command")
    parser.add_argument("--port", type=int, default=8095)
    parser.add_argument("--expected-revision")
    args = parser.parse_args()
    print(json.dumps(build_plan(args.repo, args.profile, args.language, args.bind,
                                args.port, args.expected_revision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
