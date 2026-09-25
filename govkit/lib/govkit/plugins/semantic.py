"""Semantic layer y métricas (01 §9, 11-semantic-layer-framework, 14 §12, §15.7)."""
from __future__ import annotations

import re
import unicodedata

from govkit.paths import registry
from govkit.plugins import at, at_file, line_of, plugin
from govkit.plugins.metadata import glossary_terms

METRIC_REQUIRED = ["owner", "glossary_term", "unit", "granularity", "aggregation", "source_data_product",
                   "source_fields", "sensitivity"]


def _norm(name: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", str(name).lower()) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def metrics(ctx):
    for rel in ctx.glob(ctx.artifact_globs.get("dbt_yml", [])):
        doc = ctx.doc(rel)
        if doc.error or not isinstance(doc.data, dict):
            continue
        for i, m in enumerate(doc.get("metrics") or []):
            if isinstance(m, dict) and m.get("name"):
                meta = m.get("meta") or (m.get("config") or {}).get("meta") or {}
                mpath = f"metrics[{i}].meta" if "meta" in m else f"metrics[{i}].config.meta"
                yield doc, i, m, meta, mpath


def _formula(m, meta) -> str:
    return str(meta.get("formula") or m.get("type_params") or m.get("expr") or "")


@plugin("semantic.metric_card")
def metric_card(ctx, rule):
    for doc, i, m, meta, mpath in metrics(ctx):
        missing = [k for k in METRIC_REQUIRED if meta.get(k) in (None, "", [])]
        if len(str(m.get("description") or "").strip()) < 20:
            missing.insert(0, "description")
        if not m.get("label"):
            missing.insert(0, "label")
        if not _formula(m, meta):
            missing.append("fórmula (type_params / meta.formula)")
        if missing:
            yield at(doc, f"metrics[{i}]", f"Ficha de métrica `{m['name']}` incompleta: faltan {missing} (11 §15)",
                     missing=missing)


@plugin("semantic.metric_unique")
def metric_unique(ctx, rule):
    seen = {}
    for doc, i, m, meta, _ in metrics(ctx):
        key = _norm(m["name"])
        sig = _formula(m, meta) + "|" + str(meta.get("filters", ""))
        if key in seen and seen[key][1] != sig:
            first = seen[key][0]
            yield at(doc, f"metrics[{i}].name", f"Métrica `{m['name']}` definida más de una vez con fórmulas distintas "
                     f"(primera en {first}): una métrica = una definición oficial (11 §30)")
        seen.setdefault(key, (f"{doc.path}", sig))


def corporate_index():
    reg = registry("corporate_metrics")
    idx = {}
    for name, info in (reg.get("metrics") or {}).items():
        idx[_norm(name)] = name
        for a in (info or {}).get("aliases", []):
            idx[_norm(a)] = name
    return idx, set(reg.get("owner_repos") or [])


@plugin("semantic.corporate_metrics")
def corporate_metrics(ctx, rule):
    idx, owners = corporate_index()
    if ctx.repo_name in owners:
        return
    for doc, i, m, meta, _ in metrics(ctx):
        corp = idx.get(_norm(m["name"])) or idx.get(_norm(m.get("label", "")))
        if corp and str(meta.get("tier", "")).lower() != "referencia":
            yield at(doc, f"metrics[{i}].name", f"Redefinición local de la métrica corporativa `{corp}`: se gobierna "
                     "centralmente y se hereda desde la Semantic Layer (14 §12.2, §15.7)")


@plugin("semantic.metric_glossary")
def metric_glossary(ctx, rule):
    known = glossary_terms(ctx)
    for doc, i, m, meta, mpath in metrics(ctx):
        term = meta.get("glossary_term")
        if term and str(term).lower() not in known:
            yield at(doc, f"{mpath}.glossary_term", f"Métrica `{m['name']}` apunta a término de glosario inexistente `{term}`")


BI_MEASURE = [
    ("LookML", re.compile(r"(?m)^\s*measure:\s*([A-Za-z0-9_]+)\s*\{")),
    ("DAX", re.compile(r"(?m)^\s*'?([A-Za-zÁÉÍÓÚáéíóúñÑ0-9 _]+?)'?\s*:=")),
    ("TMDL", re.compile(r"(?m)^\s*measure\s+'?([^'=\n]+?)'?\s*=")),
]


@plugin("semantic.bi_logic")
def bi_logic(ctx, rule):
    idx, _ = corporate_index()
    for rel in ctx.glob(["**/*.lkml", "**/*.dax", "**/*.tmdl", "**/*.bim"]):
        text = ctx.text(rel) or ""
        for label, rx in BI_MEASURE:
            for mm in rx.finditer(text):
                corp = idx.get(_norm(mm.group(1)))
                if corp:
                    yield at_file(rel, f"Métrica corporativa `{corp}` definida en herramienta BI ({label}): la lógica "
                                  "estratégica vive en la Semantic Layer, no en el dashboard (11 §19)",
                                  line=line_of(text, mm.start()))
