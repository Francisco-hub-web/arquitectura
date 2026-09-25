import io
import json
import re
import shutil
import unittest

from tests.helpers import EXAMPLE, TempDir, copy_example, edit_yaml, git, ids, lint
from govkit import fixer, mcpserver
from govkit.paths import yaml

DP = "metadata/catalog/data_product.yaml"
CONTRACT = "contracts/output/sales_line_daily.yaml"


def _drop_sla(root):
    p = root / DP
    p.write_text(re.sub(r"\n  sla:\n(    .*\n)+", "\n", p.read_text(encoding="utf-8"), count=1), encoding="utf-8")


class TestYamlEdit(unittest.TestCase):
    SRC = ("# ficha\nmetadata:\n  id: X   # comentario\nspec:\n  a:\n    x: 1\n  b: 2\n  empty:\n"
           "  lst:\n    - name: c1\n    - name: c2\n  flow: {k: v}\n")

    def test_inserts_nested_keys_preserving_comments(self):
        out = fixer.set_in_text("f.yaml", self.SRC, "spec.a.y.z", "<COMPLETAR>")
        self.assertIn("# comentario", out)
        self.assertIn("    y:\n      z: \"<COMPLETAR>\"\n  b: 2", out)
        self.assertEqual(yaml.safe_load(out)["spec"]["b"], 2)

    def test_fills_empty_key_and_list_item(self):
        out = fixer.set_in_text("f.yaml", self.SRC, "spec.empty.z", True)
        self.assertEqual(yaml.safe_load(out)["spec"]["empty"], {"z": True})
        out = fixer.set_in_text("f.yaml", self.SRC, "spec.lst[1].description", "<COMPLETAR>")
        self.assertEqual(yaml.safe_load(out)["spec"]["lst"][1]["description"], "<COMPLETAR>")

    def test_refuses_unsafe_edits(self):
        self.assertIsNone(fixer.set_in_text("f.yaml", self.SRC, "spec.flow.k2", "x"))      # estilo flow
        self.assertIsNone(fixer.set_in_text("f.yaml", self.SRC, "spec.lst[5].x", 1))       # crear ítems de lista
        self.assertIsNone(fixer.set_in_text("f.yaml", self.SRC, "metadata.id", "Y"))       # no sobrescribe
        self.assertIn('id: "Y"   # comentario', fixer.set_in_text("f.yaml", self.SRC, "metadata.id", "Y", overwrite=True))

    def test_json_keeps_indent(self):
        out = fixer.set_in_text("r.json", '{\n    "Roles": [{"RoleName": "x"}]\n}\n', "Roles[0].RoleName", "y",
                                overwrite=True)
        self.assertEqual(json.loads(out)["Roles"][0]["RoleName"], "y")
        self.assertIn('\n    "Roles"', out)

    def test_bump(self):
        self.assertEqual(fixer.bump("1.4.2", "major"), "2.0.0")
        self.assertEqual(fixer.bump("1.4.2", "minor"), "1.5.0")
        self.assertIsNone(fixer.bump("v-x", "major"))


