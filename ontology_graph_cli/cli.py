from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import networkx as nx
from rdflib import Graph

from .core import build, load_data, merge, validate_data
from .prd import build_prd, extract_prd, report as prd_report


def _load_output(output_dir: str):
    output = Path(output_dir); graph = nx.read_graphml(output / "graph.graphml")
    rdf = Graph(); rdf.parse(output / ("ontology_inferred.ttl" if (output / "ontology_inferred.ttl").exists() else "ontology.ttl"), format="turtle")
    return graph, rdf


def _node(graph: nx.Graph, name: str) -> str:
    if name in graph: return name
    for node, attributes in graph.nodes(data=True):
        if attributes.get("label", "").casefold() == name.casefold(): return node
    raise KeyError(f"No node matches '{name}'.")


def _query(args: argparse.Namespace) -> object:
    graph, rdf = _load_output(args.output_dir)
    if args.operation == "sparql": return [list(map(str, row)) for row in rdf.query(args.query)]
    simple = nx.Graph(graph.to_undirected())
    if args.operation == "neighbors": return [graph.nodes[node].get("label", node) for node in simple.neighbors(_node(graph, args.name))]
    if args.operation == "path": return [graph.nodes[node].get("label", node) for node in nx.shortest_path(simple, _node(graph, args.source), _node(graph, args.target))]
    scores = {"degree": nx.degree_centrality, "betweenness": nx.betweenness_centrality, "closeness": nx.closeness_centrality}[args.kind](simple)
    return [{"label": graph.nodes[node].get("label", node), "score": round(score, 6)} for node, score in sorted(scores.items(), key=lambda item: -item[1])[:args.limit]]


def _source_refs(instance: dict) -> list[str]:
    return list(instance.get("attributes", {}).get("source_refs", []))


def _compact_entity(instance: dict, max_label: int = 240) -> dict:
    label = instance.get("label", instance["id"])
    return {"label": label[:max_label] + ("..." if len(label) > max_label else ""), "type": instance.get("type"), "source_refs": _source_refs(instance)}


