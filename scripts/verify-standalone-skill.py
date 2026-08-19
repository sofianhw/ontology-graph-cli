#!/usr/bin/env python3
"""Verify that the committed standalone skill engine matches the editable CLI source."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ontology-graph-builder"
MODULES = ("__init__.py", "core.py", "prd.py", "cli.py")


def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((SKILL / "scripts" / "bundle_manifest.json").read_text())
    mismatches = [name for name in MODULES if manifest["modules"].get(name) != digest(ROOT / "ontology_graph_cli" / name)]
    runner = SKILL / "scripts" / "ontograph_runner.py"
    requirements = SKILL / "requirements.txt"
    if not runner.is_file() or not requirements.is_file(): mismatches.append("standalone runner or requirements")
    if mismatches:
        raise SystemExit("Standalone skill bundle is stale: " + ", ".join(mismatches) + ". Run scripts/build-standalone-skill.py.")
    print("Standalone skill bundle is current.")


if __name__ == "__main__": main()
