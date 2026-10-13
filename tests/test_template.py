import json
import tempfile
import unittest
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
        self.assertIn("| fail | Fraud Requirements (if any) |", report(result))

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
        self.assertIn("# Template comparison: prd.md", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
