"""Mini-resúmenes por unidad arquitectónica (SUPER PROMPT §6): pequeños, trazables y orientados al análisis.

Extracción determinista (README/encabezados, tipos, tecnologías, grafo, hechos, conflictos, ADR). Cada campo sin
evidencia queda como NO DETERMINADO; nunca se completa inventando.
"""
from __future__ import annotations

import hashlib
import posixpath
from collections import Counter
from functools import lru_cache
from typing import Any, Dict, List, Optional

from govkit.arch import NOT_DETERMINED
from govkit.arch import graph as G
from govkit.arch import index as I
from govkit.arch import parsers as P
from govkit.arch.registry import gmatch
from govkit.paths import REGISTRY_DIR, load_yaml_file

KIND_LABEL = {
    "official_doc": "documentación normativa", "standard": "estándar ejecutable / especificación",
    "policy": "política", "code": "código / validador", "ci": "CI (workflows)", "template": "plantillas oficiales",
    "example": "ejemplos de referencia", "archimate": "modelo ArchiMate", "skill": "skill / agente IA",
    "index": "índice para agentes", "repo_doc": "documentación del repositorio", "asset": "recursos / placeholders",
}


@lru_cache(maxsize=1)
def context_map() -> Dict[str, Any]:
    return load_yaml_file(REGISTRY_DIR / "arch_context_map.yaml") or {}


def units(idx: Dict[str, Any]) -> List[str]:
    """Unidades: carpetas con README, rutas del manifiesto, carpetas de primer nivel, skills, carpetas de DP en
    ArchiMate y archivos normativos."""
    files = idx["files"]
    out = set()
    for rel, e in files.items():
        parts = rel.split("/")
        if len(parts) > 1:
            out.add(parts[0])
        if parts[-1].lower() == "readme.md" and len(parts) > 1:
            out.add("/".join(parts[:-1]))
        if len(parts) > 2 and parts[0] in ("skills", "framework"):
            out.add("/".join(parts[:2]))
        if e["kind"] in ("official_doc", "standard", "policy") and not e.get("placeholder"):
            out.add(rel)
        if e["kind"] == "index":
            for v in (e.get("flat") or {}).values():
                for x in (v if isinstance(v, list) else [v]):
                    if isinstance(x, str) and "/" in x and I.files_under(idx, x):
                        out.add(x.strip("/"))
    if idx.get("archimate"):
        from govkit.arch import archimate
        out.discard("model")
        out.add("model")
        for dp in archimate.dp_inventory(idx):
            out.add(dp["folder"])
    return sorted(out)


def unit_for(idx: Dict[str, Any], rel: str) -> str:
    rel = rel.strip("/")
    best = ""
    for u in units(idx):
        if (rel == u or rel.startswith(u + "/")) and len(u) > len(best):
            best = u
    return best or (rel.split("/")[0] if rel else "")


def _unit_files(idx: Dict[str, Any], unit: str) -> List[str]:
    return I.files_under(idx, unit) if unit else list(idx["files"])


def _purpose(idx: Dict[str, Any], unit: str, files: List[str]) -> str:
    e = idx["files"].get(unit)
    if e and e.get("purpose"):
        return e["purpose"]
    for cand in (f"{unit}/README.md", f"{unit}/SKILL.md", f"{unit}/docs/README.md"):
        ce = idx["files"].get(cand)
        if ce and ce.get("purpose"):
            return ce["purpose"]
    if idx.get("archimate") and unit.startswith("model/diagrams"):
        from govkit.arch import archimate
        for dp in archimate.dp_inventory(idx):
            if dp["folder"] == unit:
                lv = ", ".join(f"{k}: {v}" for k, v in dp["levels"].items()) or "sin vistas"
                return (f"Diseño ArchiMate del Data Product `{dp['name']}` ({dp['country']}); vistas {lv}; niveles "
                        f"declarados: {', '.join(dp['declared_levels']) or '—'}.")
    titled = [idx["files"][f].get("title") for f in files if idx["files"][f].get("title") and
              idx["files"][f]["kind"] in ("official_doc", "standard", "repo_doc")]
    return f"{NOT_DETERMINED} (sin README; contiene: {', '.join(titled[:3])})" if titled else NOT_DETERMINED


