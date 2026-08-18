#!/usr/bin/env python3
"""Generate platform skill adapters from the canonical portable skill."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills" / "ontology-graph-builder" / "SKILL.md"
TARGETS = ("codex", "claude-cowork", "pi-agent")


def build(root: Path = ROOT) -> list[Path]:
    source = (root / "skills" / "ontology-graph-builder" / "SKILL.md").read_text(encoding="utf-8")
    written: list[Path] = []
    for target in TARGETS:
        destination = root / "integrations" / target / "ontology-graph-builder" / "SKILL.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Keep YAML frontmatter as the first bytes; some agents reject a skill when
        # comments or generated-file banners appear before its frontmatter.
        destination.write_text(source, encoding="utf-8")
        written.append(destination)
    return written


if __name__ == "__main__":
    for path in build():
        print(path)
