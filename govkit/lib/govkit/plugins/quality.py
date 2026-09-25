"""Calidad de datos (01 §4, 08-data-quality-framework)."""
from __future__ import annotations

import re

from govkit.paths import registry
from govkit.plugins import at, at_file, plugin

QUANT = re.compile(
    r"^\s*(?:[<>]=?|=|≥|≤)?\s*\d+(?:[.,]\d+)?\s*(?:%|ms|s|seg|min|h|d|registros|filas|rows)?\s*$"
    r"|^P(?:\d+[YMWD])*(?:T(?:\d+[HMS])+)?$"
    r"|^(?:antes de(?:\s+las)?\s*)?\d{1,2}:\d{2}(?:\s*[A-Za-z]{2,4})?$", re.IGNORECASE)
BLOCKING = {"bloquear_pipeline", "bloquear_promocion"}
BUSINESS_DIMS_NOT_IN_BRONZE = {"exactitud", "consistencia", "integridad_referencial"}


def quantifiable(v) -> bool:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    return bool(QUANT.match(str(v or "")))


def rules_of(ctx):
    for doc in ctx.artifact("quality_rules"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        for i, r in enumerate(doc.get("spec.rules") or []):
            if isinstance(r, dict):
                yield doc, i, r


@plugin("quality.slo_dimensions")
def slo_dimensions(ctx, rule):
    dims = {str(r.get("dimension")).lower() for _, _, r in rules_of(ctx) if quantifiable(r.get("threshold"))}
    for slo in ctx.dp_get("spec.quality_slos") or []:
        if isinstance(slo, dict) and quantifiable(slo.get("target")):
            dims.add(str(slo.get("dimension")).lower())
    dims.discard("none")
    if len(dims) < 3:
        target = next((d for d in ctx.artifact("quality_rules")), None) or ctx.dp
        if target:
            yield at(target, "spec.rules" if target is not ctx.dp else "spec.quality_slos",
                     f"SLOs cuantificados en {len(dims)} dimensión(es) {sorted(dims)}; se exigen ≥3 (01 §4)", dims=sorted(dims))


@plugin("quality.threshold_quantifiable")
def threshold_quantifiable(ctx, rule):
    for doc, i, r in rules_of(ctx):
        if not quantifiable(r.get("threshold")):
            yield at(doc, f"spec.rules[{i}].threshold", f"Regla '{r.get('name', i)}': umbral no cuantificable "
                     f"`{r.get('threshold')}` (usar %, número, duración ISO-8601 u hora límite)")


@plugin("quality.severity_action")
def severity_action(ctx, rule):
    for doc, i, r in rules_of(ctx):
        sev, act = str(r.get("severity", "")).lower(), str(r.get("action", "")).lower()
        if sev == "critica" and act not in BLOCKING:
            yield at(doc, f"spec.rules[{i}].action", f"Regla crítica '{r.get('name', i)}' con acción `{act}`: "
                     "una regla crítica invalida el producto para consumo/promoción (08 §13) → bloquear_*")
        if sev == "baja" and act in BLOCKING:
            yield at(doc, f"spec.rules[{i}].action", f"Regla de severidad baja '{r.get('name', i)}' bloquea el pipeline")


def gates_mandatory(ctx) -> bool:
    dom = registry("domains").get("domains", {}).get(ctx.dp_get("spec.domain"), {})
    tags = [str(t).lower() for t in ctx.dp_get("spec.tags") or []]
    return bool(dom.get("quality_gates_mandatory")) or ctx.dp_get("spec.type") == "ai_ml" or "executive" in tags


@plugin("quality.gates")
def gates(ctx, rule):
    docs = [d for d in ctx.artifact("quality_rules") if not d.error]
    if not docs:
        return
    sev = None if gates_mandatory(ctx) else "MEDIUM"
    declared = set()
    for d in docs:
        declared |= set((d.get("spec.gates") or {}).keys()) if isinstance(d.get("spec.gates"), dict) else set()
    layers = {str(l).lower() for l in ctx.dp_get("spec.modeling.layers") or ["silver", "gold"]}
    expected = [g for g in ("silver", "gold", "serving") if g in layers or g == "serving" and "semantic" in layers]
    missing = [g for g in expected if g not in declared]
    if missing:
        yield at(docs[0], "spec.gates", f"Quality gates no declarados para: {missing}"
                 + (" (obligatorios en este dominio/tipo, 08 §14)" if sev is None else ""), severity=sev)


def contract_index(ctx):
    idx = {}
    for doc in ctx.artifact("contracts_all"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        names = {doc.path.rsplit("/", 1)[-1].rsplit(".", 1)[0], str(doc.get("metadata.name"))}
        fields = {str(f.get("name")) for f in (doc.get("spec.schema") or []) if isinstance(f, dict)}
        for n in names:
            idx.setdefault(n, set()).update(fields)
    return idx


@plugin("quality.object_resolves")
def object_resolves(ctx, rule):
    idx = contract_index(ctx)
    if not idx:
        return
    all_fields = set().union(*idx.values())
    for doc, i, r in rules_of(ctx):
        obj = str(r.get("object") or "")
        if not obj:
            continue
        parts = obj.split(".")
        field, entity = parts[-1], (parts[-2] if len(parts) > 1 else None)
        if len(parts) == 1:
            if obj not in idx:
                yield at(doc, f"spec.rules[{i}].object", f"Objeto `{obj}` no corresponde a ningún contrato")
            continue
        ok = field in idx.get(entity, set()) if entity in idx else field in all_fields or field == "*"
        if not ok:
            yield at(doc, f"spec.rules[{i}].object", f"Objeto `{obj}`: el campo `{field}` no existe en los contratos")


@plugin("quality.executable_tests")
def executable_tests(ctx, rule):
    has_tests = bool([f for f in ctx.glob("tests/data_quality/**") if not f.endswith(".gitkeep")])
    has_dbt_tests = any("tests:" in (ctx.text(f) or "") or "data_tests:" in (ctx.text(f) or "")
                        for f in ctx.glob(["modeling/dbt/models/**/*.yml", "modeling/dbt/models/**/*.yaml"]))
    has_ge = bool([f for f in ctx.glob("quality/expectations/**/*.json")])
    if not (has_tests or has_dbt_tests or has_ge):
        yield at_file("tests/data_quality", "Reglas de calidad no derivadas a tests ejecutables "
                      "(tests/data_quality, dbt tests o expectations)", key="dq-tests")


@plugin("quality.layer_fit")
def layer_fit(ctx, rule):
    for doc, i, r in rules_of(ctx):
        if str(r.get("layer")).lower() == "bronze" and str(r.get("dimension")).lower() in BUSINESS_DIMS_NOT_IN_BRONZE:
            yield at(doc, f"spec.rules[{i}].layer", f"Regla '{r.get('name', i)}' ({r.get('dimension')}) en Bronze: "
                     "en Bronze solo se valida esquema, recepción, volumen y parsing (08 §10.1)")


@plugin("quality.ai_controls")
def ai_controls(ctx, rule):
    feat_rules = [r for _, _, r in rules_of(ctx) if str(r.get("layer")).lower() == "feature"]
    if not any(str(r.get("dimension")).lower() == "completitud" for r in feat_rules):
        docs = ctx.artifact("quality_rules")
        target = docs[0] if docs else ctx.dp
        if target:
            yield at(target, "spec.rules", "Data Product AI/ML sin reglas de completitud sobre features críticas (08 §10.5, §19)")
