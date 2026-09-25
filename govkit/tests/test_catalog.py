import fnmatch
import unittest

from tests.helpers import CATALOG
from govkit.plugins import PLUGINS, load_all

ALLOWED_DOCS = ("01-", "02-", "02.1-", "02.2-", "06-", "08-", "09-", "10-", "11-", "12-", "13-", "14-", "15-", "18-", "19-",
                "lineamientos/")


class TestCatalogIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_all()
        cls.rules = CATALOG["_rules"]
        cls.ids = {r.id for r in cls.rules}

    def test_unique_ids_and_format(self):
        self.assertEqual(len(self.ids), len(self.rules))
        for r in self.rules:
            self.assertRegex(r.id, r"^GOV-[A-Z]{3}-\d{3}$")

    def test_every_automated_rule_has_a_check(self):
        for r in self.rules:
            if r.nature in ("D", "H"):
                self.assertTrue(r.check, r.id)
            if r.nature == "S":
                self.assertTrue(r.semantic_question, r.id)

    def test_plugins_exist(self):
        for r in self.rules:
            if r.check and r.check.get("kind") in ("plugin", "post"):
                self.assertIn(r.check["name"], PLUGINS, r.id)

    def test_composites_reference_existing_rules(self):
        for r in self.rules:
            if r.check and r.check.get("kind") == "composite":
                for bucket, refs in r.check["requires"].items():
                    for ref in refs:
                        self.assertIn(ref, self.ids, f"{r.id}.{bucket}")

    def test_traceability_to_source_documents(self):
        for r in self.rules:
            self.assertTrue(r.source.get("doc", "").startswith(ALLOWED_DOCS), r.id)
            self.assertTrue(r.kb, r.id)
            self.assertTrue(r.remediation, r.id)

    def test_stage_values(self):
        for r in self.rules:
            for g, v in r.stages.items():
                self.assertIn(g, ("ideacion", "diseno", "desarrollo", "gate", "operacion", "salida"), r.id)
                self.assertIn(r.severity_for(g), ("OFF", "INFO", "LOW", "MEDIUM", "HIGH", "BLOCKER"), r.id)

    def test_deterministic_share(self):
        automated = sum(1 for r in self.rules if r.nature in ("D", "H"))
        self.assertGreater(automated / len(self.rules), 0.8)