def curated_for(source: str, rel: str) -> List[Dict[str, Any]]:
    return [c for c in context_map().get("corp_paths") or []
            if c.get("source") == source and (gmatch(c["glob"], rel or "") or gmatch(c["glob"], (rel or "").rstrip("/") + "/_"))]


def summarize(idx: Dict[str, Any], unit: str, edges: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    from govkit.arch import adr as A
    from govkit.arch import facts as F
    sid = idx["meta"]["source"]
    edges = edges if edges is not None else G.current()
    files = _unit_files(idx, unit)
    entries = [idx["files"][f] for f in files]
    kinds = Counter(e["kind"] for e in entries)
    statuses = Counter(e["status"] for e in entries)
    placeholders = [f for f in files if idx["files"][f].get("placeholder")]
    text = " ".join((idx["files"][f].get("text") or "")[:40000] for f in files)[:400000]
    if idx.get("archimate") and unit.startswith("model"):
        from govkit.arch import archimate
        dp = next((d for d in archimate.dp_inventory(idx) if d["folder"] == unit), None)
        if dp:
            des = archimate.design(idx, dp)
            text += " " + " ".join(des["technologies"] + des["processes"] + des["groupings"])
        else:
            text += " " + " ".join(e["name"] for e in idx["archimate"]["elements"].values())
    nb = G.neighbors(edges, sid, unit)
    deps = Counter(f"{e['dst'].get('source') or e['dst'].get('repo')}:{e['dst'].get('path') or ''}".rstrip(":")
                   for e in nb["out"] if e["type"] in ("reference", "index", "mirror", "reference_unverified", "models_dp"))
    dependents = Counter(f"{e['src']['source']}:{e['src']['path']}" for e in nb["in"]
                         if e["type"] in ("reference", "index", "mirror"))
    broken = [e for e in nb["out"] if e["type"] == "reference_broken"]
    divergent = [e for e in nb["out"] + nb["in"] if e["type"] == "duplicate_divergent"]
    cur = curated_for(sid, unit)
    conflict_ids = sorted({c for cm in cur for c in cm.get("conflicts") or []})
    conflicts = F.conflicts_for(ids=conflict_ids) + F.conflicts_for(source=sid, corp_rel=unit)
    conflicts = list({c["id"]: c for c in conflicts}.values())
    adrs, pots = A.for_path(sid, unit)
    drafts = [f for f in files if idx["files"][f].get("draft")]
    disabled = [f for f in files if idx["files"][f].get("disabled")]
    risks = [f"{c['id']} {c['title']}" for c in conflicts]
    if len(placeholders) > max(1, len(files) // 2):
        risks.append(f"mayoría de placeholders ({len(placeholders)}/{len(files)}): contenido aún no definido")
    if drafts:
        risks.append(f"documentos en borrador: {', '.join(posixpath.basename(d) for d in drafts[:3])}")
    if disabled:
        risks.append(f"CI deshabilitado: {', '.join(posixpath.basename(d) for d in disabled[:3])}")
    if broken:
        risks.append(f"{len(broken)} referencia(s) rota(s) (p.ej. {broken[0]['dst'].get('path')})")
    for d in divergent[:2]:
        risks.append(f"duplicado divergente: {d['evidence']}")
    see = [f"{s['source']}:{s['path']} — {s['why']}" for cm in cur for s in cm.get("see") or []]
    see += [f"{k} (depende de esta unidad)" for k, _ in dependents.most_common(6)]
    has_doc = any(e["label"] == "DOC" for e in entries if not e.get("placeholder"))
    has_cod = any(e["label"] == "COD" for e in entries if not e.get("placeholder"))
    real = len(files) - len(placeholders)
    confidence = ("BAJA" if real == 0 or statuses.get("UNKNOWN", 0) > real else
                  "ALTA" if has_doc and has_cod and not drafts else "MEDIA")
    subtree = hashlib.sha256("".join(f"{f}:{idx['files'][f]['sha']}" for f in sorted(files)).encode()).hexdigest()[:12]
    return {
        "source": sid, "repo": idx["meta"]["repo"], "unit": unit or "(raíz)",
        "trace": f"{idx['meta']['repo']}@{str(idx['meta'].get('commit') or '?')[:7]}:{unit or '.'}", "hash": subtree,
        "purpose": _purpose(idx, unit, files),
        "domain": idx["meta"].get("role") or NOT_DETERMINED,
        "component_type": ", ".join(f"{KIND_LABEL.get(k, k)} ({n})" for k, n in kinds.most_common(3)) or NOT_DETERMINED,
        "contents": {"files": len(files), "placeholders": len(placeholders),
                     "main": [f for f in files if not idx["files"][f].get("placeholder")][:8]},
        "technologies": P.technologies(text) or [NOT_DETERMINED],
        "dependencies": [k for k, _ in deps.most_common(8)] or ["(sin dependencias explícitas)"],
        "patterns": P.patterns(text) or [NOT_DETERMINED],
        "guidelines": sorted({s.split(" — ")[0] for s in see if ":docs/" in s or "/docs/" in s or "specs" in s})[:6]
                      or [NOT_DETERMINED],
        "kb": sorted({k for cm in cur for k in cm.get("kb") or []}),
        "rules": sorted({k for cm in cur for k in cm.get("rules") or []}),
        "adrs": [f"{a['id']} {a['title']} ({a.get('status') or 'estado ?'})" for a in adrs]
                or [f"sin ADR · Potential: {', '.join(p['id'] for p in pots)}" if pots else "sin ADR"],
        "risks": risks or ["(sin riesgos detectados con la evidencia disponible)"],
        "review_if_changes": see[:10] or [NOT_DETERMINED],
        "affected": [k for k, _ in dependents.most_common(8)] or ["(nadie la referencia explícitamente)"],
        "status": dict(statuses), "evidence": [I.trace(idx, f) for f in files if not idx["files"][f].get("placeholder")][:5],
        "confidence": confidence,
    }


def render(s: Dict[str, Any]) -> str:
    def bullets(items: List[str]) -> str:
        return "; ".join(items)
    lines = [f"### `{s['repo']}/{s['unit']}`",
             f"- **Propósito:** {s['purpose']}",
             f"- **Dominio:** {s['domain']}",
             f"- **Tipo de componente:** {s['component_type']}",
             f"- **Qué contiene:** {s['contents']['files']} archivo(s), {s['contents']['placeholders']} placeholder(s)"
             + (f" · {', '.join(s['contents']['main'][:5])}" if s['contents']['main'] else ""),
             f"- **Tecnologías:** {bullets(s['technologies'])}",
             f"- **Dependencias:** {bullets(s['dependencies'])}",
             f"- **Patrones utilizados:** {bullets(s['patterns'])}",
             f"- **Lineamientos aplicables:** {bullets(s['guidelines'])}"
             + (f" · KB govkit: {', '.join(s['kb'])}" if s['kb'] else "")
             + (f" · reglas: {', '.join(s['rules'])}" if s['rules'] else ""),
             f"- **ADR relacionados:** {bullets(s['adrs'])}",
             f"- **Riesgos arquitectónicos:** {bullets(s['risks'])}",
             f"- **Qué revisar si esta ruta cambia:** {bullets(s['review_if_changes'])}",
             f"- **Qué otras rutas podrían verse afectadas:** {bullets(s['affected'])}",
             f"- **Estado normativo:** {', '.join(f'{k} {v}' for k, v in s['status'].items())}",
             f"- **Evidencia:** {bullets(s['evidence']) or s['trace']}",
             f"- **Nivel de confianza:** {s['confidence']}"]
    return "\n".join(lines) + "\n"
