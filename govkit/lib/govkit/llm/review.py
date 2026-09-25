"""Revisor semántico (consultivo) con LLM local.

Pipeline "determinista primero, semántico después":
  1. motor determinista sobre el repo (lo que es verificable NUNCA se delega al LLM);
  2. superficie semántica = artefactos con texto de negocio/modelado (solo los cambiados si hay --base);
  3. por artefacto: enrutador de KB (modo review) + hallazgos deterministas (para no repetirlos) + preguntas;
  4. LLM con salida JSON restringida por esquema, temperature 0;
  5. verificación determinista de la salida: esquema, citas KB existentes en el contexto y grounding
     de la evidencia contra el artefacto; severidad acotada por la fuerza normativa de la regla citada.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from govkit import __version__
from govkit.kb import store
from govkit.kb.router import route
from govkit.kb.store import estimate_tokens
from govkit.llm.ollama import Ollama, OllamaError
from govkit.minischema import validate
from govkit.paths import SCHEMAS_DIR

SURFACE = [  # (glob, tarea para el enrutador)
    ("metadata/catalog/data_product.yaml", "nuevo_data_product"),
    ("contracts/output/**/*.yaml", "disenar_contrato"),
    ("contracts/input/**/*.yaml", "disenar_contrato"),
    ("modeling/dbt/models/gold/**/*.sql", "modelar_gold_dimensional"),
    ("modeling/dbt/models/silver/**/*.sql", "modelar_silver_odm"),
    ("modeling/dbt/models/**/metrics*.yml", "definir_metrica_semantica"),
    ("quality/expectations/*.yaml", "reglas_calidad"),
    ("observability/alarms/*.yaml", "observabilidad_alertas"),
    ("metadata/catalog/ai/*.yaml", "feature_ml"),
    ("publishing/**/*.sql", "exponer_consumo"),
    ("**/use_cases/*.yaml", "caso_de_uso"),
    ("README.md", "nuevo_data_product"),
]
TAG = re.compile(r"\*\*(KB\d{2}\.[RAHV]\d+) \[(MUST NOT|MUST|SHOULD|MAY|PRÁCTICA)\]")
CAP = {"MUST": "HIGH", "MUST NOT": "HIGH", "SHOULD": "MEDIUM", "MAY": "LOW", "PRÁCTICA": "LOW", None: "MEDIUM"}
ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
OUTPUT_RESERVE, SYSTEM_TOKENS = 1400, 450

SYSTEM = """Eres el Revisor Semántico de Gobernanza de Datos de Cencosud. Evalúas UN artefacto contra el CONTEXTO NORMATIVO.
Reglas estrictas:
1. Usa SOLO el contexto normativo provisto; no inventes lineamientos.
2. Cada hallazgo DEBE citar un ID que exista en el contexto (formato KBnn.Xn) y una cita TEXTUAL del artefacto en
   `evidence_quote` (copiada literalmente, máximo 300 caracteres).
