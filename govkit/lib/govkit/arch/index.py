"""Índice de conocimiento de una fuente en un commit: archivos, secciones, estado normativo, referencias.

Se guarda en ~/.govkit/arch/index/<fuente>@<commit>.json (local, con valores sensibles enmascarados).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from govkit import __version__
from govkit.arch import home, load_state, now_iso, save_state
from govkit.arch import parsers as P
from govkit.arch.readers import Reader
from govkit.arch.registry import Source, gmatch

TEXT_EXT = (".md", ".yaml", ".yml", ".json", ".py", ".sh", ".js", ".txt", ".sql", ".toml", ".cfg", ".ini", ".xml",
            ".html", ".css", ".tf", "CODEOWNERS", ".gitignore", "VACCINATED", ".gitkeep")
MAX_TEXT = 600_000
DOC_KINDS = {"official_doc", "standard", "policy", "repo_doc", "archimate", "skill"}
CODE_KINDS = {"code", "ci", "template", "example", "index"}


def is_text(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return name.endswith(TEXT_EXT) or "." not in name


def _ci_disabled(text: str) -> bool:
    if not text.strip():
        return True
    if re.search(r"^\s*if:\s*false\s*$", text, re.M):
        return True
    on = re.search(r"^on:\s*\n((?:[ \t]+.*\n?)+)", text, re.M)
    if on:
        triggers = set(re.findall(r"^[ \t]{2}([a-z_]+):", on.group(1), re.M))
        return triggers <= {"workflow_dispatch"}
    return bool(re.search(r"^on:\s*\[?\s*workflow_dispatch\s*\]?\s*$", text, re.M))


def _status(kind: str, main: bool, main_status: str, placeholder: bool, draft: bool, norm: Dict[str, int],
            disabled: bool = False, deprecated: bool = False) -> str:
    """Estado normativo (SUPER PROMPT §17). DEPRECATED solo con marca explícita en el título/cabecera."""
    if not main or placeholder or draft:
        return "UNKNOWN"
    if deprecated:
        return "DEPRECATED"
    if kind == "archimate":
        return "APPROVED" if main_status == "APPROVED" else "IMPLEMENTED"
    if kind in ("code", "ci", "example", "index", "skill"):
        return "IMPLEMENTED"
    if kind == "template":
        return "APPROVED"
    if kind in ("standard", "policy"):
        return "REQUIRED"
    if norm.get("REQUIRED", 0):
        return "REQUIRED"
    if norm.get("RECOMMENDED", 0):
        return "RECOMMENDED"
    return "APPROVED"


def build(reader: Reader, source: Source, ref_is_main: Optional[bool] = None) -> Dict[str, Any]:
    meta = dict(reader.meta)
    branch = meta.get("branch")
    main = ref_is_main if ref_is_main is not None else (branch in (None, source.branch))
    meta.update({"source": source.id, "repo": source.repo, "short": source.short, "role": source.role,
                 "main": bool(main), "generated_at": now_iso(), "govkit": __version__})
    files: Dict[str, Dict[str, Any]] = {}
    secrets: List[Dict[str, str]] = []
    masked_ids: Dict[str, int] = {}
    xml_payload = []
    for rel, info in sorted(reader.files().items()):
        kind, authority = source.classify(rel)
        data = reader.read(rel)
        entry: Dict[str, Any] = {"sha": info.get("sha"), "size": info.get("size", 0), "kind": kind,
                                 "authority": authority}
        text = None
        if data is not None and is_text(rel) and len(data) <= MAX_TEXT:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = None
        entry["binary"] = text is None and data is not None
        if kind == "archimate" and rel.endswith(".xml") and data is not None:
            xml_payload.append((rel, data))
        if text is None:
            entry.update({"placeholder": not info.get("size"), "draft": False, "status": "UNKNOWN" if not main
                          else ("IMPLEMENTED" if kind in CODE_KINDS else "APPROVED"),
                          "label": "DOC" if kind in DOC_KINDS else "COD", "title": rel.rsplit("/", 1)[-1]})
            files[rel] = entry
            continue
        masked, found, n_ids = P.mask(text)
        for f in found:
            secrets.append({"file": rel, "type": f})
        if n_ids:
            masked_ids[rel] = n_ids
        placeholder = not masked.strip() or rel.endswith(".gitkeep")
        is_md = rel.lower().endswith(".md")
        draft = P.is_draft(masked) if (is_md and kind in DOC_KINDS) else False
        norm = P.normative(masked) if kind not in ("archimate",) else {}
        disabled = kind == "ci" and _ci_disabled(masked)
        entry.update({"placeholder": placeholder, "draft": draft, "norm": norm,
                      "label": "DOC" if kind in DOC_KINDS else "COD"})
        head = "\n".join(masked.splitlines()[:6])
        deprecated = bool(P._MARKERS["DEPRECATED"].search(P.title_of(masked, rel) if is_md else "")) or \
            bool(re.search(r"(?im)^\W*(estado|status)\W*[:：]\W*(deprecad|deprecated|obsolet|retirad)", head))
        entry["status"] = _status(kind, main, source.main_status, placeholder, draft, norm, disabled, deprecated)
        if disabled:
            entry["disabled"] = True
        if kind != "archimate":
            entry["text"] = masked
            entry["title"] = P.title_of(masked, rel) if is_md else rel.rsplit("/", 1)[-1]
            entry["refs"] = P.refs(masked, is_md)
        else:
            entry["title"] = rel.rsplit("/", 1)[-1]
        if is_md:
            secs = P.md_sections(masked)
            for s in secs:
                s["status"] = _status(kind, main, source.main_status, placeholder, draft, s["norm"],
                                      deprecated=bool(P._MARKERS["DEPRECATED"].search(s["t"])))
            entry["sections"] = secs
            entry["purpose"] = P.first_paragraph(masked)
        elif rel.endswith((".yaml", ".yml", ".json")) and not placeholder:
            data_obj, err = P.load_structured(rel, masked)
            if err:
                entry["parse_error"] = err
            else:
                flat = P.flatten(data_obj)
                entry["flat"] = flat
                entry["versions"] = {k: v for k, v in flat.items() if re.search(r"version", k, re.I)
                                     and isinstance(v, (str, int, float))}
                entry["refs"] = entry.get("refs", []) + P.structured_refs(flat)
                m = re.match(r"\s*#\s*(.+)", masked)
                entry["purpose"] = m.group(1).strip()[:300] if m else ""
        files[rel] = entry
    index: Dict[str, Any] = {"meta": meta, "files": files, "secrets": secrets, "masked_account_ids": masked_ids}
    if xml_payload:
        model = P.archimate(xml_payload)
        for coll in (model["elements"].values(), model["diagrams"], model["folders"].values(), model["relations"]):
            for obj in coll:
                for k in ("name", "doc"):
                    if obj.get(k):
                        obj[k] = P.mask(obj[k])[0]
        for d in model["diagrams"]:
            d["path_names"] = P.folder_names(model, d["folder"])
        index["archimate"] = model
    return index


# ------------------------------------------------------------------------------------------------ persistencia
def index_dir() -> Path:
    return home() / "index"


def _fname(source_id: str, commit: str) -> str:
    return f"{source_id}@{(commit or 'desconocido')[:12]}.json"


def save(index: Dict[str, Any], make_current: bool = True) -> Path:
    meta = index["meta"]
    d = index_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / _fname(meta["source"], str(meta.get("commit") or ""))
    p.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    if make_current:
        state = load_state()
        s = state["sources"].setdefault(meta["source"], {})
        history = s.setdefault("history", [])
        entry = {"commit": meta.get("commit"), "commit_date": meta.get("commit_date"), "origin": meta.get("origin"),
                 "index": p.name, "analyzed_at": meta.get("generated_at"), "ref": meta.get("ref")}
        history[:] = [h for h in history if h.get("commit") != entry["commit"]][-19:] + [entry]
        s.update({k: entry[k] for k in ("commit", "commit_date", "origin", "index", "analyzed_at", "ref")})
        save_state(state)
    _cache_clear()
    return p


_MEMO: Dict[str, Dict[str, Any]] = {}


def _cache_clear() -> None:
    _MEMO.clear()
    all_current.cache_clear()
    from govkit.arch import graph, search
    graph.current.cache_clear()
    search.clear()


def load_file(name: str) -> Optional[Dict[str, Any]]:
    if name in _MEMO:
        return _MEMO[name]
    p = index_dir() / name
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    _MEMO[name] = data
    return data


def load(source_id: str, commit: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Índice vigente de una fuente (o el de un commit concreto si existe)."""
    if commit:
        hit = load_file(_fname(source_id, commit))
        if hit:
            return hit
        for p in sorted(index_dir().glob(f"{source_id}@*.json")) if index_dir().exists() else []:
            if commit.startswith(p.stem.split("@", 1)[1]) or p.stem.split("@", 1)[1].startswith(commit[:12]):
                return load_file(p.name)
        return None
    s = load_state()["sources"].get(source_id) or {}
    return load_file(s["index"]) if s.get("index") else None


@lru_cache(maxsize=1)
def all_current() -> Dict[str, Dict[str, Any]]:
    from govkit.arch import registry
    out = {}
    for sid in registry.sources():
        idx = load(sid)
        if idx:
            out[sid] = idx
    return out


def trace(index: Dict[str, Any], rel: str, section: Optional[Dict[str, Any]] = None) -> str:
    """repo@commit:ruta#sección (trazabilidad obligatoria, SUPER PROMPT §19)."""
    m = index["meta"]
    s = f"{m['repo']}@{str(m.get('commit') or '?')[:7]}:{rel}"
    if section:
        s += f" §{section['t']} (L{section['line']})"
    return s


def section_at(entry: Dict[str, Any], line: int) -> Optional[Dict[str, Any]]:
    best = None
    for s in entry.get("sections") or []:
        if s["line"] <= line <= s["end"]:
            best = s
    return best


def files_under(index: Dict[str, Any], prefix: str) -> List[str]:
    prefix = prefix.strip("/")
    if not prefix:
        return list(index["files"])
    return [f for f in index["files"] if f == prefix or f.startswith(prefix + "/") or gmatch(prefix, f)]
