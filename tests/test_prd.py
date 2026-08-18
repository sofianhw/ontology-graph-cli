import unittest
from unittest.mock import MagicMock, patch
import json
import tempfile
from pathlib import Path

import networkx as nx

from ontology_graph_cli.core import build, validate_data
from ontology_graph_cli import prd
from ontology_graph_cli.cli import _ask


INVENTORY = [
    {"id": "p1_l1", "page": 1, "locator": "page 1, line 1", "category": "heading", "text": "PRD: Sample OCR"},
    {"id": "p1_l2", "page": 1, "locator": "page 1, line 2", "category": "heading", "text": "A1 Users provide images"},
    {"id": "p1_l3", "page": 1, "locator": "page 1, line 3", "category": "heading", "text": "C1 One image per session"},
    {"id": "p2_l1", "page": 2, "locator": "page 2, line 1", "category": "heading", "text": "6.1 OCR extraction"},
    {"id": "p2_l2", "page": 2, "locator": "page 2, line 2", "category": "heading", "text": "US-01 - Scan image"},
    {"id": "p2_l3", "page": 2, "locator": "page 2, line 3", "category": "heading", "text": "AC-01 Given an image"},
    {"id": "p3_l1", "page": 3, "locator": "page 3, line 1", "category": "text", "text": "Image Upload Security"},
    {"id": "p3_l2", "page": 3, "locator": "page 3, line 2", "category": "text", "text": "Kimi K2.5"},
]


class PrdExtractionTests(unittest.TestCase):
    def test_template_extraction_has_evidence_and_required_categories(self):
        with patch("ontology_graph_cli.prd._inventory", return_value=(INVENTORY, "\n".join(x["text"] for x in INVENTORY))):
            data, inventory, notes = prd._extract_deterministic("sample.pdf")
        validate_data(data)
        types = {item["type"] for item in data["instances"]}
        self.assertTrue({"feature", "assumption", "constraint", "requirement", "user_story", "acceptance_criterion", "security_item", "ai_model"} <= types)
        self.assertTrue(all(item["attributes"].get("source_refs") for item in data["instances"]))
        self.assertEqual(inventory, INVENTORY)

    def test_candidate_relation_requires_audit_metadata(self):
        data = {"concepts": [{"id": "thing", "label": "Thing", "kind": "class", "broader": None}], "properties": [{"id": "related", "label": "related", "kind": "object", "domain": "thing", "range": "thing"}], "instances": [{"id": "a", "label": "A", "type": "thing", "attributes": {}}, {"id": "b", "label": "B", "type": "thing", "attributes": {}}], "relations": [{"subject": "a", "predicate": "related", "object": "b", "assertion": "candidate", "confidence": 0.8, "rationale": "Shared control", "source_refs": ["p1_l1"]}]}
        validate_data(data)

    def test_candidate_survives_graphml_export(self):
        data = {"concepts": [{"id": "thing", "label": "Thing", "kind": "class", "broader": None}], "properties": [{"id": "related", "label": "related", "kind": "object", "domain": "thing", "range": "thing"}], "instances": [{"id": "a", "label": "A", "type": "thing", "attributes": {}}, {"id": "b", "label": "B", "type": "thing", "attributes": {}}], "relations": [{"subject": "a", "predicate": "related", "object": "b", "assertion": "candidate", "confidence": 0.8, "rationale": "Shared control", "source_refs": ["p1_l1"]}]}
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"; input_path.write_text(json.dumps(data))
            build(input_path, Path(directory) / "out")
            graph = nx.read_graphml(Path(directory) / "out" / "graph.graphml")
        self.assertEqual(next(iter(graph.edges(data=True)))[2]["assertion"], "candidate")

    def test_enrichment_without_credentials_is_safe(self):
        data = {"concepts": [], "properties": [], "instances": [], "relations": []}
        with patch.dict("os.environ", {}, clear=True):
            returned, notes = prd._llm_enrich(data, INVENTORY, "test-model", None)
        self.assertEqual(returned, data)
        self.assertIn("OPENAI_API_KEY", notes[0])

    def test_malformed_llm_response_is_reported_without_breaking_build(self):
        data = {"concepts": [], "properties": [], "instances": [], "relations": []}
        response = MagicMock(); response.read.return_value = b"not-json"; response.__enter__.return_value = response
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}, clear=True), patch("ontology_graph_cli.prd.urllib.request.urlopen", return_value=response):
            returned, notes = prd._llm_enrich(data, INVENTORY, "test-model", "https://example.test/v1")
        self.assertEqual(returned, data)
        self.assertIn("LLM enrichment skipped", notes[0])

    def test_ask_returns_compact_unimplemented_requirement_context(self):
        data = {"concepts": [{"id": "requirement", "label": "Requirement", "kind": "class", "broader": None}, {"id": "user_story", "label": "User Story", "kind": "class", "broader": None}], "properties": [{"id": "implements", "label": "implements", "kind": "object", "domain": "user_story", "range": "requirement"}], "instances": [{"id": "r1", "label": "R1", "type": "requirement", "attributes": {"source_refs": ["p1_l1"]}}, {"id": "r2", "label": "R2", "type": "requirement", "attributes": {"source_refs": ["p1_l2"]}}, {"id": "story", "label": "US-01", "type": "user_story", "attributes": {"source_refs": ["p2_l1"]}}], "relations": [{"subject": "story", "predicate": "implements", "object": "r1", "source_refs": ["p2_l1"]}]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); (output / "graph_data.json").write_text(json.dumps(data))
            result = _ask(str(output), "Which requirements are not implemented by a user story?", 25)
        self.assertEqual(result["answer_type"], "unimplemented_requirements")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["results"][0]["label"], "R2")


if __name__ == "__main__":
    unittest.main()