3. NO repitas los hallazgos deterministas listados: ya fueron reportados por el motor.
4. NO evalúes lo listado en las secciones "D · Ya verificado por el motor determinista".
5. Sin evidencia suficiente usa verdict "insuficiente_informacion" y confidence ≤ 0.5.
6. Las reglas [PRÁCTICA] son orientación no normativa: severidad máxima LOW.
7. Reporta solo incumplimientos o dudas relevantes (máximo 8). No listes lo que cumple.
8. Responde SOLO con JSON válido: {"findings": [...], "summary": "..."}. Sin texto adicional."""


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s).lower()) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[\"'`«»“”]", "", s)).strip()


def grounding(quote: str, artifact: str) -> str:
    q, a = _norm(quote), _norm(artifact)
    if len(q) < 6:
        return "no_verificable"
    if q in a:
        return "exacto"
    words = [w for w in re.findall(r"[a-z0-9_]{3,}", q)]
    if words and sum(1 for w in words if w in a) / len(words) >= 0.8:
        return "aproximado"
    return "no_verificable"


def rule_tags(text: str) -> Dict[str, str]:
    return {m.group(1): m.group(2) for m in TAG.finditer(text)}


def surface(ctx, base_changed: Optional[List[str]], limit: int) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for pattern, task in SURFACE:
        for rel in ctx.glob(pattern):
            if base_changed is not None and rel not in base_changed:
                continue
            if rel not in [o[0] for o in out]:
                t = "exponer_consumo" if rel.endswith("data_product.yaml") and ctx.dp_get("spec.role") == "consumo" else task
                out.append((rel, t))
    return out[:limit]


def build_prompt(ctx, res, kb, rel: str, task: str, num_ctx: int) -> Dict[str, Any]:
    text = ctx.text(rel) or ""
    art_budget = int(num_ctx * 0.35)
    art_tokens = estimate_tokens(text)
    truncated = False
    if art_tokens > art_budget:
        text = text[: int(art_budget * 3.6)] + "\n[... truncado por presupuesto de contexto ...]"
        art_tokens, truncated = art_budget, True
    det = [v for v in res.violations if v.location.file == rel and v.counts][:12]
    rules = sorted({v.rule_id for v in det})
    extras = 200 + 30 * len(det)
    pack_budget = max(1200, num_ctx - OUTPUT_RESERVE - SYSTEM_TOKENS - art_tokens - extras)
    pack = route(kb, task=task, paths=[rel], rule_ids=rules, budget=pack_budget, mode="review")
    ids = set(pack.ids)
    questions = [h for h in res.handoff if set(h.get("kb", [])) & ids][:6]
    det_txt = "\n".join(f"- {v.rule_id} (línea {v.location.line}): {v.message}" for v in det) or "- (ninguno)"
    q_txt = "\n".join(f"{i}. [{h['rule_id']}] {h['question']}" for i, h in enumerate(questions, 1)) or "- (usar las preguntas V del contexto)"
    lang = "sql" if rel.endswith(".sql") else "markdown" if rel.endswith(".md") else "yaml"
    user = (f"# CONTEXTO NORMATIVO\n{pack.text()}\n"
            f"# HALLAZGOS DETERMINISTAS YA REPORTADOS (no repetir)\n{det_txt}\n\n"
            f"# PREGUNTAS DE VERIFICACIÓN PRIORITARIAS\n{q_txt}\n\n"
            f"# ARTEFACTO A REVISAR: {rel} (estado del producto: {ctx.stage})\n```{lang}\n{text}\n```\n")
    return {"artifact": rel, "task": task, "pack": pack, "messages": [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}], "artifact_text": ctx.text(rel) or "", "truncated": truncated,
            "prompt_tokens": estimate_tokens(SYSTEM + user), "questions": [h["rule_id"] for h in questions]}


def verify(raw: str, prompt: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Verificación determinista de la salida del LLM (anti-alucinación)."""
    stats = {"schema_errors": 0, "invalid_citation": 0, "ungrounded": 0, "compliant_omitted": 0}
    try:
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1]) if "{" in raw else {}
    except json.JSONDecodeError:
        return {"findings": [], "summary": "", "stats": {**stats, "schema_errors": 1}, "parse_error": True}
    allowed = set(prompt["pack"].rule_ids())
    tags = rule_tags(prompt["pack"].text())
    kept = []
    for f in data.get("findings", []) if isinstance(data, dict) else []:
        if not isinstance(f, dict) or validate({"findings": [f]}, schema):
            stats["schema_errors"] += 1
            continue
        if f["kb_rule_id"] not in allowed:
            stats["invalid_citation"] += 1
            continue
        g = grounding(f.get("evidence_quote", ""), prompt["artifact_text"])
        if g == "no_verificable":
            stats["ungrounded"] += 1
            continue
        if f["verdict"] == "cumple":
            stats["compliant_omitted"] += 1
            continue
        cap = CAP.get(tags.get(f["kb_rule_id"]))
        sev = f.get("severity_suggested") or "MEDIUM"
        if ORDER.get(sev, 2) > ORDER[cap]:
            sev = cap
        if f["confidence"] < 0.5 and f["verdict"] == "no_cumple":
            f["verdict"] = "insuficiente_informacion"
        f.update({"severity_suggested": sev, "grounding": g, "normative_strength": tags.get(f["kb_rule_id"], "heurística")})
        kept.append(f)
    return {"findings": kept, "summary": data.get("summary", "") if isinstance(data, dict) else "", "stats": stats}


