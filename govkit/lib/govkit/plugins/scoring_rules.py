"""Reglas post-evaluación que consumen el pre-score (19-scoring-model §27-§30)."""
from __future__ import annotations

import datetime as _dt

from govkit import scoring
from govkit.plugins import at, at_file, plugin


def _scorecard(ctx):
    docs = [d for d in ctx.artifact("scorecard") if not d.error and isinstance(d.data, dict)]
    return docs[0] if docs else None


@plugin("scoring.stage_minimums")
def stage_minimums(ctx, rule, res):
    mins = ctx.lifecycle.get("scoring_minimums", {}).get(ctx.stage)
    if not mins:
        return
    sc = scoring.compute(res)
    card = _scorecard(ctx)
    for pillar, minimum in mins.items():
        info = sc["pillars"].get(pillar, {})
        value = info.get("declared") if info.get("declared") is not None else info.get("score")
        if value is not None and value < minimum:
            src = "declarado" if info.get("declared") is not None else "pre-score"
            msg = f"Pilar {info.get('label', pillar)} = {value} ({src}) < mínimo {minimum} para `{ctx.stage}` (19 §27)"
            yield at(card, f"spec.pillars.{pillar}", msg) if card else at_file(".", msg, key=pillar)


@plugin("scoring.divergence")
def divergence(ctx, rule, res):
    card = _scorecard(ctx)
    if not card:
        return
    sc = scoring.compute(res)
    for pillar, info in sc["pillars"].items():
        dec, pre = info.get("declared"), info.get("score")
        if dec is not None and pre is not None and dec - pre > 1.0:
            yield at(card, f"spec.pillars.{pillar}", f"{info['label']}: declarado {dec} vs evidencia automatizada {pre} "
                     "→ score provisional hasta aportar evidencia verificable (19 §28)")


@plugin("scoring.freshness")
def freshness(ctx, rule, res):
    card = _scorecard(ctx)
    if not card:
        return
    val = card.get("spec.evaluated_at")
    try:
        d = val if isinstance(val, _dt.date) else _dt.date.fromisoformat(str(val))
    except ValueError:
        yield at(card, "spec.evaluated_at", "Fecha de evaluación inválida o ausente")
        return
    limit = int(ctx.policies.get("scorecard_max_age_days", 100))
    if (ctx.today - d).days > limit:
        yield at(card, "spec.evaluated_at", f"Scoring con {(ctx.today - d).days} días: la cadencia es trimestral (19 §30)")


@plugin("scoring.strategic", needs_dp=True)
def strategic(ctx, rule, res):
    mins = ctx.lifecycle.get("strategic_minimums", {})
    sc = scoring.compute(res)
    card = _scorecard(ctx)
    for key, minimum in mins.items():
        value = sc["global"] if key == "global" else sc["pillars"].get(key, {}).get("score")
        if value is None or value < minimum:
            msg = f"Nivel estratégico exige {key} ≥ {minimum} (evidencia: {value})"
            yield at(card, "spec.pillars", msg, key=key) if card else at(ctx.dp, "spec.lifecycle.target_level", msg, key=key)
