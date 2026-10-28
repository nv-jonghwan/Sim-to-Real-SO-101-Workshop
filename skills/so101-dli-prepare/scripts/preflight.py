#!/usr/bin/env python3
"""Inventory a DLI station without opening devices or mutating its runtime."""
import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path


def command(args):
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return {"status": "ok" if proc.returncode == 0 else "unknown",
                "exit_code": proc.returncode,
                "output": (proc.stdout + proc.stderr).strip()[:6000]}
    except FileNotFoundError:
        return {"status": "missing", "error": "executable not found: " + args[0]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unknown", "error": str(exc)}


def source_check(repo, expected):
    actual = command(["git", "-C", str(repo), "rev-parse", "HEAD"])
    selected = None
    if expected:
        selected = command(["git", "-C", str(repo), "rev-parse", "--verify",
                            "--end-of-options", expected + "^{commit}"])
    matches = None
    if selected and actual["status"] == selected["status"] == "ok":
        matches = actual["output"] == selected["output"]
    return {"actual": actual, "expected_revision": expected,
            "resolved_expected": selected, "matches_expected_revision": matches}


def course_assets(repo):
    """Read the maintained lesson inventory rather than freeze model IDs in code."""
    text = (repo / "docs/workshop-preparation.md").read_text()
    models = list(dict.fromkeys(re.findall(r"^hf download ([\w.-]+/[\w.-]+)\s*$", text, re.M)))
    section = text.split("## Download Starting-Pose Data", 1)[1]
    datasets = list(dict.fromkeys(re.findall(r"^  ([\w.-]+/[\w.-]+)\s*\\?\s*$", section, re.M)))
    if not models or not datasets:
        raise ValueError("Cannot extract model/dataset inventory from workshop preparation")
    return models, datasets


def nonempty(path):
    return path.is_file() and path.stat().st_size > 0


def policy_config(path):
    path = Path(path).expanduser().absolute()
    item = {"path": str(path), "resolved_path": str(path.resolve()), "symlink": path.is_symlink()}
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("policy config must be a JSON object")
        item.update(sha256=hashlib.sha256(raw).hexdigest(),
                    model_params_fp32=data.get("model_params_fp32"), use_bf16=data.get("use_bf16"),
                    course_precision=data.get("model_params_fp32") is False and data.get("use_bf16") is True)
    except (OSError, ValueError) as exc:
        item.update(status="unknown", error=str(exc))
    return item


def model_snapshot(path, base_model=False):
    result = {"path": str(path), "revision": path.name}
    try:
        files = [p for p in path.rglob("*") if p.is_file()]
        configs = [p.name for p in files if "processor" in p.name and p.suffix == ".json" and nonempty(p)]
        weights = [p for p in files if p.suffix in (".safetensors", ".bin") and nonempty(p)]
        missing_shards = []
        for index in files:
            if index.name.endswith((".safetensors.index.json", ".bin.index.json")):
                mapping = json.loads(index.read_text())["weight_map"]
                for name in set(mapping.values()):
                    if Path(name).is_absolute() or ".." in Path(name).parts:
                        raise ValueError("weight shard must be inside the snapshot")
                    if not nonempty(index.parent / name):
                        missing_shards.append(name)
        config = nonempty(path / "config.json")
        result.update(config_present=config, weight_files_observed=len(weights),
                      processor_configs_observed=configs, missing_weight_shards=sorted(set(missing_shards)),
                      status="files_observed" if config and weights and not missing_shards and (base_model or configs) else "partial")
        if config and not base_model:
            result["precision"] = policy_config(path / "config.json")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="unknown", error=str(exc))
    return result


def model_inventory(model_id, hub_cache, models_root, base_model=False):
    result = {"id": model_id, "snapshots": []}
    try:
        snapshots = hub_cache / ("models--" + model_id.replace("/", "--")) / "snapshots"
        candidates = list(snapshots.iterdir()) if snapshots.is_dir() else []
        if models_root:
            local = models_root / model_id
            if local.is_dir():
                candidates.append(local)
        result["snapshots"] = [model_snapshot(p, base_model) for p in sorted(candidates) if p.is_dir()]
        result["status"] = "candidates_observed" if result["snapshots"] else "missing"
    except OSError as exc:
        result.update(status="unknown", error=str(exc))
    return result


def dataset_inventory(dataset_id, datasets_root):
    path = datasets_root / dataset_id
    result = {"id": dataset_id, "path": str(path)}
    try:
        metadata = nonempty(path / "meta/info.json")
        if metadata:
            info = json.loads((path / "meta/info.json").read_text())
            if not isinstance(info, dict):
                raise ValueError("dataset info must be a JSON object")
        parquet = [p for p in (path / "data").rglob("*.parquet") if nonempty(p)]
        result.update(metadata_observed=metadata, data_parquet_files_observed=len(parquet),
                      status="files_observed" if metadata and parquet else "partial" if path.exists() else "missing")
    except (OSError, ValueError) as exc:
        result.update(status="unknown", error=str(exc))
    return result