def review(args) -> int:
    from govkit.engine import Engine, load_catalog
    from govkit.repo import RepoContext

    catalog = load_catalog()
    ctx = RepoContext(args.path, catalog, stage_override=args.stage, base_ref=args.base)
    res = Engine(ctx, catalog).run()
    kb = store.load()
    changed = ctx.changed_files() if args.base else None
    targets = surface(ctx, changed, args.max_artifacts)
    schema = json.loads((SCHEMAS_DIR / "semantic_review.schema.json").read_text(encoding="utf-8"))
    client = Ollama(model=args.model)
    report: Dict[str, Any] = {
        "schema_version": "1.0", "tool": {"name": "govkit", "version": __version__}, "model": client.model,
        "advisory": True, "target": {"repo": ctx.repo_name, "stage": ctx.stage},
        "deterministic": {"verdict": res.verdict, "counts": res.counts()}, "reviews": []}
    if not targets:
        print("govkit review: no hay artefactos en la superficie semántica (¿--base sin cambios?)", file=sys.stderr)
    ok, detail = (True, "dry-run") if args.dry_run else client.health()
    if not ok:
        print(f"⚠️  {detail}\n   El motor determinista ya corrió ({res.verdict}). Para la revisión semántica instala Ollama "
              f"y ejecuta `ollama pull {client.model}`; o usa --dry-run para ver los prompts.", file=sys.stderr)
        return 0
    for rel, task in targets:
        prompt = build_prompt(ctx, res, kb, rel, task, args.budget)
        entry: Dict[str, Any] = {"artifact": rel, "task": task, "kb_loaded": prompt["pack"].ids,
                                 "context_tokens": prompt["pack"].used, "prompt_tokens": prompt["prompt_tokens"],
                                 "truncated": prompt["truncated"], "questions": prompt["questions"]}
        if args.dry_run:
            entry["prompt"] = prompt["messages"][1]["content"] if args.format == "json" else None
            report["reviews"].append(entry)
            continue
        t0 = time.time()
        try:
            raw = client.chat(prompt["messages"], schema=schema, num_ctx=args.budget)
            checked = verify(raw, prompt, schema)
        except OllamaError as exc:
            checked = {"findings": [], "summary": "", "error": str(exc)}
        entry.update(checked)
        entry["duration_ms"] = int((time.time() - t0) * 1000)
        report["reviews"].append(entry)
    _render(report, args)
    return 0


def _render(report: Dict[str, Any], args) -> None:
    if args.format == "json":
        text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    else:
        lines = [f"Revisión semántica (consultiva) · {report['target']['repo']} · modelo {report['model']} · "
                 f"motor determinista: {report['deterministic']['verdict']}"]
        for r in report["reviews"]:
            lines.append(f"\n{r['artifact']}  (tarea: {r['task']} · KB: {', '.join(r['kb_loaded'])} · "
                         f"~{r['prompt_tokens']} tok de prompt{' · truncado' if r['truncated'] else ''})")
            if "error" in r:
                lines.append(f"  ⚠️  {r['error']}")
            for f in r.get("findings", []):
                lines.append(f"  [{f['severity_suggested']:<6}] {f['kb_rule_id']} · {f['verdict']} · conf {f['confidence']:.2f}"
                             f" · grounding {f['grounding']}\n           «{f['evidence_quote'][:110]}»\n           {f['rationale']}"
                             + (f"\n           ↳ {f['remediation']}" if f.get("remediation") else ""))
            st = r.get("stats")
            if st:
                lines.append(f"  descartados por verificación: citas inválidas {st['invalid_citation']} · sin grounding "
                             f"{st['ungrounded']} · esquema {st['schema_errors']}")
        lines.append("\nLos hallazgos semánticos son consultivos: no bloquean el pipeline; requieren validación humana.")
        text = "\n".join(lines) + "\n"
    if getattr(args, "output", None):
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def ask(args) -> int:
    kb = store.load()
    pack = route(kb, query=args.question, budget=args.budget, mode="qa")
    if args.no_llm:
        print(pack.explain() + "\n\n" + pack.text())
        return 0
    client = Ollama(model=args.model)
    ok, detail = client.health()
    if not ok:
        print(f"⚠️  {detail}\nContexto recuperado (úsalo con cualquier LLM):\n", file=sys.stderr)
        print(pack.text())
        return 0
    system = ("Eres el asistente de Gobierno de Datos de Cencosud. Responde en español, de forma concisa, usando SOLO el "
              "contexto. Cita los IDs entre corchetes, por ejemplo [KB05.R4]. Si la respuesta no está en el contexto, "
              "responde: 'No está cubierto por el framework actual' y sugiere consultar a Arquitectura de Datos Regional.")
    answer = client.chat([{"role": "system", "content": system},
                          {"role": "user", "content": pack.text() + "\n# PREGUNTA\n" + args.question}],
                         num_ctx=args.budget + 2048)
    cited = set(re.findall(r"KB\d{2}\.[RAHV]\d+", answer))
    invalid = cited - set(pack.rule_ids())
    print(answer)
    print(f"\n— Fuentes: {', '.join(pack.ids)}" + (f" · ⚠️ citas no verificables: {sorted(invalid)}" if invalid else ""))
    return 0
