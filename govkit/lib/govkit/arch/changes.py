"""Detección incremental de cambios arquitectónicos (SUPER PROMPT §10-§13, §23-§24).

Compara dos índices de la misma fuente (commit anterior vs actual; git o snapshot, por contenido sha256), clasifica
cada cambio (NEW · UPDATED · DEPRECATED · CONFLICTING · UNKNOWN), estima el impacto (NONE…CRITICAL, siempre con el
porqué), agrupa por unidad arquitectónica para no generar ruido y produce:
  · alertas ARCHITECTURAL CHANGE DETECTED;
  · el changelog ARCHITECTURAL KNOWLEDGE UPDATE (~/.govkit/arch/changes/);
  · la lista de análisis/reglas/notas posiblemente obsoletos.
`sync` hace fetch SOLO de refs remotas y lee origin/<rama> sin tocar el working tree (nunca pull).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from govkit.arch import IMPACT, IMPACT_RANK, NOT_DETERMINED, home, load_state, max_impact, save_state
from govkit.arch import facts as F
from govkit.arch import gitio, ingest, registry, summaries
from govkit.arch import index as I
from govkit.arch import parsers as P

NORMATIVE_KINDS = {"official_doc", "standard", "policy", "template", "ci", "archimate"}


# ------------------------------------------------------------------------------------------------ diff de contenido
def _sections_text(entry: Dict[str, Any]) -> Dict[str, str]:
    lines = (entry.get("text") or "").splitlines()
    out: Dict[str, str] = {}
    for s in entry.get("sections") or []:
        key = s["t"]
        n = 2
        while key in out:
            key = f"{s['t']} ({n})"
            n += 1
        out[key] = P.normalize_md("\n".join(lines[s["line"] - 1:s["end"]]))
    return out


def _detail(old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]], rel: str) -> Tuple[List[str], bool, Dict[str, int]]:
    """→ (detalles legibles, es_cosmético, delta de marcas normativas)."""
    if not old or not new:
        return [], False, {}
    delta = {k: (new.get("norm") or {}).get(k, 0) - (old.get("norm") or {}).get(k, 0) for k in ("REQUIRED", "RECOMMENDED", "DEPRECATED")}
    ot, nt = old.get("text"), new.get("text")
    if ot is not None and nt is not None and P.normalize_md(ot) == P.normalize_md(nt):
        return ["solo cambios de formato (espacios, escapes, alineación)"], True, delta
    det: List[str] = []
    if rel.lower().endswith(".md") and (old.get("sections") or new.get("sections")):
        so, sn = _sections_text(old), _sections_text(new)
        added = [t for t in sn if t not in so]
        removed = [t for t in so if t not in sn]
        changed = [t for t in sn if t in so and sn[t] != so[t]]
        if added:
            det.append("secciones nuevas: " + ", ".join(f"§{t}" for t in added[:6]))
        if removed:
            det.append("secciones eliminadas: " + ", ".join(f"§{t}" for t in removed[:6]))
        if changed:
            det.append("secciones modificadas: " + ", ".join(f"§{t}" for t in changed[:6]))
    elif "flat" in old or "flat" in new:
        fo, fn = old.get("flat") or {}, new.get("flat") or {}
        added = [k for k in fn if k not in fo]
        removed = [k for k in fo if k not in fn]
        changed = [k for k in fn if k in fo and fn[k] != fo[k]]
        for k in changed[:8]:
            det.append(f"`{k}`: {_short(fo[k])} → {_short(fn[k])}")
        if added:
            det.append("claves nuevas: " + ", ".join(f"`{k}`" for k in added[:8]))
        if removed:
            det.append("claves eliminadas: " + ", ".join(f"`{k}`" for k in removed[:8]))
    else:
        ol, nl = (ot or "").splitlines(), (nt or "").splitlines()
        det.append(f"{len(nl) - len(ol):+d} líneas ({len(ol)} → {len(nl)})")
    for k, v in delta.items():
        if v:
            det.append(f"marcas {k}: {v:+d}")
    return det, False, delta


def _short(v: Any) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return (s[:60] + "…") if len(s) > 60 else s


def _archimate_changes(old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
    mo, mn = old.get("archimate") or {}, new.get("archimate") or {}
    if not mo and not mn:
        return []
    eo, en = mo.get("elements") or {}, mn.get("elements") or {}
    det = []
    add = [en[i]["name"] for i in en if i not in eo]
    rem = [eo[i]["name"] for i in eo if i not in en]
    ren = [f"{eo[i]['name']} → {en[i]['name']}" for i in en if i in eo and eo[i]["name"] != en[i]["name"]]
    if add:
        det.append(f"elementos nuevos ({len(add)}): " + ", ".join(add[:8]))
    if rem:
        det.append(f"elementos eliminados ({len(rem)}): " + ", ".join(rem[:8]))
    if ren:
        det.append(f"elementos renombrados ({len(ren)}): " + ", ".join(ren[:6]))
    ro = {r["id"] for r in mo.get("relations") or []}
    rn = {r["id"] for r in mn.get("relations") or []}
    if ro != rn:
        det.append(f"relaciones: +{len(rn - ro)} / -{len(ro - rn)}")
    do = {d["id"]: d for d in mo.get("diagrams") or []}
    dn = {d["id"]: d for d in mn.get("diagrams") or []}
    for i, d in dn.items():
        if i not in do:
            det.append(f"vista nueva: {' / '.join(d.get('path_names') or [])} / {d['name']}")
        elif set(d["elements"]) != set(do[i]["elements"]):
            det.append(f"vista modificada: {d['name']} ({len(do[i]['elements'])} → {len(d['elements'])} elementos)")
    for i, d in do.items():
        if i not in dn:
            det.append(f"vista eliminada: {d['name']}")
    return det


def diff(old: Optional[Dict[str, Any]], new: Dict[str, Any], src: registry.Source) -> List[Dict[str, Any]]:
    """Cambios archivo a archivo entre dos índices de la misma fuente (por contenido)."""
    of = (old or {}).get("files") or {}
    nf = new["files"]
    main = new["meta"].get("main", True)
    removed = {p for p in of if p not in nf}
    added = {p for p in nf if p not in of}
    if (old or {}).get("meta", {}).get("origin") == "snapshot" and new["meta"].get("origin") != "snapshot":
        # los snapshots .txt excluyen binarios por diseño: no son "nuevos" al pasar a git
        added = {p for p in added if not nf[p].get("binary") and nf[p].get("text") is not None or nf[p].get("placeholder")}
    renames: Dict[str, str] = {}
    by_sha = {str(of[p]["sha"]): p for p in removed if of[p].get("size")}
    for p in list(added):
        o = by_sha.get(str(nf[p]["sha"]))
        if o and o in removed:
            renames[p] = o
            added.discard(p)
            removed.discard(o)
    out: List[Dict[str, Any]] = []

    def base(rel: str, e: Dict[str, Any]) -> Dict[str, Any]:
        lvl, why = src.impact_for(rel)
        return {"path": rel, "kind": e.get("kind"), "impact": lvl, "impact_why": why, "details": []}

    for rel in sorted(added):
        e = nf[rel]
        c = base(rel, e)
        if e.get("placeholder"):
            c.update(type="NEW", impact="LOW", impact_why="placeholder nuevo (estructura sin contenido)", op="A")
        else:
            c.update(type="NEW", op="A", details=[f"archivo nuevo ({e.get('kind')}, estado {e.get('status')})"])
        out.append(c)
    for rel in sorted(removed):
        e = of[rel]
        c = base(rel, e)
        c.update(op="D", type="DEPRECATED" if e.get("kind") in NORMATIVE_KINDS and not e.get("placeholder") else "UPDATED",
                 details=["archivo eliminado"])
        if e.get("placeholder"):
            c.update(impact="LOW", impact_why="se eliminó un placeholder")
        out.append(c)
    for rel, old_rel in sorted(renames.items()):
        c = base(rel, nf[rel])
        c.update(op="R", old_path=old_rel, type="UPDATED", details=[f"renombrado desde `{old_rel}`"],
                 impact=max_impact(c["impact"], "MEDIUM"), impact_why=c["impact_why"] + " · renombre rompe referencias")
        out.append(c)
    for rel in sorted(set(nf) & set(of)):
        o, n = of[rel], nf[rel]
        if o.get("sha") == n.get("sha"):
            continue
        c = base(rel, n)
        det, cosmetic, delta = _detail(o, n, rel)
        c.update(op="M", details=det, type="UPDATED")
        if cosmetic:
            c.update(impact="NONE", impact_why="cambio cosmético (sin cambio de contenido normalizado)")
        elif o.get("placeholder") and not n.get("placeholder"):
            c.update(type="NEW", details=["placeholder completado con contenido"] + det)
        elif n.get("status") == "DEPRECATED" and o.get("status") != "DEPRECATED":
            c.update(type="DEPRECATED")
        elif delta.get("DEPRECATED", 0) > 0 and n.get("kind") in NORMATIVE_KINDS:
            c.update(type="DEPRECATED", details=det + ["se agregan marcas de deprecación"])
        if not cosmetic and delta.get("REQUIRED", 0) > 0 and n.get("kind") in ("official_doc", "standard", "policy"):
            c["impact"] = max_impact(c["impact"], "HIGH")
            c["impact_why"] += " · nuevas exigencias normativas (REQUIRED)"
        vo, vn = o.get("versions") or {}, n.get("versions") or {}
        bumps = [f"{k}: {vo[k]} → {vn[k]}" for k in vn if k in vo and vo[k] != vn[k]]
        if bumps and n.get("kind") in ("standard", "policy", "template"):
            major = any(str(vo[k]).split(".")[0] != str(vn[k]).split(".")[0] for k in vn if k in vo and vo[k] != vn[k])
            c["impact"] = max_impact(c["impact"], "CRITICAL" if major else "HIGH")
            c["impact_why"] += f" · cambio de versión ({'; '.join(bumps[:3])})"
        if o.get("status") != n.get("status"):
            c["details"].append(f"estado normativo {o.get('status')} → {n.get('status')}")
        out.append(c)
    am = _archimate_changes(old or {}, new)
    if am:
        for c in out:
            if c["path"].startswith("model/"):
                c["details"] = c["details"] or ["cambio en el modelo"]
        out.append({"path": "model/ (ArchiMate)", "kind": "archimate", "op": "M", "type": "UPDATED",
                    "impact": "HIGH" if any(d.startswith(("vista", "elementos eliminados")) for d in am) else "MEDIUM",
                    "impact_why": "cambio en el modelo ArchiMate aprobado (main)", "details": am, "aggregate": True})
    if not main:
        for c in out:
            c["type"] = "UNKNOWN"
            c["impact_why"] += " · rama no principal: señal, no norma"
    return out


# ------------------------------------------------------------------------------------------------ impacto y alertas
@lru_cache(maxsize=1)
def _catalog_sources() -> Tuple[Tuple[str, str], ...]:
    from govkit.engine import load_catalog
    return tuple((r.id, str((r.source or {}).get("doc", ""))) for r in load_catalog()["_rules"])


def _rules_citing(basename: str) -> List[str]:
    return [rid for rid, doc in _catalog_sources() if basename and doc.endswith(basename)]


def _kb_citing(basename: str) -> List[str]:
    from govkit.kb import store
    return [c.id for c in store.load().chunks.values()
            if basename and any(basename in str(s) for s in c.meta.get("sources") or [])]


def _notes_citing(needles: List[str]) -> List[int]:
    try:
        from govkit import notes
        return [n["id"] for n in notes.all_notes() if any(x and x in str(n.get("body", "")) for x in needles)]
    except Exception:  # noqa: BLE001 - notas opcionales
        return []


def stale(changes: List[Dict[str, Any]], src: registry.Source) -> Dict[str, List[str]]:
    """Análisis posiblemente obsoletos: reglas y mini-contextos cuya fuente cambió, notas que la citan."""
    rules, kb, notes_ids = set(), set(), set()
    for c in changes:
        if c["impact"] == "NONE":
            continue
        base = c["path"].rsplit("/", 1)[-1]
        if src.id == "governance" or base in (src.documents or []):
            rules.update(_rules_citing(base))
            kb.update(_kb_citing(base))
        for cm in summaries.curated_for(src.id, c["path"]):
            kb.update(cm.get("kb") or [])
        notes_ids.update(_notes_citing([c["path"], base] if len(base) > 8 else [c["path"]]))
    return {"rules": sorted(rules), "kb": sorted(kb), "notes": [f"#{n}" for n in sorted(notes_ids)]}


def _group(changes: List[Dict[str, Any]], idx: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in changes:
        unit = c["path"] if c.get("aggregate") else summaries.unit_for(idx, c["path"]) or c["path"]
        groups[unit].append(c)
    return groups


def _follow_up(src: registry.Source, unit: str, items: List[Dict[str, Any]], conflicts: List[Dict[str, Any]],
               rules: List[str]) -> List[str]:
    types = {c["type"] for c in items}
    kinds = {c.get("kind") for c in items}
    out = []
    if "CONFLICTING" in types or conflicts:
        out += [f"Revisar {c['id']} ({c['state']}): {c.get('confirm')}" for c in conflicts[:3]]
    if "DEPRECATED" in types:
        out.append("Buscar dependientes de lo eliminado/deprecado (`govkit arch contexto`) y actualizar referencias.")
    if kinds & {"standard", "template", "ci"}:
        out.append("Correr `govkit lint` en tus Data Products para ver el impacto (reglas GOV-PCX-* leen el estándar).")
        out.append("Evaluar si corresponde un ADR (Potential ADR): cambio de estándar sin decisión registrada.")
    if kinds & {"official_doc", "policy"} and types & {"NEW", "UPDATED"}:
        out.append("Revisar si el cambio introduce/modifica criterios: `govkit verificar` y mini-contextos KB relacionados.")
    if rules:
        out.append(f"Revisar reglas govkit relacionadas (posible obsolescencia): {', '.join(rules[:8])}.")
    if "UNKNOWN" in types:
        out.append("Seguir la rama: es una propuesta, no norma, hasta que se fusione en main.")
    return out or ["Sin acción requerida más allá de conocer el cambio."]


def alerts(changes: List[Dict[str, Any]], old: Optional[Dict[str, Any]], new: Dict[str, Any], src: registry.Source,
           fact_changes: List[Dict[str, Any]], min_impact: str = "LOW") -> List[Dict[str, Any]]:
    from govkit.arch import adr as A
    out = []
    conflicts_all = F.conflict_states(None)
    fact_paths = {f.get("path"): f for f in F.registry_facts() if f.get("source") == src.id}
    changed_fact_ids = {f["id"] for f in fact_changes}
    for unit, items in _group(changes, new).items():
        impact = "NONE"
        for c in items:
            impact = max_impact(impact, c["impact"])
        related_conf = []
        for c in items:
            f = fact_paths.get(c["path"])
            if f and f["id"] in changed_fact_ids:
                c["type"] = "CONFLICTING"
                impact = max_impact(impact, "HIGH")
            related_conf += [x for x in conflicts_all if f and f["id"] in (x.get("facts") or [])]
        cur = summaries.curated_for(src.id, unit)
        ids = {i for cm in cur for i in cm.get("conflicts") or []}
        related_conf += [x for x in conflicts_all if x["id"] in ids]
        related_conf = list({x["id"]: x for x in related_conf}.values())
        if IMPACT_RANK[impact] < IMPACT_RANK[min_impact] and not any(c["type"] == "CONFLICTING" for c in items):
            continue
        base_names = {c["path"].rsplit("/", 1)[-1] for c in items}
        rules = sorted({r for b in base_names for r in (_rules_citing(b) if src.id == "governance" else [])}
                       | {r for cm in cur for r in cm.get("rules") or []}
                       | {r for x in related_conf for r in x.get("rules") or []})
        adrs, pots = A.for_path(src.id, unit)
        repos = sorted({s["source"] for cm in cur for s in cm.get("see") or [] if s["source"] != src.id})
        from govkit.arch.summaries import context_map
        repos += [r["to"] for r in context_map().get("relations") or [] if r["from"] == src.id]
        repos = list(dict.fromkeys(repos))
        std = sorted({f"{s['source']}:{s['path']}" for cm in cur for s in cm.get("see") or []
                      if re.search(r"specs|docs|schema|standard|policies", s["path"])})[:6]
        types = sorted({c["type"] for c in items}, key=["CONFLICTING", "DEPRECATED", "NEW", "UPDATED", "UNKNOWN"].index)
        oc = str((old or {}).get("meta", {}).get("commit") or "—")[:12]
        ncm = str(new["meta"].get("commit") or "?")[:12]
        what = []
        for c in items[:12]:
            d = "; ".join(c["details"][:3]) if c["details"] else ""
            what.append(f"[{c['type']}/{c['op']}] {c['path']}" + (f" — {d}" if d else ""))
        if len(items) > 12:
            what.append(f"… y {len(items) - 12} archivo(s) más")
        why = sorted({c["impact_why"] for c in items if c["impact"] == impact})
        out.append({
            "repository": new["meta"]["repo"], "source": src.id, "path": unit,
            "previous_commit": oc, "current_commit": ncm, "change_type": types, "impact": impact,
            "impact_why": "; ".join(why)[:400],
            "affected_components": sorted({summaries.unit_for(new, c["path"]) or c["path"] for c in items})[:8]
            + ([f"reglas govkit: {', '.join(rules[:10])}"] if rules else []),
            "affected_repositories": repos or [NOT_DETERMINED],
            "relevant_adrs": [f"{a['id']} ({a['trace']})" for a in adrs] + [f"Potential {p['id']}: {p['decision']}" for p in pots]
            or ["ninguno registrado"],
            "relevant_standards": std or [NOT_DETERMINED],
            "what_changed": what,
            "why_it_matters": (f"{summaries.KIND_LABEL.get(items[0].get('kind'), items[0].get('kind'))} con impacto {impact}: "
                               + "; ".join(why)[:300]
                               + ("" if not related_conf else " · afecta contradicciones: "
                                  + ", ".join(f"{x['id']}" for x in related_conf))),
            "follow_up": _follow_up(src, unit, items, related_conf, rules),
            "evidence": [f"{new['meta']['repo']}@{oc[:7]}..{ncm[:7]}:{c['path']}" for c in items[:6]],
            "items": items,
        })
    out.sort(key=lambda a: -IMPACT_RANK[a["impact"]])
    return out


def render_alert(a: Dict[str, Any]) -> str:
    def j(xs: List[str]) -> str:
        return "\n".join(f"  - {x}" for x in xs) if xs else "  - —"
    return (f"## ARCHITECTURAL CHANGE DETECTED\n\nRepository: {a['repository']}\nPath: {a['path']}\n"
            f"Previous commit: {a['previous_commit']}\nCurrent commit: {a['current_commit']}\n\n"
            f"Change type: {', '.join(a['change_type'])}\n\n"
            f"Architectural impact: {a['impact']} — {a['impact_why']}\n\n"
            f"Affected components:\n{j(a['affected_components'])}\n\nAffected repositories:\n{j(a['affected_repositories'])}\n\n"
            f"Relevant ADRs:\n{j(a['relevant_adrs'])}\n\nRelevant standards:\n{j(a['relevant_standards'])}\n\n"
            f"What changed:\n{j(a['what_changed'])}\n\nWhy it matters:\n  {a['why_it_matters']}\n\n"
            f"Recommended follow-up:\n{j(a['follow_up'])}\n\nEvidence:\n{j(a['evidence'])}\n")


# ------------------------------------------------------------------------------------------------ comparación completa
def compare(old: Optional[Dict[str, Any]], new: Dict[str, Any], src: registry.Source,
            repo_path: Optional[Path] = None, min_impact: str = "MEDIUM") -> Dict[str, Any]:
    changes = diff(old, new, src)
    indexes_old = dict(I.all_current())
    if old is not None:
        indexes_old[src.id] = old
    indexes_new = dict(I.all_current())
    indexes_new[src.id] = new
    fo = F.evaluate_all(indexes_old) if old is not None else {}
    fn = F.evaluate_all(indexes_new)
    fact_changes = []
    for fid, r in fn.items():
        prev = fo.get(fid)
        if prev is not None and prev["holds"] != r["holds"] and any(
                f["id"] == fid and f.get("source") in (src.id, None) for f in F.registry_facts()):
            fact_changes.append({"id": fid, "statement": r["statement"], "before": prev["holds"], "after": r["holds"],
                                 "detail": r["detail"], "trace": r["trace"]})
    al = alerts(changes, old, new, src, fact_changes, min_impact) if old is not None else []
    commits = []
    if repo_path and old is not None and old["meta"].get("commit") and new["meta"].get("commit") and \
            gitio.resolve(repo_path, str(old["meta"]["commit"])):
        commits = gitio.log_between(repo_path, str(old["meta"]["commit"]), str(new["meta"]["commit"]))
    return {"source": src.id, "repo": src.repo, "previous": (old or {}).get("meta", {}), "current": new["meta"],
            "files_analyzed": len(new["files"]),
            "first_ingest": old is None, "changes": changes, "alerts": al, "fact_changes": fact_changes,
            "stale": stale(changes, src) if old is not None else {"rules": [], "kb": [], "notes": []}, "commits": commits,
            "conflicts": [{"id": c["id"], "state": c["state"], "title": c["title"]} for c in F.conflict_states(indexes_new, fn)]}


def knowledge_update(rep: Dict[str, Any]) -> str:
    """Changelog arquitectónico (SUPER PROMPT §24)."""
    ch = rep["changes"]
    new_k = [c for c in ch if c["type"] == "NEW" and c["impact"] != "NONE"]
    upd = [c for c in ch if c["type"] in ("UPDATED", "UNKNOWN", "CONFLICTING") and c["impact"] != "NONE"]
    dep = [c for c in ch if c["type"] == "DEPRECATED"]
    impact = "NONE"
    for c in ch:
        impact = max_impact(impact, c["impact"])

    def lst(xs: List[Dict[str, Any]]) -> str:
        return "\n".join(f"  - {c['path']}" + (f" [{c['type']}]" if c["type"] in ("CONFLICTING", "UNKNOWN") else "")
                         + (f" — {'; '.join(c['details'][:2])}" if c["details"] else "") for c in xs[:25]) \
            or "  - —"
    prev = rep["previous"]
    st = rep["stale"]
    adr_impact = sorted({x for a in rep["alerts"] for x in a["relevant_adrs"] if x != "ninguno registrado"})
    docs = [c["path"] for c in ch if c.get("kind") in ("official_doc", "repo_doc", "policy") and c["impact"] != "NONE"]
    lines = [
        "ARCHITECTURAL KNOWLEDGE UPDATE", "",
        f"Repository: {rep['repo']}",
        f"Previous commit: {str(prev.get('commit') or '— (primera ingesta)')[:12]} {prev.get('commit_date') or ''}".rstrip(),
        f"New commit: {str(rep['current'].get('commit') or '?')[:12]} {rep['current'].get('commit_date') or ''}".rstrip(),
        "", f"Files analyzed: {rep.get('files_analyzed', '?')} (cambiados: {len(ch)})",
        "", "New knowledge:", lst(new_k), "", "Changed knowledge:", lst(upd), "", "Deprecated knowledge:", lst(dep), "",
        "Potential conflicts:",
        "\n".join(f"  - {f['id']}: {f['statement']} ({f['before']} → {f['after']}) — {f['trace']}" for f in rep["fact_changes"])
        or "  - ninguno nuevo", "",
        "ADR impact:", "\n".join(f"  - {x}" for x in adr_impact) or "  - ninguno", "",
        "Documentation impact:", "\n".join(f"  - {d}" for d in docs[:15]) or "  - ninguno", "",
        f"Architecture impact: {impact}", "",
        "Analysis rules affected:", f"  - reglas: {', '.join(st['rules']) or '—'}", f"  - KB: {', '.join(st['kb']) or '—'}",
        f"  - notas guardadas: {', '.join(st['notes']) or '—'}", "",
        "Recommended next action:",
        "\n".join(f"  - {x}" for x in sorted({f for a in rep["alerts"] for f in a["follow_up"]})[:8])
        or "  - Sin acción: el conocimiento quedó actualizado.",
    ]
    if rep.get("commits"):
        lines += ["", "Commits:"] + [f"  - {c['commit'][:7]} {c['date'][:10]} {c['subject'][:90]}" for c in rep["commits"][:20]]
    return "\n".join(lines) + "\n"


def write_changelog(rep: Dict[str, Any]) -> Path:
    d = home() / "changes"
    d.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    prev = str(rep["previous"].get("commit") or "inicio")[:7]
    cur = str(rep["current"].get("commit") or "?")[:7]
    p = d / f"{stamp}-{rep['source']}-{prev}..{cur}.md"
    body = knowledge_update(rep)
    if rep["alerts"]:
        body += "\n" + "\n".join(render_alert(a) for a in rep["alerts"])
    p.write_text(body, encoding="utf-8")
    slim = {k: v for k, v in rep.items() if k not in ("previous", "current")}
    slim["previous_commit"], slim["current_commit"] = rep["previous"].get("commit"), rep["current"].get("commit")
    for a in slim.get("alerts", []):
        a.pop("items", None)
    p.with_suffix(".json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def list_changelogs(limit: int = 20) -> List[Path]:
    d = home() / "changes"
    return sorted(d.glob("*.md"), reverse=True)[:limit] if d.exists() else []


# ------------------------------------------------------------------------------------------------ ramas señal
def branch_signals(src: registry.Source, state_src: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    path = src.path
    branches = gitio.remote_branches(path)
    known: Dict[str, str] = state_src.get("branches") or {}
    now = {b["name"]: b["commit"] for b in branches}
    out = []
    main_ref = f"origin/{src.branch}"
    for b in branches:
        if b["name"] == src.branch or not src.is_signal_branch(b["name"]):
            continue
        if known.get(b["name"]) == b["commit"]:
            continue
        status = "nueva" if b["name"] not in known else "actualizada"
        files: List[Tuple[str, str, Optional[str]]] = []
        try:
            files = _branch_files(path, main_ref, b["name"])
        except gitio.GitError:
            pass
        impact = "NONE"
        for _, rel, _ in files:
            impact = max_impact(impact, src.impact_for(rel)[0])
        out.append({"branch": b["name"], "status": status, "commit": b["commit"][:12], "date": b["date"],
                    "files": [f"{s} {r}" for s, r, _ in files[:10]], "n_files": len(files), "impact": impact,
                    "type": "UNKNOWN", "note": "propuesta en curso (no es norma hasta fusionarse en main)"})
    return out, now


def _branch_files(path: Path, main_ref: str, branch: str) -> List[Tuple[str, str, Optional[str]]]:
    base = gitio.git(path, "merge-base", main_ref, f"origin/{branch}").strip()
    return gitio.diff_name_status(path, base, f"origin/{branch}")


# ------------------------------------------------------------------------------------------------ sync
def sync(source_ids: Optional[List[str]] = None, fetch: bool = True, min_impact: str = "MEDIUM",
         write: bool = True) -> List[Dict[str, Any]]:
    reports = []
    srcs = [registry.get(s) for s in source_ids] if source_ids else list(registry.sources().values())
    for src in srcs:
        rep: Dict[str, Any] = {"source": src.id, "repo": src.repo, "path": str(src.path)}
        if not gitio.is_repo(src.path):
            rep["skipped"] = (f"sin clon git en {src.path} (clona el repo o `govkit arch config {src.id} <ruta>`; "
                              f"alternativa: `govkit arch ingest --snapshot <archivo.txt>`)")
            reports.append(rep)
            continue
        st = gitio.status(src.path)
        rep["working_tree"] = {"clean": st.get("clean"), "changes": [f"{x} {p}" for x, p in st.get("changes", [])],
                               "branch": st.get("branch_line")}
        if fetch:
            ok, msg = gitio.fetch(src.path)
            rep["fetch"] = "ok" if ok else f"falló: {msg[:200]} (se usa lo último descargado)"
        ref, _ = ingest.default_ref(src)
        new_commit = gitio.resolve(src.path, ref)
        state = load_state()
        s_state = state["sources"].get(src.id) or {}
        signals, branches_now = branch_signals(src, s_state)
        rep["signals"] = signals
        old = I.load(src.id)
        rep["ref"] = ref
        if old is not None and str(old["meta"].get("commit")) == str(new_commit) and old["meta"].get("origin") == "git":
            rep["up_to_date"] = True
            rep["commit"] = new_commit
        else:
            new = ingest.ingest_git(src, ref)
            rep.update(compare(old, new, src, repo_path=src.path, min_impact=min_impact))
            if write:
                rep["changelog"] = str(write_changelog(rep))
        state = load_state()
        state["sources"].setdefault(src.id, {})["branches"] = branches_now
        state["sources"][src.id]["synced_at"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
        save_state(state)
        if st.get("changes"):
            rep["pull_advice"] = _pull_advice(src, st, ref)
        reports.append(rep)
    return reports


def _pull_advice(src: registry.Source, st: Dict[str, Any], ref: str) -> str:
    changes = ", ".join(f"{x.strip()} {p}" for x, p in st["changes"][:5])
    return (f"Working tree con cambios locales ({changes}). govkit NO hace pull: el análisis usa `{ref}` sin tocar tus "
            f"archivos. Si quieres actualizar tu copia, revisa antes esos cambios (p.ej. .github/setup.js borrado por "
            f"la vacuna Miasma: NO lo restaures) y confírmalo con Seguridad.")


def ingest_snapshot_with_diff(path: Path, min_impact: str = "MEDIUM", write: bool = True) -> Dict[str, Any]:
    """Snapshot .txt nuevo → compara contra el índice vigente de esa fuente (actualización incremental sin git)."""
    from govkit.arch.readers import SnapshotReader
    reader = SnapshotReader(path)
    src = registry.find(str(reader.meta.get("repo")))
    if not src:
        raise KeyError(f"El snapshot es de `{reader.meta.get('repo')}`, que no está registrado")
    old = I.load(src.id)
    new = ingest.ingest_snapshot(path)
    if old is not None and old["meta"].get("commit") == new["meta"].get("commit") and \
            all(old["files"].get(k, {}).get("sha") == v.get("sha") for k, v in new["files"].items()):
        return {"source": src.id, "repo": src.repo, "up_to_date": True, "commit": new["meta"].get("commit")}
    rep = compare(old, new, src, min_impact=min_impact)
    if write:
        rep["changelog"] = str(write_changelog(rep))
    return rep
