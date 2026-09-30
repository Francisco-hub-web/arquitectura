"""Capa de memoria arquitectónica (govkit arch) y estándar platform-core (GOV-PCX-*).

Fixtures 100 % sintéticos (sin contenido corporativo): repos git temporales con un `origin` bare local.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "lib"))


def sh(cwd, *args):
    subprocess.run(list(args), cwd=cwd, check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                            GIT_COMMITTER_EMAIL="t@t"))


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


STANDARD_V1 = """
profile_version: "1.2.0"
forbidden_root_keys: [x-cencosud, dataQuality, sla]
forbidden_extension_blocks_from_profile: {profile_from: "1.2.0", blocks: [processing]}
required_extension_property: xCencosud
lineage_rules:
  profile_from: "1.2.0"
  bidirectional_consistency: true
  bronze_landing: {upstream_contract_ref: forbidden, downstream_path_prefix: contracts/bronze/raw/}
  bronze_raw: {upstream_contract_ref: required, upstream_path_prefix: contracts/bronze/landing/, downstream_path_prefix: contracts/silver/odm/}
  silver_odm: {upstream_contract_ref: required, upstream_path_prefix: contracts/bronze/raw/, downstream_path_prefix: contracts/gold/}
  gold_dim: {upstream_contract_ref: required, upstream_path_prefix: contracts/silver/odm/}
  gold_fact: {upstream_contract_ref: required, upstream_path_prefixes: [contracts/silver/odm/, contracts/gold/dim/]}
