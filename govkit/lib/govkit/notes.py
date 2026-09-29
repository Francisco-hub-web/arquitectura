"""Notas reutilizables: cada respuesta guardada como Markdown en `~/.govkit/notas/` (fuera de cualquier repo).

Sirven para retomar o sumar contexto después (`govkit -p --nota 3 "…"`, `--sumar 3`), copiarlas a otro lugar
(`govkit notas copiar 3`) o exportarlas todas (`govkit notas exportar`). También accesibles desde Claude Code vía MCP.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

_HEAD = re.compile(r"^---\n(.*?)\n---\n", re.S)


def notes_dir() -> Path:
    d = Path(os.environ.get("GOVKIT_NOTES_DIR") or Path.home() / ".govkit" / "notas")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower().encode("ascii", "ignore").decode())[:48].strip("-")
    return s or "nota"


def _parse(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8")
    meta: Dict[str, object] = {}
    m = _HEAD.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    meta["body"] = text[m.end():] if m else text
    meta["path"] = str(path)
    meta["id"] = int(path.name.split("-", 1)[0])
    return meta


def all_notes() -> List[Dict[str, object]]:
    return sorted((_parse(p) for p in notes_dir().glob("[0-9][0-9][0-9][0-9]-*.md")), key=lambda n: n["id"])


def get(note_id: int) -> Optional[Dict[str, object]]:
    hit = list(notes_dir().glob(f"{int(note_id):04d}-*.md"))
    return _parse(hit[0]) if hit else None


def save(title: str, body: str, repo: str = "", folder: str = "", tags: str = "") -> Dict[str, object]:
    existing = [n["id"] for n in all_notes()]
    nid = (max(existing) + 1) if existing else 1
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    head = [f"id: {nid}", f"fecha: {now}", f'titulo: "{title.strip()[:120]}"']
    if repo:
        head.append(f"repo: {repo}")
    if folder:
        head.append(f"carpeta: {folder}")
    if tags:
        head.append(f"tags: {tags}")
    path = notes_dir() / f"{nid:04d}-{_slug(title)}.md"
    path.write_text("---\n" + "\n".join(head) + "\n---\n" + body.strip() + "\n", encoding="utf-8")
    return _parse(path)


def append(note_id: int, title: str, body: str) -> Optional[Dict[str, object]]:
    note = get(note_id)
    if not note:
        return None
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(str(note["path"]), "a", encoding="utf-8") as fh:
        fh.write(f"\n---\n\n## {now} · {title.strip()[:120]}\n\n{body.strip()}\n")
    return get(note_id)


def delete(note_id: int) -> bool:
    note = get(note_id)
    if not note:
        return False
    Path(str(note["path"])).unlink()
    return True


def as_context(note_ids: List[int]) -> str:
    parts = []
    for i in note_ids:
        n = get(i)
        if n:
            parts.append(f"<nota id=\"{i}\" titulo=\"{n.get('titulo', '')}\">\n{str(n['body']).strip()}\n</nota>")
    if not parts:
        return ""
    return ("Contexto guardado por el usuario en sesiones anteriores (úsalo como base; complétalo o corrígelo):\n"
            + "\n\n".join(parts) + "\n\n")


def export(notes: List[Dict[str, object]]) -> str:
    out = ["# Notas de gobierno de datos", ""]
    for n in notes:
        out += [f"## #{n['id']} · {n.get('titulo', '')}", f"_{n.get('fecha', '')} · {n.get('repo', '')}_", "",
                str(n["body"]).strip(), ""]
    return "\n".join(out) + "\n"
