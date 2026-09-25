"""Pack `portfolio`: auditoría cross-repo (periódica) sobre un directorio con N repos de Data Products."""
from __future__ import annotations

from collections import defaultdict

from govkit.plugins import at, plugin
from govkit.plugins.semantic import _formula, _norm


def products(ctx):
    for doc in ctx.artifact("portfolio_dps"):
        if not doc.error and isinstance(doc.data, dict) and doc.get("metadata.id"):
            yield doc


@plugin("portfolio.duplicate_ids")
def duplicate_ids(ctx, rule):
    seen = {}
    for doc in products(ctx):
        pid = doc.get("metadata.id")
        if pid in seen:
            yield at(doc, "metadata.id", f"ID `{pid}` duplicado (también en {seen[pid]})")
        seen.setdefault(pid, doc.path)


@plugin("portfolio.retired_consumed")
def retired_consumed(ctx, rule):
    dps = list(products(ctx))
    retired = {d.get("metadata.id") for d in dps if d.get("spec.lifecycle.state") in ("en_retiro", "retirado")}
    for doc in dps:
        for i, inp in enumerate(doc.get("spec.inputs") or []):
            ref = isinstance(inp, dict) and inp.get("data_product_ref")
            if ref in retired:
                yield at(doc, f"spec.inputs[{i}].data_product_ref", f"Consume `{ref}`, que está en retiro/retirado (18 §30)")


@plugin("portfolio.dangling_refs")
def dangling_refs(ctx, rule):
    dps = list(products(ctx))
    ids = {d.get("metadata.id") for d in dps}
    for doc in dps:
        for i, inp in enumerate(doc.get("spec.inputs") or []):
            ref = isinstance(inp, dict) and inp.get("data_product_ref")
            if ref and ref not in ids:
                yield at(doc, f"spec.inputs[{i}].data_product_ref", f"Referencia a Data Product desconocido `{ref}`")


@plugin("portfolio.consumo_from_master")
def consumo_from_master(ctx, rule):
    dps = list(products(ctx))
    role = {d.get("metadata.id"): d.get("spec.role") for d in dps}
    for doc in dps:
        if doc.get("spec.role") != "consumo":
            continue
        for i, inp in enumerate(doc.get("spec.inputs") or []):
            ref = isinstance(inp, dict) and inp.get("data_product_ref")
            if ref in role and role[ref] != "maestro":
                yield at(doc, f"spec.inputs[{i}].data_product_ref", f"DP de consumo alimentado por `{ref}` (rol "
                         f"`{role[ref]}`), no por un Data Product maestro (14 §8.2)")


@plugin("portfolio.metric_collisions")
def metric_collisions(ctx, rule):
    defs = defaultdict(list)
    for rel in ctx.glob(["**/modeling/dbt/models/**/*.yml", "**/modeling/dbt/models/**/*.yaml"]):
        doc = ctx.doc(rel)
        for i, m in enumerate((doc.get("metrics") or []) if isinstance(doc.data, dict) else []):
            if isinstance(m, dict) and m.get("name"):
                meta = m.get("meta") or (m.get("config") or {}).get("meta") or {}
                defs[_norm(m["name"])].append((doc, i, _formula(m, meta)))
    for name, items in defs.items():
        if len({f for _, _, f in items}) > 1:
            for doc, i, _ in items[1:]:
                yield at(doc, f"metrics[{i}].name", f"Métrica `{name}` con {len(items)} definiciones distintas en el "
                         f"portafolio ({', '.join(sorted({d.path.split('/')[0] for d, _, _ in items}))})")


@plugin("portfolio.overlap")
def overlap(ctx, rule):
    groups = defaultdict(list)
    for doc in products(ctx):
        if doc.get("spec.lifecycle.state") in ("retirado",):
            continue
        outs = {str(o.get("name")) for o in doc.get("spec.outputs") or [] if isinstance(o, dict)}
        groups[(doc.get("spec.domain"), doc.get("spec.subdomain"))].append((doc, outs))
    for (dom, sub), items in groups.items():
        for a in range(len(items)):
            for b in range(a + 1, len(items)):
                shared = items[a][1] & items[b][1]
                if shared:
                    yield at(items[b][0], "spec.outputs", f"Solapamiento con {items[a][0].get('metadata.id')} en "
                             f"{dom}/{sub}: outputs {sorted(shared)} → evaluar consolidación (18 §19)")
