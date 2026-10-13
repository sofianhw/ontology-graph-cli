import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from ontology_graph_cli.cli import main
from ontology_graph_cli.template import compare, load_template, report, template_spec


TEMPLATE = """# PRD Title
## [A] General Overview
### Background
[Please give a high level description of the current situation]
### Problem Statement
[What is the problem you're trying to solve?]
## 6.4. Feature Flag (if any)
Please include Feature Flag requirements here.
If you think this sub-section isn't applicable, please provide a justification. Do not leave it blank.
## 6.6. Risk requirements (if any)
Please include Risk requirements here. Do not leave it blank.
## 6.7. Fraud Requirements (if any)
Please include Fraud requirements here. Do not leave it blank.
## Out of scope
[what functions will not be part of this feature]
## Appendix (optional)
Anything else.
## User Stories
| No | User Story | Acceptance Criteria | Priority |
| --- | --- | --- | --- |
| | As a ... | Given ... | P0/P1/P2 |
"""

PRD = """# Instant Transfer
## General Overview
### Background
Users wait two days for transfers today; this feature makes them instant.
### Problem Statement
[What is the problem you're trying to solve?]
## 6.4 Feature Flag
N/A
## 6.6 Risk Requirements
Not applicable because no money leaves the customer's own accounts.
## Out of scope
TBD with legal
## Rollout notes
Phase 1 internal staff only.
## User Stories
| No | User Story | Acceptance Criteria |
| --- | --- | --- |
| US-01 | As a user I want instant transfer | Given balance When send Then arrives |
"""


class TemplateComparisonTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)
        self.template, self.prd = self.work / "template.md", self.work / "prd.md"
        self.template.write_text(TEMPLATE, encoding="utf-8"); self.prd.write_text(PRD, encoding="utf-8")

    def test_spec_rules_are_derived_from_template_wording(self):
        spec = template_spec(self.template)
        rules = {section["id"]: section["rule"] for section in spec["sections"]}
        self.assertEqual(rules["background"], "required")
        self.assertEqual(rules["feature_flag"], "justify")
        self.assertEqual(rules["appendix"], "optional")
        self.assertEqual(rules["general_overview"], "heading")
        self.assertEqual(spec["tables"][0]["columns"], ["No", "User Story", "Acceptance Criteria", "Priority"])
        self.assertTrue(all(section["source_refs"] for section in spec["sections"]))

    def test_compare_grades_each_template_section_with_evidence(self):
        result = compare(template_spec(self.template), self.prd)
        status = {section["id"]: (section["status"], section["result"]) for section in result["sections"]}
        self.assertEqual(status["background"], ("filled", "pass"))
        self.assertEqual(status["problem_statement"], ("placeholder", "fail"))
        self.assertEqual(status["feature_flag"], ("not_applicable_unjustified", "fail"))
        self.assertEqual(status["risk_requirements"], ("not_applicable", "pass"))
        self.assertEqual(status["fraud_requirements"], ("missing", "fail"))
        self.assertEqual(status["out_of_scope"], ("incomplete", "warn"))
        self.assertEqual(status["appendix"], ("missing", "pass"))
        self.assertEqual(result["tables"][0]["status"], "partial")
        self.assertEqual(result["tables"][0]["missing_columns"], ["Priority"])
        self.assertIn("Rollout notes", [section["label"] for section in result["extra_sections"]])
        self.assertTrue(all(section["source_refs"] for section in result["sections"] if section["status"] != "missing"))
        completeness = result["summary"]["completeness"]
        self.assertEqual(completeness["total"], 8)
        self.assertEqual(completeness["missing"]["components"], ["Fraud Requirements (if any)"])
        self.assertEqual(completeness["missing"]["percent"], 12.5)
        self.assertEqual(set(completeness["not_filled"]["components"]), {"Problem Statement", "Feature Flag (if any)"})
        self.assertEqual(set(completeness["partial"]["components"]), {"Out of scope", "Table: No, User Story, Acceptance Criteria, ..."})
        text = report(result)
        self.assertIn("**37.5% complete, 12.5% missing**", text)
        self.assertIn("| Missing | 1 | 12.5% | Fraud Requirements (if any) |", text)
        self.assertIn("add --llm-model", text)

    def test_aliases_in_edited_spec_match_renamed_sections(self):
        spec = template_spec(self.template)
        fraud = next(section for section in spec["sections"] if section["id"] == "fraud_requirements")
        fraud["aliases"] = ["Rollout notes"]
        path = self.work / "spec.json"; path.write_text(json.dumps(spec), encoding="utf-8")
        result = compare(load_template(path), self.prd)
        self.assertEqual(next(s for s in result["sections"] if s["id"] == "fraud_requirements")["status"], "filled")

    def test_invalid_spec_is_rejected(self):
        path = self.work / "spec.json"; path.write_text(json.dumps({"template_spec_version": 1, "sections": [{"id": "x", "label": "X", "rule": "maybe"}]}), encoding="utf-8")
        with self.assertRaises(ValueError): load_template(path)
        path.write_text(json.dumps({"concepts": []}), encoding="utf-8")
        with self.assertRaises(ValueError): load_template(path)

    def test_cli_extracts_spec_and_writes_json_report(self):
        spec, output = self.work / "spec.json", self.work / "report.json"
        with redirect_stdout(StringIO()):
            main(["extract-template", str(self.template), str(spec)])
            main(["compare-template", str(spec), str(self.prd), "--output", str(output)])
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["summary"]["fail"], 3)
        with redirect_stdout(StringIO()) as printed:
            main(["compare-template", str(self.template), str(self.prd)])
        self.assertIn("# PRD template check: prd.md", printed.getvalue())

    def test_quality_flags_catch_filled_but_illegitimate_content(self):
        weak = self.work / "weak.md"
        weak.write_text("""# Weak PRD
### Background
Users wait two days for transfers today and it hurts retention badly.
### Problem Statement
Users wait two days for transfers today and it hurts retention badly.
## 6.6 Risk Requirements
See Figma
## 6.7 Fraud Requirements
xkcd brrrt pfft zzzt qwrtp
## Out of scope
asdf
""", encoding="utf-8")
        result = compare(template_spec(self.template), weak)
        sections = {section["id"]: section for section in result["sections"]}
        self.assertEqual(sections["background"]["quality_flags"], [])
        self.assertEqual(sections["problem_statement"]["quality_flags"], ["duplicate_of:background"])
        self.assertEqual(sections["problem_statement"]["result"], "warn")
        self.assertIn("reference_only", sections["risk_requirements"]["quality_flags"])
        self.assertIn("gibberish", sections["fraud_requirements"]["quality_flags"])
        self.assertEqual(sections["out_of_scope"]["result"], "fail")
        self.assertIn("filler_text", sections["out_of_scope"]["quality_flags"])
        content = result["summary"]["content"]
        self.assertEqual(content["reviewed_by"], "automatic")
        self.assertEqual(set(content["placeholder"]["components"]), {"Fraud Requirements (if any)", "Out of scope"})
        self.assertEqual(set(content["weak"]["components"]), {"Problem Statement", "Risk requirements (if any)"})

    def test_llm_review_marks_weak_sections_and_ignores_unknown_ids(self):
        content = {"reviews": [{"id": "section:background", "verdict": "placeholder", "reason": "Generic boilerplate"}, {"id": "nope", "verdict": "legit"}, {"id": "section:risk_requirements", "verdict": "bogus"}, {"id": "table:table_1", "verdict": "legit", "reason": "Concrete story"}]}
        response = MagicMock(); response.read.return_value = json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode(); response.__enter__.return_value = response
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}, clear=True), patch("ontology_graph_cli.template.urllib.request.urlopen", return_value=response) as urlopen:
            result = compare(template_spec(self.template), self.prd, model="test-model", base_url="https://example.test/v1")
        sent = json.loads(json.loads(urlopen.call_args.args[0].data)["messages"][1]["content"])
        sent_ids = [component["id"] for component in sent["components"]]
        self.assertIn("section:background", sent_ids); self.assertIn("table:table_1", sent_ids)
        self.assertNotIn("section:fraud_requirements", sent_ids); self.assertNotIn("section:problem_statement", sent_ids)
        background = next(s for s in result["sections"] if s["id"] == "background")
        self.assertEqual((background["content"]["verdict"], background["content"]["source"], background["result"]), ("placeholder", "llm", "warn"))
        risk = next(s for s in result["sections"] if s["id"] == "risk_requirements")
        self.assertNotIn("llm_review", risk); self.assertEqual(risk["content"]["source"], "automatic")
        content = result["summary"]["content"]
        self.assertEqual((content["reviewed_by"], content["legit"]["components"], content["placeholder"]["components"]), ("llm:test-model", ["Table: No, User Story, Acceptance Criteria, ..."], ["Background"]))
        self.assertIn("Background**: placeholder - Generic boilerplate", report(result))

    def test_llm_review_without_credentials_keeps_deterministic_result(self):
        with patch.dict("os.environ", {}, clear=True):
            result = compare(template_spec(self.template), self.prd, model="test-model")
        self.assertIn("OPENAI_API_KEY", result["notes"][0])
        self.assertEqual(result["summary"]["fail"], 3)

    def test_agent_reviews_are_merged_without_any_network_call(self):
        first, reviews, output = self.work / "check.json", self.work / "reviews.json", self.work / "report.md"
        with redirect_stdout(StringIO()):
            main(["compare-template", str(self.template), str(self.prd), "--output", str(first)])
        filled = [c for c in json.loads(first.read_text())["sections"] if c.get("review_id")]
        self.assertTrue(all(c.get("excerpt") for c in filled if c["id"] != "general_overview"))
        reviews.write_text(json.dumps({"reviews": [{"id": "section:background", "verdict": "legit", "reason": "Specific current-state context"}, {"id": "section:risk_requirements", "verdict": "weak", "reason": "Justification is thin"}, {"id": "section:background", "verdict": "nonsense"}]}), encoding="utf-8")
        with patch("ontology_graph_cli.template.urllib.request.urlopen") as urlopen, redirect_stdout(StringIO()):
            main(["compare-template", str(self.template), str(self.prd), "--reviews", str(reviews), "--reviewer", "claude", "--output", str(output)])
        urlopen.assert_not_called()
        text = output.read_text(encoding="utf-8")
        self.assertIn("reviewed by LLM review (claude)", text)
        self.assertIn("| Legit content | 1 | 20% | Background |", text)
        self.assertIn("Risk requirements (if any)**: weak - Justification is thin", text)
        with self.assertRaises(SystemExit), redirect_stdout(StringIO()), patch("sys.stderr", StringIO()):
            main(["compare-template", str(self.template), str(self.prd), "--reviews", str(reviews), "--llm-model", "x"])


if __name__ == "__main__":
    unittest.main()
