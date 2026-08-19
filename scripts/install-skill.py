#!/usr/bin/env python3
"""Install a generated Ontology Graph Builder adapter into an agent skill folder."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "ontology-graph-builder"
TARGETS = {
    "codex": lambda: Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills" / SKILL_NAME,
    "claude-cowork": lambda: Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "skills" / SKILL_NAME,
    "pi-agent": lambda: Path(os.environ.get("PI_CONFIG_DIR", Path.home() / ".pi")) / "skills" / SKILL_NAME,
}


def adapter_root(target: str, repository_root: Path) -> Path:
    return repository_root / "integrations" / target / SKILL_NAME


def install(target: str, project_root: Path = REPOSITORY_ROOT, destination: Path | None = None, force: bool = False, dry_run: bool = False, repository_root: Path = REPOSITORY_ROOT) -> Path:
    if target not in TARGETS:
        raise ValueError(f"Unsupported target '{target}'. Choose: {', '.join(TARGETS)}")
    source = adapter_root(target, repository_root)
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"Adapter is missing: {source}")
    destination = (destination or TARGETS[target]()).expanduser()
    if destination.exists() and not force:
        raise FileExistsError(f"Destination exists: {destination}. Use --force to replace it.")
    if dry_run:
        print(f"Would install {target} skill from {source} to {destination}")
        return destination
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    print(f"Installed {target} skill at {destination}")
    return destination


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--target", required=True, choices=sorted(TARGETS))
    command.add_argument("--project-root", type=Path, default=REPOSITORY_ROOT)
    command.add_argument("--destination", type=Path)
    command.add_argument("--force", action="store_true")
    command.add_argument("--dry-run", action="store_true")
    return command


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        install(args.target, args.project_root, args.destination, args.force, args.dry_run)
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
