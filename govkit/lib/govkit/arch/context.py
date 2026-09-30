"""Architecture Context Map: "para analizar correctamente esta ruta revisa también A, B, C… porque…" (§7, §16, §18).

Acepta:
  · rutas corporativas: `global-data-platform-core/framework/x`, `PC:framework/x` o una ruta absoluta dentro de un
    clon registrado;
  · rutas de un repo de Data Product (absolutas o relativas al cwd): `contracts/gold/fact/x.yaml`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from govkit.arch import NOT_DETERMINED
from govkit.arch import facts as F
from govkit.arch import graph as G
from govkit.arch import index as I
from govkit.arch import registry, summaries
from govkit.arch.registry import gmatch


def resolve_target(target: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    cwd = Path(cwd or os.getcwd())
    t = target.strip()
    m = re.match(r"^([A-Za-z]{2,4}|global-[a-z0-9-]+):?/(.*)$", t) or re.match(r"^([A-Za-z]{2,4}):(.*)$", t)
    if m:
        src = registry.find(m.group(1))
        if src:
            return {"mode": "corp", "source": src, "rel": m.group(2).strip("/")}
    if re.match(r"^global-[a-z0-9-]+$", t):
        src = registry.find(t)
        if src:
            return {"mode": "corp", "source": src, "rel": ""}
    p = Path(os.path.expanduser(t))
    p = p if p.is_absolute() else (cwd / p)
    hit = registry.source_for_path(p)
    if hit:
        return {"mode": "corp", "source": hit[0], "rel": hit[1]}
    from govkit.arch import gitio
    base = p if p.is_dir() else p.parent
    while not base.exists() and base != base.parent:
        base = base.parent
    top = gitio.toplevel(base) if base.exists() else None
    if top is None:  # sin git: carpeta con nombre *-dp-XX o que contenga contracts/ o metadata/
        for anc in [base, *base.parents]:
            if re.search(r"-dp-[a-z]{2,3}$", anc.name) or (anc / "contracts").is_dir() or (anc / "metadata").is_dir():
                top = anc
                break
    root = top or cwd
    try:
        rel = p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = t.strip("/")
    return {"mode": "dp", "root": root, "rel": "" if rel == "." else rel, "repo": root.name}


def _see_item(item: Dict[str, str], indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    src = registry.find(item.get("source"))
    out = {"source": item.get("source"), "path": item.get("path"), "why": item.get("why", ""), "exists": None,
           "trace": f"{src.repo if src else item.get('source')}:{item.get('path')}", "status": None}
    if not src:
        return out
    idx = indexes.get(src.id)
    if idx is None:
        out["trace"] += " (fuente no ingerida)"
        return out
    rel = str(item.get("path") or "").strip("/")
    files = I.files_under(idx, rel)
    out["exists"] = bool(files)
    out["trace"] = f"{idx['meta']['repo']}@{str(idx['meta'].get('commit') or '?')[:7]}:{rel}"
    if files:
        sts = {idx["files"][f]["status"] for f in files}
        out["status"] = next((s for s in ("REQUIRED", "APPROVED", "RECOMMENDED", "IMPLEMENTED", "DEPRECATED", "UNKNOWN")
                              if s in sts), None)
        if all(idx["files"][f].get("placeholder") for f in files):
            out["status"] = "UNKNOWN"
            out["why"] += " [solo placeholders]"
    else:
        out["why"] += " [NO EXISTE en el commit indexado]"
    return out


def _status_of(indexes: Dict[str, Dict[str, Any]], ref: Dict[str, Any]) -> Optional[str]:
    idx = indexes.get(ref.get("source") or "")
    e = idx["files"].get(ref.get("path") or "") if idx else None
    return e["status"] if e else None


def _kb_for(rel: str) -> List[Tuple[str, str]]:
    from govkit.kb import store
    out = []
    for c in store.load().chunks.values():
        for g in ((c.meta.get("triggers") or {}).get("paths") or []):
            if gmatch(g, rel):
                out.append((c.id, c.title))
                break
    return out


def _rule_globs(raw: Dict[str, Any], artifacts: Dict[str, List[str]]) -> List[str]:
    out: List[str] = []
    chk = raw.get("check") or {}
    for key in ("all", "any", "globs"):
        v = chk.get(key)
        out += [v] if isinstance(v, str) else list(v or [])
    for pat in chk.get("patterns") or []:
        if isinstance(pat, dict) and pat.get("glob"):
            out.append(pat["glob"])
    for key in ("target",):
        if chk.get(key):
            out += artifacts.get(chk[key], [])
    req = raw.get("requires") or {}
    if req.get("artifact"):
        out += artifacts.get(req["artifact"], [])
    g = req.get("glob")
    out += [g] if isinstance(g, str) else list(g or [])
    return [x.rstrip("/") + ("/**" if x.endswith("/") else "") for x in out if isinstance(x, str)]


def _rules_for(rel: str, standard: str) -> List[Tuple[str, str]]:
    from govkit.engine import load_catalog
    cat = load_catalog()
    arts = cat.get("artifacts") or {}
    out = []
    for r in cat["_rules"]:
        stds = r.raw.get("standards")
        if stds and standard not in stds:
            continue
        if r.pack != "dp":
            continue
        if any(gmatch(g, rel) for g in _rule_globs(r.raw, arts)):
            out.append((r.id, r.title))
    return out


def context(target: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
    tgt = resolve_target(target, cwd)
    indexes = I.all_current()
    if tgt["mode"] == "corp":
        return _corp_context(tgt["source"], tgt["rel"], indexes)
    return _dp_context(tgt["root"], tgt["rel"], tgt["repo"], indexes)


def _corp_context(src: registry.Source, rel: str, indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    idx = indexes.get(src.id)
    out: Dict[str, Any] = {"mode": "corp", "target": f"{src.repo}/{rel}".rstrip("/"), "source": src.id, "rel": rel}
    if idx is None:
        out["error"] = (f"{NOT_DETERMINED}: la fuente {src.repo} no está ingerida. Ejecuta `govkit arch sync` (con el "
                        f"clon en {src.path}) o `govkit arch ingest --snapshot <archivo.txt>`.")
        return out
    edges = G.current()
    unit = summaries.unit_for(idx, rel)
    out["summary"] = summaries.summarize(idx, unit, edges)
    entry = idx["files"].get(rel)
    if entry:
        out["file"] = {"trace": I.trace(idx, rel), "status": entry["status"], "label": entry["label"],
                       "kind": entry["kind"], "title": entry.get("title"), "draft": entry.get("draft"),
                       "placeholder": entry.get("placeholder"), "sections": [
                           {"t": s["t"], "line": s["line"], "status": s["status"]} for s in (entry.get("sections") or [])][:25]}
    elif rel and not I.files_under(idx, rel):
        out["warning"] = f"`{rel}` no existe en {I.trace(idx, '')}"
    see: List[Dict[str, Any]] = []
    for cm in summaries.curated_for(src.id, rel or unit):
        see += [_see_item(s, indexes) for s in cm.get("see") or []]
    nb = G.neighbors(edges, src.id, rel or unit)
    derived: List[Dict[str, Any]] = []
    for e in nb["out"]:
        if e["type"] in ("reference", "index", "mirror", "reference_unverified"):
            d = e["dst"]
            didx = indexes.get(d.get("source") or "")
            tr = I.trace(didx, d.get("path") or "") if didx else f"{d.get('source')}:{d.get('path')}"
            why = ("copia espejo (mismo contenido)" if e["type"] == "mirror" else
                   f"citado en {e['src']['path']}" + (f":{e['src']['line']}" if e['src'].get('line') else "")
                   + (" (no verificable en el índice)" if e["type"] == "reference_unverified" else ""))
            derived.append({"source": d.get("source"), "path": d.get("path"), "why": why, "trace": tr,
                            "exists": e["type"] != "reference_unverified", "status": _status_of(indexes, d)})
    for e in nb["in"]:
        if e["type"] in ("reference", "index", "mirror"):
            sidx = indexes.get(e["src"]["source"])
            derived.append({"source": e["src"]["source"], "path": e["src"]["path"],
                            "why": "copia espejo (mismo contenido)" if e["type"] == "mirror" else
                            f"depende de esta ruta (la referencia en L{e['src'].get('line') or '?'})",
                            "trace": I.trace(sidx, e["src"]["path"]) if sidx else e["src"]["path"], "exists": True,
                            "status": _status_of(indexes, e["src"])})
    see += derived[:14]
    out["see"] = _dedupe(see)[:25]
    out["broken"] = [e["evidence"] for e in nb["out"] if e["type"] == "reference_broken"][:10]
    out["divergent"] = [e["evidence"] for e in nb["out"] + nb["in"] if e["type"] == "duplicate_divergent"]
    fr = F.evaluate_all(indexes)
    out["facts"] = [r for fid, r in fr.items() if any(
        f.get("id") == fid and f.get("source") == src.id and (f.get("path") or "").startswith(rel or unit)
        for f in F.registry_facts())]
    ids = sorted({c for cm in summaries.curated_for(src.id, rel or unit) for c in cm.get("conflicts") or []})
    states = {c["id"]: c for c in F.conflict_states(indexes, fr)}
    out["conflicts"] = [states[c["id"]] for c in F.conflicts_for(ids=ids) + F.conflicts_for(source=src.id, corp_rel=rel or unit)
                        if c["id"] in states]
    out["conflicts"] = list({c["id"]: c for c in out["conflicts"]}.values())
    from govkit.arch import adr as A
    out["adrs"], out["potential_adrs"] = A.for_path(src.id, rel or unit)
    out["impact_if_changes"] = src.impact_for(rel or unit)
    return out


def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, res = set(), []
    for it in items:
        key = (it.get("source"), (it.get("path") or "").rstrip("/"))
        if key in seen or not it.get("path"):
            continue
        seen.add(key)
        res.append(it)
    return res


def _dp_context(root: Path, rel: str, repo: str, indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    from govkit import standards
    std, why = standards.detect(root) if root.exists() else ("lineamientos", "repo no encontrado")
    out: Dict[str, Any] = {"mode": "dp", "target": f"{repo}/{rel}".rstrip("/"), "repo": repo, "rel": rel,
                           "root": str(root), "standard": std, "standard_reason": why,
                           "exists": (root / rel).exists() if rel else root.exists()}
    see: List[Dict[str, Any]] = []
    kb: List[str] = []
    ids: List[str] = []
    for dpm in summaries.context_map().get("dp_paths") or []:
        if gmatch(dpm["glob"], rel or "README.md") or (dpm["glob"].endswith("/**") and
                                                       (rel + "/").startswith(dpm["glob"][:-2])):
            see += [_see_item(s, indexes) for s in dpm.get("see") or []]
            kb += dpm.get("kb") or []
            ids += dpm.get("conflicts") or []
    out["see"] = _dedupe(see)[:20]
    out["kb"] = list(dict.fromkeys(kb)) + [k for k, _ in _kb_for(rel) if k not in kb]
    out["rules"] = _rules_for(rel, std)[:30] if rel else []
    fr = F.evaluate_all(indexes) if indexes else {}
    states = {c["id"]: c for c in F.conflict_states(indexes, fr)} if indexes else {}
    cs = F.conflicts_for(ids=ids) + F.conflicts_for(dp_rel=rel)
    out["conflicts"] = [states.get(c["id"], dict(c, state=NOT_DETERMINED)) for c in {c["id"]: c for c in cs}.values()]
    am = indexes.get("archimate")
    if am is not None:
        from govkit.arch import archimate
        found = archimate.find_dp(am, repo)
        out["archimate"] = {"found": bool(found["dp"]), "similar": found["similar"],
                            "trace": I.trace(am, found["dp"]["folder"]) if found["dp"] else None,
                            "views": found["dp"]["view_names"] if found["dp"] else [],
                            "levels": found["dp"]["declared_levels"] if found["dp"] else []}
    else:
        out["archimate"] = {"found": None, "note": f"{NOT_DETERMINED}: modelo ArchiMate no ingerido"}
    from govkit.arch import adr as A
    local = A.repo_adrs(root) if root.exists() else []
    out["adrs"] = [a for a in local if not rel or any(rel in r or r in rel for r in a.get("refs") or [])] or local[:5]
    out["ingested"] = sorted(indexes)
    return out


# ------------------------------------------------------------------------------------------------ render
def render(ctx: Dict[str, Any]) -> str:
    L: List[str] = []
    if ctx.get("error"):
        return ctx["error"] + "\n"
    L.append(f"## Contexto · `{ctx['target']}`")
    if ctx["mode"] == "dp":
        L.append(f"Repo de Data Product · estándar **{ctx['standard']}** ({ctx['standard_reason']})"
                 + ("" if ctx.get("exists") else " · ⚠️ la ruta no existe en el repo"))
    else:
        s = ctx["summary"]
        f = ctx.get("file")
        if f:
            L.append(f"Archivo · {f['kind']} · estado **{f['status']}** · [{f['label']}] · {f['trace']}"
                     + (" · BORRADOR" if f.get("draft") else "") + (" · PLACEHOLDER" if f.get("placeholder") else ""))
        if ctx.get("warning"):
            L.append(f"⚠️ {ctx['warning']}")
        lvl, why = ctx["impact_if_changes"]
        L.append(f"Impacto si cambia: **{lvl}** ({why})")
        L.append("")
        L.append(summaries.render(s))
    L.append("### Para analizar correctamente esta ruta revisa también")
    if not ctx.get("see"):
        L.append(f"- {NOT_DETERMINED}: sin relaciones registradas ni derivadas para esta ruta.")
    for i, it in enumerate(ctx.get("see") or [], 1):
        st = f" · {it['status']}" if it.get("status") else ""
        ex = "" if it.get("exists") is not False else " · ⚠️ no existe"
        L.append(f"{i}. `{it['trace']}`{st}{ex} — {it['why']}")
    if ctx.get("kb"):
        L.append(f"- Conocimiento govkit: {', '.join(ctx['kb'])}")
    if ctx.get("rules"):
        L.append(f"- Reglas que evalúan esta ruta ({len(ctx['rules'])}): " + ", ".join(r for r, _ in ctx["rules"][:15]))
    if ctx["mode"] == "dp":
        am = ctx.get("archimate") or {}
        if am.get("found"):
            L.append(f"- Diseño aprobado en ArchiMate: `{am['trace']}` · vistas: {', '.join(am['views']) or '—'}")
        elif am.get("found") is False:
            L.append(f"- Diseño ArchiMate: {NOT_DETERMINED} (sin carpeta para `{ctx['repo']}`"
                     + (f"; similares: {', '.join(am['similar'])}" if am.get("similar") else "") + ")")
        else:
            L.append(f"- Diseño ArchiMate: {am.get('note')}")
    if ctx.get("broken"):
        L.append("### Referencias rotas desde esta ruta")
        L += [f"- {b}" for b in ctx["broken"]]
    if ctx.get("divergent"):
        L.append("### Duplicados divergentes")
        L += [f"- {d}" for d in ctx["divergent"]]
    if ctx.get("facts"):
        L.append("### Arquitectura esperada (hechos verificados)")
        for r in ctx["facts"]:
            mark = "✔" if r["holds"] else "✘" if r["holds"] is False else "?"
            L.append(f"- {mark} [{r.get('label')}] {r['statement']} ({r.get('status')}) — {r['trace']}")
    if ctx.get("conflicts"):
        L.append("### Contradicciones abiertas que aplican")
        for c in ctx["conflicts"]:
            L.append(f"- **{c['id']}** [{c.get('state', '?')}] {c['title']} — confirmar: {c.get('confirm')}"
                     + (f" · mitigación: {c['mitigation']}" if c.get("mitigation") else ""))
    adrs = ctx.get("adrs") or []
    pots = ctx.get("potential_adrs") or []
    L.append("### ADR")
    L.append("- " + ("; ".join(f"{a['id']} {a['title']} ({a.get('status') or '?'}) — {a['trace']}" for a in adrs)
                     if adrs else "sin ADR que cite esta ruta"))
    for p in pots:
        L.append(f"- Potential ADR **{p['id']}**: {p['decision']} — {p['why']}")
    if ctx["mode"] == "dp" and not ctx.get("ingested"):
        L.append(f"\n⚠️ Ninguna fuente corporativa ingerida: las rutas corporativas no se verificaron "
                 f"(`govkit arch sync` o `govkit arch ingest --snapshot`).")
    return "\n".join(L) + "\n"
