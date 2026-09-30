"""Acceso git en SOLO LECTURA para los repos corporativos (SUPER PROMPT §11).

Garantías (verificadas por tests):
  · lista blanca de subcomandos: nunca `pull`, `checkout`, `reset`, `stash`, `clean`, `merge`, `push`, `commit`;
  · `fetch` solo actualiza refs remotas (`refs/remotes/origin/*`): el working tree del usuario no cambia;
  · el contenido se lee con `ls-tree` + `cat-file` sobre un commit, sin checkout;
  · hooks desactivados (`core.hooksPath=/dev/null`), sin prompts de credenciales y sin locks opcionales del índice;
  · nunca se ejecuta código del repositorio analizado.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ALLOWED = frozenset({"rev-parse", "status", "fetch", "ls-tree", "cat-file", "diff", "log", "for-each-ref", "remote",
                     "config", "show", "merge-base", "rev-list"})
NULL_HOOKS = "NUL" if os.name == "nt" else "/dev/null"


class GitError(RuntimeError):
    pass


def git(repo: os.PathLike, *args: str, timeout: int = 120, input_bytes: Optional[bytes] = None,
        binary: bool = False):
    if not args or args[0] not in ALLOWED or (args[0] == "remote" and args[1:2] != ("get-url",)) or \
            (args[0] == "config" and not set(args[1:2]) & {"--get", "--get-regexp", "--list", "-l"}):
        raise GitError(f"operación git no permitida en modo solo lectura: {' '.join(args[:2]) or '(vacía)'}")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C", GCM_INTERACTIVE="never")
    cmd = ["git", "-C", str(repo), "-c", f"core.hooksPath={NULL_HOOKS}", "-c", "core.fsmonitor=false",
           "-c", "color.ui=false", *args]
    try:
        out = subprocess.run(cmd, input=input_bytes, capture_output=True, timeout=timeout, env=env)
    except FileNotFoundError as exc:
        raise GitError("git no está instalado") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {args[0]} excedió {timeout}s") from exc
    if out.returncode != 0:
        raise GitError((out.stderr or b"").decode("utf-8", "replace").strip() or f"git {args[0]} falló")
    return out.stdout if binary else out.stdout.decode("utf-8", "replace")


def is_repo(path: os.PathLike) -> bool:
    if not Path(path).is_dir():
        return False
    try:
        return git(path, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except GitError:
        return False


def toplevel(path: os.PathLike) -> Optional[Path]:
    try:
        return Path(git(path, "rev-parse", "--show-toplevel").strip())
    except GitError:
        return None


def resolve(path: os.PathLike, ref: str) -> Optional[str]:
    try:
        return git(path, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip() or None
    except GitError:
        return None


def current_branch(path: os.PathLike) -> Optional[str]:
    try:
        b = git(path, "rev-parse", "--abbrev-ref", "HEAD").strip()
    except GitError:
        return None
    return None if b == "HEAD" else b


def remote_url(path: os.PathLike, remote: str = "origin") -> Optional[str]:
    try:
        return git(path, "remote", "get-url", remote).strip() or None
    except GitError:
        return None


def status(path: os.PathLike) -> Dict[str, object]:
    """Estado del working tree (solo informativo: nunca se modifica)."""
    try:
        out = git(path, "status", "--porcelain=v1", "-b", "--untracked-files=no")
    except GitError as exc:
        return {"ok": False, "error": str(exc), "changes": [], "clean": False, "branch_line": ""}
    lines = out.splitlines()
    head = lines[0][3:] if lines and lines[0].startswith("## ") else ""
    changes = [(ln[:2], ln[3:]) for ln in lines[1:] if ln.strip()]
    return {"ok": True, "branch_line": head, "changes": changes, "clean": not changes}


def fetch(path: os.PathLike, remote: str = "origin", timeout: int = 180) -> Tuple[bool, str]:
    """Actualiza SOLO refs remotas. No toca ramas locales ni working tree."""
    try:
        git(path, "fetch", "--prune", "--no-tags", "--no-recurse-submodules", remote, timeout=timeout)
        return True, "fetch ok"
    except GitError as exc:
        return False, str(exc)


def commit_info(path: os.PathLike, ref: str) -> Dict[str, str]:
    out = git(path, "log", "-1", "--format=%H%x1f%cI%x1f%s", ref)
    sha, date, subject = (out.strip().split("\x1f") + ["", "", ""])[:3]
    return {"commit": sha, "date": date, "subject": subject}


def ls_tree(path: os.PathLike, ref: str) -> Dict[str, Tuple[str, int]]:
    """{ruta: (blob, bytes)} de todos los archivos del commit (sin submódulos ni symlinks)."""
    out = git(path, "ls-tree", "-r", "-l", "-z", ref, binary=True)
    files: Dict[str, Tuple[str, int]] = {}
    for rec in out.split(b"\x00"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        parts = meta.split()
        if len(parts) < 4 or parts[1] != b"blob" or parts[0] == b"120000":
            continue
        size = int(parts[3]) if parts[3].isdigit() else 0
        files[name.decode("utf-8", "replace")] = (parts[2].decode(), size)
    return files


def read_blobs(path: os.PathLike, blobs: List[str], max_bytes: int = 5_000_000) -> Dict[str, Optional[bytes]]:
    """Lee blobs en lote (`cat-file --batch`). Blobs > max_bytes → None (se indexa solo su hash)."""
    if not blobs:
        return {}
    uniq = list(dict.fromkeys(blobs))
    raw = git(path, "cat-file", "--batch", input_bytes=("\n".join(uniq) + "\n").encode(), binary=True, timeout=300)
    out: Dict[str, Optional[bytes]] = {}
    pos = 0
    for blob in uniq:
        nl = raw.index(b"\n", pos)
        header = raw[pos:nl].split()
        pos = nl + 1
        if len(header) < 3 or header[1] == b"missing":
            out[blob] = None
            continue
        size = int(header[2])
        data = raw[pos:pos + size]
        pos += size + 1
        out[blob] = None if size > max_bytes else data
    return out


def diff_name_status(path: os.PathLike, a: str, b: str) -> List[Tuple[str, str, Optional[str]]]:
    """[(estado, ruta, ruta_anterior)] entre dos commits, con detección de renombres."""
    out = git(path, "diff", "--name-status", "-M", "-z", a, b, binary=True).split(b"\x00")
    res: List[Tuple[str, str, Optional[str]]] = []
    i = 0
    while i < len(out) and out[i]:
        st = out[i].decode()
        if st.startswith(("R", "C")):
            res.append((st[0], out[i + 2].decode("utf-8", "replace"), out[i + 1].decode("utf-8", "replace")))
            i += 3
        else:
            res.append((st[0], out[i + 1].decode("utf-8", "replace"), None))
            i += 2
    return res


def log_between(path: os.PathLike, a: Optional[str], b: str, limit: int = 200) -> List[Dict[str, str]]:
    rng = f"{a}..{b}" if a else b
    try:
        out = git(path, "log", f"--max-count={limit}", "--format=%H%x1f%cI%x1f%s", rng)
    except GitError:
        return []
    res = []
    for line in out.splitlines():
        sha, date, subject = (line.split("\x1f") + ["", "", ""])[:3]
        res.append({"commit": sha, "date": date, "subject": subject})
    return res


def count_between(path: os.PathLike, a: str, b: str) -> Optional[int]:
    try:
        return int(git(path, "rev-list", "--count", f"{a}..{b}").strip())
    except (GitError, ValueError):
        return None


def remote_branches(path: os.PathLike, remote: str = "origin") -> List[Dict[str, str]]:
    try:
        out = git(path, "for-each-ref", "--format=%(refname:strip=3)%1f%(objectname)%1f%(committerdate:iso-strict)",
                  f"refs/remotes/{remote}")
    except GitError:
        return []
    res = []
    for line in out.splitlines():
        name, sha, date = (line.split("\x1f") + ["", "", ""])[:3]
        if name and name != "HEAD":
            res.append({"name": name, "commit": sha, "date": date})
    return res
