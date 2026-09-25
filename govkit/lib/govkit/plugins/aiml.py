"""AI / ML / GenAI sobre Data Products gobernados (12-ai-ml-data-framework, 14 §9.12, §11.6)."""
from __future__ import annotations

from govkit.plugins import at, plugin


def _features(ctx):
    out = {}
    for doc in ctx.artifact("features"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        for i, f in enumerate(doc.get("spec.features") or []):
            if isinstance(f, dict) and f.get("name"):
                out[str(f["name"])] = (doc, i, f)
    return out


def _refs(items):
    """Normaliza referencias a features: `nombre` o `nombre@version`."""
    out = {}
    for r in items or []:
        if isinstance(r, dict):
            out[str(r.get("name"))] = str(r.get("version", ""))
        else:
            name, _, ver = str(r).partition("@")
            out[name] = ver
    return out


@plugin("aiml.train_inference_consistency")
def train_inference_consistency(ctx, rule):
    trained = {}
    for doc in ctx.artifact("training_sets"):
        for ts in (doc.get("spec.training_sets") or []) if isinstance(doc.data, dict) else []:
            if isinstance(ts, dict):
                trained.update(_refs(ts.get("features")))
    if not trained:
        return
    for doc in ctx.artifact("inference"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        for i, inf in enumerate(doc.get("spec.inference") or []):
            if not isinstance(inf, dict):
                continue
            for name, ver in _refs(inf.get("features")).items():
                if name not in trained:
                    yield at(doc, f"spec.inference[{i}].features", f"Feature `{name}` usada en inferencia no existe en "
                             "el dataset de entrenamiento (12 §16)")
                elif ver and trained[name] and ver != trained[name]:
                    yield at(doc, f"spec.inference[{i}].features", f"Feature `{name}` con versión {ver} en inferencia "
                             f"≠ {trained[name]} en entrenamiento (training/serving skew)")


@plugin("aiml.feature_sources")
def feature_sources(ctx, rule):
    declared = {str(i.get("data_product_ref")) for i in ctx.dp_get("spec.inputs") or [] if isinstance(i, dict)}
    declared.add(str(ctx.dp_get("metadata.id")))
    for name, (doc, i, f) in _features(ctx).items():
        src = f.get("source_data_product")
        if src and str(src) not in declared:
            yield at(doc, f"spec.features[{i}].source_data_product", f"Feature `{name}` proviene de `{src}`, que no está "
                     "declarado como input del Data Product (AI sobre activos gobernados, 12 §10)")


@plugin("aiml.pii_training")
def pii_training(ctx, rule):
    for name, (doc, i, f) in _features(ctx).items():
        if str(f.get("sensitivity", "")).lower() in ("pii", "sensible_pii"):
            for key in ("consent_basis", "minimization"):
                if not f.get(key):
                    yield at(doc, f"spec.features[{i}].{key}", f"Feature PII `{name}` sin `{key}` declarado (12 §22)")