def _ask(output_dir: str, question: str, limit: int) -> dict:
    """Answer a small set of high-value PRD questions from graph_data.json only.

    This deliberately returns compact evidence rather than loading the source PDF or
    calling a model. Agent skills can interpret the response without re-reading a PRD.
    """
    data = load_data(Path(output_dir) / "graph_data.json")
    instances = {item["id"]: item for item in data["instances"]}
    q = re.sub(r"\s+", " ", question.casefold())
    scope = {"entities": len(instances), "relations": len(data["relations"])}

    # Traceability is a key PRD question: requirements with no user-story implements edge.
    asks_requirements = "requirement" in q
    asks_story = "user stor" in q or "userstory" in q
    asks_unlinked = any(word in q for word in ("not implement", "not applied", "unimplemented", "missing", "without"))
    if asks_requirements and asks_story and asks_unlinked:
        requirement_types = {"requirement", "nfr_requirement", "risk_requirement", "data_privacy_requirement", "regulatory_requirement", "audit_requirement", "operational_requirement", "fraud_requirement", "feature_flag_requirement", "rate_limiting_requirement"}
        implemented = {edge["object"] for edge in data["relations"] if edge["predicate"] == "implements" and instances.get(edge["subject"], {}).get("type") == "user_story"}
        results = [_compact_entity(item) for item in instances.values() if item.get("type") in requirement_types and item["id"] not in implemented]
        return {"question": question, "interpretation": "Requirements with no asserted user-story implements relationship.", "answer_type": "unimplemented_requirements", "total_matches": len(results), "results": results[:limit], "truncated": len(results) > limit, "scope": scope, "note": "An empty implements relationship set means this is a traceability gap in the graph, not proof the PRD omits implementation."}

    # Exact entity mention: return a one-hop compact subgraph, useful for most follow-ups.
    labels = {item["id"]: item.get("label", item["id"]) for item in instances.values()}
    matched = [item for item in instances.values() if item.get("label", "").casefold() in q or item["id"].casefold() in q]
    matched.sort(key=lambda item: (item.get("type") != "feature", item.get("type") != "prd_document", item["label"]))
    if matched:
        selected = matched[:1]
        node_ids = {item["id"] for item in selected}
        raw_edges = [edge for edge in data["relations"] if edge["subject"] in node_ids or edge["object"] in node_ids][:limit]
        edges = [{"from": labels.get(edge["subject"], edge["subject"]), "predicate": edge["predicate"], "to": labels.get(edge["object"], edge["object"]), "assertion": edge.get("assertion", "asserted"), "source_refs": edge.get("source_refs", [])} for edge in raw_edges]
        # Derive the displayed nodes from raw edges; rendered edges are intentionally
        # label-based to keep this context small enough for an agent prompt.
        related_ids = {edge["subject"] for edge in raw_edges} | {edge["object"] for edge in raw_edges}
        results = [_compact_entity(instances[node_id]) for node_id in related_ids if node_id in instances]
        return {"question": question, "interpretation": f"One-hop graph context for '{selected[0]['label']}'.", "answer_type": "entity_neighborhood", "total_matches": len(results), "results": results, "edges": edges, "truncated": False, "scope": scope}

    return {"question": question, "answer_type": "unsupported_question", "results": [], "scope": scope, "guidance": "Use `ontograph query` with neighbors, path, centrality, or a read-only SPARQL query. The graph was not expanded and no PDF content was loaded."}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="ontograph", description="Build, inspect, query, and merge ontology graphs.")
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate canonical graph JSON"); validate.add_argument("data")
    extract = commands.add_parser("extract-prd", help="extract a review draft from a PRD PDF")
    extract.add_argument("pdf_path"); extract.add_argument("output", help="draft graph_data.json path")
    build_prd_p = commands.add_parser("build-prd", help="extract, enrich, and build all graph artifacts from a PRD PDF")
    build_prd_p.add_argument("pdf_path"); build_prd_p.add_argument("output_dir")
    build_prd_p.add_argument("--base-uri", default="http://example.org/kg#")
    build_prd_p.add_argument("--llm-model", help="OpenAI-compatible model for optional semantic enrichment")
    build_prd_p.add_argument("--llm-base-url", help="OpenAI-compatible API base URL; defaults to OPENAI_BASE_URL or OpenAI")
    build_p = commands.add_parser("build", help="build all graph artifacts"); build_p.add_argument("data"); build_p.add_argument("output_dir"); build_p.add_argument("--base-uri", default="http://example.org/kg#")
    merge_p = commands.add_parser("merge", help="merge new graph JSON into prior output"); merge_p.add_argument("existing_dir"); merge_p.add_argument("data"); merge_p.add_argument("output_dir"); merge_p.add_argument("--base-uri", default="http://example.org/kg#")
    query = commands.add_parser("query", help="query a built output directory"); query.add_argument("output_dir")
    operations = query.add_subparsers(dest="operation", required=True)
    neighbors = operations.add_parser("neighbors"); neighbors.add_argument("name")
    path = operations.add_parser("path"); path.add_argument("source"); path.add_argument("target")
    centrality = operations.add_parser("centrality"); centrality.add_argument("--kind", choices=("degree", "betweenness", "closeness"), default="degree"); centrality.add_argument("--limit", type=int, default=15)
    sparql = operations.add_parser("sparql"); sparql.add_argument("query")
    ask = commands.add_parser("ask", help="answer a supported natural-language question from compact local graph data")
    ask.add_argument("output_dir"); ask.add_argument("question"); ask.add_argument("--limit", type=int, default=25)
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            validate_data(load_data(args.data)); print("Valid graph_data.json")
        elif args.command == "extract-prd":
            data = extract_prd(args.pdf_path); validate_data(data)
            destination = Path(args.output); destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"Created review draft: {destination}")
            print(f"Proposed vocabulary: {len(data['concepts'])} classes, {len(data['properties'])} properties")
            print(f"Extracted: {len(data['instances'])} instances, {len(data['relations'])} relations")
            print("Review this draft before running 'ontograph build'.")
        elif args.command == "build-prd":
            data, inventory, notes = build_prd(args.pdf_path, args.llm_model, args.llm_base_url)
            output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
            draft = output / "extraction_draft.json"; draft.write_text(json.dumps(data, indent=2), encoding="utf-8")
            (output / "source_inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
            (output / "extraction_report.md").write_text(prd_report(data, inventory, notes), encoding="utf-8")
            nodes, edges, inferred = build(draft, output, args.base_uri)
            print(f"Built PRD graph: {nodes} nodes, {edges} edges ({inferred} inferred RDF triples)")
            print(f"Audit outputs written to {output}")
        elif args.command == "build":
            nodes, edges, inferred = build(args.data, args.output_dir, args.base_uri); print(f"Built graph: {nodes} nodes, {edges} edges ({inferred} inferred RDF triples)")
        elif args.command == "merge":
            merged = merge(args.existing_dir, args.data); temp = Path(args.output_dir) / "_merged_graph_data.json"; temp.parent.mkdir(parents=True, exist_ok=True); temp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
            nodes, edges, inferred = build(temp, args.output_dir, args.base_uri); temp.unlink(missing_ok=True); print(f"Merged and built graph: {nodes} nodes, {edges} edges ({inferred} inferred RDF triples)")
        elif args.command == "ask":
            if args.limit < 1: raise ValueError("--limit must be at least 1")
            print(json.dumps(_ask(args.output_dir, args.question, args.limit), indent=2))
        else: print(json.dumps(_query(args), indent=2))
    except (ValueError, KeyError, nx.NetworkXException, OSError) as error:
        print(f"Error: {error}", file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__": main()
