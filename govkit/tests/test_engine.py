import json
import unittest
from pathlib import Path

from tests.helpers import (CATALOG, EXAMPLE, TempDir, copy_example, edit_json, edit_yaml, git, ids, lint)
from govkit.scaffold import scaffold

DP = "metadata/catalog/data_product.yaml"
POLICY = "infra/iam/policy-data.json"


class TestReferenceAndScaffold(unittest.TestCase):
    def test_reference_example_passes_gate(self):
        res = lint(EXAMPLE)
        self.assertEqual(res.verdict, "PASS", [v.to_dict() for v in res.counting])
        evaluated = sum(1 for o in res.outcomes.values() if o.status in ("pass", "fail"))
        self.assertGreater(evaluated, 150)

    def test_scaffold_has_no_blockers_in_definition(self):
        with TempDir() as tmp:
            root = scaffold("sales", "transactions", "anl", "cl", tmp, owner="ana.perez@cencosud.com")
            res = lint(root)
            self.assertEqual(res.counts()["BLOCKER"], 0, [v.to_dict() for v in res.counting if v.severity == "BLOCKER"])
            self.assertIn("GOV-BIZ-001", ids(res))  # capacidad aún sin completar

    def test_scaffold_is_blocked_at_production_gate(self):
        with TempDir() as tmp:
            root = scaffold("sales", "transactions", "anl", "cl", tmp)
            res = lint(root, stage="listo_para_produccion")
            self.assertEqual(res.verdict, "FAIL")
            self.assertIn("GOV-DPD-028", ids(res))  # Definition of Done compuesto


