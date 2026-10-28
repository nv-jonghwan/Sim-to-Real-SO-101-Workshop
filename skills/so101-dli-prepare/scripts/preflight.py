#!/usr/bin/env python3
"""Inventory a DLI station without opening devices or mutating its runtime."""
import argparse
import datetime
import csv
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



def assess(report, requirements):
    """Compare observed facts with course requirements; never certify unrun workloads."""
    checks = []

    def add(group, name, status, observed, action):
        checks.append(dict(group=group, name=name, status=status, observed=observed, next_action=action))

    host = report["host"]
    release = host["os"]
    add("host", "OS", "passed" if (release.get("ID"), release.get("VERSION_ID")) ==
        (requirements["os_id"], requirements["os_version"]) else "unknown",
        release.get("PRETTY_NAME", "unknown"), "교재 기준 Ubuntu 24.04 native Linux 환경을 확인합니다.")
    add("host", "architecture", "passed" if host["architecture"] == requirements["architecture"] else "failed",
        host["architecture"], "교재의 x86_64 Container를 실행할 수 있는 Host가 필요합니다.")
    gpu = report["gpu"]
    rows = []
    if gpu["status"] == "ok":
        for row in csv.reader(gpu["output"].splitlines(), skipinitialspace=True):
            if len(row) == 6:
                try:
                    rows.append(dict(index=row[0], name=row[1], driver_branch=int(row[2].split(".")[0]),
                                     vram_gib=round(float(row[3]) / 1024, 2), free_vram_mib=row[4]))
                except ValueError:
                    continue
    candidates = [row for row in rows if requirements["gpu_name_contains"].lower() in row["name"].lower()]
    compatible = [row for row in candidates if row["driver_branch"] >= requirements["minimum_driver_branch"]]
    add("host", "RTX GPU / Driver", "passed" if compatible else "failed" if rows else "unknown",
        rows or gpu, "RTX GPU와 R580 이상 Driver를 확인합니다. 여러 GPU의 VRAM을 합산하지 않습니다.")
    for name, value, minimum in (("RAM GiB", host["ram_gib"], requirements["minimum_ram_gib"]),
                                  ("VRAM GiB", max((row["vram_gib"] for row in compatible), default=None), requirements["minimum_vram_gib"]),
                                  ("disk free GiB", report["disk_free_gib"], requirements["minimum_free_disk_gib"])):
        status = "unknown" if minimum is None or value is None else "passed" if value >= minimum else "failed"
        add("capacity", name, status, value, "교재에 수치 기준이 없으면 합격을 추정하지 않습니다. 실제 mount 여유 공간과 simulation·policy 동시 실행을 확인합니다.")
    for name, observed in report["tools"].items():
        add("software", name, "passed" if observed["status"] == "ok" else "failed" if observed["status"] == "missing" else "unknown",
            observed, "누락된 도구를 준비하고, 권한 문제라면 실제 수업 계정에서 재확인합니다.")
    runtimes = report["docker_runtimes"]
    runtime_names = runtimes.get("output", "").split() if runtimes["status"] == "ok" else None
    add("software", "Docker NVIDIA runtime", "unknown" if not runtime_names else
        "passed" if "nvidia" in runtime_names else "failed", runtimes,
        "수업 계정의 Docker 접근 권한과 NVIDIA runtime 설정을 확인합니다.")
    source = report["source"]["matches_expected_revision"]
    add("assets", "source revision", "unknown" if source is None else "passed" if source else "failed",
        report["source"], "합의한 commit을 --expected-revision으로 지정하고 실제 image·mount와 비교합니다.")
    lfs = report["lfs"]
    add("assets", "Git LFS files", "unknown" if lfs["errors"] else "failed" if lfs["pointers"] else "passed",
        lfs, "미완료 LFS 파일을 준비합니다.")
    for model in report["models"]:
        complete = [snap for snap in model["snapshots"] if snap.get("status") == "files_observed" and
                    ("precision" not in snap or snap["precision"].get("course_precision") is True)]
        add("assets", model["id"], "unknown" if complete or model["status"] == "unknown" else "failed",
            model, "실제 사용할 revision·mount를 선택하고 Container에서 model을 로드합니다. 파일 관측만으로 실행 합격을 판정하지 않습니다.")
    for dataset in report["starting_pose_datasets"]:
        add("assets", dataset["id"], "unknown" if dataset["status"] in {"files_observed", "unknown"} else "failed",
            dataset, "meta·data의 존재와 실제 Container 경로·dataset 호환성을 확인합니다.")
    for name, action in (("simulation / cameras / policy", "Physics·wrist/external rendering·viewer와 policy 동시 실행을 실제 검증합니다."),
                         ("power / display / network", "AC 전원·발열·suspend·참가자 화면과 필요한 서비스 접근을 확인합니다."),
                         ("robot station", "현재 작업자와 두 arm·두 camera·calibration·Real Teleop를 확인합니다.")):
        add("runtime", name, "unknown", "읽기 전용 점검에서 실행하지 않음", action)
    host_checks = [check for check in checks if check["group"] == "host"]
    eligibility = "failed" if any(c["status"] == "failed" for c in host_checks) else "unknown" if any(
        c["status"] == "unknown" for c in host_checks) else "passed"
    messages = {"passed": "기본 실행 조건 충족: DLI 환경 준비를 진행할 수 있습니다. 수업 실행 검증은 아직 완료되지 않았습니다.",
                "failed": "교재의 기본 실행 조건에 미달하는 항목이 있습니다. 해당 항목을 해결한 뒤 재점검해야 합니다.",
                "unknown": "기본 실행 조건을 확정할 수 없습니다. 미확인 항목의 실제 Host 정보·권한을 확인해야 합니다."}
    return dict(requirements=requirements, eligibility=eligibility, summary_ko=messages[eligibility],
                dli_ready="unknown", checks=checks,
                next_actions=[{"name": c["name"], "status": c["status"], "action": c["next_action"]}
                              for c in checks if c["status"] != "passed"])


