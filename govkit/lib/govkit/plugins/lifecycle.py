"""Ciclo de vida del Data Product (18-data-product-lifecycle)."""
from __future__ import annotations

from govkit.plugins import at, plugin
from govkit.yamlloc import parse_text


@plugin("lifecycle.transition", needs_dp=True)
def transition(ctx, rule):
    dp = ctx.dp
    if not dp or not ctx.base_ref:
        return
    old_text = ctx.base_text(dp.path)
    if not old_text:
        return
    old = parse_text(dp.path, old_text)
    prev, cur = old.get("spec.lifecycle.state") if not old.error else None, dp.get("spec.lifecycle.state")
    if not prev or not cur or prev == cur:
        return
    allowed = ctx.lifecycle.get("transitions", {}).get(prev, [])
    if cur not in allowed:
        yield at(dp, "spec.lifecycle.state", f"Transición `{prev}` → `{cur}` no permitida (desde `{prev}` solo: "
                 f"{allowed}). Los saltos de estado evitan los gates del lifecycle (18 §22)")


@plugin("lifecycle.catalog_status", needs_dp=True)
def catalog_status(ctx, rule):
    docs = [d for d in ctx.artifact("openmetadata") if not d.error and isinstance(d.data, dict)]
    state = ctx.dp_get("spec.lifecycle.state")
    if not docs or not state:
        return
    expected = ctx.lifecycle["states"].get(state, {}).get("catalog_status")
    status = docs[0].get("status") or docs[0].get("dataProduct.status")
    if expected and status != expected:
        yield at(docs[0], "status", f"Estado de catálogo `{status}` ≠ `{expected}` esperado para `{state}` (18 §27)",
                 fix={"type": "set", "path": "status", "value": expected})