class TestFix(unittest.TestCase):
    def test_brownfield_plan_apply_and_idempotency(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            (root / "CHANGELOG.md").unlink()
            shutil.rmtree(root / "contracts/policies")
            shutil.rmtree(root / "docs/engineering")
            _drop_sla(root)
            comments = (root / DP).read_text(encoding="utf-8").count("#")
            before = lint(root)
            actions = fixer.plan(before)
            kinds = {(a.kind, a.file, a.key) for a in actions}
            self.assertIn(("template", "CHANGELOG.md", None), kinds)
            self.assertIn(("template", "docs/engineering/runbook.md", None), kinds)
            self.assertIn(("mkdir", "contracts/policies", None), kinds)
            self.assertIn(("placeholder", DP, "spec.sla.frequency"), kinds)
            fixer.apply(before.ctx, actions)
            self.assertTrue(all(a.status in ("applied", "manual") for a in actions), [a.to_dict() for a in actions])
            self.assertTrue((root / "contracts/policies/.gitkeep").exists())
            self.assertFalse((root / "docs/engineering/.gitkeep").exists())  # la plantilla ya pobló la carpeta
            self.assertGreaterEqual((root / DP).read_text(encoding="utf-8").count("#"), comments)
            after = lint(root)
            self.assertNotIn("GOV-STR-006", ids(after))
            self.assertLess(after.counts()["MEDIUM"], before.counts()["MEDIUM"])
            self.assertEqual([a for a in fixer.plan(after) if a.kind in fixer.AUTO_KINDS], [])  # idempotente

    def test_never_overwrites_human_content(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / DP, lambda d: d["spec"]["business"].update(problem="TODO"))
            actions = fixer.plan(lint(root))
            hit = [a for a in actions if a.key == "spec.business.problem"]
            self.assertTrue(hit and all(a.kind == "manual" for a in hit))

    def test_contract_bump_on_breaking_change(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            git(root, "init", "-q")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "feat: inicial")
            edit_yaml(root / CONTRACT, lambda d: d["spec"].update(schema=d["spec"]["schema"][:-1]))
            res = lint(root, base="HEAD")
            bump = [a for a in fixer.plan(res) if a.kind == "bump"]
            self.assertEqual(len(bump), 1)
            fixer.apply(res.ctx, bump)
            self.assertEqual(yaml.safe_load((root / CONTRACT).read_text())["metadata"]["version"], bump[0].value)
            self.assertNotIn("GOV-CTR-007", ids(lint(root, base="HEAD")))

    def test_scaffold_brownfield_without_data_product(self):
        with TempDir() as tmp:
            root = copy_example(tmp)
            (root / DP).unlink()
            actions = fixer.plan(lint(root))
            self.assertIn(("template", DP), {(a.kind, a.file) for a in actions})


class TestMcp(unittest.TestCase):
    def rpc(self, *msgs):
        out = io.StringIO()
        mcpserver.serve(io.StringIO("\n".join(m if isinstance(m, str) else json.dumps(m) for m in msgs) + "\n"), out)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def call(self, name, **args):
        r = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})[0]
        return r["result"]

    def test_handshake_and_listing(self):
        init, tools, res, prompts = self.rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": 4, "method": "prompts/list"})
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(init["result"]["serverInfo"]["name"], "govkit")
        names = {t["name"] for t in tools["result"]["tools"]}
        self.assertTrue({"lint", "gate", "fix", "kb_context", "verify_semantic_findings"} <= names)
        self.assertTrue(all(t["inputSchema"]["type"] == "object" for t in tools["result"]["tools"]))
        self.assertIn("govkit://kb/KB_05", {r["uri"] for r in res["result"]["resources"]})
        self.assertIn("revision_gobernanza", {p["name"] for p in prompts["result"]["prompts"]})

    def test_protocol_errors(self):
        bad_json, unknown, bad_tool, missing = self.rpc(
            "{no json", {"jsonrpc": "2.0", "id": 2, "method": "nope"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "zzz"}},
            {"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "nuevo_data_product"}})
        self.assertEqual(bad_json["error"]["code"], -32700)
        self.assertEqual(unknown["error"]["code"], -32601)
        self.assertEqual(bad_tool["error"]["code"], -32602)
        self.assertEqual(missing["error"]["code"], -32602)
        self.assertTrue(self.call("lint", path="/no/existe")["isError"])
        self.assertTrue(self.call("lint", bogus=1)["isError"])

    def test_tools_return_engine_results(self):
        lint_out = json.loads(self.call("lint", path=str(EXAMPLE))["content"][0]["text"])
        self.assertEqual(lint_out["verdict"], "PASS")
        gate = json.loads(self.call("gate", path=str(EXAMPLE), to="listo_para_produccion")["content"][0]["text"])
        self.assertTrue(gate["approved"])
        ctx = json.loads(self.call("kb_context", task="iam_policies", budget=2500)["content"][0]["text"])
        self.assertIn("KB_11", [i["id"] for i in ctx["manifest"]["items"]])
        doc = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "govkit://kb/KB_05"}})[0]
        self.assertIn("KB05.R1", doc["result"]["contents"][0]["text"])

    def test_semantic_findings_are_verified(self):
        plan = mcpserver.t_semantic_review_plan(str(EXAMPLE), artifact=CONTRACT)
        cite = re.findall(r"\*\*(KB\d{2}\.R\d+) \[MUST\]", plan["brief"])[0]
        quote = next(l.strip() for l in (EXAMPLE / CONTRACT).read_text(encoding="utf-8").splitlines() if len(l.strip()) > 30)
        base = {"verdict": "no_cumple", "confidence": 0.8, "artifact": CONTRACT, "rationale": "r"}
        out = mcpserver.t_verify_semantic_findings(CONTRACT, [
            {**base, "kb_rule_id": cite, "evidence_quote": quote},
            {**base, "kb_rule_id": "KB99.R1", "evidence_quote": quote},
            {**base, "kb_rule_id": cite, "evidence_quote": "cita inventada que no aparece en el artefacto revisado"}],
            path=str(EXAMPLE))
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(out["stats"]["invalid_citation"], 1)
        self.assertEqual(out["stats"]["ungrounded"], 1)


class TestHtmlReport(unittest.TestCase):
    def test_self_contained_and_escaped(self):
        from govkit.report import html
        with TempDir() as tmp:
            root = copy_example(tmp)
            edit_yaml(root / DP, lambda d: d["spec"]["business"].update(problem="<script>alert(1)</script>"))
            res = lint(root, stage="listo_para_produccion")
            page = html.build(res)
            self.assertNotIn("<script>alert(1)</script>", page)
            self.assertEqual(page.count('<tr data-sev="'), len(res.counting))
            self.assertNotRegex(page, r'(src|href)="https?://')  # sin recursos externos
            self.assertIn("prefers-color-scheme:dark", page)
        self.assertIn("PASS · Aprobado", html.build(lint(EXAMPLE)))


if __name__ == "__main__":
    unittest.main()
