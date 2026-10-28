#!/usr/bin/env python3
"""Enable or remove the two instructor skill links without altering student skills."""
import argparse
from pathlib import Path

NAMES = ("so101-dli-prepare", "so101-dli-docs")


def configure(repo, disable=False):
    folder = repo / ".agents/skills"
    if not folder.resolve().is_relative_to(repo):
        raise ValueError("Instructor links must stay inside the selected checkout")
    targets = []
    for name in NAMES:
        source = repo / "skills" / name
        link = folder / name
        if not (source / "SKILL.md").is_file():
            raise ValueError("Missing canonical instructor skill: " + str(source))
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or link.readlink() != Path("../../skills") / name:
                raise ValueError("Refusing to change an unrelated existing path: " + str(link))
        targets.append((name, link))
    if not disable:
        folder.mkdir(parents=True, exist_ok=True)
    for name, link in targets:
        if disable:
            if link.is_symlink():
                link.unlink()
        elif not link.is_symlink():
            link.symlink_to(Path("../../skills") / name, target_is_directory=True)
    return {name: "disabled" if disable else "enabled" for name, _ in targets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    try:
        for name, state in configure(args.repo.expanduser().resolve(), args.disable).items():
            print(name, state)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
