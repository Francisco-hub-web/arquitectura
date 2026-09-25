"""Estructura del repositorio (lineamiento "Estructura de Repositorio" + 15-dataops-cicd §14, §23)."""
from __future__ import annotations

import json
import re
import unicodedata

from govkit.plugins import at_file, plugin

STANDARD_TOP = {".github", "contracts", "docs", "metadata", "modeling", "observability", "pipelines",
                "publishing", "quality", "shared", "src", "tests"}
README_SECTIONS = {
    "propósito / descripción": ("proposito", "descripcion", "description", "purpose", "resumen", "objetivo"),
    "owners / ownership": ("owner", "responsable", "ownership", "equipo"),
    "inputs / outputs": ("input", "output", "entrada", "salida", "fuentes", "consumidores"),
    "SLA": ("sla", "slo", "frescura", "freshness"),
    "branches / flujo de trabajo": ("branch", "rama", "flujo", "workflow", "contribu"),
    "runbook / operación": ("runbook", "operacion", "soporte", "troubleshooting", "contingencia"),
}


def norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


@plugin("structure.unknown_top_level")
def unknown_top_level(ctx, rule):
    allowed = STANDARD_TOP | set(ctx.policies.get("allowed_extra_top_level", []))
    for d in ctx.dirs():
        if "/" not in d and d not in allowed and not d.startswith("."):
            yield at_file(d, f"Carpeta raíz no estándar `{d}/` (la estructura de repositorio es fija)",
                          fix={"type": "move_or_adr", "path": d})


@plugin("structure.readme_sections")
def readme_sections(ctx, rule):
    text = ctx.text("README.md")
    if text is None:
        return
    headings = norm(" ".join(l for l in text.splitlines() if l.lstrip().startswith("#")))
    missing = [label for label, keys in README_SECTIONS.items() if not any(k in headings for k in keys)]
    if missing:
        yield at_file("README.md", f"README sin secciones mínimas: {', '.join(missing)}", missing=missing)


@plugin("structure.asl_valid")
def asl_valid(ctx, rule):
    for rel in ctx.glob(ctx.artifact_globs.get("asl", [])):
        text = ctx.text(rel) or ""
        try:
            asl = json.loads(text)
        except json.JSONDecodeError as exc:
            yield at_file(rel, f"Definición Step Functions no es JSON válido: {exc.msg}", line=exc.lineno)
            continue
        if not isinstance(asl, dict) or "StartAt" not in asl or "States" not in asl:
            yield at_file(rel, "Definición ASL sin `StartAt` y/o `States`")
            continue
        if asl["StartAt"] not in asl["States"]:
            yield at_file(rel, f"`StartAt` apunta a un estado inexistente: {asl['StartAt']}")
        for name, st in asl["States"].items():
            nxt = st.get("Next") if isinstance(st, dict) else None
            if nxt and nxt not in asl["States"]:
                line = text[:text.find(f'"{nxt}"')].count("\n") + 1 if f'"{nxt}"' in text else 1
                yield at_file(rel, f"Estado `{name}` → `Next` inexistente `{nxt}`", line=line, key=f"{rel}:{name}")


@plugin("structure.adr_format")
def adr_format(ctx, rule):
    for rel in ctx.glob("docs/adr/*.md"):
        name = rel.rsplit("/", 1)[-1]
        if name.lower() in ("readme.md", "template.md", "0000-template.md"):
            continue
        if not re.match(r"^(ADR-)?\d{3,4}[-_][a-z0-9-_]+\.md$", name, re.IGNORECASE):
            yield at_file(rel, f"ADR `{name}` no sigue el formato NNNN-titulo-en-kebab.md")
        body = norm(ctx.text(rel) or "")
        missing = [s for s in ("contexto", "decision", "consecuencias") if s not in body]
        if missing:
            yield at_file(rel, f"ADR sin secciones: {', '.join(missing)}", missing=missing)


@plugin("structure.syntax")
def syntax(ctx, rule):
    """Analizador sintáctico: todo YAML/JSON del repo debe parsear (pre-requisito del resto de checks)."""
    for rel in ctx.glob(["**/*.yaml", "**/*.yml", "**/*.json"]):
        if ctx.text(rel) is None:
            continue
        doc = ctx.doc(rel)
        if doc.error:
            yield at_file(rel, doc.error, line=doc.error_line)
