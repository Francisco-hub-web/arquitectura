"""Validación de trazabilidad de govkit contra las fuentes reales (`govkit arch trazabilidad`).

Cada regla (`source.doc`) y cada mini-contexto KB (`sources`) debe apuntar a un documento que exista en governance;
las que citan `lineamientos/*` quedan con procedencia DESCONOCIDA (no versionados en los repos corporativos, C-14).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from govkit.arch import index as I
from govkit.arch import registry

_DOC = re.compile(r"(\d{2}(?:\.\d)?-[\w.-]+\.md)")


def known_documents() -> Dict[str, str]:
    """{nombre: origen} — del índice de governance si está ingerido; si no, del registro (arch_sources.yaml)."""
    gov = registry.get("governance")
    idx = I.load("governance")
    if idx:
        return {rel.rsplit("/", 1)[-1]: I.trace(idx, rel) for rel in idx["files"] if _DOC.fullmatch(rel.rsplit("/", 1)[-1])}
    return {d: "registro arch_sources.yaml (sin índice)" for d in gov.documents}


def check() -> Dict[str, Any]:
    from govkit.engine import load_catalog
    from govkit.kb import store
    docs = known_documents()
    by_prefix = {d.split("-", 1)[0]: d for d in docs}
    unknown, external, ok, corp_unverified = [], [], 0, []
    for r in load_catalog()["_rules"]:
        doc = str((r.source or {}).get("doc") or "")
        if not doc:
            continue
        if doc.startswith("lineamientos/"):
            external.append({"id": r.id, "doc": doc})
            continue
        if doc.startswith("global-"):
            src_name, _, rel = doc.partition("/")
            src = registry.find(src_name)
            idx = I.load(src.id) if src else None
            if idx is None:
                corp_unverified.append({"id": r.id, "doc": doc})
            elif rel in idx["files"]:
                ok += 1
            else:
                unknown.append({"id": r.id, "doc": doc, "suggest": None})
            continue
        name = doc.rsplit("/", 1)[-1]
        if name in docs:
            ok += 1
        else:
            unknown.append({"id": r.id, "doc": doc, "suggest": by_prefix.get(name.split("-", 1)[0])})
    kb_bad = []
    for c in store.load().chunks.values():
        for s in c.meta.get("sources") or []:
            for m in _DOC.finditer(str(s)):
                if m.group(1) not in docs:
                    kb_bad.append({"id": c.id, "doc": m.group(1), "suggest": by_prefix.get(m.group(1).split("-", 1)[0])})
    return {"documents": len(docs), "origin": "índice" if I.load("governance") else "registro",
            "rules_ok": ok, "rules_unknown_doc": unknown, "rules_external": external, "kb_unknown_doc": kb_bad,
            "rules_corp_unverified": corp_unverified}


def render(res: Dict[str, Any]) -> str:
    L = [f"Trazabilidad de govkit contra governance ({res['documents']} documentos, fuente: {res['origin']})",
         f"- Reglas con fuente verificada: {res['rules_ok']}"]
    if res["rules_unknown_doc"]:
        L.append(f"- ✘ Reglas que citan un documento que NO existe ({len(res['rules_unknown_doc'])}):")
        L += [f"    {x['id']}: {x['doc']}" + (f" → ¿{x['suggest']}?" if x.get("suggest") else "") for x in res["rules_unknown_doc"]]
    if res["kb_unknown_doc"]:
        L.append(f"- ✘ Mini-contextos KB que citan un documento inexistente ({len(res['kb_unknown_doc'])}):")
        L += [f"    {x['id']}: {x['doc']}" + (f" → ¿{x['suggest']}?" if x.get("suggest") else "") for x in res["kb_unknown_doc"]]
    ext = res["rules_external"]
    if ext:
        docs = sorted({x["doc"] for x in ext})
        L.append(f"- ? Procedencia DESCONOCIDA (lineamientos fuera de los repos, C-14): {len(ext)} reglas · {', '.join(docs)}")
    if res.get("rules_corp_unverified"):
        L.append(f"- ? {len(res['rules_corp_unverified'])} regla(s) citan repos corporativos no ingeridos "
                 "(govkit arch sync/ingest para verificarlas)")
    if not res["rules_unknown_doc"] and not res["kb_unknown_doc"]:
        L.append("- ✔ Todas las citas a documentos del framework resuelven a un archivo real.")
    return "\n".join(L) + "\n"
