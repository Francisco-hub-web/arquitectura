import io
import json
import os
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tests.helpers import TempDir  # noqa: F401  (inicializa sys.path)
from govkit import claims, cli, mcpserver, notes

FAKE = """#!{py}
import sys, json
if sys.argv[1:3] == ["mcp", "get"]:
    sys.exit(0)
open({log!r}, "a").write(json.dumps(sys.argv[1:]) + "\\n")
result = ("Veredicto: EXISTE CON MATICES — es una práctica recomendada, no una regla obligatoria.\\n"
          "Qué dice el framework:\\n- KB03.H3: «Owners nominales (personas), no buzones genéricos»\\n- KB99.R9 inventado")
for ev in [{{"type": "assistant", "message": {{"content": [{{"type": "tool_use", "name": "mcp__govkit__kb_context",
                                                            "input": {{}}}}]}}}},
           {{"type": "result", "subtype": "success", "is_error": False, "result": result}}]:
    print(json.dumps(ev), flush=True)
"""


def top(claim, n):
    return [c["id"] for c in claims.candidates(claim)[:n]]


class TestClaimRetrieval(unittest.TestCase):
    def test_finds_the_criterion_behind_what_was_heard(self):
        self.assertIn("KB03.H3", top("el business owner puede ser un buzón genérico del equipo", 3))
        self.assertTrue({"GOV-QLT-006", "KB08.R7"} & set(top("todo data product debe tener 3 dimensiones de calidad", 3)))
        self.assertTrue({"KB06.R5", "GOV-ARC-001"} & set(top("los dashboards pueden leer directo de bronze", 3)))
        self.assertIn("GOV-CTR-007", top("un cambio que elimina una columna del contrato requiere versión mayor", 6))
        self.assertIn("GOV-IAM-004", top("se pueden usar wildcards de escritura en buckets compartidos", 3))

    def test_every_candidate_has_a_verifiable_source(self):
        for c in claims.candidates("clasificación de datos personales y enmascaramiento"):
            self.assertTrue(c["where"], c)
            self.assertTrue(c["text"], c)


class TestVerifyCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__import__("tempfile").mkdtemp(prefix="govkit-claims-"))
        self.log = self.tmp / "log.json"
        fake = self.tmp / "claude"
        fake.write_text(FAKE.format(py=sys.executable, log=str(self.log)))
        fake.chmod(0o755)
        self.env = {k: os.environ.get(k) for k in ("GOVKIT_CLAUDE", "GOVKIT_NOTES_DIR")}
        os.environ["GOVKIT_CLAUDE"] = str(fake)
        os.environ["GOVKIT_NOTES_DIR"] = str(self.tmp / "notas")

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = cli.main(argv)
        return rc, out.getvalue()

    def test_verdict_with_sources_and_invented_id_flagged(self):
        rc, out = self.run_cli(["verificar", "el business owner puede ser un buzón genérico del equipo"])
        self.assertEqual(rc, 0)
        self.assertIn("Veredicto: EXISTE CON MATICES", out)
        self.assertIn("Fuentes para verificar", out)
        self.assertIn("KB03.H3", out)
        self.assertIn("NO existe en el framework", out)      # KB99.R9 citado pero inexistente
        self.assertIn("KB99.R9", out)
        argv = json.loads(self.log.read_text().splitlines()[0])
        self.assertIn("CANDIDATOS", argv[1])                   # la evidencia determinista va en el prompt
        tools = argv[argv.index("--allowedTools") + 1]
        self.assertNotIn("lint", tools)                        # una pregunta libre no evalúa el repo
        saved = notes.all_notes()
        self.assertEqual(len(saved), 1)
        self.assertIn("Verificación", str(saved[0]["titulo"]))

    def test_without_ai_lists_closest_criteria(self):
        rc, out = self.run_cli(["verificar", "--sin-ia", "--no-guardar", "los dashboards pueden leer directo de bronze"])
        self.assertEqual(rc, 0)
        self.assertIn("Criterios más cercanos", out)
        self.assertIn("KB06.R5", out)
        self.assertFalse(self.log.exists())                    # no llamó a Claude
        self.assertEqual(notes.all_notes(), [])

    def test_mcp_criteria_search(self):
        res = mcpserver.t_criteria_search("owner buzón genérico", k=5)
        self.assertIn("KB03.H3", [c["id"] for c in res["candidatos"]])
        self.assertIn("criteria_search", {t["name"] for t in mcpserver.NOTE_TOOLS})


if __name__ == "__main__":
    unittest.main()
