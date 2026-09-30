"""Inventario de ADR (fuentes corporativas, govkit y repo de Data Product) y detección de Potential ADR.

Nunca crea un ADR: clasifica decisiones de facto como `Potential ADR` y explica por qué (SUPER PROMPT §9, §15).
"""
from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from govkit.arch import index as I
from govkit.arch import parsers as P
from govkit.arch.facts import potential_adrs
from govkit.arch.registry import gmatch

ADR_PATH = re.compile(r"(^|/)(adr|adrs|decisions)/[^/]+\.md$|(^|/)ADR[-_]?\d+[^/]*\.md$", re.I)
_FIELD = {
    "date": re.compile(r"(?im)^\W*(fecha|date)\W*[:：]\s*(.+)$"),
    "status": re.compile(r"(?im)^\W*(estado|status)\W*[:：]\s*(.+)$"),
}
_SECTIONS = {
    "context": r"contexto|context|antecedentes|problema",
    "decision": r"decisi[oó]n|decision",
    "alternatives": r"alternativas|alternatives|opciones|options considered",
    "consequences": r"consecuencias|consequences|impacto",
}


def parse(text: str, rel: str) -> Dict[str, Any]:
    name = rel.rsplit("/", 1)[-1]
    m = re.search(r"ADR[-_ ]?(\d+)", name, re.I) or re.search(r"ADR[-_ ]?(\d+)", text[:400], re.I)
    ident = f"ADR-{int(m.group(1)):03d}" if m else re.sub(r"\.md$", "", name)
    title = P.title_of(text, rel)
    title = re.sub(r"^ADR[-_ ]?\d+\s*[:：-]\s*", "", title, flags=re.I)
    out: Dict[str, Any] = {"id": ident, "title": title, "file": rel, "template": "template" in name.lower()}
    for k, rx in _FIELD.items():
        fm = rx.search(text)
        out[k] = re.sub(r"[*_`]", "", fm.group(2)).strip()[:120] if fm else None
    secs = P.md_sections(text)
    lines = text.splitlines()
    for key, rx in _SECTIONS.items():
        sec = next((s for s in secs if re.search(rx, s["t"], re.I)), None)
        if sec:
            body = "\n".join(lines[sec["line"]:sec["end"]]).strip()
            out[key] = re.sub(r"\s+", " ", body)[:600]
    out["related"] = sorted({f"ADR-{int(x):03d}" for x in re.findall(r"ADR[-_ ]?(\d{1,4})", text, re.I)} - {ident})
    out["refs"] = [r["target"] for r in P.refs(text, True)][:20]
    return out


def _from_index(idx: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for rel, e in idx["files"].items():
        if ADR_PATH.search(rel) and e.get("text"):
            a = parse(e["text"], rel)
            a.update({"source": idx["meta"]["source"], "repo": idx["meta"]["repo"], "trace": I.trace(idx, rel)})
            yield a


def govkit_adrs() -> List[Dict[str, Any]]:
    from govkit.paths import DOCS_DIR, KIT_HOME
    out = []
    for d in (DOCS_DIR / "adr", KIT_HOME.parent / "docs" / "adr"):
        if d.is_dir():
            for p in sorted(d.glob("*.md")):
                a = parse(p.read_text(encoding="utf-8"), p.name)
                a.update({"source": "govkit", "repo": "govkit", "trace": f"govkit:docs/adr/{p.name}"})
                out.append(a)
            break
    return out


def repo_adrs(repo: Path) -> List[Dict[str, Any]]:
    out = []
    for p in sorted(repo.glob("docs/adr/**/*.md")):
        rel = p.relative_to(repo).as_posix()
        a = parse(p.read_text(encoding="utf-8", errors="replace"), rel)
        a.update({"source": "repo", "repo": repo.name, "trace": f"{repo.name}:{rel}"})
        out.append(a)
    return out


def inventory(repo: Optional[Path] = None, include_govkit: bool = True) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx in I.all_current().values():
        out += list(_from_index(idx))
    if include_govkit:
        out += govkit_adrs()
    if repo:
        out += repo_adrs(repo)
    return out


def _auto_potentials(indexes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Decisiones de facto detectadas en el índice (versionado con supersedes, deprecaciones explícitas en estándares)."""
    out = []
    for sid, idx in indexes.items():
        for rel, e in idx["files"].items():
            flat = e.get("flat") or {}
            if e["kind"] not in ("standard", "policy", "index"):
                continue
            sup = sorted({str(v) for k, v in flat.items() if k.endswith(".supersedes")})
            if sup:
                out.append({"id": f"PA-AUTO-{sid[:3].upper()}-{zlib.crc32(rel.encode()) % 997:03d}",
                            "decision": f"Evolución versionada de `{rel.rsplit('/', 1)[-1]}` (supersedes {', '.join(sup)})",
                            "evidence": I.trace(idx, rel), "label": "COD", "auto": True,
                            "why": "Hay una cadena de versiones que reemplazan a otras: cada salto de versión es una "
                                   "decisión de arquitectura sin ADR visible.", "paths": [f"{sid}:{rel}"]})
            forb = [k for k in flat if re.search(r"forbidden|deprecated|prohibid", k, re.I)]
            if forb:
                out.append({"id": f"PA-AUTO-{sid[:3].upper()}-{zlib.crc32((rel + 'f').encode()) % 997:03d}",
                            "decision": f"Prohibiciones/deprecaciones declaradas en `{rel.rsplit('/', 1)[-1]}` "
                                        f"({', '.join(sorted({k.split('.')[0] for k in forb})[:3])})",
                            "evidence": I.trace(idx, rel), "label": "COD", "auto": True,
                            "why": "Restricciones normativas nuevas (prohibir/deprecar) cambian lo que los Data "
                                   "Products pueden hacer; requieren decisión trazable.", "paths": [f"{sid}:{rel}"]})
    return out


def potentials(indexes: Optional[Dict[str, Dict[str, Any]]] = None, adrs: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    indexes = indexes if indexes is not None else I.all_current()
    adrs = adrs if adrs is not None else inventory(include_govkit=False)
    curated = [dict(p, auto=False) for p in potential_adrs()]
    covered = {g for p in curated for g in p.get("paths") or []}
    auto = [p for p in _auto_potentials(indexes)
            if not any(gmatch(g.split(":", 1)[1], p["paths"][0].split(":", 1)[1])
                       for g in covered if g.split(":", 1)[0] == p["paths"][0].split(":", 1)[0])]
    res = curated + auto
    for p in res:  # ¿algún ADR corporativo ya lo cubre? (búsqueda por rutas citadas)
        p["adr"] = [a["id"] for a in adrs if any(path.split(":", 1)[-1].rstrip("*/") in " ".join(a.get("refs") or [])
                                                 for path in p.get("paths") or [])]
    return res


def for_path(source: str, rel: str, adrs: Optional[List[Dict[str, Any]]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(ADR que citan la ruta, Potential ADR cuyas rutas la cubren)."""
    adrs = adrs if adrs is not None else inventory()
    hits = [a for a in adrs if any(rel and (rel in r or r.rstrip("/") in rel) for r in a.get("refs") or [])]
    pots = [p for p in potentials(adrs=[a for a in adrs if a["source"] != "govkit"])
            if any(g.split(":", 1)[0] == source and (gmatch(g.split(":", 1)[1], rel) or
                   rel.startswith(g.split(":", 1)[1].rstrip("*").rstrip("/")))
                   for g in p.get("paths") or [])]
    return hits, pots
