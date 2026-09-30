"""Grafo de relaciones con evidencia entre archivos de las fuentes (y hacia repos de Data Product).

Tipos de arista: reference · reference_broken · mirror · duplicate_divergent · index · models_dp · curated.
Cada arista lleva evidencia (repo@commit:ruta:línea) y etiqueta epistemológica (COD/DOC/INF/CONF).
"""
from __future__ import annotations

import difflib
import posixpath
import re
from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from govkit.arch import index as I
from govkit.arch import parsers as P
from govkit.arch import registry

Edge = Dict[str, Any]
_EXT = re.compile(r"\.(md|ya?ml|json|py|sh|xlsx|xml|sql|toml|js|csv)$", re.I)
_BINARY = re.compile(r"\.(xlsx|xls|png|jpe?g|gif|pdf|docx|pptx|zip|parquet)$", re.I)
_BRANCHY = re.compile(r"^(proposal|feat|feature|update|fix|hotfix|docs|dp|domain|model|pattern|chore|release)/")


_DOCNAME = re.compile(r"^\d{2}(?:\.\d)?-[\w.-]+\.md$")


def _resolve(target: str, src_file: str, src_id: str, indexes: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    """→ (fuente destino, ruta destino, existe: True/False/None=no verificable). Resuelve rutas relativas, a repos
    globales (incl. URLs blob/tree de GitHub), rutas desde la raíz, nombres de documento del framework y rutas que
    pertenecen a OTRA fuente."""
    t = target.strip().replace("%20", " ")
    m = re.match(r"^(?:\.\./)*(global-[a-z0-9-]+)/?(.*)$", t)
    if m:
        src = registry.find(m.group(1))
        if not src:
            return None, None, False
        rel = re.sub(r"^(?:blob|tree)/[^/]+/", "", m.group(2)).strip("/")
        idx = indexes.get(src.id)
        if idx is None:
            return src.id, rel, None
        return src.id, rel, _exists(idx, rel)
    idx = indexes.get(src_id)
    if idx is None:
        return None, None, False
    if t.startswith("file:"):
        return None, None, False
    candidates = []
    base = posixpath.dirname(src_file)
    if t.startswith(("./", "../")):
        candidates.append(posixpath.normpath(posixpath.join(base, t)))
        if candidates[0].startswith(".."):
            return src_id, t, None  # sale del repositorio: no verificable desde esta fuente
    else:
        candidates.append(t.strip("/"))
        while True:  # relativo a la carpeta del archivo o a alguna carpeta ancestro (p.ej. raíz de una skill)
            candidates.append(posixpath.normpath(posixpath.join(base, t)))
            if not base:
                break
            base = posixpath.dirname(base)
    for c in candidates:
        if not c.startswith("..") and _exists(idx, c):
            return src_id, c, True
    name = t.rsplit("/", 1)[-1]
    if _DOCNAME.match(name):  # documento del framework citado por nombre desde otra carpeta
        hits = [f for f in idx["files"] if f.rsplit("/", 1)[-1] == name]
        if len(hits) == 1:
            return src_id, hits[0], True
    for other_id, other in indexes.items():  # ruta que pertenece a otra fuente (p.ej. framework/… de platform-core)
        if other_id == src_id:
            continue
        rel = t.lstrip("./").strip("/")
        if _exists(other, rel):
            return other_id, rel, True
        parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
        if parent and _exists(other, parent) and parent.count("/") >= 1:
            return other_id, rel, None  # carpeta existe; el archivo no está indexado (p.ej. binario)
    first = next((c for c in candidates if not c.startswith("..")), candidates[0] if candidates else t)
    return src_id, first, False


def _exists(idx: Dict[str, Any], rel: str) -> bool:
    rel = rel.strip("/")
    if not rel:
        return True
    files = idx["files"]
    if rel in files:
        return True
    prefix = rel + "/"
    return any(f.startswith(prefix) for f in files)


def build(indexes: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Edge]:
    indexes = indexes if indexes is not None else I.all_current()
    edges: List[Edge] = []
    for sid, idx in indexes.items():
        commit = str(idx["meta"].get("commit") or "")[:7]
        for rel, e in idx["files"].items():
            for r in e.get("refs") or []:
                tgt = r["target"]
                has_ext = bool(_EXT.search(tgt))
                if ("/" not in tgt and not has_ext) or "*" in tgt or "@" in tgt or _BRANCHY.match(tgt):
                    continue
                if r.get("kind") in ("path", "value") and "/" not in tgt and not _DOCNAME.match(tgt):
                    continue  # nombre suelto en `código` (p.ej. owners.yaml de ejemplo): no es una referencia
                dsid, drel, ok = _resolve(tgt, rel, sid, indexes)
                if dsid is None or (ok is False and not has_ext and r.get("kind") != "link"):
                    continue  # sin extensión ni enlace explícito no hay evidencia suficiente de referencia rota
                # Rutas "de ejemplo" en tablas/código de un DP (contracts/…, metadata/…) no son referencias rotas
                # del repo corporativo: se registran como referencia al patrón de repositorio de Data Product.
                dp_like = ok is False and dsid == sid and re.match(
                    r"^(contracts|metadata|modeling|src|tests|pipelines|quality|observability|docs/adr|scripts|bronze|silver|"
                    r"gold|semantic|_examples|_templates|repo-data-product)/", drel or "")
                if dp_like and sid != "platform-core":
                    continue
                if ok is False and (r.get("kind") == "value" or (_BINARY.search(tgt) and idx["meta"].get("origin") == "snapshot")):
                    ok = None  # valor YAML (puede ser una fuente externa) o binario excluido del snapshot
                edge_type = ("reference" if ok else "reference_unverified" if ok is None else
                             "dp_pattern" if dp_like else "reference_broken")
                edges.append({"type": edge_type, "src": {"source": sid, "path": rel, "line": r.get("line", 0)},
                              "dst": {"source": dsid, "path": drel}, "label": "DOC" if e.get("label") == "DOC" else "COD",
                              "evidence": f"{idx['meta']['repo']}@{commit}:{rel}:{r.get('line', 0)} → `{tgt}`"})
        if idx.get("archimate"):
            edges += _archimate_edges(sid, idx)
    edges += _mirrors(indexes)
    edges += _manifest_edges(indexes)
    return _dedupe(edges)


def _dedupe(edges: List[Edge]) -> List[Edge]:
    seen, out = set(), []
    for e in edges:
        key = (e["type"], e["src"]["source"], e["src"]["path"], e["dst"].get("source"), e["dst"].get("path"))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def _mirrors(indexes: Dict[str, Dict[str, Any]]) -> List[Edge]:
    """Mismo contenido en rutas distintas (espejo) y mismo nombre con contenido casi igual (duplicado divergente)."""
    by_sha: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    by_name: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for sid, idx in indexes.items():
        for rel, e in idx["files"].items():
            if e.get("placeholder") or not e.get("size") or e["kind"] == "archimate":
                continue
            by_sha[str(e["sha"])].append((sid, rel))
            name = rel.rsplit("/", 1)[-1]
            if name.lower() not in ("readme.md", "__init__.py", "vaccinated", "codeowners", ".gitignore") and e.get("text"):
                by_name[name].append((sid, rel))
    out: List[Edge] = []
    for sha, locs in by_sha.items():
        if len(locs) > 1:
            (s0, r0) = locs[0]
            for (s1, r1) in locs[1:]:
                out.append({"type": "mirror", "src": {"source": s1, "path": r1, "line": 0},
                            "dst": {"source": s0, "path": r0}, "label": "COD",
                            "evidence": f"sha256 idéntico ({sha[:12]}…) en {s0}:{r0} y {s1}:{r1}"})
    for name, locs in by_name.items():
        shas = {str(indexes[s]["files"][r]["sha"]) for s, r in locs}
        if len(locs) < 2 or len(shas) < 2:
            continue
        for i in range(len(locs)):
            for j in range(i + 1, len(locs)):
                (sa, ra), (sb, rb) = locs[i], locs[j]
                ea, eb = indexes[sa]["files"][ra], indexes[sb]["files"][rb]
                if ea["sha"] == eb["sha"]:
                    continue
                na, nb = P.normalize_md(ea["text"]), P.normalize_md(eb["text"])
                if len(na) < 200:
                    continue
                ratio = difflib.SequenceMatcher(None, na, nb, autojunk=False).quick_ratio()
                if ratio < 0.9:
                    continue
                diff = [d for d in difflib.unified_diff(na.splitlines(), nb.splitlines(), lineterm="", n=0)
                        if d[:1] in "+-" and not d.startswith(("+++", "---"))]
                if not diff:
                    out.append({"type": "mirror", "src": {"source": sb, "path": rb, "line": 0},
                                "dst": {"source": sa, "path": ra}, "label": "COD",
                                "evidence": f"`{name}`: mismo contenido salvo formato (escapes/espacios)"})
                    continue
                out.append({"type": "duplicate_divergent", "src": {"source": sb, "path": rb, "line": 0},
                            "dst": {"source": sa, "path": ra}, "label": "CONF", "diff_lines": len(diff),
                            "diff_sample": [d[:200] for d in diff[:4]],
                            "evidence": f"`{name}` duplicado en {sa} y {sb}: {len(diff)} línea(s) distintas tras "
                                        f"normalizar formato"})
    return out


def _manifest_edges(indexes: Dict[str, Dict[str, Any]]) -> List[Edge]:
    out: List[Edge] = []
    for sid, idx in indexes.items():
        for rel, e in idx["files"].items():
            if e["kind"] != "index" and not rel.endswith("architecture-standard.yaml"):
                continue
            for key, val in (e.get("flat") or {}).items():
                for v in (val if isinstance(val, list) else [val]):
                    if isinstance(v, str) and "/" in v and _exists(idx, v):
                        out.append({"type": "index", "src": {"source": sid, "path": rel, "line": 0},
                                    "dst": {"source": sid, "path": v.strip("/")}, "label": "COD",
                                    "evidence": f"{rel} · `{key}` → {v}"})
    return out


def _archimate_edges(sid: str, idx: Dict[str, Any]) -> List[Edge]:
    """Carpetas de Data Products en el modelo → repos de Data Product (por nombre de carpeta)."""
    from govkit.arch import archimate
    out: List[Edge] = []
    for dp in archimate.dp_inventory(idx):
        out.append({"type": "models_dp", "src": {"source": sid, "path": dp["folder"], "line": 0},
                    "dst": {"repo": dp["name"]}, "label": "DOC",
                    "evidence": f"carpeta ArchiMate `{' / '.join(dp['path_names'])}` ({dp['views']} vista(s))"})
    return out


def neighbors(edges: List[Edge], sid: str, prefix: str) -> Dict[str, List[Edge]]:
    """Aristas salientes y entrantes de los archivos bajo `prefix` en la fuente `sid`."""
    def under(src: Optional[str], path: Optional[str]) -> bool:
        if src != sid or path is None:
            return False
        p = prefix.strip("/")
        return not p or path == p or path.startswith(p + "/") or p.startswith(path + "/") and path != ""
    out = {"out": [], "in": []}
    for e in edges:
        if under(e["src"]["source"], e["src"]["path"]) and not under(e["dst"].get("source"), e["dst"].get("path")):
            out["out"].append(e)
        elif under(e["dst"].get("source"), e["dst"].get("path")) and not under(e["src"]["source"], e["src"]["path"]):
            out["in"].append(e)
    return out


@lru_cache(maxsize=1)
def current() -> List[Edge]:
    return build()
