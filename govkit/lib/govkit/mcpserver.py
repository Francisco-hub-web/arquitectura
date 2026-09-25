"""`govkit mcp`: servidor MCP (Model Context Protocol, stdio) sin dependencias.

Expone el sistema híbrido a agentes de código (Claude Code, Cursor, etc.) manteniendo la frontera de confianza:
  · Capa 1 (verdad): lint / gate / score / fix → motor determinista, hallazgos con línea y remediación.
  · Capa 2 (consultiva): kb_context / semantic_review_plan → contexto normativo mínimo enrutado;
    verify_semantic_findings → el MISMO verificador determinista del revisor Ollama (citas + grounding + tope de
    severidad) aplicado a los hallazgos que proponga el agente. Ningún juicio semántico se reporta sin verificar.
Recursos: mini-contextos KB (govkit://kb/KB_nn), matriz de reglas y SAD. Prompts: flujos guiados.

Transporte: JSON-RPC 2.0, un mensaje por línea en stdin/stdout (stdout reservado al protocolo; logs a stderr).
Registro en Claude Code:  claude mcp add --scope user govkit -- govkit mcp
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional

from govkit import __version__

PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
SEV_ORDER = ["INFO", "LOW", "MEDIUM", "HIGH", "BLOCKER"]
PACKS = ["dp", "omd", "docs", "portfolio"]

INSTRUCTIONS = """govkit = gobierno de datos Cencosud (Data & AI Discipline Framework) como herramienta.
Flujo recomendado sobre un repo de Data Product:
1. `lint` → hallazgos deterministas (fuente de verdad: regla GOV-*, archivo:línea, remediación). No los discutas: corrígelos.
2. `fix` (apply=false primero) → remediaciones mecánicas seguras; luego completa a mano las marcas <COMPLETAR>
   con información real que te dé el usuario (nunca inventes owners, SLAs ni valores de negocio).
3. Para diseño/semántica: `kb_context` (task o query) entrega el contexto normativo mínimo; cita IDs KBnn.Xn.
4. Revisión semántica: `semantic_review_plan` → evalúa cada artefacto → `verify_semantic_findings` ANTES de reportar.
   Solo reporta los hallazgos que el verificador conserve; son consultivos (no bloquean).