"""
MANIFEST = 'profile_manifest_version: "{v}"\ncurrent_profile_version: "{v}"\napproved_odcs_api_versions: ["v3.1.0"]\n'


class ArchBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="govkit-arch-"))
        self.env_backup = dict(os.environ)
        os.environ["GOVKIT_ARCH_HOME"] = str(self.tmp / "home")
        os.environ["GOVKIT_NOTES_DIR"] = str(self.tmp / "notas")
        for sid in ("GOVERNANCE", "PLATFORM_CORE", "ARCHIMATE", "METADATA_CATALOG"):
            os.environ[f"GOVKIT_ARCH_PATH_{sid}"] = str(self.tmp / f"nope-{sid.lower()}")
        self._clear()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env_backup)
        self._clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clear(self):
        from govkit.arch import index as I
        I._cache_clear()  # noqa: SLF001

    def make_origin(self, name="pc"):
        """origin bare + clon de trabajo (para publicar cambios) + clon local del usuario (solo lectura)."""
        origin = self.tmp / f"{name}.git"
        sh(self.tmp, "git", "init", "-q", "--bare", str(origin))
        sh(origin, "git", "symbolic-ref", "HEAD", "refs/heads/main")
        work = self.tmp / f"{name}-work"
        sh(self.tmp, "git", "clone", "-q", str(origin), str(work))
        sh(work, "git", "checkout", "-q", "-b", "main")
        return origin, work

    def publish(self, work, msg="c"):
        sh(work, "git", "add", "-A")
        sh(work, "git", "commit", "-q", "-m", msg)
        sh(work, "git", "push", "-q", "origin", "HEAD:main")


class TestGitSafety(ArchBase):
    def test_destructive_git_commands_are_refused(self):
        from govkit.arch import gitio
        for args in (("pull",), ("checkout", "main"), ("reset", "--hard"), ("stash",), ("clean", "-fd"),
                     ("push",), ("merge", "x"), ("remote", "add", "x", "y"), ("config", "user.name", "x")):
            with self.assertRaises(gitio.GitError, msg=args):
                gitio.git(self.tmp, *args)

    def test_sync_reads_origin_without_touching_working_tree(self):
        from govkit.arch import changes, gitio
        origin, work = self.make_origin()
        write(work, "framework/data-contracts/specs/schemas/profile-manifest.yaml", MANIFEST.format(v="1.2.0"))
        write(work, "framework/data-contracts/docs/gold-contract-patterns.md",
              "# Gold\n\n## 2. Dim vs fact\n| Hecho | gold/fact/ | `fct_<process>.yaml` |\n")
        self.publish(work, "init")
        local = self.tmp / "local-pc"
        sh(self.tmp, "git", "clone", "-q", str(origin), str(local))
        os.environ["GOVKIT_ARCH_PATH_PLATFORM_CORE"] = str(local)
        (local / "README.local").write_text("cambio local sin commitear", encoding="utf-8")
        head0 = gitio.resolve(local, "HEAD")

        r1 = changes.sync(["platform-core"])[0]
        self.assertTrue(r1.get("first_ingest"))
        self.assertEqual(r1["fetch"], "ok")

        write(work, "framework/data-contracts/specs/schemas/profile-manifest.yaml", MANIFEST.format(v="2.0.0"))
        write(work, "framework/data-contracts/docs/gold-contract-patterns.md",
              "# Gold\n\n## 2. Dim vs fact\n| Hecho | gold/fact/ | `fact_<process>.yaml` |\n\n## 3. Nuevo\nSe debe declarar grain.\n")
        self.publish(work, "perfil 2.0")
        sh(work, "git", "checkout", "-q", "-b", "proposal/x")
        write(work, "framework/data-contracts/specs/schemas/nuevo.yaml", "a: 1\n")
        sh(work, "git", "add", "-A")
        sh(work, "git", "commit", "-q", "-m", "prop")
        sh(work, "git", "push", "-q", "origin", "proposal/x")

        r2 = changes.sync(["platform-core"])[0]
        self.assertFalse(r2.get("first_ingest"))
        impacts = {a["path"]: a["impact"] for a in r2["alerts"]}
        self.assertEqual(impacts.get("framework/data-contracts/specs/schemas/profile-manifest.yaml"), "CRITICAL")
        self.assertIn("F-PC-04", {f["id"] for f in r2["fact_changes"]})
        self.assertIn("F-PC-06", {f["id"] for f in r2["fact_changes"]})
        self.assertTrue(any(a["change_type"] == ["CONFLICTING"] for a in r2["alerts"]))
        self.assertEqual([s["branch"] for s in r2["signals"]], ["proposal/x"])
        self.assertEqual(r2["signals"][0]["type"], "UNKNOWN")
        self.assertTrue(Path(r2["changelog"]).read_text(encoding="utf-8").startswith("ARCHITECTURAL KNOWLEDGE UPDATE"))
        self.assertIn("ARCHITECTURAL CHANGE DETECTED", Path(r2["changelog"]).read_text(encoding="utf-8"))
        # el working tree del usuario no cambió (ni HEAD ni sus archivos locales)
        self.assertEqual(gitio.resolve(local, "HEAD"), head0)
        self.assertTrue((local / "README.local").exists())
        self.assertIn("1.2.0", (local / "framework/data-contracts/specs/schemas/profile-manifest.yaml").read_text())
        r3 = changes.sync(["platform-core"])[0]
        self.assertTrue(r3.get("up_to_date"))
        self.assertEqual(r3["signals"], [])


class TestSnapshotAndIndex(ArchBase):
    def _snapshot(self, files, commit="a" * 40):
        inv = "\n".join(f"- {p} | bytes={len(c.encode())} | sha256={hashlib.sha256(c.encode()).hexdigest()}"
                        for p, c in files.items())
        blocks = []
        for i, (p, c) in enumerate(files.items(), 1):
            blocks.append("#" * 100 + f"\nFILE {i}/{len(files)}\nRELATIVE PATH: {p}\nABSOLUTE PATH: /x/{p}\n"
                          f"SIZE BYTES: {len(c.encode())}\nENCODING: utf-8\nSHA256: {hashlib.sha256(c.encode()).hexdigest()}\n"
                          + "#" * 100 + f"\n\n{c}\n\nEND FILE: {p}\n")
        return (f"{'=' * 100}\nSNAPSHOT COMPLETO DE REPOSITORIO: global-data-governance\n{'=' * 100}\n\n"
                f"REPOSITORIO: global-data-governance\nFECHA DE SNAPSHOT: 2026-09-30T10:00:00-03:00\n\n## GIT METADATA\n\n"
                f"### Remote origin\nhttps://example.invalid/global-data-governance.git\n\n### Branch\nmain\n\n"
                f"### HEAD\n{commit}\n\n### Last commit\n{commit}\nautor\n2026-09-29 17:00:00 -0300\nmsg\n\n"
                f"### Working tree status\n## main...origin/main\n\n## INVENTARIO DE ARCHIVOS\n\n{inv}\n\n"
                f"{'=' * 100}\nCONTENIDO DE LOS ARCHIVOS\n{'=' * 100}\n\n" + "\n".join(blocks))

    def test_snapshot_roundtrip_masking_and_incremental_diff(self):
        from govkit.arch import changes, readers
        fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        files = {
            "docs/data-framework/01-data-principles.md": "# Principios\n\nEstado: Validado\n\nTodo producto debe tener owner.\n",
            "docs/data-framework/19-scoring-model.md": "# Scoring\n\nEstado: Draft para revisión\n\nSe recomienda medir.\n",
            "scripts/deploy.sh": f"export KEY={fake_key}\n# cuenta 123456789012\n",
            "policies/.gitkeep": "",
        }
        snap = self.tmp / "gov.txt"
        snap.write_text(self._snapshot(files), encoding="utf-8")
        r = readers.SnapshotReader(snap)
        for rel, content in files.items():
            self.assertEqual(r.read(rel), content.encode(), rel)
        rep = changes.ingest_snapshot_with_diff(snap)
        from govkit.arch import index as I
        idx = I.load("governance")
        self.assertTrue(rep["first_ingest"])
        self.assertEqual(idx["files"]["docs/data-framework/01-data-principles.md"]["status"], "REQUIRED")
        self.assertEqual(idx["files"]["docs/data-framework/19-scoring-model.md"]["status"], "UNKNOWN")
        self.assertTrue(idx["files"]["docs/data-framework/19-scoring-model.md"]["draft"])
        self.assertIn({"file": "scripts/deploy.sh", "type": "aws_access_key"}, idx["secrets"])
        raw = (I.index_dir() / next(p.name for p in I.index_dir().glob("governance@*.json"))).read_text()
        self.assertNotIn(fake_key, raw)
        self.assertNotIn("123456789012", raw)
        # snapshot posterior: cambia un doc normativo y se completa un placeholder
        files2 = dict(files)
        files2["docs/data-framework/01-data-principles.md"] += "\n## Nuevo\nEl contrato es obligatorio.\n"
        files2["policies/.gitkeep"] = ""
        files2["policies/nueva.md"] = "# Política\n\nNo se permite X.\n"
        snap2 = self.tmp / "gov2.txt"
        snap2.write_text(self._snapshot(files2, commit="b" * 40), encoding="utf-8")
        rep2 = changes.ingest_snapshot_with_diff(snap2)
        types = {c["path"]: c["type"] for c in rep2["changes"]}
        self.assertEqual(types["docs/data-framework/01-data-principles.md"], "UPDATED")
        self.assertEqual(types["policies/nueva.md"], "NEW")
        doc_alert = [a for a in rep2["alerts"] if a["path"].endswith("01-data-principles.md")]
        self.assertTrue(doc_alert and doc_alert[0]["impact"] == "HIGH")
        self.assertIn("GOV-", " ".join(rep2["stale"]["rules"]))  # reglas cuya fuente cambió


class TestContextFactsConflicts(ArchBase):
    def _pc_dir(self):
        root = self.tmp / "pcdir"
        write(root, "framework/data-contracts/specs/schemas/profile-manifest.yaml", MANIFEST.format(v="1.2.0"))
        write(root, "framework/data-contracts/specs/schemas/data-contracts-architecture-standard.yaml", STANDARD_V1)
        write(root, "framework/data-contracts/docs/gold-contract-patterns.md",
              "# Gold\n\n## 2. Dim vs fact\n`fct_<process>.yaml`\n")
        write(root, "framework/data-contracts/specs/schemas/README.md",
              "# Schemas\n\nArtefactos canónicos. Ver `framework/data-contracts/docs/gold-contract-patterns.md`.\n")
        return root

    def test_context_corp_and_dp_paths(self):
        from govkit.arch import context, ingest, registry
        ingest.ingest_dir(registry.get("platform-core"), self._pc_dir())
        ctx = context.context("global-data-platform-core/framework/data-contracts/specs/schemas")
        self.assertEqual(ctx["mode"], "corp")
        self.assertEqual(ctx["impact_if_changes"][0], "CRITICAL")
        self.assertTrue(any(s["path"].endswith("gold-contract-patterns.md") for s in ctx["see"]))
        text = context.render(ctx)
        self.assertIn("Para analizar correctamente esta ruta revisa también", text)
        dp = self.tmp / "ventas-dp-cl"
        write(dp, "contracts/gold/fact/fct_x.yaml", "apiVersion: v3.1.0\nkind: DataContract\n")
        ctx2 = context.context(str(dp / "contracts/gold/fact/fct_x.yaml"))
        self.assertEqual(ctx2["mode"], "dp")
        self.assertEqual(ctx2["standard"], "platform-core")
        self.assertIn("C-13", {c["id"] for c in ctx2["conflicts"]})
        self.assertTrue(any("gold-contract-patterns" in s["path"] for s in ctx2["see"]))

    def test_facts_and_conflict_states(self):
        from govkit.arch import facts, ingest, registry
        ingest.ingest_dir(registry.get("platform-core"), self._pc_dir())
        res = facts.evaluate_all()
        self.assertTrue(res["F-PC-04"]["holds"])
        self.assertTrue(res["F-PC-06"]["holds"])
        self.assertIsNone(res["F-GOV-01"]["holds"])  # governance no ingerido → NO DETERMINADO
        states = {c["id"]: c["state"] for c in facts.conflict_states()}
        self.assertEqual(states["C-13"], "VIGENTE")
        self.assertEqual(states["C-05"], "NO DETERMINADO")

    def test_traceability_of_rules_and_kb(self):
        from govkit.arch import tracecheck
        res = tracecheck.check()  # sin índice: contra la lista de documentos del registro
        self.assertEqual(res["rules_unknown_doc"], [])
        self.assertEqual(res["kb_unknown_doc"], [])
        self.assertTrue(res["rules_external"])  # lineamientos: procedencia desconocida (C-14)


class TestArchimate(ArchBase):
    def test_dp_inventory_and_compare(self):
        from govkit.arch import archimate, ingest, registry
        root = self.tmp / "am"
        ns = 'xmlns:archimate="http://www.archimatetool.com/archimate"'
        write(root, "model/diagrams/folder.xml", f'<archimate:Folder {ns} name="Views" id="f0"/>')
        write(root, "model/diagrams/a/folder.xml", f'<archimate:Folder {ns} name="Data Products" id="f1"/>')
        write(root, "model/diagrams/a/b/folder.xml", f'<archimate:Folder {ns} name="Chile" id="f2"/>')
        write(root, "model/diagrams/a/b/c/folder.xml", f'<archimate:Folder {ns} name="ventas-master-dp-cl" id="f3"/>')
        write(root, "model/diagrams/a/b/c/d/folder.xml", f'<archimate:Folder {ns} name="LLD" id="f4"/>')
        write(root, "model/other/Grouping_g1.xml", f'<archimate:Grouping {ns} name="Silver ODM" id="g1"/>')
        write(root, "model/other/Grouping_g2.xml", f'<archimate:Grouping {ns} name="GOLD Fact" id="g2"/>')
        write(root, "model/diagrams/a/b/c/d/ArchimateDiagramModel_v1.xml", textwrap.dedent(f'''
            <archimate:ArchimateDiagramModel {ns} xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" name="LLD" id="v1">
              <children xsi:type="archimate:DiagramModelArchimateObject" id="c1">
                <archimateElement xsi:type="archimate:Grouping" href="Grouping_g1.xml#g1"/></children>
              <children xsi:type="archimate:DiagramModelArchimateObject" id="c2">
                <archimateElement xsi:type="archimate:Grouping" href="Grouping_g2.xml#g2"/></children>
            </archimate:ArchimateDiagramModel>'''))
        idx = ingest.ingest_dir(registry.get("archimate"), root)
        inv = archimate.dp_inventory(idx)
        self.assertEqual([d["name"] for d in inv], ["ventas-master-dp-cl"])
        self.assertEqual(inv[0]["levels"], {"LLD": 1})
        repo = self.tmp / "ventas-master-dp-cl"
        write(repo, "contracts/silver/odm/x.yaml", "a: 1\n")
        res = archimate.compare(idx, repo)
        states = {r["layer"]: r["state"] for r in res["rows"]}
        self.assertEqual(states["silver/odm"], "coincide")
        self.assertIn("modelado, no implementado", states["gold/fact"])


def _pc_contract(cid, layer, zone, obj, up=None, down=None, extra=""):
    lines = [f"apiVersion: v3.1.0", "kind: DataContract", f'id: "{cid}"', f"name: {obj}", 'version: "1.0.0"',
             "status: draft", "domain: ventas", "description:", "  purpose: Contrato sintético de prueba para govkit.",
             "schema:", f"  - name: {obj}", "    customProperties:", "      - {property: compatibility, value: backward}",
             "    quality:", "      - {type: library, metric: nullValues, mustBe: 0}",
             "    properties:", "      - name: venta_id", "        logicalType: string",
             "        description: Identificador de la venta", "customProperties:", "  - property: xCencosud", "    value:",
             "      data_product_repo: ventas-master-dp-cl", f"      layer: {layer}", f"      medallion_zone: {zone}",
             "      asset_type: table", f"      medallion_object: {obj}", "      pii_classification: none"]
    if layer == "bronze" and zone == "landing":
        lines += ["      ingestion_origin: object_store_s3", "      physical: {kind: object_store, format: parquet}"]
    elif layer == "bronze":
        lines += ["      physical: {kind: object_store, format: parquet}"]
    else:
        lines += ["      catalog: {glue_database: db, iceberg_table: db.t, table_type: iceberg}"]
    if up:
        lines += ["      upstream_contract_ref:"] + [f"        - {u}" for u in up]
    if down:
        lines += ["      downstream_contract_ref:"] + [f"        - {d}" for d in down]
    return "\n".join(lines) + "\n" + extra


class TestPlatformCoreStandard(ArchBase):
    def make_dp(self):
        dp = self.tmp / "ventas-master-dp-cl"
        write(dp, "contracts/_schema/profile-manifest.yaml", MANIFEST.format(v="1.2.0"))
        write(dp, "contracts/_schema/data-contracts-architecture-standard.yaml", STANDARD_V1)
        write(dp, "metadata/data_product.yaml", textwrap.dedent('''
            data_product_id: ventas-master-dp-cl
            display_name: Ventas Master
            domain: ventas
            udn: cl
            stage: "1"
            architecture_pattern: medallion
            lifecycle_status: draft
            owner_data: steward@example.com
            owner_tech: "@org/ventas"
            classification: interno
            catalog_export: {target_path: specs/data-products/cl/ventas-master-dp-cl.yaml}
            odcs: {api_version_default: v3.1.0, profile_version: "1.2.0", profile_schema: cencosud-odcs-minimal.schema.json}
            data_contracts:
              - {contract_path: contracts/bronze/landing/src.yaml, contract_id: 00000000-0000-4000-8000-000000000001}
              - {contract_path: contracts/bronze/raw/src_raw.yaml, contract_id: 00000000-0000-4000-8000-000000000002}
              - {contract_path: contracts/silver/odm/venta.yaml, contract_id: 00000000-0000-4000-8000-000000000003}
              - {contract_path: contracts/gold/fact/fct_ventas.yaml, contract_id: 00000000-0000-4000-8000-000000000004}
            '''))
        write(dp, "contracts/bronze/landing/src.yaml", _pc_contract(
            "00000000-0000-4000-8000-000000000001", "bronze", "landing", "src", down=["contracts/bronze/raw/src_raw.yaml"]))
        write(dp, "contracts/bronze/raw/src_raw.yaml", _pc_contract(
            "00000000-0000-4000-8000-000000000002", "bronze", "raw", "src_raw", up=["contracts/bronze/landing/src.yaml"],
            down=["contracts/silver/odm/venta.yaml"]))
        write(dp, "contracts/silver/odm/venta.yaml", _pc_contract(
            "00000000-0000-4000-8000-000000000003", "silver", "odm", "venta", up=["contracts/bronze/raw/src_raw.yaml"],
            down=["contracts/gold/fact/fct_ventas.yaml"]))
        write(dp, "contracts/gold/fact/fct_ventas.yaml", _pc_contract(
            "00000000-0000-4000-8000-000000000004", "gold", "fact", "fct_ventas", up=["contracts/silver/odm/venta.yaml"]))
        write(dp, "metadata/catalog-export/ventas-master-dp-cl.yaml", "x: 1\n")
        write(dp, ".github/workflows/validate-contracts.yaml", "name: v\n")
        return dp

    def lint(self, dp, rules="GOV-PCX-*"):
        from govkit.engine import Engine, load_catalog
        from govkit.repo import RepoContext
        cat = load_catalog()
        ctx = RepoContext(dp, cat)
        return ctx, Engine(ctx, cat, only=[rules]).run()

    def test_standard_detection(self):
        from govkit import standards
        dp = self.make_dp()
        self.assertEqual(standards.detect(dp)[0], "platform-core")
        self.assertEqual(standards.detect(self.tmp)[0], "lineamientos")
        self.assertEqual(standards.detect(dp, "lineamientos")[0], "lineamientos")

    def test_valid_repo_has_no_contract_findings(self):
        dp = self.make_dp()
        ctx, res = self.lint(dp)
        ids = sorted({v.rule_id for v in res.violations if v.rule_id != "GOV-PCX-020"})
        self.assertEqual(ids, [], [f"{v.rule_id} {v.location.file} {v.message}" for v in res.violations])
        self.assertEqual(ctx.stage, "en_desarrollo")  # lifecycle_status draft → en_desarrollo

    def test_violations_are_detected(self):
        dp = self.make_dp()
        write(dp, "contracts/input/legacy.yaml", _pc_contract("00000000-0000-4000-8000-000000000009", "bronze", "raw", "l"))
        shutil.move(str(dp / "contracts/gold/fact/fct_ventas.yaml"), str(dp / "contracts/gold/fact/fact_ventas.yaml"))
        p = dp / "contracts/silver/odm/venta.yaml"
        p.write_text(p.read_text().replace("      catalog:", "      processing: {job: x}\n      catalog:")
                     .replace("contracts/gold/fact/fct_ventas.yaml", "contracts/gold/fact/fact_ventas.yaml"), encoding="utf-8")
        g = dp / "contracts/gold/fact/fact_ventas.yaml"
        g.write_text(g.read_text().replace("  - property: xCencosud", "  - property: xCencosud").replace(
            "      upstream_contract_ref:\n        - contracts/silver/odm/venta.yaml\n", ""), encoding="utf-8")
        _, res = self.lint(dp)
        ids = {v.rule_id for v in res.violations}
        for rid in ("GOV-PCX-006", "GOV-PCX-009", "GOV-PCX-010", "GOV-PCX-013", "GOV-PCX-014", "GOV-PCX-004"):
            self.assertIn(rid, ids)
        self.assertEqual(res.verdict, "FAIL")  # contracts/input es BLOCKER

    def test_lineamiento_rules_do_not_apply_in_platform_core(self):
        dp = self.make_dp()
        _, res = self.lint(dp, rules="GOV-CTR-001")
        self.assertEqual(res.outcomes["GOV-CTR-001"].status, "not_applicable")
        self.assertIn("platform-core", res.outcomes["GOV-CTR-001"].detail)

    def test_fix_creates_platform_core_ficha(self):
        from govkit import fixer
        dp = self.make_dp()
        (dp / "metadata/data_product.yaml").unlink()
        ctx, res = self.lint(dp)
        acts = fixer.plan(res)
        self.assertIn("pc_ficha", {a.kind for a in acts})
        fixer.apply(ctx, [a for a in acts if a.kind == "pc_ficha"])
        text = (dp / "metadata/data_product.yaml").read_text(encoding="utf-8")
        self.assertIn('profile_version: "1.2.0"', text)
        self.assertIn("<COMPLETAR", text)


class TestArchCli(ArchBase):
    def test_help_status_and_mcp_tools(self):
        from govkit import cli, mcpserver
        self.assertEqual(cli.main(["arch", "estado", "--json"]), 0)
        with self.assertRaises(SystemExit) as cm:
            from govkit.arch import cli as acli
            acli.main(["-h"])
        self.assertEqual(cm.exception.code, 0)
        names = {t["name"] for t in mcpserver.ARCH_TOOLS}
        self.assertTrue({"arch_context", "arch_sync", "arch_conflicts", "arch_adrs", "arch_dp"} <= names)
        self.assertTrue(all(n in mcpserver.TOOLS for n in names))


if __name__ == "__main__":
    unittest.main()
