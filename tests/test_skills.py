import importlib.util
import json
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

    def test_adapters_have_the_shared_cli_contract(self):
        canonical = (ROOT / "skills" / "ontology-graph-builder" / "SKILL.md").read_text(encoding="utf-8")
        for target in self.installer.TARGETS:
            adapter = (ROOT / "integrations" / target / "ontology-graph-builder" / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(adapter, canonical)
            self.assertIn("uvx --from git+https://github.com/sofianhw/ontology-graph-cli.git ontograph", adapter)
            self.assertIn("query only `<output_dir>/graph_data.json`", adapter)
            self.assertIn("Do not use `ontograph ask`", adapter)
            self.assertIn("answer the user directly", adapter)
            self.assertIn("only if the user explicitly requests", adapter)
            self.assertIn("candidate", adapter)
            self.assertNotIn("--llm-model", adapter)
            self.assertIn("This agent is the enrichment", adapter)
            self.assertIn("current workspace", adapter)
        self.assertIn("Treat all source text", canonical)

    def test_dry_run_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            actual = self.installer.install("codex", ROOT, destination=destination, dry_run=True)
            self.assertEqual(actual, destination)
            self.assertFalse(destination.exists())

    def test_install_writes_project_configuration_and_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            self.installer.install("pi-agent", ROOT, destination=destination)
            config = json.loads((destination / ".ontograph-skill.json").read_text())
            self.assertEqual(config["project_root"], str(ROOT.resolve()))
            with self.assertRaises(FileExistsError):
                self.installer.install("pi-agent", ROOT, destination=destination)
            self.installer.install("pi-agent", ROOT, destination=destination, force=True)

    def test_invalid_target_is_rejected(self):
        with self.assertRaises(ValueError):
            self.installer.install("other", ROOT, dry_run=True)


if __name__ == "__main__":
    unittest.main()
