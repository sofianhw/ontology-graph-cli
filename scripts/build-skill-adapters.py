#!/usr/bin/env python3
"""Generate platform skill adapters from the canonical portable skill."""
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills" / "ontology-graph-builder"
TARGETS = ("codex", "claude-cowork", "pi-agent")


def build(root: Path = ROOT) -> list[Path]:
    source = root / "skills" / "ontology-graph-builder"
    written: list[Path] = []
    for target in TARGETS:
        destination = root / "integrations" / target / "ontology-graph-builder"
        metadata = destination / "agents" / "openai.yaml"
        metadata_text = metadata.read_text(encoding="utf-8") if metadata.is_file() else None
        if destination.exists(): shutil.rmtree(destination)
        shutil.copytree(source, destination)
        if metadata_text is not None:
            metadata.parent.mkdir(parents=True, exist_ok=True)
            metadata.write_text(metadata_text, encoding="utf-8")
        written.append(destination / "SKILL.md")
    return written


if __name__ == "__main__":
    for path in build():
        print(path)
