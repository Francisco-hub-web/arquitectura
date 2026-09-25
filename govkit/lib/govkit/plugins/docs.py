"""Pack `docs`: lint de la propia documentación del Data & AI Discipline Framework.

La base de conocimiento solo es confiable si la fuente es consistente: referencias cruzadas
a documentos inexistentes o renumerados rompen la trazabilidad regla → documento → sección.
"""
from __future__ import annotations

import re

from govkit.plugins import at_file, plugin

REF = re.compile(r"(?<![\w/])(\d{2}(?:\.\d+)?-[a-z0-9-]+\.md)")
HEADER_KEYS = ("versión", "estado", "alcance")
TOP = re.compile(r"^#\s+(?:\[)?(\d+)\\?\.\s", re.MULTILINE)
SUB = re.compile(r"^##\s+(\d+)\.(\d+)\s", re.MULTILINE)
PENDING = re.compile(r"(?i)(nota\s*:?\*{0,2}\s*[^\n]*(pendiente|revisar|validar|deber[ií]a|queda)|\(revisar[^)]*\)|"
                     r"\(a revisar\)|pendiente validar|por revisar|todo:)")


def docs(ctx):
    return [f for f in ctx.glob(ctx.artifact_globs.get("framework_docs", ["**/*.md"])) if REF.match(f.rsplit("/", 1)[-1])]


def _slug(name: str) -> str:
    return re.sub(r"^\d{2}(?:\.\d+)?-", "", name)


@plugin("docs.cross_refs")
def cross_refs(ctx, rule):
    files = docs(ctx)
    names = {f.rsplit("/", 1)[-1] for f in files}
    by_slug = {_slug(n): n for n in names}
    for rel in files:
        text = ctx.text(rel) or ""
        seen = set()
        for m in REF.finditer(text):
            ref = m.group(1)
            if ref in names or ref in seen:
                continue
            seen.add(ref)
            line = text.count("\n", 0, m.start()) + 1
            hint = by_slug.get(_slug(ref))
            msg = f"Referencia a `{ref}` inexistente" + (f" — ¿quiso decir `{hint}`? (numeración distinta)" if hint else "")
            yield at_file(rel, msg, line=line, ref=ref)


@plugin("docs.header")
def header(ctx, rule):
    for rel in docs(ctx):
        head = (ctx.text(rel) or "")[:1200].lower()
        missing = [k for k in HEADER_KEYS if k not in head]
        if missing:
            yield at_file(rel, f"Encabezado sin: {missing}")


@plugin("docs.section_numbering")
def section_numbering(ctx, rule):
    for rel in docs(ctx):
        text = ctx.text(rel) or ""
        prev = 0
        for m in TOP.finditer(text):
            n = int(m.group(1))
            if n != prev + 1:
                line = text.count("\n", 0, m.start()) + 1
                kind = "duplicada" if n == prev else ("salto" if n > prev + 1 else "retroceso")
                yield at_file(rel, f"Numeración de secciones: {kind} {prev} → {n}", line=line, key=f"{rel}:{n}")
            prev = n
        last = {}
        for m in SUB.finditer(text):
            sec, sub = int(m.group(1)), int(m.group(2))
            if sec in last and sub < last[sec]:
                line = text.count("\n", 0, m.start()) + 1
                yield at_file(rel, f"Subsección {sec}.{sub} aparece después de {sec}.{last[sec]}", line=line,
                              key=f"{rel}:{sec}.{sub}")
            last[sec] = max(last.get(sec, 0), sub)


@plugin("docs.final_rule")
def final_rule(ctx, rule):
    for rel in docs(ctx):
        if "regla final" not in (ctx.text(rel) or "").lower():
            yield at_file(rel, "Documento sin 'Regla final' (patrón editorial del framework)")


@plugin("docs.pending_notes")
def pending_notes(ctx, rule):
    for rel in docs(ctx):
        text = ctx.text(rel) or ""
        for m in PENDING.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            snippet = text[m.start():text.find("\n", m.start())].strip()[:110]
            yield at_file(rel, f"Pendiente documental: {snippet}", line=line)
