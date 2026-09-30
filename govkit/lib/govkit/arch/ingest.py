"""Ingesta de una fuente: clon git local (solo lectura), snapshot .txt o directorio."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from govkit.arch import gitio, index, registry
from govkit.arch.readers import DirReader, GitReader, SnapshotReader


def default_ref(src: registry.Source) -> Tuple[str, bool]:
    """origin/<rama principal> si existe; si no, HEAD. → (ref, es_rama_principal)."""
    path = src.path
    if gitio.resolve(path, f"origin/{src.branch}"):
        return f"origin/{src.branch}", True
    branch = gitio.current_branch(path)
    return "HEAD", branch in (None, src.branch)


def ingest_git(src: registry.Source, ref: Optional[str] = None, make_current: bool = True) -> Dict[str, Any]:
    path = src.path
    if not gitio.is_repo(path):
        raise FileNotFoundError(f"{src.repo}: no hay un clon git en {path} (configura: govkit arch config "
                                f"{src.id} /ruta/al/clon)")
    if ref:
        is_main = ref in (src.branch, f"origin/{src.branch}") or ref.endswith(f"/{src.branch}")
    else:
        ref, is_main = default_ref(src)
    idx = index.build(GitReader(path, ref), src, ref_is_main=is_main)
    st = gitio.status(path)
    idx["meta"]["working_tree"] = st.get("branch_line", "") + "".join(f"\n{x} {p}" for x, p in st.get("changes", []))
    idx["meta"]["local_branch"] = gitio.current_branch(path)
    index.save(idx, make_current=make_current)
    return idx


def ingest_snapshot(path: os.PathLike, make_current: bool = True) -> Dict[str, Any]:
    reader = SnapshotReader(path)
    src = registry.find(str(reader.meta.get("repo"))) or registry.find(Path(path).stem)
    if not src:
        raise KeyError(f"El snapshot es de `{reader.meta.get('repo')}`, que no está registrado en arch_sources.yaml")
    idx = index.build(reader, src, ref_is_main=reader.meta.get("branch") in (None, src.branch))
    index.save(idx, make_current=make_current)
    return idx


def ingest_dir(src: registry.Source, path: os.PathLike, make_current: bool = True) -> Dict[str, Any]:
    idx = index.build(DirReader(path), src, ref_is_main=True)
    index.save(idx, make_current=make_current)
    return idx
