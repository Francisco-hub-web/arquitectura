"""Observabilidad del Data Product (13-data-observability, 08 §17)."""
from __future__ import annotations

from govkit.plugins import at, at_file, plugin

FIVE = ["freshness", "volume", "schema", "quality", "lineage"]


def monitors(ctx):
    for doc in ctx.artifact("monitors"):
        if doc.error or not isinstance(doc.data, dict):
            continue
        for i, m in enumerate(doc.get("spec.monitors") or []):
            if isinstance(m, dict):
                yield doc, i, m


def signals(ctx) -> set:
    return {str(m.get("signal", "")).lower() for _, _, m in monitors(ctx)}


def _anchor(ctx):
    docs = ctx.artifact("monitors")
    return docs[0] if docs else None


@plugin("observability.five_pillars")
def five_pillars(ctx, rule):
    anchor = _anchor(ctx)
    if not anchor:
        return
    missing = [s for s in FIVE if s not in signals(ctx)]
    if missing:
        yield at(anchor, "spec.monitors", f"Monitores sin cobertura de los pilares: {missing} (13 §9)", missing=missing)


@plugin("observability.runbook_links")
def runbook_links(ctx, rule):
    for doc, i, m in monitors(ctx):
        if str(m.get("severity", "")).lower() in ("critico", "crítico", "critical", "alto", "high"):
            rb = m.get("runbook")
            if not rb:
                yield at(doc, f"spec.monitors[{i}].runbook", f"Monitor '{m.get('name', i)}' crítico/alto sin runbook")
            elif not ctx.exists(str(rb).split("#")[0]):
                yield at(doc, f"spec.monitors[{i}].runbook", f"Runbook `{rb}` inexistente")


@plugin("observability.usage_monitor")
def usage_monitor(ctx, rule):
    anchor = _anchor(ctx)
    if anchor and "usage" not in signals(ctx):
        yield at(anchor, "spec.monitors", "Sin monitor de uso/adopción (13 §18)")


@plugin("observability.security_monitor")
def security_monitor(ctx, rule):
    sensitive = ctx.dp_get("spec.classification.pii") is True or \
        ctx.dp_get("spec.classification.level") in ("confidencial", "sensible_pii")
    anchor = _anchor(ctx)
    if sensitive and anchor and "security" not in signals(ctx):
        yield at(anchor, "spec.monitors", "Datos sensibles sin monitor de accesos/extracciones anómalas (13 §22, 10 §22)")


@plugin("aiml.drift_monitors")
def drift_monitors(ctx, rule):
    anchor = _anchor(ctx)
    sig = signals(ctx)
    missing = [s for s in ("data_drift", "model_drift") if s not in sig]
    if missing:
        if anchor:
            yield at(anchor, "spec.monitors", f"Data Product AI/ML sin monitores {missing} (12 §23, 13 §20)")
        else:
            yield at_file("observability/alarms", f"Data Product AI/ML sin monitores {missing}", key="drift")
