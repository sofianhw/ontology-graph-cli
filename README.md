# Ontology Graph CLI

`ontograph` turns structured graph data and Product Requirements Document (PRD)
PDFs into a queryable RDF/OWL/SKOS ontology, a GraphML property graph, an
interactive HTML visualization, and an insight report.

The PRD workflow is designed for repeatable product documentation: it inventories
source text by page and line, maps known PRD sections into a stable ontology, and
optionally uses an OpenAI-compatible model to add supported cross-links and clearly
marked candidate relationships.

## Requirements

- Python 3.9 or later
- [uv](https://docs.astral.sh/uv/)
- For PDF workflows, an extractable text layer in the PDF. Scanned PDFs must be OCRed
  before use.

## Installation

Create the managed environment with every optional feature enabled:

```sh
uv sync --extra full
uv run ontograph --help
```

No global installation is required. Run every command through `uv run`.

## Quick start: build a graph from a PRD PDF

```sh
uv run ontograph build-prd \
  "$HOME/Downloads/product-requirements-document.pdf" \
  outputs/product-requirements \
  --base-uri https://example.org/product-requirements#
```

Open the interactive graph when the command completes:

```sh
open outputs/product-requirements/visualization.html
```

The command always performs deterministic, template-based extraction. If no LLM
configuration is supplied, it completes normally and records that enrichment was
skipped in `extraction_report.md`.

## PRD PDF workflow

`build-prd` is the end-to-end command:

```text
PDF → source inventory → template extraction → optional LLM enrichment → ontology outputs
```

It recognizes standard PRD material when present, including document metadata,
stakeholders/sign-off, artifacts, assumptions, constraints, requirements, NFRs,
user stories, acceptance criteria, metrics, events, security controls, rollout,
rate limiting, architecture, and AI-model decisions.

Every extracted entity and relationship has `source_refs` that point to stable IDs in
the inventory, such as `p14_l7` for page 14, line 7.

### Output directory

`build-prd` writes these files to the selected output directory:

| File | Purpose |
| --- | --- |
| `graph_data.json` | Canonical v1 graph data used to build the graph. |
| `extraction_draft.json` | The pre-build extraction snapshot for audit or comparison. |
| `source_inventory.json` | Every extractable source line, with page and line location. |
| `extraction_report.md` | Coverage, entity/predicate counts, candidates, and extraction notes. |
| `ontology.ttl` | Asserted RDF/OWL/SKOS ontology. |
| `ontology_inferred.ttl` | Ontology after OWL-RL inference, when available. |
| `graph.graphml` | Property graph for NetworkX, Gephi, and other graph tools. |
| `visualization.html` | Self-contained interactive graph view. |
| `insights.md` | Centrality, bridge-node, and link-prediction analysis. |

## Optional LLM enrichment

The extractor can ask an OpenAI-compatible Chat Completions API to find semantic
relationships that the template parser did not identify. The model receives only the
source inventory, permitted entity IDs, and permitted predicates; document content is
explicitly treated as data rather than instructions.

```sh
export OPENAI_API_KEY="..."

uv run ontograph build-prd document.pdf outputs/prd \
  --llm-model gpt-4.1-mini
```

For a compatible internal gateway or another provider:

```sh
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://gateway.example.com/v1"

uv run ontograph build-prd document.pdf outputs/prd \
  --llm-model your-model-name
```

You may also pass `--llm-base-url` for one command. LLM enrichment is optional; a
missing key, unavailable endpoint, or malformed model response does not prevent the
deterministic graph from being built.

### Asserted vs candidate links

- `asserted` links are explicitly supported by cited source inventory items.
- `candidate` links are plausible, non-explicit connections. They include a
  `confidence`, a `rationale`, and `source_refs`.

Candidate edges are retained in JSON and GraphML, summarized in `insights.md`, and
rendered as dashed amber arrows in `visualization.html`. Review them before treating
them as facts.

## Build from canonical JSON

Use `build` when you already have graph data:

```sh
uv run ontograph validate graph_data.json

uv run ontograph build graph_data.json outputs/org-network \
  --base-uri https://example.org/org#
```

The v1 format has four top-level arrays:

```json
{
  "concepts": [
    {"id": "employee", "label": "Employee", "kind": "class", "broader": null}
  ],
  "properties": [
    {
      "id": "worksFor",
      "label": "works for",
      "kind": "object",
      "domain": "employee",
      "range": "organization",
      "inverse_of": "employs"
    }
  ],
  "instances": [
    {"id": "alice", "label": "Alice", "type": "employee", "attributes": {"age": 34}}
  ],
  "relations": [
    {
      "subject": "alice",
      "predicate": "worksFor",
      "object": "acme",
      "assertion": "asserted",
      "source_refs": ["p1_l7"]
    }
  ]
}
```

All IDs must be unique across concepts, properties, and instances. Every relation
must resolve to declared IDs. A `candidate` relation additionally requires
`confidence` between `0` and `1`, `rationale`, and at least one source reference.

## Query a built graph

```sh
uv run ontograph query outputs/org-network neighbors Alice
uv run ontograph query outputs/org-network path Alice "Acme Corp"
uv run ontograph query outputs/org-network centrality --kind betweenness --limit 10
uv run ontograph query outputs/org-network sparql \
  'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10'
```

The available centrality kinds are `degree`, `betweenness`, and `closeness`.

### Ask graph-first questions with minimal context

`ask` answers supported PRD traceability questions from the built `graph_data.json`.
It never reopens the PDF, reads the full source inventory, or calls an external model.
Its compact JSON response contains only the matching graph entities, relationships,
and their source references, making it the preferred command for agent-skill follow-up
questions.

```sh
uv run ontograph ask outputs/product-requirements \
  "Which requirements are not implemented by a user story?"
```

Use `--limit` to cap returned entities. If the response reports
`"answer_type": "unsupported_question"`, use a precise `query` command or a
read-only SPARQL query instead.

## Extract a PRD draft without building

Use `extract-prd` when you want to inspect or edit the deterministic draft before
creating ontology artifacts:

```sh
uv run ontograph extract-prd document.pdf graph_data.json
uv run ontograph validate graph_data.json
uv run ontograph build graph_data.json outputs/prd
```

## Merge graph data

Extend a previously built graph with another canonical JSON file:

```sh
uv run ontograph merge outputs/org-network new_data.json outputs/org-network-v2
```

Nodes with the same ID are merged with new values taking precedence. Identical
relations are deduplicated. A merge fragment may refer to vocabulary already defined
in the prior graph.

## Troubleshooting

| Problem | Resolution |
| --- | --- |
| `PDF has no extractable text` | OCR the scanned PDF, then rerun `build-prd`. |
| LLM enrichment is skipped | Set `OPENAI_API_KEY` and pass `--llm-model`; the graph still builds without it. |
| Validation fails | Check duplicate IDs and ensure each relation refers to declared concepts, properties, or instances. |
| HTML view says `pyvis` is missing | Run `uv sync --extra full`. |
| No inferred triples | Run `uv sync --extra full`, which installs `owlrl`. |

## Development checks

```sh
uv run --extra full python -m unittest discover -s tests -v
```

The test suite covers template extraction, source evidence, candidate-edge GraphML
export, missing credentials, and malformed LLM replies.

## License

This project is licensed under the [MIT License](LICENSE).

## Use from Codex, Claude Cowork, or pi-agent

The repository has two deliverables with the same deterministic graph capability:

- **CLI distribution:** `uv run ontograph ...` for developers and terminal users.
- **Standalone skill distribution:** `npx skills` installs a bundled Python runner,
  graph engine, and dependency list. It needs `uv` on first use, but never needs this
  repository path or a local CLI checkout.

The standalone engine is generated from the CLI modules. Contributors edit the CLI,
then rebuild the skill bundle; see [AGENTS.md](AGENTS.md).

Install one adapter from the repository root. The examples below use the platform's
default skill location; use `--destination <path>` to select a project-specific one.

```sh
# Codex
uv run python scripts/install-skill.py --target codex

# Claude Cowork
uv run python scripts/install-skill.py --target claude-cowork

# pi-agent
uv run python scripts/install-skill.py --target pi-agent
```

Each installed adapter contains its own runner and dependencies. To preview an
installation without changing files, add `--dry-run`. Existing installations are
protected; pass `--force` only when deliberately replacing one.

After pulling an updated repository version, refresh the adapter:

```sh
git pull
uv run python scripts/build-standalone-skill.py
uv run python scripts/build-skill-adapters.py
uv run python scripts/install-skill.py --target codex --force
```

The shared source is [skills/ontology-graph-builder/SKILL.md](skills/ontology-graph-builder/SKILL.md).
Generated platform packages live under `integrations/`.

### Install with `npx skills`

After publishing this repository to GitHub, the open
[`skills`](https://github.com/vercel-labs/skills) installer can install the canonical
skill directly from this published repository.

```sh
npx skills add sofianhw/ontology-graph-cli \
  --skill ontology-graph-builder \
  --global \
  --agent codex \
  --agent claude-code \
  --agent pi
```

`claude-code` is the compatible target for Claude Cowork's standard skill layout;
`pi` is the `npx skills` target name for pi-agent. To install only for the current
repository, omit `--global`.

The skill needs `uv`. On its first graph build, `uv` downloads and caches the bundled
runner's Python dependencies; later builds reuse that cache. It does not download this
repository or require a `.ontograph-skill.json` configuration file.
For graph follow-up questions, it directly filters the generated `graph_data.json` and
shows the result in the conversation. The CLI's `ask` command remains available for
terminal users, but the skill does not use it. It writes a reproducible query file only
when you explicitly request one.
