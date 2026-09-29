"""Trazabilidad verificable: de un ID citado (GOV-XXX-NNN, KBnn.Xn, KB_nn) al documento y sección del framework.

Determinista (no depende del LLM): las reglas GOV-* traen `source` en el catálogo; los criterios KB llevan su
referencia al final de la línea — p.ej. `(06 §26)` — y, si no la tienen, se usa la fuente declarada del mini-contexto.
Los números cortos de documento (`06`) se expanden al nombre del archivo (`06-data-product-definition.md`).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional

ID_RX = re.compile(r"\b(GOV-[A-Z]{3}-\d{3}|KB\d{2}\.[RAHVEDG]\d+|KB_\d{2})\b")
_TRAIL = re.compile(r"\(([^()]*)\)\s*$")
_LINE = re.compile(r"^\s*-\s+\*\*(KB\d{2}\.[RAHVEDG]\d+)(?:\s+\[([^\]]+)\])?\*\*\s*(.*)$")


@lru_cache(maxsize=1)
def _catalog():
    from govkit.engine import load_catalog
    return {r.id: r for r in load_catalog()["_rules"]}


@lru_cache(maxsize=1)
def _kb():
    from govkit.kb import store
    return store.load()


@lru_cache(maxsize=1)
def doc_index() -> Dict[str, str]:
    """'06' → '06-data-product-definition.md' a partir de las fuentes de la KB y del catálogo."""
    names: List[str] = []
    for c in _kb().chunks.values():
        names += [str(s) for s in (c.meta.get("sources") or [])]
    names += [str((r.source or {}).get("doc", "")) for r in _catalog().values()]
    index: Dict[str, str] = {}
    for n in names:
        m = re.match(r"^((\d{2})(?:\.\d)?)-[\w.-]+\.md", n.strip())
        if m:
            index.setdefault(m.group(1), m.group(0))
    return index


def _expand(ref: str) -> List[str]:
    """'06 §26, 14 §8.3' → ['06-data-product-definition.md §26', '14-data-consumption-…md §8.3']."""
    out: List[str] = []
    last_doc: Optional[str] = None
    for part in [p.strip() for p in ref.split(",") if p.strip()]:
        m = re.match(r"^(\d{2}(?:\.\d)?)\s*(§.*)?$", part)
        if m:
            last_doc = doc_index().get(m.group(1), m.group(1))
            out.append(f"{last_doc} {m.group(2) or ''}".strip())
        elif part.startswith("§") and last_doc:
            out.append(f"{last_doc} {part}")
        else:
            out.append(part)
    return out


@lru_cache(maxsize=1)
def _kb_lines() -> Dict[str, Dict[str, object]]:
    out: Dict[str, Dict[str, object]] = {}
    for c in _kb().chunks.values():
        for letter, text in c.sections.items():
            for line in text.splitlines():
                m = _LINE.match(line)
                if not m:
                    continue
                body = m.group(3).strip()
                t = _TRAIL.search(body)
                refs: List[str] = []
                if t and ("§" in t.group(1) or re.match(r"^\d{2}\b", t.group(1)) or "Repositorio" in t.group(1)
                          or "IAM" in t.group(1) or "OpenMetadata" in t.group(1)):
                    refs = _expand(t.group(1))
                    body = body[: t.start()].strip()
                general = [x for src in (c.meta.get("sources") or []) for x in _expand(str(src))]
                out[m.group(1)] = {"text": body, "strength": m.group(2), "chunk": c.id, "chunk_title": c.title,
                                   "refs": refs, "chunk_sources": general}
    return out


def resolve(ident: str) -> Optional[Dict[str, object]]:
    ident = ident.strip()
    if ident.startswith("GOV-"):
        r = _catalog().get(ident.upper())
        if not r:
            return None
        src = r.source or {}
        doc = str(src.get("doc", ""))
        return {"id": r.id, "kind": "regla", "title": r.title, "nature": r.nature, "severity": r.severity,
                "where": f"{doc} {src.get('section', '')}".strip(), "quote": src.get("quote"), "kb": r.kb}
    if re.match(r"^KB_\d{2}$", ident):
        c = _kb().chunks.get(ident)
        return None if not c else {"id": c.id, "kind": "mini-contexto", "title": c.title,
                                   "where": "; ".join(map(str, c.meta.get("sources") or []))}
    e = _kb_lines().get(ident)
    if not e:
        return None
    where = "; ".join(e["refs"]) if e["refs"] else "; ".join(e["chunk_sources"]) + " (fuente general del tema)"
    return {"id": ident, "kind": "criterio", "strength": e["strength"], "title": e["chunk_title"],
            "where": where, "quote": _clip(str(e["text"])), "chunk": e["chunk"]}


def _clip(text: str, n: int = 200) -> str:
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def extract_ids(text: str) -> List[str]:
    seen: List[str] = []
    for m in ID_RX.finditer(text or ""):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def resolve_all(ids: List[str]) -> List[Dict[str, object]]:
    out = []
    for i in ids:
        r = resolve(i)
        if r and not (r["kind"] == "mini-contexto" and any(x["kind"] != "mini-contexto" for x in out)):
            out.append(r)
    return out


def render(entries: List[Dict[str, object]], markdown: bool = True) -> str:
    """Bloque «Fuentes para verificar»: ID · documento § sección · cita (qué revisar si algo parece raro)."""
    if not entries:
        return ""
    lines = ["### Fuentes para verificar" if markdown else "Fuentes para verificar:"]
    for e in entries:
        tag = f" [{e['strength']}]" if e.get("strength") else ""
        quote = f" · «{e['quote']}»" if e.get("quote") else ""
        lines.append(f"- {e['id']}{tag} → {e['where']}{quote}")
    return "\n".join(lines) + "\n"
