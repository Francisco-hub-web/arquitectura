"""Análisis léxico de SQL/dbt (capas, desacople, sobrescritura destructiva, tests y documentación)."""
from __future__ import annotations

import re

from govkit.plugins import at_file, line_of, plugin

COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
BRONZE_REF = re.compile(r"(?i)source\(\s*['\"][^'\"]*(bronze|brz|raw)[^'\"]*['\"]|\bdlk_brz_\w+|\bbronze\.\w+")
SILVER_OR_BRONZE = re.compile(r"(?i)\bdlk_(brz|slv)_\w+|\b(bronze|silver)\.\w+|source\(\s*['\"][^'\"]*(bronze|brz|silver|slv|raw)")
SELECT_STAR = re.compile(r"(?i)\bselect\s+(distinct\s+)?\*\s")
HARDCODED = re.compile(r"(?i)\b(from|join)\s+(`|\")?(dlk_[a-z0-9_]+|[a-z0-9_]+_(dev|prd|prod|stg))(`|\")?\.\w+")
DESTRUCTIVE = re.compile(r"(?i)\b(truncate\s+table|drop\s+table|insert\s+overwrite|delete\s+from\s+\w+\s*;|"
                         r"delete\s+from\s+\w+\s*$)", re.MULTILINE)


def sql_body(ctx, rel: str) -> str:
    """SQL sin comentarios pero preservando saltos de línea (para reportar líneas exactas)."""
    text = ctx.text(rel) or ""
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


@plugin("sql.no_bronze_in_gold")
def no_bronze_in_gold(ctx, rule):
    for rel in ctx.glob(["modeling/dbt/models/gold/**/*.sql", "modeling/dbt/models/semantic/**/*.sql",
                         "src/gold/**/*.sql", "src/semantic/**/*.sql"]):
        body = sql_body(ctx, rel)
        m = BRONZE_REF.search(body)
        if m:
            yield at_file(rel, f"Modelo de consumo lee Bronze directamente (`{m.group(0)}`): consumir desde Silver/Gold",
                          line=line_of(body, m.start()))


@plugin("sql.publishing_sources")
def publishing_sources(ctx, rule):
    for rel in ctx.glob(["publishing/**/*.sql", "publishing/**/*.lkml", "publishing/**/*.yml", "publishing/**/*.yaml"]):
        body = sql_body(ctx, rel)
        m = SILVER_OR_BRONZE.search(body)
        if m:
            yield at_file(rel, f"Publicación a consumidores desde capa técnica (`{m.group(0)}`): exponer solo Gold/Serving/Semantic",
                          line=line_of(body, m.start()))


@plugin("sql.select_star")
def select_star(ctx, rule):
    for rel in ctx.glob(["modeling/dbt/models/gold/**/*.sql", "modeling/dbt/models/semantic/**/*.sql",
                         "publishing/**/*.sql"]):
        body = sql_body(ctx, rel)
        for m in SELECT_STAR.finditer(body):
            after = body[m.end():m.end() + 80].lower()
            if after.lstrip().startswith("from") and re.match(r"\s*from\s+(final|renamed|joined|base|\w+_final)\b", after):
                continue  # patrón dbt `select * from final` sobre CTE con columnas explícitas
            yield at_file(rel, "`SELECT *` en capa de consumo: la interfaz debe ser explícita y estable (contrato)",
                          line=line_of(body, m.start()))
            break


@plugin("sql.hardcoded_relations")
def hardcoded_relations(ctx, rule):
    for rel in ctx.glob("modeling/dbt/models/**/*.sql"):
        body = sql_body(ctx, rel)
        m = HARDCODED.search(body)
        if m:
            yield at_file(rel, f"Relación física hardcodeada `{m.group(3)}...`: usar ref()/source() de dbt",
                          line=line_of(body, m.start()))


@plugin("sql.gold_key_tests")
def gold_key_tests(ctx, rule):
    ymls = {rel: ctx.doc(rel) for rel in ctx.glob(["modeling/dbt/models/**/*.yml", "modeling/dbt/models/**/*.yaml"])}
    tested = set()
    for doc in ymls.values():
        for m in (doc.get("models") or []) if isinstance(doc.data, dict) else []:
            if not isinstance(m, dict):
                continue
            blob = str(m)
            if re.search(r"unique|not_null|unique_combination_of_columns|primary_key", blob):
                tested.add(m.get("name"))
    for rel in ctx.glob("modeling/dbt/models/gold/**/*.sql"):
        stem = rel.rsplit("/", 1)[-1][:-4]
        if stem not in tested:
            yield at_file(rel, f"Modelo Gold `{stem}` sin tests de clave (unique / not_null) en schema.yml")


@plugin("sql.model_docs")
def model_docs(ctx, rule):
    described = set()
    for rel in ctx.glob(["modeling/dbt/models/**/*.yml", "modeling/dbt/models/**/*.yaml"]):
        doc = ctx.doc(rel)
        for m in (doc.get("models") or []) if isinstance(doc.data, dict) else []:
            if isinstance(m, dict) and len(str(m.get("description") or "").strip()) >= 20:
                described.add(m.get("name"))
    for rel in ctx.glob(["modeling/dbt/models/silver/**/*.sql", "modeling/dbt/models/gold/**/*.sql"]):
        stem = rel.rsplit("/", 1)[-1][:-4]
        if stem not in described:
            yield at_file(rel, f"Modelo `{stem}` sin descripción (≥20 caracteres) en schema.yml")