class TestMutations(unittest.TestCase):
    def mutate_and_lint(self, fn, stage=None):
        with TempDir() as tmp:
            root = copy_example(tmp)
            fn(root)
            return lint(root, stage=stage)

    def test_missing_classification_is_blocker(self):
        res = self.mutate_and_lint(lambda r: edit_yaml(r / DP, lambda d: d["spec"]["classification"].pop("level")))
        v = next(v for v in res.counting if v.rule_id == "GOV-SEC-001")
        self.assertEqual(v.severity, "BLOCKER")
        self.assertEqual(v.location.file, DP)
        self.assertGreater(v.location.line, 1)

    def test_pii_requires_sensitive_and_masking(self):
        res = self.mutate_and_lint(lambda r: edit_yaml(r / DP, lambda d: d["spec"]["classification"].update(pii=True)))
        self.assertIn("GOV-SEC-003", ids(res))
        self.assertIn("GOV-DPD-009", ids(res))  # security contact

    def test_hardcoded_secret_with_exact_line(self):
        def fn(r):
            p = r / "src/bronze/glue/job_brz_prd_sal_pos_transactions_cdc.py"
            p.write_text(p.read_text() + '\nAWS_KEY = "AKIAIOSFODNN7EXAMPLE"\nboto3.client("s3", aws_secret_access_key="abc123secret")\n')
        res = self.mutate_and_lint(fn)
        hits = [v for v in res.counting if v.rule_id == "GOV-SEC-006"]
        self.assertGreaterEqual(len(hits), 2)
        self.assertTrue(all(v.severity == "BLOCKER" and v.location.line > 20 for v in hits))

    def test_iam_write_on_star_and_kms_wildcard(self):
        def fn(r):
            def m(d):
                st = d["PolicyDocument"]["Statement"]
                st.append({"Sid": "S3BadWrite", "Effect": "Allow", "Action": ["s3:PutObject"], "Resource": "*"})
                for s in st:
                    if s["Sid"] == "KMSEncryption":
                        s["Resource"] = ["arn:aws:kms:us-east-1:*:key/*"]
            edit_json(r / POLICY, m)
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-IAM-004", ids(res))
        self.assertIn("GOV-IAM-005", ids(res))

    def test_iam_mixed_read_write_and_size(self):
        def fn(r):
            def m(d):
                st = d["PolicyDocument"]["Statement"]
                st.append({"Sid": "S3Mixed", "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"],
                           "Resource": ["arn:aws:s3:::cencosud-cl-dlk-gld-sal-x/*"]})
                st.append({"Sid": "Padding", "Effect": "Allow", "Action": ["athena:GetQueryResults"],
                           "Resource": [f"arn:aws:athena:us-east-1:*:workgroup/wg{i:04d}" for i in range(200)]})
            edit_json(r / POLICY, m)
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-IAM-003", ids(res))
        self.assertIn("GOV-IAM-002", ids(res))

    def test_shared_bucket_path_wildcard(self):
        def fn(r):
            edit_json(r / POLICY, lambda d: d["PolicyDocument"]["Statement"].append(
                {"Sid": "S3SharedWrite", "Effect": "Allow", "Action": ["s3:PutObject"],
                 "Resource": ["arn:aws:s3:::cencosud-cl-shared-landing/sales/raw/*"]}))
        res = self.mutate_and_lint(fn)
        v = next(v for v in res.counting if v.rule_id == "GOV-IAM-004")
        self.assertEqual(v.severity, "HIGH")

    def test_sql_layer_rules(self):
        def fn(r):
            (r / "modeling/dbt/models/gold/fact_sales_line.sql").write_text(
                "select * from {{ source('bronze_pos', 'pos_transactions') }}\n")
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-ARC-001", ids(res))
        self.assertIn("GOV-ARC-002", ids(res))

    def test_destructive_overwrite_on_critical_data(self):
        def fn(r):
            p = r / "src/bronze/glue/job_brz_prd_sal_pos_transactions_cdc.py"
            p.write_text(p.read_text().replace('df.writeTo(ARGS["target_table"]).append()',
                                               'df.write.mode("overwrite").saveAsTable(ARGS["target_table"])'))
            edit_yaml(r / DP, lambda d: d["spec"].update(criticality="critica"))
        res = self.mutate_and_lint(fn)
        v = next(v for v in res.counting if v.rule_id == "GOV-ARC-004")
        self.assertEqual(v.severity, "BLOCKER")

    def test_time_travel_format(self):
        res = self.mutate_and_lint(lambda r: edit_yaml(r / DP, lambda d: d["spec"]["modeling"].update(table_format="parquet")))
        self.assertIn("GOV-ARC-005", ids(res))

    def test_quality_rules(self):
        def fn(r):
            def m(d):
                d["spec"]["rules"] = [x for x in d["spec"]["rules"] if x["dimension"] in ("completitud", "unicidad")]
                d["spec"]["rules"][0]["action"] = "alertar_owner"
            edit_yaml(r / "quality/expectations/sales_transactions.yaml", m)
            edit_yaml(r / DP, lambda d: d["spec"].update(quality_slos=[]))
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-QLT-006", ids(res))
        self.assertIn("GOV-QLT-009", ids(res))

    def test_corporate_and_duplicate_metrics(self):
        def fn(r):
            def m(d):
                base = dict(d["metrics"][0])
                d["metrics"].append({**base, "name": "venta_neta", "label": "Venta neta local"})
                d["metrics"].append({**base, "type_params": {"measure": "otra_medida"}})
            edit_yaml(r / "modeling/dbt/models/semantic/metrics.yml", m)
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-SML-003", ids(res))
        self.assertIn("GOV-SML-002", ids(res))

    def test_naming_and_tech_domain(self):
        def fn(r):
            (r / "src/bronze/glue/job_brz_prd_sal_pos_transactions_cdc.py").rename(r / "src/bronze/glue/ingesta.py")
            edit_yaml(r / DP, lambda d: d["spec"].update(subdomain="big_data"))
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-NAM-003", ids(res))
        self.assertIn("GOV-ARC-006", ids(res))

    def test_pii_in_sample_files(self):
        def fn(r):
            (r / "tests/fixtures").mkdir(parents=True, exist_ok=True)
            (r / "tests/fixtures/clientes.csv").write_text("rut,email\n12.345.678-5,juan.perez@gmail.com\n")
        res = self.mutate_and_lint(fn)
        self.assertIn("GOV-SEC-008", ids(res))

    def test_yaml_syntax_error_reports_line(self):
        def fn(r):
            (r / "observability/alarms/extra.yaml").write_text("kind: Monitors\nspec:\n  monitors: [\n")
        res = self.mutate_and_lint(fn)
        v = next(v for v in res.counting if v.rule_id == "GOV-STR-013")
        self.assertEqual(v.severity, "BLOCKER")
        self.assertGreaterEqual(v.location.line, 3)

    def test_consumption_pattern_matrix(self):
        def fn(r):
            edit_yaml(r / DP, lambda d: d["spec"].update(role="consumo", consumption_pattern="extraccion_distribucion_masiva",
                                                         consumption={"platform": "powerbi"}))
        res = self.mutate_and_lint(fn)
        v = next(v for v in res.counting if v.rule_id == "GOV-CNS-003" and "prohibida" in v.message)
        self.assertEqual(v.severity, "BLOCKER")
        self.assertIn("GOV-CNS-004", ids(res))  # inputs no maestros


