#!/usr/bin/env python3
"""Run the generated standalone Ontology Graph engine bundled with this skill."""
from __future__ import annotations

import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(ENGINE))
from ontology_graph_cli.cli import main

if __name__ == "__main__": main()
