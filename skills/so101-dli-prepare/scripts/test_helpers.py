"""Offline regression checks for station audits and opt-in skill discovery."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import shutil
import sys
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load("preflight")
plans = load("setup_plan")


class PreparationTests(unittest.TestCase):
    def test_revision_uses_the_selected_commit_and_unknown_without_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", tmp], check=True)
            subprocess.run(["git", "-C", tmp, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                            "commit", "--allow-empty", "-qm", "fixture"], check=True)
            self.assertTrue(preflight.source_check(repo, "HEAD")["matches_expected_revision"])
            self.assertIsNone(preflight.source_check(repo, None)["matches_expected_revision"])
            self.assertIsNone(preflight.source_check(repo, "absent-revision")["matches_expected_revision"])

    def test_shards_and_processors_are_observed_without_loading_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "config.json").write_text('{"model_params_fp32":false,"use_bf16":true}')
            (path / "policy_preprocessor.json").write_text('{}')
            (path / "part-1.safetensors").write_bytes(b'fixture')
            (path / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"a": "part-1.safetensors", "b": "part-2.safetensors"}}))
            result = preflight.model_snapshot(path)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["missing_weight_shards"], ["part-2.safetensors"])
            (path / "part-2.safetensors").write_bytes(b'fixture')
            self.assertEqual(preflight.model_snapshot(path)["status"], "files_observed")

    def test_config_audit_preserves_shared_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "blob"
            original = b'{"model_params_fp32":true,"use_bf16":false}'
            blob.write_bytes(original)
            config = Path(tmp) / "config.json"
            config.symlink_to(blob)
            result = preflight.policy_config(config)
            self.assertFalse(result["course_precision"])
            self.assertTrue(result["symlink"])
            self.assertEqual(blob.read_bytes(), original)

    def test_dataset_metadata_is_not_data_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "owner/data"
            (path / "meta").mkdir(parents=True)
            (path / "meta/info.json").write_text('{}')
            self.assertEqual(preflight.dataset_inventory("owner/data", root)["status"], "partial")
            (path / "data").mkdir()
            (path / "data/part.parquet").write_bytes(b'fixture')
            self.assertEqual(preflight.dataset_inventory("owner/data", root)["status"], "files_observed")

    def test_permission_is_unknown(self):
        with patch.object(preflight.subprocess, "run", side_effect=PermissionError("denied")):
            self.assertEqual(preflight.command(["docker", "info"])["status"], "unknown")

    def test_inventory_tracks_the_course_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs/workshop-preparation.md").write_text('hf download owner/new-model\n## Download Starting-Pose Data\n  owner/new-data \\\n')
            self.assertEqual(preflight.course_assets(root), (["owner/new-model"], ["owner/new-data"]))

    def test_default_setup_selects_only_student_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = plans.build_plan(tmp)
            self.assertEqual(plan["profile"], "student")
            self.assertEqual(plan["document_audience"], "event")
            self.assertEqual(plan["document_build_command"][-2:], ["event", "all"])
            self.assertIn("/ko/event/", plan["guide_path"])
            self.assertIn("student", plan["preview_command"])
            self.assertFalse(plan["executed"])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_explicit_instructor_uses_the_same_installation_checkpoints(self):
        student = plans.build_plan(".")
        instructor = plans.build_plan(".", profile="instructor", language="en")
        self.assertEqual(student["checkpoints"], instructor["checkpoints"])
        self.assertEqual(student["preflight_command"], instructor["preflight_command"])
        self.assertEqual(instructor["document_build_command"][-2:], ["instructor", "en"])
        self.assertIn("instructor", instructor["preview_command"])
        self.assertEqual(instructor["guide_path"], "/instructor/html/index.html")

    def test_build_default_executes_student_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            tools = repo / "skills/so101-dli-docs/scripts"
            tools.mkdir(parents=True)
            original = Path(__file__).parents[2] / "so101-dli-docs/scripts/build.sh"
            shutil.copyfile(original, tools / "build.sh")
            (tools / "localization.py").write_text('pass')
            (repo / ".venv/bin").mkdir(parents=True)
            (repo / ".venv/bin/python").symlink_to(sys.executable)
            stub = repo / ".venv/bin/sphinx-build"
            stub.write_text('#!' + sys.executable + '\nimport json,sys\nfrom pathlib import Path\nwith (Path(__file__).parents[2]/"calls.jsonl").open("a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\n')
            stub.chmod(0o755)
            subprocess.run(["bash", str(tools / "build.sh")], check=True, capture_output=True)
            calls = [json.loads(line) for line in (repo / "calls.jsonl").read_text().splitlines()]
            self.assertEqual(len(calls), 2)
            self.assertEqual({call[3] for call in calls}, {"docs/_build/event", "docs/_build/ko/event"})
            (repo / "calls.jsonl").unlink()
            subprocess.run(["bash", str(tools / "build.sh"), "instructor", "all"], check=True, capture_output=True)
            calls = [json.loads(line) for line in (repo / "calls.jsonl").read_text().splitlines()]
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(call[3].endswith("instructor") for call in calls))
            self.assertTrue(all("-t" in call and "instructor" in call for call in calls))

    def test_student_preview_blocks_leftover_instructor_files(self):
        spec = importlib.util.spec_from_file_location("preview", Path(__file__).parents[2] / "so101-dli-docs/scripts/preview.py")
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for audience in ("event", "instructor"):
                for prefix in ("", "ko/"):
                    path = root / (prefix + audience) / "html"
                    path.mkdir(parents=True)
                    (path / "index.html").write_text(audience)
            with patch.object(preview, "ROOT", root):
                handler = preview.Handler.__new__(preview.Handler)
                handler.directory = str(root)
                handler.profile = "student"
                self.assertEqual(handler.translate_path("/ko/event/html/index.html"), str(root / "ko/event/html/index.html"))
                self.assertEqual(handler.translate_path("/ko/instructor/html/index.html"), str(root / "__forbidden__"))
                handler.profile = "instructor"
                self.assertEqual(handler.translate_path("/ko/instructor/html/index.html"), str(root / "ko/instructor/html/index.html"))
                self.assertEqual(handler.translate_path("/ko/event/html/index.html"), str(root / "__forbidden__"))
                self.assertEqual(set(preview.preview_urls("10.0.0.1", 8095, "student")), {"event", "ko/event"})


if __name__ == "__main__":
    unittest.main()
