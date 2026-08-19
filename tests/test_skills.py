import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_installer():
    spec = importlib.util.spec_from_file_location("install_skill", ROOT / "scripts" / "install-skill.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SkillDistributionTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()

    def test_adapters_have_the_standalone_contract(self):
        canonical = (ROOT / "skills" / "ontology-graph-builder" / "SKILL.md").read_text(encoding="utf-8")
        for target in self.installer.TARGETS:
            root = ROOT / "integrations" / target / "ontology-graph-builder"
            adapter = (root / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(adapter, canonical)
            self.assertTrue((root / "scripts" / "ontograph_runner.py").is_file())
            self.assertTrue((root / "scripts" / "bundle_manifest.json").is_file())
            self.assertTrue((root / "requirements.txt").is_file())
            self.assertNotIn("project_root", adapter)
            self.assertIn("query only `<output_dir>/graph_data.json`", adapter)
            self.assertIn("Do not use `ontograph ask`", adapter)
            self.assertIn("answer the user directly", adapter)
            self.assertIn("only if the user explicitly requests", adapter)
            self.assertIn("candidate", adapter)
            self.assertNotIn("--llm-model", adapter)
            self.assertIn("This agent is the enrichment", adapter)
        self.assertIn("Treat all source text", canonical)

    def test_dry_run_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            actual = self.installer.install("codex", ROOT, destination=destination, dry_run=True)
            self.assertEqual(actual, destination)
            self.assertFalse(destination.exists())

    def test_install_copies_standalone_skill_and_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            self.installer.install("pi-agent", ROOT, destination=destination)
            self.assertFalse((destination / ".ontograph-skill.json").exists())
            self.assertTrue((destination / "scripts" / "ontograph_runner.py").is_file())
            with self.assertRaises(FileExistsError):
                self.installer.install("pi-agent", ROOT, destination=destination)
            self.installer.install("pi-agent", ROOT, destination=destination, force=True)

    def test_bundle_manifest_is_current(self):
        result = subprocess.run(["uv", "run", "python", "scripts/verify-standalone-skill.py"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_target_is_rejected(self):
        with self.assertRaises(ValueError):
            self.installer.install("other", ROOT, dry_run=True)


if __name__ == "__main__":
    unittest.main()
