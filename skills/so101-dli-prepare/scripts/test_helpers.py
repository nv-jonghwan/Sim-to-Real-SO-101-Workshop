"""Offline regression checks for station audits and opt-in skill discovery."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load("preflight")
links = load("instructor_skills")


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

    def test_activation_is_idempotent_and_preserves_student_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            folder = repo / ".agents/skills"
            folder.mkdir(parents=True)
            student = folder / "so101-dli"
            student.symlink_to("../../skills/so101-dli")
            for name in links.NAMES:
                path = repo / "skills" / name
                path.mkdir(parents=True)
                (path / "SKILL.md").write_text('fixture')
            links.configure(repo)
            links.configure(repo)
            self.assertEqual(len(list(folder.iterdir())), 3)
            links.configure(repo, disable=True)
            self.assertEqual(list(folder.iterdir()), [student])
            self.assertEqual(student.readlink(), Path("../../skills/so101-dli"))

    def test_activation_conflict_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for name in links.NAMES:
                path = repo / "skills" / name
                path.mkdir(parents=True)
                (path / "SKILL.md").write_text('fixture')
            folder = repo / ".agents/skills"
            folder.mkdir(parents=True)
            conflict = folder / links.NAMES[1]
            conflict.write_text('user-owned')
            with self.assertRaises(ValueError):
                links.configure(repo)
            self.assertFalse((folder / links.NAMES[0]).is_symlink())
            self.assertEqual(conflict.read_text(), 'user-owned')


if __name__ == "__main__":
    unittest.main()