class TestLifecycleAndPolicy(unittest.TestCase):
    def test_stage_escalation(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / DP, lambda d: d["spec"]["sla"].pop("availability"))
            early = next(v for v in lint(root, stage="en_definicion").violations if v.rule_id == "GOV-DPD-013")
            gate = next(v for v in lint(root, stage="listo_para_produccion").violations if v.rule_id == "GOV-DPD-013")
            self.assertEqual(early.severity, "LOW")
            self.assertEqual(gate.severity, "BLOCKER")

    def test_waiver_suppresses_and_expired_waiver_is_reported(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            (root / "notebooks").mkdir()
            (root / "notebooks/x.py").write_text("print(1)\n")
            self.assertIn("GOV-STR-005", ids(lint(root)))
            edit_yaml(root / ".govkit.yaml", lambda d: d.update(waivers=[
                {"rule": "GOV-STR-005", "reason": "exploración", "owner": "a@cencosud.com",
                 "adr": "docs/adr/0002-arts-odm-extension.md", "expires": "2026-12-31"}]))
            res = lint(root)
            self.assertNotIn("GOV-STR-005", ids(res))
            self.assertIn("GOV-STR-005", ids(res, counting=False))
            edit_yaml(root / ".govkit.yaml", lambda d: d["waivers"][0].update(expires="2026-01-01"))
            res = lint(root)
            self.assertIn("GOV-STR-005", ids(res))
            self.assertIn("GOV-OPS-009", ids(res))

    def test_baseline_suppresses_known_findings(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / DP, lambda d: d["spec"].update(tags=["sales", "no_existe"]))
            res = lint(root)
            fps = {v.fingerprint for v in res.counting}
            self.assertTrue(fps)
            self.assertEqual(lint(root, baseline=fps).counting, [])

    def test_git_breaking_change_and_lifecycle_jump(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            git(root, "init", "-q")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "feat: inicial")
            edit_yaml(root / "contracts/output/sales_line_daily.yaml",
                      lambda d: d["spec"].update(schema=d["spec"]["schema"][:-1]))
            edit_yaml(root / DP, lambda d: d["spec"]["lifecycle"].update(state="en_retiro"))
            res = lint(root, base="HEAD")
            self.assertIn("GOV-CTR-007", ids(res))
            self.assertIn("GOV-CTR-008", ids(res))
            self.assertIn("GOV-LCY-002", ids(res))

    def test_monorepo_subfolder_diff_without_branch_attribution(self):
        import shutil
        with TempDir() as tmp:
            mono = Path(tmp) / "lakehousev2"
            root = mono / "products" / "sales-transactions-anl-dp-cl"
            shutil.copytree(EXAMPLE, root)
            git(mono, "init", "-q")
            git(mono, "checkout", "-q", "-b", "rama-no-convencional")
            git(mono, "add", "-A")
            git(mono, "commit", "-qm", "commit no convencional")
            edit_yaml(root / "contracts/output/sales_line_daily.yaml",
                      lambda d: d["spec"].update(schema=d["spec"]["schema"][:-1]))
            res = lint(root, base="HEAD")
            self.assertIn("GOV-CTR-007", ids(res))          # el diff funciona dentro del monorepo
            self.assertNotIn("GOV-NAM-007", ids(res))       # la rama del monorepo no se atribuye al producto
            self.assertEqual(res.ctx.changed_files(), ["contracts/output/sales_line_daily.yaml"])

    def test_repo_level_stricter_severity_only(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / DP, lambda d: d["spec"].update(tags=["sales", "no_existe"]))
            edit_yaml(root / ".govkit.yaml", lambda d: d.update(rules={"severity": {"GOV-MET-008": "HIGH"}}))
            self.assertEqual(next(v for v in lint(root).counting if v.rule_id == "GOV-MET-008").severity, "HIGH")
            edit_yaml(root / ".govkit.yaml", lambda d: d.update(rules={"severity": {"GOV-MET-008": "LOW"}}))
            self.assertEqual(next(v for v in lint(root).counting if v.rule_id == "GOV-MET-008").severity, "MEDIUM")


class TestScoring(unittest.TestCase):
    def test_prescore_reference_and_classification(self):
        from govkit import scoring
        sc = scoring.compute(lint(EXAMPLE))
        self.assertGreaterEqual(sc["global"], 4.5)
        with TempDir() as tmp:
            root = scaffold("sales", "transactions", "anl", "cl", tmp)
            low = scoring.compute(lint(root))
            self.assertLess(low["global"], 3.5)
            self.assertEqual(low["reference_state"], "productivo")

    def test_declared_score_without_evidence_is_flagged(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            (root / "observability/alarms/monitors.yaml").unlink()
            edit_yaml(root / "metadata/catalog/scorecard.yaml",
                      lambda d: d["spec"]["pillars"]["observability_operations"].update(score=5))
            self.assertIn("GOV-SCO-002", ids(lint(root)))


if __name__ == "__main__":
    unittest.main()
