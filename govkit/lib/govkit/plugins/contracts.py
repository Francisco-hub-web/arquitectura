"""Data Contracts (01 §6, 06 §11, 15-dataops-cicd §17/§20, Estructura de Repositorio `contracts/`)."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from govkit.plugins import at, at_file, plugin
from govkit.plugins.product import schema_findings
from govkit.yamlloc import parse_text

_ISO_DUR = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


def interface_contracts(ctx):
    return [d for d in ctx.artifact("contracts_interface") if not d.error]


def _fields(data) -> Dict[str, dict]:
    out = {}
    for f in ((data or {}).get("spec", {}) or {}).get("schema", []) or []:
        if isinstance(f, dict) and f.get("name"):
            out[str(f["name"])] = f
    return out


def _major(v) -> Optional[int]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(v or ""))
    return int(m.group(1)) if m else None


def breaking_changes(old: dict, new: dict, direction: str) -> List[str]:
    reasons = []
    of, nf = _fields(old), _fields(new)
    for name, f in of.items():
        if name not in nf:
            reasons.append(f"campo eliminado/renombrado `{name}`")
            continue
        if str(f.get("type")) != str(nf[name].get("type")):
            reasons.append(f"cambio de tipo en `{name}` ({f.get('type')} → {nf[name].get('type')})")
        if direction == "output" and f.get("required") and not nf[name].get("required"):
            reasons.append(f"`{name}` deja de ser obligatorio (consumidores asumen no-nulo)")
    if direction == "input":
        reasons += [f"nuevo campo obligatorio `{n}` exigido al productor" for n, f in nf.items()
                    if n not in of and f.get("required")]
    os_, ns_ = (old.get("spec") or {}), (new.get("spec") or {})
    if os_.get("business_keys") and os_.get("business_keys") != ns_.get("business_keys"):
        reasons.append("cambio de claves de negocio")
    if os_.get("granularity") and os_.get("granularity") != ns_.get("granularity"):
        reasons.append("cambio de granularidad")
    return reasons


@plugin("contracts.schema_valid")
def schema_valid(ctx, rule):
    for doc in ctx.artifact("contracts_interface"):
        yield from schema_findings(doc, "contract")


@plugin("contracts.input_coverage")
def input_coverage(ctx, rule):
    dp = ctx.dp
    if not dp or not isinstance(dp.data, dict):
        return
    names = {str(d.get("metadata.name")) for d in ctx.artifact("contracts_input") if not d.error}
    for i, inp in enumerate(dp.get("spec.inputs") or []):
        if not isinstance(inp, dict):
            continue
        ref = inp.get("contract")
        if (ref and ctx.exists(str(ref))) or str(inp.get("name")) in names:
            continue
        yield at(dp, f"spec.inputs[{i}]", f"Input '{inp.get('name', i)}' sin contrato de entrada en contracts/input/",
                 fix={"type": "create", "path": f"contracts/input/{inp.get('name', 'input')}.yaml"})


@plugin("contracts.dp_ref")
def dp_ref(ctx, rule):
    dp_id = ctx.dp_get("metadata.id")
    if not dp_id:
        return
    for doc in interface_contracts(ctx):
        ref = doc.get("metadata.data_product")
        if ref and ref != dp_id:
            yield at(doc, "metadata.data_product", f"Contrato apunta a `{ref}` pero el Data Product del repo es `{dp_id}`")


@plugin("contracts.gold_model_coverage")
def gold_model_coverage(ctx, rule):
    contract_names = set()
    for doc in ctx.artifact("contracts_all"):
        contract_names.add(doc.path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        if not doc.error and isinstance(doc.data, dict):
            contract_names.add(str(doc.get("metadata.name")))
    for rel in ctx.glob("modeling/dbt/models/gold/**/*.sql"):
        stem = rel.rsplit("/", 1)[-1][:-4]
        if stem.startswith(("dim_", "fact_")) and stem not in contract_names:
            sub = "dim" if stem.startswith("dim_") else "fact"
            yield at_file(rel, f"Modelo Gold `{stem}` sin contrato en contracts/gold/{sub}/",
                          fix={"type": "create", "path": f"contracts/gold/{sub}/{stem}.yaml"})


@plugin("contracts.breaking_change")
def breaking_change(ctx, rule):
    if not ctx.base_ref:
        return
    for doc in interface_contracts(ctx):
        old_text = ctx.base_text(doc.path)
        if not old_text:
            continue
        old = parse_text(doc.path, old_text)
        if old.error or not isinstance(old.data, dict) or not isinstance(doc.data, dict):
            continue
        direction = str(doc.get("spec.direction", "output"))
        reasons = breaking_changes(old.data, doc.data, direction)
        o_ver, n_ver = old.get("metadata.version"), doc.get("metadata.version")
        if reasons and (_major(n_ver) or 0) <= (_major(o_ver) or 0):
            yield at(doc, "metadata.version", f"Breaking change sin bump MAJOR ({o_ver} → {n_ver}): {'; '.join(reasons)}",
                     reasons=reasons, fix={"type": "bump", "part": "major"})
        elif not reasons and _fields(old.data) != _fields(doc.data) and o_ver == n_ver:
            yield at(doc, "metadata.version", f"Schema modificado sin cambiar versión ({n_ver}): usar MINOR/PATCH",
                     severity="MEDIUM", fix={"type": "bump", "part": "minor"})


@plugin("contracts.changelog_on_change")
def changelog_on_change(ctx, rule):
    changed = ctx.changed_files()
    if not changed:
        return
    touched = [f for f in changed if f.startswith("contracts/")]
    if touched and "CHANGELOG.md" not in changed:
        yield at_file(touched[0], f"Se modificaron {len(touched)} contrato(s) sin entrada en CHANGELOG.md", key="changelog")


def _dur_hours(v) -> Optional[float]:
    m = _ISO_DUR.match(str(v or "").strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi = (int(x or 0) for x in m.groups())
    return d * 24 + h + mi / 60


@plugin("contracts.sla_consistency")
def sla_consistency(ctx, rule):
    dp_fresh = _dur_hours(ctx.dp_get("spec.sla.freshness"))
    if dp_fresh is None:
        return
    for doc in interface_contracts(ctx):
        if doc.get("spec.direction") != "output":
            continue
        c = _dur_hours(doc.get("spec.sla.freshness"))
        if c is not None and c > dp_fresh:
            yield at(doc, "spec.sla.freshness", f"Freshness del contrato ({doc.get('spec.sla.freshness')}) más laxa que "
                     f"la del Data Product ({ctx.dp_get('spec.sla.freshness')})")
