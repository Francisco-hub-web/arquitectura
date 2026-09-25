"""Análisis AST de jobs Python/PySpark y reglas de arquitectura de almacenamiento (01 §5, §7)."""
from __future__ import annotations

import ast
import re

from govkit.paths import registry
from govkit.plugins import at, at_file, line_of, plugin
from govkit.plugins.sql import DESTRUCTIVE, sql_body

TIME_TRAVEL = {"iceberg", "delta", "hudi"}


def _critical(ctx) -> bool:
    return str(ctx.dp_get("spec.criticality", "")).lower() in ("alta", "critica")


def _overwrites(tree):
    """Detecta `.mode("overwrite")`, `.saveAsTable(..., mode="overwrite")` e `insertInto(..., overwrite=True)`."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        if attr == "mode" and node.args and isinstance(node.args[0], ast.Constant) \
                and str(node.args[0].value).lower() == "overwrite":
            yield node, ".mode('overwrite')"
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and str(kw.value.value).lower() == "overwrite":
                yield node, f".{attr}(mode='overwrite')"
            if attr == "insertInto" and kw.arg == "overwrite" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                yield node, ".insertInto(overwrite=True)"
        if attr == "sql" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            if DESTRUCTIVE.search(node.args[0].value):
                yield node, "spark.sql(<sentencia destructiva>)"


@plugin("arch.destructive_writes")
def destructive_writes(ctx, rule):
    if not _critical(ctx):
        return
    sev = "BLOCKER" if str(ctx.dp_get("spec.criticality")).lower() == "critica" else None
    for rel in ctx.glob(["src/**/*.py", "shared/**/*.py"]):
        try:
            tree = ast.parse(ctx.text(rel) or "")
        except SyntaxError:
            continue
        for node, what in _overwrites(tree):
            yield at_file(rel, f"Sobrescritura destructiva `{what}` en producto de criticidad "
                          f"`{ctx.dp_get('spec.criticality')}`: usar MERGE/append sobre tabla con Time Travel (01 §5)",
                          line=node.lineno, col=node.col_offset + 1, severity=sev)
    for rel in ctx.glob(["src/**/*.sql", "modeling/dbt/models/**/*.sql"]):
        body = sql_body(ctx, rel)
        m = DESTRUCTIVE.search(body)
        if m:
            yield at_file(rel, f"Sentencia destructiva `{m.group(0).strip()}` en producto crítico (01 §5)",
                          line=line_of(body, m.start()), severity=sev)


def table_formats(ctx):
    found = {}
    declared = ctx.dp_get("spec.modeling.table_format")
    if declared:
        found["spec.modeling.table_format"] = str(declared).lower()
    for rel in ctx.glob(["modeling/dbt/dbt_project.yml", "modeling/dbt/profiles.yml"]):
        m = re.search(r"(?im)^\s*\+?(file_format|table_type|datalake_formats)\s*:\s*['\"]?(\w+)", ctx.text(rel) or "")
        if m:
            found[rel] = m.group(2).lower()
    return found


@plugin("arch.time_travel_format", needs_dp=True)
def time_travel_format(ctx, rule):
    formats = table_formats(ctx)
    if not formats:
        if ctx.dp:
            yield at(ctx.dp, "spec.modeling.table_format", "Formato de tabla no declarado: se exige almacenamiento con "
                     "Time Travel (iceberg | delta | hudi)")
        return
    for where, fmt in formats.items():
        if fmt not in TIME_TRAVEL:
            sev = "BLOCKER" if str(ctx.dp_get("spec.criticality")).lower() == "critica" else None
            if where.startswith("spec."):
                yield at(ctx.dp, where, f"Formato `{fmt}` sin Time Travel (01 §5)", severity=sev)
            else:
                yield at_file(where, f"Formato `{fmt}` sin Time Travel en configuración dbt (01 §5)", severity=sev)


@plugin("arch.tech_domain", needs_dp=True)
def tech_domain(ctx, rule):
    forbidden = set(registry("domains").get("forbidden_names", []))
    for key in ("spec.domain", "spec.subdomain"):
        val = str(ctx.dp_get(key) or "").lower()
        if val and (val in forbidden or any(t in forbidden for t in re.split(r"[_\-]", val))):
            yield at(ctx.dp, key, f"`{val}` es un nombre orientado a tecnología/sistema origen: los dominios deben ser "
                     "de negocio (Customer, Sales, Pricing...) (01 §7, 02.1 §19)")


@plugin("dataops.hardcoded_env")
def hardcoded_env(ctx, rule):
    rx = re.compile(r"['\"](?:[^'\"]*\b\d{12}\b[^'\"]*|[^'\"]*-(?:prd|prod|dev|stg)-[^'\"]*|[^'\"]*_(?:prd|prod)_[^'\"]*)['\"]")
    for rel in ctx.glob(["src/**/*.py", "shared/**/*.py"]):
        text = ctx.text(rel) or ""
        m = rx.search(text)
        if m:
            yield at_file(rel, f"Valor dependiente de ambiente hardcodeado {m.group(0)[:60]}: externalizar en config/ "
                          "(15 §22)", line=line_of(text, m.start()))
