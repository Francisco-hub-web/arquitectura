"""Consumo y explotación (14-data-consumption-exploitation-framework)."""
from __future__ import annotations

import datetime as _dt
import re

from govkit.paths import registry
from govkit.plugins import at, at_file, line_of, plugin

LOCAL_FILTER = re.compile(r"(?i)(sql_always_where|always_filter|filters?)\s*:[^\n]*(is\s+not\s+null|<>\s*''|!=\s*''|"
                          r"not\s+in\s*\(\s*'n/?a')|not\s+isblank\s*\(|where[^\n]*\bis\s+not\s+null\b[^\n]*--\s*(fix|parche|limpieza)")


def _pattern(ctx):
    return str(ctx.dp_get("spec.consumption_pattern") or "")


def _as_list(v):
    return [str(x).lower() for x in (v if isinstance(v, list) else [v])] if v else []


@plugin("consumption.platform_matrix", needs_dp=True)
def platform_matrix(ctx, rule):
    pat = _pattern(ctx)
    conf = registry("consumption_matrix").get("patterns", {}).get(pat)
    if not conf:
        return
    platforms = _as_list(ctx.dp_get("spec.consumption.platform"))
    if not platforms:
        yield at(ctx.dp, "spec.consumption.platform", f"Plataforma de exposición no declarada (recomendadas para "
                 f"`{pat}`: {conf['platforms']})")
    for p in platforms:
        if p in conf.get("forbidden", []):
            yield at(ctx.dp, "spec.consumption.platform", f"Plataforma `{p}` prohibida para el patrón `{pat}` (14 §10, §15)",
                     severity="BLOCKER")
        elif p not in conf["platforms"]:
            yield at(ctx.dp, "spec.consumption.platform", f"Plataforma `{p}` no recomendada para `{pat}` "
                     f"(matriz 14 §14: {conf['platforms']})")
    serving = str(ctx.dp_get("spec.consumption.serving.type") or "").lower()
    if serving and serving not in conf.get("serving", []):
        yield at(ctx.dp, "spec.consumption.serving.type", f"Serving `{serving}` no corresponde al patrón `{pat}` "
                 f"(esperado: {conf.get('serving')})")


@plugin("consumption.certified_sources", needs_dp=True)
def certified_sources(ctx, rule):
    for i, inp in enumerate(ctx.dp_get("spec.inputs") or []):
        if not isinstance(inp, dict):
            continue
        blob = f"{inp.get('name', '')} {inp.get('source_system', '')}".lower()
        if str(inp.get("type", "")).lower() != "data_product":
            yield at(ctx.dp, f"spec.inputs[{i}].type", f"Input '{inp.get('name', i)}' de tipo `{inp.get('type')}`: un "
                     "Data Product de consumo solo se alimenta de Data Products maestros certificados (14 §8.2)")
        elif re.search(r"\b(bronze|brz|raw|landing)\b", blob):
            yield at(ctx.dp, f"spec.inputs[{i}]", f"Input '{inp.get('name', i)}' apunta a capa técnica (Bronze/raw)")


@plugin("consumption.api_serving", needs_dp=True)
def api_serving(ctx, rule):
    if _pattern(ctx) != "api_consulta_operacional":
        return
    forbidden = registry("consumption_matrix")["patterns"]["api_consulta_operacional"].get("forbidden_serving_tech", [])
    tech = str(ctx.dp_get("spec.consumption.serving.technology") or "").lower()
    if not tech:
        yield at(ctx.dp, "spec.consumption.serving.technology", "API operacional sin tecnología de serving declarada "
                 "(Redis, DynamoDB, PostgreSQL indexado...)")
    elif any(f in tech for f in forbidden):
        yield at(ctx.dp, "spec.consumption.serving.technology", f"API sobre `{tech}`: prohibido consumir almacenamiento "
                 "analítico sin Serving Layer operacional intermedia (14 §10.5)", severity="BLOCKER")


@plugin("consumption.inactivity", needs_dp=True)
def inactivity(ctx, rule):
    last = ctx.dp_get("spec.adoption.last_usage")
    if not last:
        return
    try:
        d = last if isinstance(last, _dt.date) else _dt.date.fromisoformat(str(last))
    except ValueError:
        return
    days = (ctx.today - d).days
    limit = int(ctx.policies.get("inactivity_days", 60))
    if days > limit:
        yield at(ctx.dp, "spec.adoption.last_usage", f"Sin uso registrado hace {days} días (> {limit}): reclasificar "
                 "como candidato a retiro (14 §17, §21)")


@plugin("consumption.bi_detail", needs_dp=True)
def bi_detail(ctx, rule):
    if not _pattern(ctx).startswith(("bi_", "analitica_embebida")):
        return
    gran = str(ctx.dp_get("spec.consumption.granularity") or "").lower()
    if "transacc" in gran or "unitario" in gran:
        yield at(ctx.dp, "spec.consumption.granularity", "Dashboard BI con granularidad transaccional: usar estructuras "
                 "resumidas de la Serving Layer o un DP de exploración/extracción (14 §8.7, §15.8)")


@plugin("consumption.local_quality_filters")
def local_quality_filters(ctx, rule):
    for rel in ctx.glob(["**/*.lkml", "**/*.dax", "**/*.tmdl", "publishing/**/*.sql"]):
        text = ctx.text(rel) or ""
        m = LOCAL_FILTER.search(text)
        if m:
            yield at_file(rel, "Posible filtro local para ocultar problemas de calidad del maestro "
                          f"(`{m.group(0)[:60]}`) — corregir en el Data Product origen (14 §8.8)", line=line_of(text, m.start()))
