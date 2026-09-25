import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

from tests.helpers import EXAMPLE, TempDir
from govkit.llm import review as rv
from govkit.llm.ollama import Ollama


def fake_answer(body):
    user = body["messages"][-1]["content"]
    findings = [
        {"kb_rule_id": "KB05.R2", "verdict": "no_cumple", "severity_suggested": "HIGH", "confidence": 0.9,
         "artifact": "x", "evidence_quote": "granularity: línea de ticket por día de negocio",
         "rationale": "La granularidad no precisa zona horaria del día de negocio."},
        {"kb_rule_id": "KB99.R1", "verdict": "no_cumple", "severity_suggested": "HIGH", "confidence": 0.9,
         "artifact": "x", "evidence_quote": "granularity", "rationale": "cita inventada"},
        {"kb_rule_id": "KB05.R5", "verdict": "no_cumple", "severity_suggested": "HIGH", "confidence": 0.9,
         "artifact": "x", "evidence_quote": "texto que no existe en absoluto en el artefacto revisado",
         "rationale": "sin grounding"},
        {"kb_rule_id": "KB05.H3", "verdict": "no_cumple", "severity_suggested": "HIGH", "confidence": 0.9,
         "artifact": "x", "evidence_quote": "granularity", "rationale": "heurística no proyectada en modo review"},
        {"kb_rule_id": "KB07.R2", "verdict": "no_cumple", "severity_suggested": "HIGH", "confidence": 0.3,
         "artifact": "x", "evidence_quote": "business_keys: [ticket_id, line_number]", "rationale": "SHOULD"},
    ]
    if "**KB07.R2" not in user:
        findings.pop()
    return "<think>razonando...</think>" + json.dumps({"findings": findings, "summary": "ok"})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send({"version": "0.9.0"} if self.path == "/api/version" else {"models": [{"name": "qwen2.5:7b-instruct"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._send({"message": {"role": "assistant", "content": fake_answer(body)}})


class TestSemanticReviewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.host = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_client_strips_thinking(self):
        out = Ollama(host=self.host).chat([{"role": "user", "content": "hola <<< KB_07 >>>"}])
        self.assertFalse(out.startswith("<think>"))

    def test_review_verifies_citations_and_grounding(self):
        import os
        os.environ["OLLAMA_HOST"] = self.host
        try:
            with TempDir() as tmp:
                out = f"{tmp}/review.json"
                args = SimpleNamespace(path=str(EXAMPLE), model="qwen2.5:7b-instruct", task=None, base=None, budget=8192,
                                       max_artifacts=2, dry_run=False, format="json", output=out, stage=None)
                self.assertEqual(rv.review(args), 0)
                with open(out, encoding="utf-8") as fh:
                    report = json.load(fh)
        finally:
            os.environ.pop("OLLAMA_HOST", None)
        self.assertTrue(report["advisory"])
        contract = next(r for r in report["reviews"] if r["artifact"].startswith("contracts/output"))
        kept = {f["kb_rule_id"] for f in contract["findings"]}
        self.assertIn("KB05.R2", kept)
        self.assertNotIn("KB99.R1", kept)     # cita inexistente → descartada
        self.assertNotIn("KB05.R5", kept)     # evidencia sin grounding → descartada
        # KB99.R1 no existe y KB05.H3 existe pero NO fue proyectada al modelo (modo review = R,A,V,D)
        self.assertEqual(contract["stats"]["invalid_citation"], 2)
        self.assertEqual(contract["stats"]["ungrounded"], 1)
        should = [f for f in contract["findings"] if f["kb_rule_id"] == "KB07.R2"]
        if should:  # [SHOULD] → severidad acotada a MEDIUM; confianza < 0.5 → insuficiente_informacion
            self.assertEqual(should[0]["severity_suggested"], "MEDIUM")
            self.assertEqual(should[0]["verdict"], "insuficiente_informacion")

    def test_grounding_levels(self):
        art = "granularity: línea de ticket por día de negocio\nbusiness_keys: [ticket_id, line_number]"
        self.assertEqual(rv.grounding("línea de ticket por día", art), "exacto")
        self.assertEqual(rv.grounding("business keys ticket_id line_number", art), "aproximado")
        self.assertEqual(rv.grounding("monto en dólares", art), "no_verificable")
