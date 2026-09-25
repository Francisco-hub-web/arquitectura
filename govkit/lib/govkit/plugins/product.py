"""Ficha del Data Product (06-data-product-definition.md) — validaciones estructurales y relacionales."""
from __future__ import annotations

import json

from govkit.minischema import validate
from govkit.paths import SCHEMAS_DIR
from govkit.plugins import at, at_file, plugin

_SCHEMAS = {}


def schema(name: str) -> dict:
    if name not in _SCHEMAS:
        with open(SCHEMAS_DIR / f"{name}.schema.json", encoding="utf-8") as fh:
            _SCHEMAS[name] = json.load(fh)
    return _SCHEMAS[name]


def schema_findings(doc, name: str):
    if doc.error:
        yield at_file(doc.path, doc.error, line=doc.error_line)
        return
    for path, msg in validate(doc.data, schema(name))[:40]:
        yield at(doc, path or None, f"`{path or '(raíz)'}`: {msg}")


@plugin("product.schema_valid")
def schema_valid(ctx, rule):
    if ctx.dp:
        yield from schema_findings(ctx.dp, "data_product")


@plugin("product.active_consumer", needs_dp=True)
def active_consumer(ctx, rule):
    dp = ctx.dp
    if not dp or not isinstance(dp.data, dict):
        return
    consumers = dp.get("spec.consumers") or []
    if not any(isinstance(c, dict) and str(c.get("status", "")).lower() in ("activo", "validado") for c in consumers):
        yield at(dp, "spec.consumers", "Ningún consumidor en estado `activo` o `validado` (criterio de certificación 06 §25)")


@plugin("product.dp_input_refs", needs_dp=True)
def dp_input_refs(ctx, rule):
    dp = ctx.dp
    if not dp or not isinstance(dp.data, dict):
        return
    for i, inp in enumerate(dp.get("spec.inputs") or []):
        if not isinstance(inp, dict) or str(inp.get("type", "")).lower() != "data_product":
            continue
        for key in ("data_product_ref", "contract_version"):
            if not inp.get(key):
                yield at(dp, f"spec.inputs[{i}].{key}", f"Input '{inp.get('name', i)}' de tipo data_product sin `{key}`: "
                         "la dependencia entre productos debe declararse por contrato versionado")
