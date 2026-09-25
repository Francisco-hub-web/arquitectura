"""Contract test: el schema publicado debe cumplir contracts/output/sales_line_daily.yaml (se ejecuta pre-deploy)."""
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


class TestOutputContract(unittest.TestCase):
    def test_contract_fields_match_gold_contract(self):
        out = yaml.safe_load((ROOT / "contracts/output/sales_line_daily.yaml").read_text())
        gold = yaml.safe_load((ROOT / "contracts/gold/fact/fact_sales_line.yaml").read_text())
        self.assertEqual([f["name"] for f in out["spec"]["schema"]], [f["name"] for f in gold["spec"]["schema"]])