5. `gate` con el estado destino antes de promover. `explain_rule` para la trazabilidad de cualquier regla."""


# ============================================================== utilidades
def _ctx(path: str, stage: Optional[str] = None, base: Optional[str] = None):
    from govkit.engine import load_catalog
    from govkit.repo import RepoContext

    catalog = load_catalog()
    if not os.path.isdir(path):
        raise ValueError(f"`{path}` no es un directorio (cwd del servidor: {os.getcwd()})")
    return RepoContext(path, catalog, stage_override=stage, base_ref=base), catalog


def _run(path=".", packs=("dp",), stage=None, base=None, rules=None, changed_only=False, fail_on="BLOCKER"):
    from govkit.engine import Engine

    ctx, catalog = _ctx(path, stage, base)
    only = [r.strip() for r in rules.split(",")] if isinstance(rules, str) and rules else rules or None
    return Engine(ctx, catalog, packs=list(packs), only=only, fail_on=fail_on, changed_only=changed_only).run()


def _finding(v) -> Dict[str, Any]:
    d = {"rule_id": v.rule_id, "severity": v.severity, "message": v.message, "file": v.location.file,
         "line": v.location.line}
    if v.location.json_path:
        d["json_path"] = v.location.json_path
    if v.fix:
        d["autofix"] = v.fix
    return d


def _findings(res, min_severity="LOW", limit=60):
    """Hallazgos compactos + ficha de cada regla una sola vez (el contexto del agente es un recurso escaso)."""
    floor = SEV_ORDER.index(min_severity) if min_severity in SEV_ORDER else 1
    rows = [v for v in res.counting if SEV_ORDER.index(v.severity) >= floor]
    rows.sort(key=lambda v: (-SEV_ORDER.index(v.severity), v.location.file, v.location.line))
    rows = rows[:limit] if limit else rows
    rules = {v.rule_id: {"title": v.title, "remediation": v.remediation, "kb": v.kb,
                         "source": f"{v.source.get('doc', '')} {v.source.get('section', '')}".strip()} for v in rows}
    total = sum(1 for v in res.counting if SEV_ORDER.index(v.severity) >= floor)
    return [_finding(v) for v in rows], rules, max(0, total - len(rows))


# ============================================================== herramientas
def t_lint(path=".", packs=None, stage=None, base=None, rules=None, min_severity="LOW", limit=60, changed_only=False):
    res = _run(path, packs or ["dp"], stage, base, rules, changed_only)
    rows, rule_info, omitted = _findings(res, min_severity, limit)
    statuses: Dict[str, int] = {}
    for o in res.outcomes.values():
        statuses[o.status] = statuses.get(o.status, 0) + 1
    return {"verdict": res.verdict, "fail_on": res.fail_on, "counts": res.counts(), "rules": statuses,
            "target": {"repo": res.ctx.repo_name, "lifecycle_state": res.ctx.stage, "stage_group": res.ctx.stage_group,
                       "data_product_id": res.ctx.dp_get("metadata.id")},
            "findings": rows, "rules_info": rule_info, "omitted": omitted,
            "semantic_handoff": [{"rule_id": h["rule_id"], "question": h["question"], "kb": h.get("kb", [])}
                                 for h in res.handoff[:12]],
            "next": "Corrige BLOCKER/HIGH primero; `fix` resuelve lo mecánico; `explain_rule` da fuente y KB."}


def t_gate(path=".", to="listo_para_produccion"):
    res = _run(path, ["dp"], stage=to)
    rows, rule_info, omitted = _findings(res, "HIGH", 80)
    return {"to": to, "approved": res.verdict != "FAIL", "counts": res.counts(),
            "blockers": [r for r in rows if r["severity"] == "BLOCKER"],
            "high": [r for r in rows if r["severity"] == "HIGH"], "rules_info": rule_info, "omitted": omitted}


def t_score(path="."):
    from govkit import scoring

    sc = scoring.compute(_run(path, ["dp"]))
    return {"global": sc["global"], "classification": sc["classification"], "dimensions": sc["dimensions"],
            "reference_state": sc.get("reference_state"), "note": sc.get("note"),
            "pillars": {k: {"label": p["label"], "score": p["score"], "declared": p["declared"], "weight": p["weight"],
                            "blocker_cap": p["blocker_cap"], "rules_failed": p["rules_failed"]}
                        for k, p in sc["pillars"].items()}}


def t_fix(path=".", apply=False, stage=None, rules=None, placeholders=True):
    from govkit import fixer

    before = _run(path, ["dp"], stage, rules=rules)
    actions = fixer.plan(before, placeholders=placeholders)
    out: Dict[str, Any] = {"mode": "apply" if apply else "plan", "before": before.counts()}
    if apply:
        fixer.apply(before.ctx, actions)
        after = _run(path, ["dp"], stage, rules=rules)
        out.update(after=after.counts(), verdict_after=after.verdict)
    out["actions"] = [a.to_dict() for a in actions]
    out["note"] = ("Las marcas <COMPLETAR> requieren datos reales del usuario; las acciones `manual` necesitan "
                   "decisión humana. Ejecuta `lint` otra vez tras completar.")
    return out


def t_explain_rule(rule_id: str):
    from govkit.engine import load_catalog
    from govkit.kb import store

    rule = next((r for r in load_catalog()["_rules"] if r.id == rule_id.upper()), None)
    if not rule:
        raise ValueError(f"Regla desconocida: {rule_id}")
    kb = store.load()
    out = {k: v for k, v in rule.raw.items() if k not in ("check",)}
    out["automated"] = rule.automated
    out["kb_rules"] = {cid: kb.chunks[cid].render(["R"]) for cid in rule.kb[:1] if cid in kb.chunks}
    return out


def t_search_rules(query: str, nature=None, pack=None, limit=15):
    from govkit.engine import load_catalog
    from govkit.kb.bm25 import BM25

    rules = {r.id: r for r in load_catalog()["_rules"] if (not nature or r.nature in nature.upper())
             and (not pack or r.pack == pack)}
    idx = BM25({rid: " ".join(str(x) for x in (r.id, r.title, r.category, r.pillar, r.remediation,
                                               r.source.get("doc", ""), r.source.get("quote", "")))
                for rid, r in rules.items()})
    hits = [rules[rid] for rid, _ in idx.search(query, k=limit)]
    if not hits:  # IDs exactos o prefijos (GOV-IAM)
        hits = [r for rid, r in rules.items() if rid.startswith(query.upper())][:limit]
    return [{"id": r.id, "nature": r.nature, "severity": r.severity, "title": r.title, "pillar": r.pillar,
             "source": f"{r.source.get('doc', '')} {r.source.get('section', '')}".strip()} for r in hits]


def t_kb_context(task=None, query=None, files=None, rule_ids=None, mode="assist", budget=4000):
    from govkit.kb import store
    from govkit.kb.router import route

    if not (task or query or files or rule_ids):
        raise ValueError("indica al menos uno: task, query, files o rule_ids")
    kb = store.load()
    pack = route(kb, task=task, query=query, paths=files or [], rule_ids=rule_ids or [], budget=int(budget), mode=mode)
    return {"manifest": pack.manifest(), "citable_ids": len(pack.rule_ids()), "context": pack.text()}


def _surface(path, base):
    from govkit.engine import Engine
    from govkit.llm.review import surface

    ctx, catalog = _ctx(path, base=base)
    res = Engine(ctx, catalog).run()
    return ctx, res, surface(ctx, ctx.changed_files() if base else None, 50)


def t_semantic_review_plan(path=".", artifact=None, base=None, budget=8192):
    from govkit.kb import store
    from govkit.llm.review import SYSTEM, build_prompt
    from govkit.paths import SCHEMAS_DIR

    ctx, res, targets = _surface(path, base)
    if not artifact:
        return {"deterministic_verdict": res.verdict, "artifacts": [
            {"artifact": rel, "task": task, "open_findings": sum(1 for v in res.counting if v.location.file == rel)}
            for rel, task in targets],
            "next": "Llama de nuevo con `artifact` para obtener el brief de revisión de cada uno."}
    task = dict(targets).get(artifact)
    if not task:
        raise ValueError(f"`{artifact}` no está en la superficie semántica: {[t[0] for t in targets]}")
    prompt = build_prompt(ctx, res, store.load(), artifact, task, int(budget))
    schema = json.loads((SCHEMAS_DIR / "semantic_review.schema.json").read_text(encoding="utf-8"))
    return {"artifact": artifact, "task": task, "kb_loaded": prompt["pack"].ids, "questions": prompt["questions"],
            "reviewer_rules": SYSTEM, "brief": prompt["messages"][1]["content"], "output_schema": schema,
            "next": "Produce `findings` según output_schema y pásalos a verify_semantic_findings con el mismo "
                    "path/artifact/budget antes de reportar."}


def t_verify_semantic_findings(artifact: str, findings: List[Dict[str, Any]], path=".", base=None, budget=8192):
    from govkit.kb import store
    from govkit.llm.review import build_prompt, verify
    from govkit.paths import SCHEMAS_DIR

    ctx, res, targets = _surface(path, base)
    task = dict(targets).get(artifact)
    if not task:
        raise ValueError(f"`{artifact}` no está en la superficie semántica")
    prompt = build_prompt(ctx, res, store.load(), artifact, task, int(budget))  # mismo enrutamiento → mismo contexto
    schema = json.loads((SCHEMAS_DIR / "semantic_review.schema.json").read_text(encoding="utf-8"))
    checked = verify(json.dumps({"findings": findings}, ensure_ascii=False), prompt, schema)
    checked["advisory"] = True
    checked["note"] = "Solo los hallazgos en `findings` superaron la verificación (citas visibles + grounding)."
    return checked


def t_init_data_product(domain: str, subdomain: str, type="anl", country="cl", dest=".", owner=None):
    from govkit.scaffold import scaffold

    root = scaffold(domain, subdomain, type, country, dest, owner=owner)
    res = _run(str(root), ["dp"])
    return {"created": str(root), "verdict": res.verdict, "counts": res.counts(),
            "next": "Completa las marcas <COMPLETAR> con el usuario; `gate` muestra lo que exige cada etapa."}


def _states() -> List[str]:
    from govkit.paths import registry

    return list((registry("lifecycle").get("states") or {}).keys())


def _tasks() -> List[str]:
    from govkit.kb import store

    return list((store.load().graph.get("tasks") or {}).keys())


def _p(desc, **kw):
    return {"description": desc, **kw}


def tool_specs() -> List[Dict[str, Any]]:
    path = _p("Raíz del repo de Data Product (relativa al cwd del servidor)", type="string", default=".")
    ro = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}
    sevs = {"type": "string", "enum": SEV_ORDER}
    finding_schema = {"type": "object", "required": ["kb_rule_id", "verdict", "confidence", "artifact", "evidence_quote",
                                                     "rationale"]}
    return [
        {"name": "lint", "title": "Validar Data Product (motor determinista)",
         "description": "Evalúa el repo contra ~260 reglas del framework. Devuelve veredicto, hallazgos con archivo:línea, "
                        "severidad según ciclo de vida, remediación y autofix; y preguntas semánticas pendientes.",
         "inputSchema": {"type": "object", "properties": {
             "path": path, "packs": {"type": "array", "items": {"type": "string", "enum": PACKS}, "default": ["dp"]},
             "stage": _p("Forzar estado del ciclo de vida", type="string", enum=_states()),
             "base": _p("Ref git base para checks de diff (breaking changes)", type="string"),
             "rules": _p("Filtro de reglas (glob, coma): GOV-SEC-*,GOV-IAM-004", type="string"),
             "min_severity": {**sevs, "default": "LOW"},
             "limit": _p("Máximo de hallazgos (0 = todos)", type="integer", default=60),
             "changed_only": {"type": "boolean", "default": False}}}, "annotations": ro},
        {"name": "gate", "title": "Pre-flight de promoción",
         "description": "Evalúa el repo como si estuviera en el estado destino: ¿se aprueba la promoción? Lista BLOCKER y HIGH.",
         "inputSchema": {"type": "object", "properties": {"path": path, "to": {"type": "string", "enum": _states(),
                                                                                 "default": "listo_para_produccion"}}},
         "annotations": ro},
        {"name": "score", "title": "Pre-score por pilar (19-scoring-model)",
         "description": "Pre-score determinista por los 11 pilares, evaluado contra el estado productivo.",
         "inputSchema": {"type": "object", "properties": {"path": path}}, "annotations": ro},
        {"name": "fix", "title": "Auto-remediación segura",
         "description": "Planifica (apply=false) o aplica remediaciones mecánicas: carpetas estándar, archivos desde "
                        "plantilla corporativa, valores deterministas, bumps semver y claves ausentes como <COMPLETAR>. "
                        "Nunca sobrescribe contenido humano; cada edición se verifica re-parseando.",
         "inputSchema": {"type": "object", "properties": {
             "path": path, "apply": {"type": "boolean", "default": False},
             "stage": _p("Planificar contra un estado destino", type="string", enum=_states()),
             "rules": {"type": "string"}, "placeholders": {"type": "boolean", "default": True}}},
         "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
        {"name": "explain_rule", "title": "Trazabilidad de una regla",
         "description": "Fuente (documento § cita), naturaleza, severidad por etapa, remediación y reglas KB de una regla GOV-*.",
         "inputSchema": {"type": "object", "required": ["rule_id"], "properties": {"rule_id": {"type": "string"}}},
         "annotations": ro},
        {"name": "search_rules", "title": "Buscar reglas del catálogo",
         "description": "Búsqueda BM25 en el catálogo de reglas (título, remediación, fuente).",
         "inputSchema": {"type": "object", "required": ["query"], "properties": {
             "query": {"type": "string"}, "nature": _p("D, H, S, O (combinables)", type="string"),
             "pack": {"type": "string", "enum": PACKS}, "limit": {"type": "integer", "default": 15}}},
         "annotations": ro},
        {"name": "kb_context", "title": "Contexto normativo mínimo (KB)",
         "description": "Enrutador de la base de conocimiento: devuelve solo los mini-contextos relevantes para la tarea, "
                        "archivos o reglas, dentro de un presupuesto de tokens. Cita los IDs KBnn.Xn en tus respuestas.",
         "inputSchema": {"type": "object", "properties": {
             "task": {"type": "string", "enum": _tasks()}, "query": {"type": "string"},
             "files": {"type": "array", "items": {"type": "string"}},
             "rule_ids": {"type": "array", "items": {"type": "string"}},
             "mode": {"type": "string", "enum": ["assist", "review", "qa"], "default": "assist"},
             "budget": {"type": "integer", "default": 4000}}}, "annotations": ro},
        {"name": "semantic_review_plan", "title": "Plan de revisión semántica",
         "description": "Sin `artifact`: lista la superficie semántica del repo. Con `artifact`: brief de revisión "
                        "(contexto KB enrutado, hallazgos deterministas a no repetir, preguntas y esquema de salida).",
         "inputSchema": {"type": "object", "properties": {"path": path, "artifact": {"type": "string"},
                                                          "base": {"type": "string"},
                                                          "budget": {"type": "integer", "default": 8192}}},
         "annotations": ro},
        {"name": "verify_semantic_findings", "title": "Verificar hallazgos semánticos",
         "description": "Verificador determinista anti-alucinación: descarta hallazgos con citas KB fuera del contexto o "
                        "evidencia no presente en el artefacto, y acota la severidad por la fuerza normativa.",
         "inputSchema": {"type": "object", "required": ["artifact", "findings"], "properties": {
             "path": path, "artifact": {"type": "string"}, "findings": {"type": "array", "items": finding_schema},
             "base": {"type": "string"}, "budget": {"type": "integer", "default": 8192}}}, "annotations": ro},
        {"name": "init_data_product", "title": "Crear Data Product estándar",
         "description": "Genera un repositorio de Data Product conforme al estándar (estructura, ficha, contratos, IAM, CI).",
         "inputSchema": {"type": "object", "required": ["domain", "subdomain"], "properties": {
             "domain": {"type": "string"}, "subdomain": {"type": "string"},
             "type": {"type": "string", "enum": ["anl", "txd"], "default": "anl"},
             "country": {"type": "string", "default": "cl"}, "dest": {"type": "string", "default": "."},
             "owner": {"type": "string"}}},
         "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}},
    ]


TOOLS: Dict[str, Callable[..., Any]] = {
    "lint": t_lint, "gate": t_gate, "score": t_score, "fix": t_fix, "explain_rule": t_explain_rule,
    "search_rules": t_search_rules, "kb_context": t_kb_context, "semantic_review_plan": t_semantic_review_plan,
    "verify_semantic_findings": t_verify_semantic_findings, "init_data_product": t_init_data_product,
}


# ============================================================== recursos y prompts
def _docs_dir():
    from govkit.paths import DOCS_DIR, KIT_HOME

    for d in (DOCS_DIR, KIT_HOME.parent / "docs"):
        if (d / "00-SAD-sistema-gobernanza-hibrido.md").exists():
            return d
    return None


def resources() -> List[Dict[str, Any]]:
    from govkit.kb import store

    out = [{"uri": f"govkit://kb/{c.id}", "name": c.id, "title": c.title, "mimeType": "text/markdown",
            "description": f"Mini-contexto KB · tier {c.tier} · ~{c.tokens} tokens"} for c in store.load().chunks.values()]
    out.append({"uri": "govkit://rules/matrix", "name": "matriz-reglas", "title": "Matriz de reglas (catálogo completo)",
                "mimeType": "text/markdown"})
    if _docs_dir():
        out.append({"uri": "govkit://docs/sad", "name": "sad", "title": "SAD · Sistema de Gobernanza Híbrido",
                    "mimeType": "text/markdown"})
    return out


def read_resource(uri: str) -> str:
    from govkit.kb import store

    if uri.startswith("govkit://kb/"):
        c = store.load().chunks.get(uri.rsplit("/", 1)[-1].upper())
        if not c:
            raise ValueError(f"Recurso desconocido: {uri}")
        with open(c.path, encoding="utf-8") as fh:
            return fh.read()
    if uri == "govkit://rules/matrix":
        from govkit.docgen import rules_markdown
        from govkit.engine import load_catalog
        return rules_markdown(load_catalog())
    if uri == "govkit://docs/sad" and _docs_dir():
        return (_docs_dir() / "00-SAD-sistema-gobernanza-hibrido.md").read_text(encoding="utf-8")
    raise ValueError(f"Recurso desconocido: {uri}")


PROMPTS = {
    "revision_gobernanza": {
        "title": "Revisión de gobernanza de un Data Product",
        "description": "Flujo completo: lint → fix → completar → revisión semántica verificada → gate.",
        "arguments": [{"name": "path", "description": "Ruta del repo (default .)", "required": False},
                      {"name": "destino", "description": "Estado destino para el gate", "required": False}],
        "text": ("Revisa la gobernanza del Data Product en `{path}` con las herramientas de govkit:\n"
                 "1. `lint` y resume por severidad. 2. `fix` con apply=false; muéstrame el plan y aplícalo si lo apruebo.\n"
                 "3. Para cada BLOCKER/HIGH manual, propón el cambio exacto (archivo:línea) y pregúntame los datos de negocio"
                 " que falten; no inventes valores.\n4. `semantic_review_plan`, revisa los artefactos y pasa tus hallazgos"
                 " por `verify_semantic_findings`; reporta solo los verificados, citando KBnn.Xn.\n"
                 "5. `gate` hacia `{destino}` y dime qué falta para aprobar."),
        "defaults": {"path": ".", "destino": "listo_para_produccion"}},
    "nuevo_data_product": {
        "title": "Diseñar un Data Product nuevo",
        "description": "Crea el repo estándar y guía la ficha con el contexto normativo.",
        "arguments": [{"name": "dominio", "required": True}, {"name": "subdominio", "required": True},
                      {"name": "tipo", "description": "anl | txd", "required": False},
                      {"name": "pais", "required": False}],
        "text": ("Vamos a crear el Data Product {dominio}/{subdominio} ({tipo}, {pais}). Usa `kb_context` con "
                 "task=nuevo_data_product, luego `init_data_product`. Después guíame sección por sección de "
                 "metadata/catalog/data_product.yaml (negocio, ownership, SLA, clasificación, contratos), preguntándome "
                 "los datos reales y citando las reglas KB. Termina con `lint` y `gate` hacia en_desarrollo."),
        "defaults": {"tipo": "anl", "pais": "cl"}},
    "consulta_framework": {
        "title": "Consultar el Data & AI Discipline Framework",
        "description": "Responde con citas verificables de la base de conocimiento.",
        "arguments": [{"name": "pregunta", "required": True}],
        "text": ("Responde usando SOLO el contexto de `kb_context` (query = la pregunta, mode=qa) y cita los IDs "
                 "KBnn.Xn. Si no está cubierto, dilo explícitamente.\nPregunta: {pregunta}"),
        "defaults": {}},
}


def get_prompt(name: str, args: Dict[str, str]) -> Dict[str, Any]:
    p = PROMPTS.get(name)
    if not p:
        raise ValueError(f"Prompt desconocido: {name}")
    vals = {**p["defaults"], **{k: v for k, v in (args or {}).items() if v}}
    missing = [a["name"] for a in p["arguments"] if a.get("required") and a["name"] not in vals]
    if missing:
        raise ValueError(f"Faltan argumentos: {missing}")
    return {"description": p["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": p["text"].format(**vals)}}]}


# ============================================================== JSON-RPC
class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def handle(msg: Dict[str, Any], state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method is None:  # respuesta del cliente (no usamos sampling): ignorar
        return None
    is_notification = "id" not in msg
    try:
        result = dispatch(method, params, state)
    except RpcError as exc:
        return None if is_notification else {"jsonrpc": "2.0", "id": mid, "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:  # noqa: BLE001 - nunca botar el servidor
        return None if is_notification else {"jsonrpc": "2.0", "id": mid,
                                              "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"}}
    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def dispatch(method: str, params: Dict[str, Any], state: Dict[str, Any]) -> Any:
    if method == "initialize":
        requested = params.get("protocolVersion")
        state["protocol"] = requested if requested in PROTOCOLS else PROTOCOLS[0]
        return {"protocolVersion": state["protocol"],
                "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False},
                                 "prompts": {"listChanged": False}},
                "serverInfo": {"name": "govkit", "title": "govkit · Gobernanza Híbrida de Datos", "version": __version__},
                "instructions": INSTRUCTIONS}
    if method.startswith("notifications/"):
        return None
    if method in ("ping", "logging/setLevel"):
        return {}
    if method == "tools/list":
        return {"tools": tool_specs()}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        fn = TOOLS.get(name)
        if not fn:
            raise RpcError(-32602, f"Herramienta desconocida: {name}")
        try:
            data = fn(**args)
        except TypeError as exc:
            return {"content": [{"type": "text", "text": f"Argumentos inválidos para `{name}`: {exc}"}], "isError": True}
        except (ValueError, KeyError, FileNotFoundError, SystemExit) as exc:
            return {"content": [{"type": "text", "text": f"{name}: {exc}"}], "isError": True}
        except Exception as exc:  # noqa: BLE001
            print(traceback.format_exc(), file=sys.stderr)
            return {"content": [{"type": "text", "text": f"{name}: error interno {type(exc).__name__}: {exc}"}],
                    "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, separators=(",", ":"),
                                                                 default=str)}], "isError": False}
    if method == "resources/list":
        return {"resources": resources()}
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "resources/read":
        uri = params.get("uri", "")
        try:
            return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": read_resource(uri)}]}
        except ValueError as exc:
            raise RpcError(-32002, str(exc))
    if method == "prompts/list":
        return {"prompts": [{"name": n, "title": p["title"], "description": p["description"], "arguments": [
            {k: v for k, v in a.items()} for a in p["arguments"]]} for n, p in PROMPTS.items()]}
    if method == "prompts/get":
        try:
            return get_prompt(params.get("name", ""), params.get("arguments") or {})
        except ValueError as exc:
            raise RpcError(-32602, str(exc))
    raise RpcError(-32601, f"Método no soportado: {method}")


def serve(stdin=None, stdout=None) -> int:
    """Bucle stdio. stdout queda reservado al protocolo: cualquier print del motor se desvía a stderr."""
    rin = stdin or io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    rout = stdout or io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
    real_stdout, sys.stdout = sys.stdout, sys.stderr
    try:
        return _loop(rin, rout)
    finally:
        sys.stdout = real_stdout


def _loop(rin, rout) -> int:
    state: Dict[str, Any] = {}

    def send(obj: Any) -> None:
        rout.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        rout.flush()

    for line in rin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"JSON inválido: {exc}"}})
            continue
        batch = msg if isinstance(msg, list) else [msg]
        replies = [r for r in (handle(m, state) if isinstance(m, dict) else
                               {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Solicitud inválida"}}
                               for m in batch) if r is not None]
        if isinstance(msg, list):
            if replies:
                send(replies)  # lote JSON-RPC → arreglo de respuestas
        elif replies:
            send(replies[0])
    return 0
