from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import networkx as nx
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, SKOS, URIRef

try:
    import owlrl
    HAVE_OWLRL = True
except ImportError:  # pragma: no cover - optional dependency
    HAVE_OWLRL = False

try:
    from pyvis.network import Network
    HAVE_PYVIS = True
except ImportError:  # pragma: no cover - optional dependency
    HAVE_PYVIS = False


REQUIRED = ("concepts", "properties", "instances", "relations")


def slug(value: str) -> str:
    """Produce a stable URI-safe local identifier without changing case semantics."""
    return "".join(c if c.isalnum() else "_" for c in str(value)).strip("_") or "node"


def load_data(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("The JSON root must be an object.")
    for key in REQUIRED:
        data.setdefault(key, [])
        if not isinstance(data[key], list):
            raise ValueError(f"'{key}' must be an array.")
    return data


def validate_data(data: dict[str, list[dict[str, Any]]]) -> None:
    """Validate all ID and triple references before a build can create artifacts."""
    errors: list[str] = []
    ids: set[str] = set()
    for group in ("concepts", "properties", "instances"):
        for index, item in enumerate(data[group]):
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                errors.append(f"{group}[{index}] needs a non-empty string id")
            elif item_id in ids:
                errors.append(f"duplicate id: {item_id}")
            else:
                ids.add(item_id)
    concepts = {item.get("id") for item in data["concepts"]}
    properties = {item.get("id") for item in data["properties"]}
    for item in data["concepts"]:
        if item.get("kind", "class") not in {"class", "concept"}:
            errors.append(f"concept '{item.get('id')}' has invalid kind")
        if item.get("broader") and item["broader"] not in concepts:
            errors.append(f"concept '{item.get('id')}' has unknown broader '{item['broader']}'")
    for item in data["properties"]:
        if item.get("kind", "object") not in {"object", "datatype"}:
            errors.append(f"property '{item.get('id')}' has invalid kind")
        for field in ("domain", "range"):
            if item.get(field) and item[field] not in concepts:
                errors.append(f"property '{item.get('id')}' has unknown {field} '{item[field]}'")
        if item.get("inverse_of") and item["inverse_of"] not in properties:
            errors.append(f"property '{item.get('id')}' has unknown inverse '{item['inverse_of']}'")
        unknown = set(item.get("characteristics", [])) - {"transitive", "symmetric", "functional", "inverse_functional"}
        if unknown:
            errors.append(f"property '{item.get('id')}' has unsupported characteristic(s): {', '.join(sorted(unknown))}")
    for item in data["instances"]:
        if item.get("type") and item["type"] not in concepts:
            errors.append(f"instance '{item.get('id')}' has unknown type '{item['type']}'")
    for index, relation in enumerate(data["relations"]):
        missing = {key for key in ("subject", "predicate", "object") if not relation.get(key)}
        if missing:
            errors.append(f"relations[{index}] is missing {', '.join(sorted(missing))}")
            continue
        if relation["subject"] not in ids:
            errors.append(f"relations[{index}] has unknown subject '{relation['subject']}'")
        if relation["predicate"] not in properties:
            errors.append(f"relations[{index}] has unknown predicate '{relation['predicate']}'")
        if relation["object"] not in ids:
            errors.append(f"relations[{index}] has unknown object '{relation['object']}'")
        assertion = relation.get("assertion", "asserted")
        if assertion not in {"asserted", "candidate"}:
            errors.append(f"relations[{index}] has invalid assertion '{assertion}'")
        if assertion == "candidate":
            if not isinstance(relation.get("confidence"), (int, float)) or not 0 <= relation["confidence"] <= 1:
                errors.append(f"candidate relations[{index}] needs confidence between 0 and 1")
            if not relation.get("rationale") or not relation.get("source_refs"):
                errors.append(f"candidate relations[{index}] needs rationale and source_refs")
    if errors:
        raise ValueError("Invalid graph_data.json:\n- " + "\n- ".join(errors))


def _uri(ex: Namespace, identifier: str) -> URIRef:
    return ex[slug(identifier)]


def build_rdf(data: dict[str, list[dict[str, Any]]], base_uri: str) -> tuple[Graph, Namespace, set[URIRef]]:
    ex = Namespace(base_uri)
    graph = Graph()
    for prefix, ns in (("ex", ex), ("skos", SKOS), ("owl", OWL), ("rdfs", RDFS)):
        graph.bind(prefix, ns)
    for concept in data["concepts"]:
        node, kind = _uri(ex, concept["id"]), concept.get("kind", "class")
        if kind == "concept":
            graph.add((node, RDF.type, SKOS.Concept)); graph.add((node, SKOS.prefLabel, Literal(concept.get("label", concept["id"]))))
            if concept.get("definition"): graph.add((node, SKOS.definition, Literal(concept["definition"])))
            if concept.get("broader"):
                parent = _uri(ex, concept["broader"]); graph.add((node, SKOS.broader, parent)); graph.add((parent, SKOS.narrower, node))
        else:
            graph.add((node, RDF.type, OWL.Class)); graph.add((node, RDFS.label, Literal(concept.get("label", concept["id"]))))
            if concept.get("definition"): graph.add((node, RDFS.comment, Literal(concept["definition"])))
            if concept.get("broader"): graph.add((node, RDFS.subClassOf, _uri(ex, concept["broader"])))
    chars = {"transitive": OWL.TransitiveProperty, "symmetric": OWL.SymmetricProperty, "functional": OWL.FunctionalProperty, "inverse_functional": OWL.InverseFunctionalProperty}
    predicates: set[URIRef] = {SKOS.broader, SKOS.narrower}
    for prop in data["properties"]:
        node = _uri(ex, prop["id"]); predicates.add(node)
        graph.add((node, RDF.type, OWL.DatatypeProperty if prop.get("kind") == "datatype" else OWL.ObjectProperty))
        graph.add((node, RDFS.label, Literal(prop.get("label", prop["id"]))))
        if prop.get("domain"): graph.add((node, RDFS.domain, _uri(ex, prop["domain"])))
        if prop.get("range") and prop.get("kind") != "datatype": graph.add((node, RDFS.range, _uri(ex, prop["range"])))
        for char in prop.get("characteristics", []): graph.add((node, RDF.type, chars[char]))
        if prop.get("inverse_of"):
            inverse = _uri(ex, prop["inverse_of"]); graph.add((node, OWL.inverseOf, inverse)); predicates.add(inverse)
    for instance in data["instances"]:
        node = _uri(ex, instance["id"]); graph.add((node, RDF.type, OWL.NamedIndividual)); graph.add((node, RDFS.label, Literal(instance.get("label", instance["id"]))))
        if instance.get("type"): graph.add((node, RDF.type, _uri(ex, instance["type"])))
        for key, value in (instance.get("attributes") or {}).items(): graph.add((node, _uri(ex, key), Literal(value)))
    for relation in data["relations"]:
        graph.add((_uri(ex, relation["subject"]), _uri(ex, relation["predicate"]), _uri(ex, relation["object"])))
    return graph, ex, predicates


def to_networkx(graph: Graph, base_uri: str, predicates: set[URIRef], relations: list[dict[str, Any]] | None = None) -> nx.MultiDiGraph:
    result = nx.MultiDiGraph()
    labels = {str(subject): str(label) for predicate in (RDFS.label, SKOS.prefLabel) for subject, _, label in graph.triples((None, predicate, None))}
    own = lambda node: isinstance(node, URIRef) and str(node).startswith(base_uri)
    namespace = Namespace(base_uri)
    metadata = {(str(_uri(namespace, relation["subject"])), str(_uri(namespace, relation["predicate"])), str(_uri(namespace, relation["object"]))): relation for relation in relations or []}
    for subject, predicate, obj in graph:
        if predicate not in predicates or not own(subject) or not own(obj): continue
        for node in (subject, obj):
            result.add_node(str(node), label=labels.get(str(node), str(node).rsplit("#", 1)[-1]))
        relation = metadata.get((str(subject), str(predicate), str(obj)), {})
        result.add_edge(str(subject), str(obj), predicate=str(predicate).rsplit("#", 1)[-1], assertion=relation.get("assertion", "asserted"), confidence=str(relation.get("confidence", "")), rationale=relation.get("rationale", ""), source_refs=json.dumps(relation.get("source_refs", [])))
    return result


def insights(graph: nx.MultiDiGraph, top_n: int = 15) -> str:
    lines = ["# Graph Insights (automatic lightweight pass)", ""]
    if not graph.nodes: return "\n".join(lines + ["_Graph is empty — nothing to analyze._", ""])
    simple = nx.Graph(graph.to_undirected())
    lines += [f"- Nodes: {graph.number_of_nodes()}, Edges: {graph.number_of_edges()}", "", "## Most-connected nodes (degree centrality)", ""]
    for node, score in sorted(nx.degree_centrality(simple).items(), key=lambda item: -item[1])[:top_n]: lines.append(f"- **{graph.nodes[node]['label']}** — {score:.3f}")
    lines += ["", "## Bridging nodes (betweenness centrality)", ""]
    bridges = [(node, score) for node, score in nx.betweenness_centrality(simple).items() if score > 0]
    lines += [f"- **{graph.nodes[node]['label']}** — {score:.3f}" for node, score in sorted(bridges, key=lambda item: -item[1])[:top_n]] or ["_No bridging nodes found._"]
    lines += ["", "## Plausible missing relationships (Jaccard neighbor-similarity)", ""]
    predictions = sorted((row for row in nx.jaccard_coefficient(simple) if row[2] > 0), key=lambda row: -row[2])[:top_n]
    lines += [f"- **{graph.nodes[u]['label']}** ↔ **{graph.nodes[v]['label']}** — similarity {score:.3f}" for u, v, score in predictions] or ["_No candidate pairs found — graph may be too sparse or too dense._"]
    candidates = [(u, v, attrs) for u, v, attrs in graph.edges(data=True) if attrs.get("assertion") == "candidate"]
    lines += ["", "## LLM candidate relationships (review before treating as facts)", ""]
    lines += [f"- **{graph.nodes[u]['label']}** → **{graph.nodes[v]['label']}** via `{attrs['predicate']}` — confidence {attrs.get('confidence') or 'n/a'}; {attrs.get('rationale', '')}" for u, v, attrs in candidates] or ["_No candidate relationships._"]
    return "\n".join(lines) + "\n"


def render(graph: nx.MultiDiGraph, target: Path) -> None:
    if not HAVE_PYVIS:
        target.write_text("<html><body><p>Interactive visualization requires the optional pyvis dependency.</p></body></html>", encoding="utf-8"); return
    net = Network(height="800px", width="100%", directed=True, notebook=False, cdn_resources="in_line")
    for node, attrs in graph.nodes(data=True): net.add_node(node, label=attrs["label"], title=node)
    for source, target_node, attrs in graph.edges(data=True):
        candidate = attrs.get("assertion") == "candidate"
        title = attrs["predicate"] + (f"\nCandidate ({attrs.get('confidence', 'n/a')}): {attrs.get('rationale', '')}" if candidate else "")
        net.add_edge(source, target_node, label=attrs["predicate"], title=title, dashes=candidate, color="#d97706" if candidate else "#64748b")
    net.write_html(str(target), notebook=False)


def build(data_path: str | Path, output_dir: str | Path, base_uri: str = "http://example.org/kg#") -> tuple[int, int, int]:
    if not base_uri.endswith(("#", "/")): base_uri += "#"
    data = load_data(data_path); validate_data(data)
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True); shutil.copyfile(data_path, output / "graph_data.json")
    rdf, _, predicates = build_rdf(data, base_uri); rdf.serialize(destination=str(output / "ontology.ttl"), format="turtle")
    inferred, added = rdf, 0
    if HAVE_OWLRL:
        before = len(inferred); owlrl.DeductiveClosure(owlrl.CombinedClosure.RDFS_OWLRL_Semantics).expand(inferred); added = len(inferred) - before
    inferred.serialize(destination=str(output / "ontology_inferred.ttl"), format="turtle")
    graph = to_networkx(inferred, base_uri, predicates, data["relations"]); nx.write_graphml(graph, output / "graph.graphml")
    report = insights(graph) + (f"\n_OWL-RL reasoning added {added} schema-entailed triple(s)._\n" if HAVE_OWLRL else "\n_owlrl is not installed — inference was skipped._\n")
    (output / "insights.md").write_text(report, encoding="utf-8"); render(graph, output / "visualization.html")
    return graph.number_of_nodes(), graph.number_of_edges(), added


def merge(existing_dir: str | Path, new_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    old = load_data(Path(existing_dir) / "graph_data.json"); new = load_data(new_path); validate_data(old)
    merged: dict[str, list[dict[str, Any]]] = {}
    for group in ("concepts", "properties", "instances"):
        entries = {item["id"]: item for item in old[group]}
        entries.update({item["id"]: {**entries.get(item["id"], {}), **item} for item in new[group]})
        merged[group] = list(entries.values())
    seen: set[tuple[str, str, str]] = set(); merged["relations"] = []
    for relation in old["relations"] + new["relations"]:
        key = (relation["subject"], relation["predicate"], relation["object"])
        if key not in seen: seen.add(key); merged["relations"].append(relation)
    # A merge fragment may validly refer to a class/property/entity already held by
    # the prior graph, so validate only after the two datasets are combined.
    validate_data(merged); return merged
