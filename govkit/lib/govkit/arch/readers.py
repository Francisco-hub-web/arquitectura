"""Lectores de una fuente en un punto del tiempo: commit git, snapshot .txt o directorio.

Todos exponen la misma interfaz (`meta`, `files()`, `read()`), y todos identifican el contenido por sha256, de modo
que se pueden comparar un snapshot antiguo con un commit nuevo (o viceversa) sin depender de git.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Optional

from govkit.arch import gitio

MAX_BYTES = 5_000_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Reader:
    origin = "?"

    def __init__(self) -> None:
        self.meta: Dict[str, object] = {}
        self._files: Dict[str, Dict[str, object]] = {}

    def files(self) -> Dict[str, Dict[str, object]]:
        """{ruta: {"sha": sha256|None, "size": bytes}}"""
        return self._files

    def read(self, rel: str) -> Optional[bytes]:  # pragma: no cover - interfaz
        raise NotImplementedError


class GitReader(Reader):
    """Contenido de un commit (p.ej. origin/main) sin checkout."""
    origin = "git"

    def __init__(self, repo: os.PathLike, ref: str):
        super().__init__()
        self.repo = Path(repo)
        commit = gitio.resolve(self.repo, ref)
        if not commit:
            raise gitio.GitError(f"ref `{ref}` no existe en {self.repo}")
        info = gitio.commit_info(self.repo, commit)
        self.meta = {"origin": "git", "location": str(self.repo), "ref": ref, "commit": commit,
                     "commit_date": info["date"], "subject": info["subject"],
                     "remote": gitio.remote_url(self.repo), "branch": _branch_of(ref)}
        tree = gitio.ls_tree(self.repo, commit)
        blobs = gitio.read_blobs(self.repo, [b for b, size in tree.values() if size <= MAX_BYTES], MAX_BYTES)
        self._data: Dict[str, Optional[bytes]] = {}
        for rel, (blob, size) in tree.items():
            data = blobs.get(blob)
            self._data[rel] = data
            self._files[rel] = {"sha": sha256(data) if data is not None else f"git:{blob}", "size": size}

    def read(self, rel: str) -> Optional[bytes]:
        return self._data.get(rel)


def _branch_of(ref: str) -> Optional[str]:
    if ref.startswith("origin/"):
        return ref[len("origin/"):]
    if ref.startswith("refs/remotes/origin/"):
        return ref[len("refs/remotes/origin/"):]
    return None if re.fullmatch(r"[0-9a-f]{7,40}|HEAD", ref) else ref


# ---------------------------------------------------------------------------------------------------- snapshot .txt
_BLOCK = re.compile(r"\n#{100}\nFILE (\d+)/(\d+)\n")
_HEADER_END = "#" * 100 + "\n"


def _field(head: str, name: str) -> Optional[str]:
    m = re.search(rf"^### {re.escape(name)}\n(.+?)(?:\n\n|\n###|\Z)", head, re.M | re.S)
    return m.group(1).strip() if m else None


def parse_snapshot(text: str) -> Dict[str, object]:
    """Parser del formato de snapshot del usuario (cabecera GIT METADATA + INVENTARIO + bloques FILE i/N)."""
    repo = re.search(r"^REPOSITORIO: (.+)$", text, re.M)
    if not repo:
        raise ValueError("no parece un snapshot de repositorio (falta 'REPOSITORIO:')")
    head = text.split("CONTENIDO DE LOS ARCHIVOS")[0]
    last = (_field(head, "Last commit") or "").splitlines()
    date = next((ln for ln in last if re.match(r"^\d{4}-\d{2}-\d{2}", ln)), "")
    subject = last[-1] if len(last) >= 2 else ""
    meta: Dict[str, object] = {
        "origin": "snapshot", "repo": repo.group(1).strip(), "remote": _field(head, "Remote origin"),
        "branch": _field(head, "Branch"), "commit": _field(head, "HEAD"), "commit_date": date.strip(),
        "subject": subject.strip(), "working_tree": _field(head, "Working tree status") or "",
        "snapshot_date": (re.search(r"^FECHA DE SNAPSHOT: (.+)$", head, re.M) or [None, ""])[1],
    }
    inventory: Dict[str, Dict[str, object]] = {}
    for m in re.finditer(r"^- (.+?) \| bytes=(\d+) \| sha256=([0-9a-f]{64})$", head, re.M):
        inventory[m.group(1)] = {"size": int(m.group(2)), "sha": m.group(3)}
    contents: Dict[str, bytes] = {}
    parts = _BLOCK.split(text)
    for i in range(1, len(parts), 3):
        body = parts[i + 2]
        rel_m = re.search(r"^RELATIVE PATH: (.+)$", body, re.M)
        if not rel_m or _HEADER_END not in body:
            continue
        rel = rel_m.group(1).strip()
        payload = body.split(_HEADER_END, 1)[1]
        end = payload.rfind("\nEND FILE: ")
        payload = payload[:end] if end >= 0 else payload
        want = (inventory.get(rel) or {}).get("sha") or (re.search(r"^SHA256: (\w+)$", body, re.M) or [None, None])[1]
        contents[rel] = _exact_content(payload, want)
        inventory.setdefault(rel, {"size": len(contents[rel]), "sha": sha256(contents[rel])})
    return {"meta": meta, "inventory": inventory, "contents": contents}


def _exact_content(payload: str, want: Optional[str]) -> bytes:
    """El bloque agrega saltos de línea alrededor del contenido: se elige la variante cuyo sha256 coincide."""
    candidates = [payload[1:-1] if payload.startswith("\n") and payload.endswith("\n") else payload,
                  payload[1:] if payload.startswith("\n") else payload, payload, payload.strip("\n"),
                  payload.strip("\n") + "\n"]
    for c in candidates:
        b = c.encode("utf-8")
        if want and sha256(b) == want:
            return b
    return candidates[0].encode("utf-8")


class SnapshotReader(Reader):
    origin = "snapshot"

    def __init__(self, path: os.PathLike):
        super().__init__()
        self.path = Path(path)
        parsed = parse_snapshot(self.path.read_text(encoding="utf-8", errors="replace"))
        self.meta = dict(parsed["meta"], location=str(self.path), ref=parsed["meta"].get("branch"))  # type: ignore
        self._contents: Dict[str, bytes] = parsed["contents"]  # type: ignore
        for rel, inv in parsed["inventory"].items():  # type: ignore
            self._files[rel] = {"sha": inv["sha"], "size": inv["size"]}

    def read(self, rel: str) -> Optional[bytes]:
        return self._contents.get(rel)


class DirReader(Reader):
    """Directorio sin git (o working tree tal cual): útil para pruebas y carpetas exportadas."""
    origin = "dir"

    def __init__(self, path: os.PathLike, label: Optional[str] = None):
        super().__init__()
        self.root = Path(path)
        self.meta = {"origin": "dir", "location": str(self.root), "ref": None, "commit": label or "working-tree",
                     "commit_date": "", "subject": ""}
        self._data: Dict[str, Optional[bytes]] = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                p = Path(dirpath) / name
                rel = p.relative_to(self.root).as_posix()
                size = p.stat().st_size
                data = p.read_bytes() if size <= MAX_BYTES else None
                self._data[rel] = data
                self._files[rel] = {"sha": sha256(data) if data is not None else None, "size": size}
        combined = hashlib.sha256("".join(f"{k}:{v['sha']}" for k, v in sorted(self._files.items())).encode())
        if not label:
            self.meta["commit"] = "dir-" + combined.hexdigest()[:12]

    def read(self, rel: str) -> Optional[bytes]:
        return self._data.get(rel)
