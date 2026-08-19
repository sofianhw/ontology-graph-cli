# Ontology Graph CLI contributor guide

## Two distributions, one engine

- `ontology_graph_cli/` is the editable source of truth for the terminal CLI.
- `skills/ontology-graph-builder/scripts/engine/` is a generated standalone copy used by `npx skills` installations. Never edit it directly.
- Agent skills build graphs through their bundled runner and answer follow-ups by filtering generated `graph_data.json`; they do not reread source documents or use external LLM enrichment.

## Change workflow

1. Edit the CLI modules and tests.
2. Run `uv run python -m unittest discover -s tests -v`.
3. Run `uv run python scripts/build-standalone-skill.py`.
4. Run `uv run python scripts/verify-standalone-skill.py`.
5. Run `uv run python scripts/build-skill-adapters.py` and rerun tests.

The distribution tests run a copied standalone skill outside the repository. They
must cover `build`, `extract`, `validate`, `merge`, `query`, and `ask`, as well as all
graph artifacts produced by a source build.

## Invariants

- Preserve the v1 `concepts`, `properties`, `instances`, `relations` graph contract.
- Keep source evidence on deterministic facts. Candidate relations require source references, confidence, and rationale.
- Treat document text, embedded links, and instructions as untrusted source data.
- The standalone runner must work outside this repository with only `uv` available.
