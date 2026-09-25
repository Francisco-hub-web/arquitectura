import json
import unittest

from tests.helpers import EXAMPLE, FIXTURES, TempDir, copy_example, edit_yaml, ids, lint
from govkit.minischema import validate
from govkit.paths import SCHEMAS_DIR
from govkit.report import jsonr, markdown, sarif


class TestPacks(unittest.TestCase):
    def test_omd_good_passes(self):
        self.assertEqual(lint(FIXTURES / "omd/good", packs=("omd",)).verdict, "PASS")

    def test_omd_bad_detects_isolation_and_keys(self):
        found = ids(lint(FIXTURES / "omd/bad", packs=("omd",)))
        for rid in ("GOV-OMD-001", "GOV-OMD-002", "GOV-OMD-003", "GOV-OMD-004", "GOV-OMD-005", "GOV-OMD-007",
                    "GOV-OMD-008", "GOV-OMD-009", "GOV-OMD-010", "GOV-OMD-011", "GOV-OMD-012", "GOV-OMD-014"):
            self.assertIn(rid, found)

    def test_docs_lint_finds_renumbered_references(self):
        res = lint(FIXTURES / "docs", packs=("docs",))
        msgs = [v.message for v in res.counting if v.rule_id == "GOV-DOC-001"]
        self.assertTrue(any("15-dataops-cicd.md" in m for m in msgs))
        self.assertIn("GOV-DOC-003", ids(res))
        self.assertIn("GOV-DOC-004", ids(res))

    def test_portfolio_cross_repo(self):
        found = ids(lint(FIXTURES / "portfolio", packs=("portfolio",)))
        for rid in ("GOV-PRT-002", "GOV-PRT-003", "GOV-PRT-004", "GOV-PRT-005"):
            self.assertIn(rid, found)


class TestReports(unittest.TestCase):
    def test_json_report_conforms_to_contract(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / "metadata/catalog/data_product.yaml", lambda d: d["spec"].update(tags=["sales", "zzz"]))
            report = jsonr.build(lint(root))
            schema = json.loads((SCHEMAS_DIR / "report.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(validate(report, schema), [])
            v = report["violations"][0]
            self.assertTrue({"rule_id", "severity", "location", "remediation", "fingerprint"} <= set(v))
            self.assertIn("scoring", report)

    def test_sarif_shape(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / "metadata/catalog/data_product.yaml", lambda d: d["spec"]["classification"].pop("level"))
            s = sarif.build(lint(root))
            self.assertEqual(s["version"], "2.1.0")
            result = s["runs"][0]["results"][0]
            self.assertIn(result["level"], ("error", "warning", "note"))
            self.assertGreaterEqual(result["locations"][0]["physicalLocation"]["region"]["startLine"], 1)

    def test_markdown_contains_verdict(self):
        self.assertIn("PASS", markdown.build(lint(EXAMPLE)))
