"""Hechos verificables (arch_facts.yaml) y contradicciones (arch_conflicts.yaml) evaluados contra el índice."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from govkit.arch import NOT_DETERMINED
from govkit.arch import index as I
from govkit.arch import parsers as P
from govkit.paths import REGISTRY_DIR, load_yaml_file


@lru_cache(maxsize=1)
def registry_facts() -> List[Dict[str, Any]]:
    return (load_yaml_file(REGISTRY_DIR / "arch_facts.yaml") or {}).get("facts") or []


@lru_cache(maxsize=1)
def registry_conflicts() -> Dict[str, Any]:
    return load_yaml_file(REGISTRY_DIR / "arch_conflicts.yaml") or {}


def conflicts_list() -> List[Dict[str, Any]]:
    return list(registry_conflicts().get("conflicts") or [])


def potential_adrs() -> List[Dict[str, Any]]:
    return list(registry_conflicts().get("potential_adrs") or [])


def evaluate(fact: Dict[str, Any], indexes: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """→ {holds: True|False|None, detail, trace}. None = NO DETERMINADO (fuente no ingerida o archivo ausente)."""
    indexes = indexes if indexes is not None else I.all_current()
    kind = fact.get("kind")
    out: Dict[str, Any] = {"id": fact["id"], "statement": fact.get("statement", ""), "status": fact.get("status"),
                           "label": fact.get("label"), "holds": None, "detail": NOT_DETERMINED, "trace": ""}
    if kind == "absent_everywhere":
        if not indexes:
            out["detail"] = f"{NOT_DETERMINED}: ninguna fuente ingerida"
            return out
        rx = re.compile(fact["pattern"])
        hits = [f"{sid}:{rel}" for sid, idx in indexes.items() for rel in idx["files"] if rx.search(rel)]
        out.update(holds=not hits, detail="sin coincidencias en las fuentes ingeridas" if not hits else
                   f"encontrado en {', '.join(hits[:3])}", trace=", ".join(sorted(indexes)))
        return out
    idx = indexes.get(fact.get("source", ""))
    if idx is None:
        out["detail"] = f"{NOT_DETERMINED}: fuente `{fact.get('source')}` no ingerida (govkit arch ingest/sync)"
        return out
    commit = str(idx["meta"].get("commit") or "?")[:7]
    rel = fact.get("path", "")
    out["trace"] = f"{idx['meta']['repo']}@{commit}:{rel}" if rel else f"{idx['meta']['repo']}@{commit}"
    if kind == "archimate_folder":
        from govkit.arch import archimate
        rx = re.compile(fact["pattern"])
        names = [d["name"] for d in archimate.dp_inventory(idx) if rx.search(d["name"])]
        out.update(holds=bool(names), detail=f"carpetas: {', '.join(names[:6])}" if names else "sin carpetas que coincidan")
        return out
    if kind == "empty_dir":
        under = I.files_under(idx, rel)
        real = [f for f in under if not idx["files"][f].get("placeholder")]
        out.update(holds=bool(under) and not real, detail=(f"{len(under)} archivo(s), todos placeholders" if under and not real
                   else f"contiene {len(real)} archivo(s) con contenido" if real else "la carpeta no existe"))
        return out
    entry = idx["files"].get(rel)
    if kind == "absent":
        out.update(holds=entry is None and not I.files_under(idx, rel), detail="no existe" if entry is None else "existe")
        return out
    if kind == "exists":
        out.update(holds=entry is not None, detail="existe" if entry else "no existe")
        return out
    if entry is None:
        out["detail"] = f"{NOT_DETERMINED}: `{rel}` no existe en {out['trace']}"
        return out
    if kind == "placeholder":
        out.update(holds=bool(entry.get("placeholder")), detail="vacío/placeholder" if entry.get("placeholder") else "tiene contenido")
        return out
    text = entry.get("text") or ""
    if kind in ("contains", "not_contains"):
        m = re.search(fact["pattern"], text, re.M)
        line = text.count("\n", 0, m.start()) + 1 if m else None
        holds = bool(m) if kind == "contains" else not m
        out.update(holds=holds, detail=(f"coincide en L{line}" if m else "sin coincidencia"))
        if m:
            sec = I.section_at(entry, line or 0)
            out["trace"] += f":{line}" + (f" §{sec['t']}" if sec else "")
        return out
    if kind == "value":
        found, value = P.dig(entry.get("flat_source") or _structured(rel, text), fact["key"])
        if not found:
            out["detail"] = f"{NOT_DETERMINED}: clave `{fact['key']}` ausente"
            return out
        want = fact.get("equals")
        norm = (lambda v: [str(x) for x in v] if isinstance(v, list) else str(v))
        out.update(holds=norm(value) == norm(want), detail=f"{fact['key']} = {value!r}", value=value)
        return out
    out["detail"] = f"tipo de hecho desconocido: {kind}"
    return out


def _structured(rel: str, text: str) -> Any:
    data, _ = P.load_structured(rel, text)
    return data


def evaluate_all(indexes: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    indexes = indexes if indexes is not None else I.all_current()
    return {f["id"]: evaluate(f, indexes) for f in registry_facts()}


def conflict_states(indexes: Optional[Dict[str, Dict[str, Any]]] = None,
                    fact_results: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Estado de cada contradicción: VIGENTE (toda su evidencia se sostiene) · REVISAR (algún hecho cambió) ·
    NO DETERMINADO (falta ingerir fuentes)."""
    fr = fact_results if fact_results is not None else evaluate_all(indexes)
    out = []
    for c in conflicts_list():
        results = [fr.get(fid) or {"id": fid, "holds": None, "detail": "hecho no registrado"} for fid in c.get("facts") or []]
        if any(r["holds"] is False for r in results):
            state = "REVISAR"
        elif results and all(r["holds"] is True for r in results):
            state = "VIGENTE"
        else:
            state = NOT_DETERMINED
        out.append({**c, "state": state, "fact_results": results})
    return out


def conflicts_for(dp_rel: Optional[str] = None, source: Optional[str] = None, corp_rel: Optional[str] = None,
                  ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    from govkit.arch.registry import gmatch
    out = []
    for c in conflicts_list():
        if ids and c["id"] in ids:
            out.append(c)
        elif dp_rel is not None and any(gmatch(g, dp_rel) for g in c.get("dp_globs") or []):
            out.append(c)
        elif source and corp_rel is not None and any(
                ev.startswith(f"{source}:") and (corp_rel.startswith(ev.split(":", 1)[1].split(" ")[0].rstrip("/"))
                                                  or ev.split(":", 1)[1].startswith(corp_rel.rstrip("/") + "/")
                                                  or ev.split(":", 1)[1].split(" ")[0] == corp_rel)
                for ev in c.get("evidence") or []):
            out.append(c)
    seen, res = set(), []
    for c in out:
        if c["id"] not in seen:
            seen.add(c["id"])
            res.append(c)
    return res