def markdown_report(report):
    """Render a Korean assessment with measured facts and scoped next actions."""
    assessment = report["assessment"]
    lines = ["# DLI 환경 점검", "", assessment["summary_ko"], "",
             "기준: " + assessment["requirements"]["source"],
             "점검 Host: " + report["hostname"], "",
             "| 구분 | 항목 | 결과 | 관측값 |", "|---|---|---|---|"]
    labels = {"passed": "충족", "failed": "미충족", "unknown": "미확인"}
    for check in assessment["checks"]:
        observed = check["observed"]
        if isinstance(observed, dict):
            if "output" in observed or "error" in observed:
                value = observed.get("output", observed.get("error", ""))
            elif "id" in observed:
                value = observed.get("status", "unknown")
            elif "actual" in observed:
                value = observed["actual"].get("output", "unknown")
            else:
                value = json.dumps(observed, ensure_ascii=False)
        elif isinstance(observed, list):
            value = "; ".join(f"GPU {gpu['index']}: {gpu['name']}, R{gpu['driver_branch']}, {gpu['vram_gib']} GiB" for gpu in observed)
        else:
            value = "기준 수치 없음 / 관측 불가" if observed is None else str(observed)
        value = value[:240]
        value = value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")
        lines.append(f"| {check['group']} | {check['name']} | {labels[check['status']]} | {value} |")
    lines += ["", "## 다음 조치", ""]
    lines += [f"- {action['name']}: {action['action']}" for action in assessment["next_actions"]]
    lines += ["", "RAM·VRAM·저장 공간의 수치 기준이 없는 항목은 미확인입니다. 읽기 전용 결과는 수업 실행·robot 동작 검증을 대신하지 않습니다."]
    return "\n".join(lines) + "\n"


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
    report = {
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hostname": platform.node(), "repo": str(repo),
        "host": {"architecture": platform.machine(), "os": platform.freedesktop_os_release(),
                 "ram_gib": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 2)},
        "source": source, "tools": tools,
        "git_status": command(["git", "--no-optional-locks", "-C", str(repo), "status", "--short"]),
        "disk_free_gib": round(shutil.disk_usage(repo).free / 2**30, 2),
        "gpu": command(["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.free,utilization.gpu", "--format=csv,noheader,nounits"]),
        "containers": command(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]),
        "docker_runtimes": command(["docker", "info", "--format", "{{range $name, $_ := .Runtimes}}{{$name}} {{end}}"]),
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

    requirements = json.loads((repo / "docs/_static/dli-requirements.json").read_text())
    report["assessment"] = assess(report, requirements)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--expected-revision", help="agreed commit or locally resolvable Git ref")
    parser.add_argument("--policy-config", action="append", default=[])
    parser.add_argument("--hub-cache", type=Path)
    parser.add_argument("--models-root", type=Path, help="local models at ROOT/owner/name")
    parser.add_argument("--datasets-root", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="new report under this checkout's ignored runs directory")
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    if not (repo / ".git").exists() or not (repo / "docs/conf.py").is_file():
        parser.error("--repo must be the workshop Git checkout")
    try:
        report = inspect(repo, args.policy_config, args.expected_revision, args.hub_cache, args.models_root, args.datasets_root)
        text = markdown_report(report) if args.format == "markdown" else json.dumps(report, indent=2, ensure_ascii=False) + "\n"
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
