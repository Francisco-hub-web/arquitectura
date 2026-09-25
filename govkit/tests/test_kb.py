import unittest

from tests.helpers import CATALOG
from govkit.kb import store
from govkit.kb.router import route


class TestKnowledgeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = store.load()

    def test_kb_is_valid_and_cross_referenced_with_catalog(self):
        self.assertEqual(self.kb.validate(CATALOG), [])

    def test_every_rule_kb_reference_exists(self):
        for r in CATALOG["_rules"]:
            for k in r.kb:
                self.assertIn(k, self.kb.chunks, r.id)

    def test_chunks_fit_small_context(self):
        for c in self.kb.chunks.values():
            self.assertLess(c.tokens, 1300, c.id)

    def test_kernel_always_first_and_budget_respected(self):
        for budget in (1500, 3000, 6000):
            pack = route(self.kb, task="exponer_consumo", budget=budget, mode="review")
            self.assertEqual(pack.ids[0], "KB_00")
            self.assertLessEqual(pack.used, budget)

    def test_dependencies_loaded_before_children(self):
        pack = route(self.kb, task="definir_metrica_semantica", budget=8000)
        self.assertLess(pack.ids.index("KB_09"), pack.ids.index("KB_12"))

    def test_rule_signal_routes_to_owner_chunk(self):
        pack = route(self.kb, rule_ids=["GOV-IAM-004"], budget=4000)
        self.assertIn("KB_11", pack.ids)

    def test_query_retrieval(self):
        pack = route(self.kb, query="openmetadata assume role test connection access denied", budget=3000)
        self.assertIn("KB_21", pack.ids)

    def test_projection_reduces_tokens(self):
        full = route(self.kb, task="reglas_calidad", budget=20000, mode="qa").used
        review = route(self.kb, task="reglas_calidad", budget=20000, mode="review").used
        self.assertLess(review, full)

    def test_deterministic_routing(self):
        a = route(self.kb, task="nuevo_data_product", query="pii masking", budget=5000).manifest()
        b = route(self.kb, task="nuevo_data_product", query="pii masking", budget=5000).manifest()
        self.assertEqual(a, b)
