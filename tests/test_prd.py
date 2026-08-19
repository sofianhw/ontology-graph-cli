import unittest
from unittest.mock import MagicMock, patch
import json
import tempfile
from pathlib import Path

import networkx as nx

from ontology_graph_cli.core import build, validate_data
from ontology_graph_cli import prd
from ontology_graph_cli.cli import _ask, _ask_with_llm


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
    def test_comprehensive_semantic_categories_from_table_rows(self):
        inventory = INVENTORY + [
            {"id": "p4_t1_r1", "page": 4, "locator": "page 4, table 1, row 1", "category": "table_row", "text": "Short-tail Bank Jago Mandiri BNI Bank Neo Commerce BCA Standard-tail Allo Bank Bank Aladin Syariah blu by BCA Digital DANA SeaBank Long-tail Bank ICBC Indonesia Bank MNC Bank Raya KSEI"},
            {"id": "p5_l1", "page": 5, "locator": "page 5, line 1", "category": "heading", "text": "US-17 - Rate limiting"},
            {"id": "p5_l2", "page": 5, "locator": "page 5, line 2", "category": "text", "text": "RR-01 Rate limit applies to US-17"},
            {"id": "p5_l3", "page": 5, "locator": "page 5, line 3", "category": "table_row", "text": "DE [P0] Snowflake audit copy | Data Engineering"},
            {"id": "p5_l4", "page": 5, "locator": "page 5, line 4", "category": "text", "text": "HTTP 400, 422, 429, 500, 503, 504"},
        ]
        with patch("ontology_graph_cli.prd._inventory", return_value=(inventory, "\n".join(x["text"] for x in inventory))):
            data, _, _ = prd._extract_deterministic("sample.pdf")
        validate_data(data)
        types = {item["type"] for item in data["instances"]}
        predicates = {item["predicate"] for item in data["relations"]}
        self.assertTrue({"bank", "account_pattern", "dependency_request", "squad", "error_code", "rate_limiting_requirement"} <= types)
        self.assertTrue({"supportsBank", "requestsFrom", "blockedByDependency", "implements", "acceptanceCriterionFor"} <= predicates)
        self.assertTrue(all(item["attributes"].get("source_refs") for item in data["instances"]))
        self.assertTrue(all(item.get("source_refs") for item in data["relations"]))

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

    def test_llm_entities_require_known_source_references(self):
        data = {"concepts": [{"id": "thing", "label": "Thing", "kind": "class", "broader": None}], "properties": [], "instances": [], "relations": []}
        response = MagicMock(); response.read.return_value = json.dumps({"choices": [{"message": {"content": json.dumps({"entities": [{"id": "bad", "label": "Bad", "type": "bank", "source_refs": ["unknown"]}]})}}]}).encode(); response.__enter__.return_value = response
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}, clear=True), patch("ontology_graph_cli.prd.urllib.request.urlopen", return_value=response):
            returned, _ = prd._llm_enrich(data, INVENTORY, "test", "https://example.test/v1")
        self.assertEqual(returned["instances"], [])

    def test_ask_returns_compact_unimplemented_requirement_context(self):
        data = {"concepts": [{"id": "requirement", "label": "Requirement", "kind": "class", "broader": None}, {"id": "user_story", "label": "User Story", "kind": "class", "broader": None}], "properties": [{"id": "implements", "label": "implements", "kind": "object", "domain": "user_story", "range": "requirement"}], "instances": [{"id": "r1", "label": "R1", "type": "requirement", "attributes": {"source_refs": ["p1_l1"]}}, {"id": "r2", "label": "R2", "type": "requirement", "attributes": {"source_refs": ["p1_l2"]}}, {"id": "story", "label": "US-01", "type": "user_story", "attributes": {"source_refs": ["p2_l1"]}}], "relations": [{"subject": "story", "predicate": "implements", "object": "r1", "source_refs": ["p2_l1"]}]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); (output / "graph_data.json").write_text(json.dumps(data))
            result = _ask(str(output), "Which requirements are not implemented by a user story?", 25)
        self.assertEqual(result["answer_type"], "unimplemented_requirements")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["results"][0]["label"], "R2")

    def test_ask_with_llm_uses_compact_graph_evidence_only(self):
        data = {"concepts": [{"id": "requirement", "label": "Requirement", "kind": "class", "broader": None}, {"id": "user_story", "label": "User Story", "kind": "class", "broader": None}], "properties": [{"id": "implements", "label": "implements", "kind": "object", "domain": "user_story", "range": "requirement"}], "instances": [{"id": "r1", "label": "R1", "type": "requirement", "attributes": {"source_refs": ["p1_l1"]}}, {"id": "r2", "label": "R2", "type": "requirement", "attributes": {"source_refs": ["p1_l2"]}}, {"id": "story", "label": "US-01", "type": "user_story", "attributes": {"source_refs": ["p2_l1"]}}], "relations": [{"subject": "story", "predicate": "implements", "object": "r1", "source_refs": ["p2_l1"]}]}
        response = MagicMock(); response.read.return_value = json.dumps({"choices": [{"message": {"content": "R2 has no asserted implementation link."}}]}).encode(); response.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); (output / "graph_data.json").write_text(json.dumps(data))
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}, clear=True), patch("ontology_graph_cli.cli.urllib.request.urlopen", return_value=response) as urlopen:
                result = _ask_with_llm(str(output), "Which requirements are not implemented by a user story?", 25, "test-model", "https://example.test/v1")
        request_body = json.loads(urlopen.call_args.args[0].data)
        evidence = json.loads(request_body["messages"][1]["content"])["graph_evidence"]
        self.assertEqual(result["answer"], "R2 has no asserted implementation link.")
        self.assertEqual(evidence["answer_type"], "unimplemented_requirements")
        self.assertNotIn("source_inventory", request_body["messages"][1]["content"])

    def test_ask_with_llm_requires_credentials(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            (Path(directory) / "graph_data.json").write_text(json.dumps({"concepts": [], "properties": [], "instances": [], "relations": []}))
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                _ask_with_llm(directory, "What is missing?", 25, "test-model", None)


if __name__ == "__main__":
    unittest.main()
