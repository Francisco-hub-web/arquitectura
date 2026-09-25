"""Metadata as control plane (01 §3, 09-metadata-governance, 15-dataops-cicd §18)."""
from __future__ import annotations

import datetime as _dt

from govkit.declarative import check_value, is_placeholder
from govkit.paths import registry
from govkit.plugins import at, plugin

LAYER_ORDER = ["bronze", "silver", "gold", "semantic", "serving", "feature"]
OWNER_KEYS = ["business_owner", "data_owner", "data_steward", "technical_owner", "architect",
              "security_contact", "bi_lead", "ml_owner"]


def _date(v):
    if isinstance(v, _dt.date):
        return v
    try:
        return _dt.date.fromisoformat(str(v))
    except ValueError:
        return None


@plugin("metadata.domain_registered", needs_dp=True)
def domain_registered(ctx, rule):
    dom = ctx.dp_get("spec.domain")
    if dom and dom not in registry("domains").get("domains", {}):
        yield at(ctx.dp, "spec.domain", f"Dominio `{dom}` no registrado: los límites de dominio los define el Data Council")


@plugin("metadata.subdomain_registered", needs_dp=True)
def subdomain_registered(ctx, rule):
    dom, sub = ctx.dp_get("spec.domain"), ctx.dp_get("spec.subdomain")
    reg = registry("domains").get("domains", {})
    if not sub:
        yield at(ctx.dp, "spec.subdomain", "Subdominio no declarado")
    elif dom in reg and sub not in reg[dom].get("subdomains", []):
        yield at(ctx.dp, "spec.subdomain", f"Subdominio `{sub}` no registrado para `{dom}` "
                 f"(registrados: {reg[dom].get('subdomains')})")


def glossary_terms(ctx) -> set:
    terms = set()
    for doc in ctx.artifact("glossary"):
        for t in (doc.get("terms") or []) if isinstance(doc.data, dict) else []:
            if isinstance(t, dict) and t.get("term"):
                terms.add(str(t["term"]).lower())
    terms |= {m.lower() for m in registry("corporate_metrics").get("metrics", {})}
    return terms


@plugin("metadata.glossary_resolved", needs_dp=True)
def glossary_resolved(ctx, rule):
    known = glossary_terms(ctx)
    for i, term in enumerate(ctx.dp_get("spec.glossary_terms") or []):
        if str(term).lower() not in known:
            yield at(ctx.dp, f"spec.glossary_terms[{i}]", f"Término `{term}` no definido en el glosario "
                     "(metadata/catalog/glossary.yaml ni glosario corporativo)")


@plugin("metadata.lineage_expected", needs_dp=True)
def lineage_expected(ctx, rule):
    lin = [str(x).lower() for x in (ctx.dp_get("spec.lineage.expected") or [])]
    if len(lin) < 3:
        yield at(ctx.dp, "spec.lineage.expected", "Linaje esperado incompleto: se espera "
                 "Fuente → ingestión → Bronze → Silver → Gold/Semantic/Serving → consumo")
        return
    if lin[0] in LAYER_ORDER:
        yield at(ctx.dp, "spec.lineage.expected[0]", "El linaje debe comenzar en la fuente, no en una capa del lakehouse")
    if lin[-1] in ("bronze", "silver"):
        yield at(ctx.dp, f"spec.lineage.expected[{len(lin) - 1}]", "El linaje debe terminar en un consumidor")
    layers = [str(x).lower() for x in (ctx.dp_get("spec.modeling.layers") or [])]
    missing = [l for l in layers if l not in lin]
    if missing:
        yield at(ctx.dp, "spec.lineage.expected", f"Capas declaradas en spec.modeling.layers ausentes del linaje: {missing}")
    positions = [LAYER_ORDER.index(l) for l in lin if l in LAYER_ORDER[:3]]
    if positions != sorted(positions):
        yield at(ctx.dp, "spec.lineage.expected", "Orden de capas inválido en el linaje (Bronze → Silver → Gold)")


def allowed_tags() -> set:
    reg = registry("tags")
    out = {t for vals in reg.get("groups", {}).values() for t in vals}
    doms = registry("domains")
    if reg.get("include_domains"):
        for name, d in doms.get("domains", {}).items():
            out |= {name, name.replace("_", "-"), *d.get("subdomains", [])}
    if reg.get("include_countries"):
        out |= set(doms.get("countries", []))
    return out


@plugin("metadata.tags_controlled", needs_dp=True)
def tags_controlled(ctx, rule):
    allowed = allowed_tags()
    for i, tag in enumerate(ctx.dp_get("spec.tags") or []):
        if str(tag).lower() not in allowed:
            yield at(ctx.dp, f"spec.tags[{i}]", f"Tag `{tag}` fuera de la taxonomía controlada (rules/registry/tags.yaml)")


@plugin("metadata.owner_emails")
def owner_emails(ctx, rule):
    dp = ctx.dp
    if dp and isinstance(dp.data, dict):
        for key in OWNER_KEYS:
            path = f"spec.ownership.{key}"
            val = dp.get(path)
            if val and not is_placeholder(val):  # los vacíos/relleno los reporta GOV-DPD-008
                err = check_value(val, True, {"email": True}, ctx)
                if err:
                    yield at(dp, path, f"{key}: {err}")
    for doc in ctx.artifact("contracts_interface"):
        val = doc.get("metadata.owner") if isinstance(doc.data, dict) else None
        if val and not is_placeholder(val):
            err = check_value(val, True, {"email": True}, ctx)
            if err:
                yield at(doc, "metadata.owner", f"owner del contrato: {err}")


@plugin("metadata.staleness", needs_dp=True)
def staleness(ctx, rule):
    upd = _date(ctx.dp_get("metadata.updated"))
    max_age = int(ctx.policies.get("metadata_max_age_days", 180))
    if upd and (ctx.today - upd).days > max_age:
        yield at(ctx.dp, "metadata.updated", f"Metadata sin revisión hace {(ctx.today - upd).days} días (> {max_age})")


@plugin("metadata.dates", needs_dp=True)
def dates(ctx, rule):
    created, updated = ctx.dp_get("metadata.created"), ctx.dp_get("metadata.updated")
    for key, val in (("metadata.created", created), ("metadata.updated", updated)):
        if val and not _date(val):
            yield at(ctx.dp, key, f"Fecha `{val}` no es ISO YYYY-MM-DD")
    c, u = _date(created), _date(updated)
    if c and u and u < c:
        yield at(ctx.dp, "metadata.updated", "metadata.updated es anterior a metadata.created")
    if u and u > ctx.today:
        yield at(ctx.dp, "metadata.updated", "metadata.updated en el futuro")
