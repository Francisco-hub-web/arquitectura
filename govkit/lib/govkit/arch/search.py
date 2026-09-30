"""Búsqueda determinista (BM25) sobre las secciones del índice corporativo, con trazabilidad repo@commit:ruta§sección."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Tuple

from govkit.arch import index as I
from govkit.kb.bm25 import BM25


def _norm(text: str) -> str:
    from govkit.claims import normalize
    return normalize(text)


@lru_cache(maxsize=1)
def _corpus() -> Tuple[BM25, Dict[str, Dict[str, Any]]]:
    docs: Dict[str, str] = {}
    meta: Dict[str, Dict[str, Any]] = {}
    for sid, idx in I.all_current().items():
        for rel, e in idx["files"].items():
            text = e.get("text")
            if not text or e.get("placeholder") or e["kind"] in ("asset",):
                continue
            lines = text.splitlines()
            secs = e.get("sections") or [{"t": e.get("title") or rel, "line": 1, "end": len(lines), "status": e["status"]}]
            for s in secs:
                body = "\n".join(lines[s["line"] - 1:s["end"]])
                if len(body.strip()) < 30:
                    continue
                key = f"{sid}|{rel}|{s['line']}"
                docs[key] = _norm(f"{s['t']} {e.get('title', '')} {rel.replace('/', ' ')} {body[:6000]}")
                meta[key] = {"source": sid, "repo": idx["meta"]["repo"], "path": rel, "section": s["t"], "line": s["line"],
                             "status": s.get("status", e["status"]), "label": e["label"], "kind": e["kind"],
                             "trace": I.trace(idx, rel, s if e.get("sections") else None),
                             "snippet": " ".join(body.split())[:280]}
    return BM25(docs), meta


def search(query: str, k: int = 10, source: str = "") -> List[Dict[str, Any]]:
    if not I.all_current():
        return []
    bm, meta = _corpus()
    hits = bm.search(_norm(query), k=k * 4 if source else k)
    out = []
    for key, score in hits:
        m = meta[key]
        if source and m["source"] != source:
            continue
        out.append({**m, "score": round(score, 2)})
        if len(out) >= k:
            break
    return out


def clear() -> None:
    _corpus.cache_clear()