def lfs_inventory(repo):
    pointers, errors = [], []
    for tree in ("docs", "images", "source"):
        for parent, dirs, files in os.walk(repo / tree, onerror=lambda e: errors.append(str(e))):
            dirs[:] = [d for d in dirs if d not in {"_build", ".git", ".venv", ".local"}]
            for name in files:
                path = Path(parent) / name
                try:
                    if path.stat().st_size < 512 and path.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
                        pointers.append(str(path.relative_to(repo)))
                except OSError as exc:
                    errors.append(str(exc))
    return {"pointers": pointers, "errors": errors, "status": "unknown" if errors else "observed"}


def inspect(repo, configs, expected=None, hub_cache=None, models_root=None, datasets_root=None):
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface"))
    cache = Path(hub_cache or os.environ.get("HF_HUB_CACHE", hf_home / "hub")).expanduser()
    datasets_root = Path(datasets_root or repo / "datasets").expanduser()
    models_root = Path(models_root).expanduser() if models_root else None
    model_ids, dataset_ids = course_assets(repo)
    tools = {name: command(args) for name, args in {
        "git": ["git", "--version"], "git_lfs": ["git", "lfs", "version"],
        "docker": ["docker", "--version"], "nvidia_container_toolkit": ["nvidia-ctk", "--version"],
        "hf": ["hf", "version"], "uv": ["uv", "--version"]}.items()}
    listeners = command(["ss", "-H", "-ltnp"])
    if listeners["status"] == "ok":
        listeners["output"] = "\n".join(line for line in listeners["output"].splitlines()
                                         if re.search(r":(?:8080|8081|8090|8091|8095)\b", line))
    source = source_check(repo, expected)
    return {
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hostname": platform.node(), "repo": str(repo),
        "host": {"architecture": platform.machine(), "os": platform.freedesktop_os_release(),
                 "ram_gib": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 2)},
        "source": source, "tools": tools,
        "git_status": command(["git", "--no-optional-locks", "-C", str(repo), "status", "--short"]),
        "disk_free_gib": round(shutil.disk_usage(repo).free / 2**30, 2),
        "gpu": command(["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.free,utilization.gpu", "--format=csv,noheader"]),
        "containers": command(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]),
        "docker_runtimes": command(["docker", "info", "--format", "{{json .Runtimes}}"]),
        "network_interfaces": command(["ip", "-br", "-4", "addr"]),
        "workshop_listeners": listeners,
        "serial_by_id": {str(p): str(p.resolve()) for p in Path("/dev/serial/by-id").glob("*")},
        "camera_by_id": {str(p): str(p.resolve()) for p in Path("/dev/v4l/by-id").glob("*")},
        "lfs": lfs_inventory(repo), "hub_cache": str(cache),
        "models": [model_inventory(mid, cache, models_root, mid == model_ids[0]) for mid in model_ids],
        "starting_pose_datasets": [dataset_inventory(did, datasets_root) for did in dataset_ids],
        "policy_configs": [policy_config(p) for p in configs],
        "limitations": ["Read-only inventory: no downloads, device opens, CUDA/model load or robot qualification.",
                        "Observed files do not prove complete snapshots, tensor integrity, dataset compatibility or runtime success.",
                        "All cached revisions are candidates; the operator must select and record the actual revision and mount.",
                        "Listening sockets do not establish ownership or policy readiness.",
                        "HF credentials and identity are not inspected; verify effective identity before authorized HF calls."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--expected-revision", help="agreed commit or locally resolvable Git ref")
    parser.add_argument("--policy-config", action="append", default=[])
    parser.add_argument("--hub-cache", type=Path)
    parser.add_argument("--models-root", type=Path, help="local models at ROOT/owner/name")
    parser.add_argument("--datasets-root", type=Path)
    parser.add_argument("--output", type=Path, help="new JSON report under this checkout's ignored runs directory")
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    if not (repo / ".git").exists() or not (repo / "docs/conf.py").is_file():
        parser.error("--repo must be the workshop Git checkout")
    try:
        report = inspect(repo, args.policy_config, args.expected_revision, args.hub_cache, args.models_root, args.datasets_root)
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            output = args.output.expanduser().resolve()
            if not output.is_relative_to(repo / "runs"):
                parser.error("--output must be inside the selected checkout's runs directory")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x") as stream:
                stream.write(text)
        print(text, end="")
    except (OSError, ValueError, IndexError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
