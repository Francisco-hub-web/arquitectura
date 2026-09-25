"""Puente motor → Scoring Model (19-scoring-model): pre-score determinista por pilar basado en evidencia.

El pre-score no reemplaza la evaluación colaborativa (19 §29): la contrasta. Un score declarado
que supera la evidencia automatizada en más de 1 punto se marca como provisional (19 §28).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from govkit.model import SEV_WEIGHT
from govkit.paths import registry


def classify(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    for c in registry("scoring")["classification"]:
        if score >= c["min"]:
            return c["label"]
    return None


def weights_for(dp_type: Optional[str]) -> Dict[str, float]:
    reg = registry("scoring")
    w = {p: float(v["weight"]) for p, v in reg["pillars"].items()}
    emph = reg.get("type_emphasis", {})
    for p in emph.get(dp_type or "", []):
        w[p] *= float(emph.get("multiplier", 1.5))
    return w


def declared_scores(ctx) -> Dict[str, float]:
    docs = [d for d in ctx.artifact("scorecard") if not d.error and isinstance(d.data, dict)]
    out = {}
    if docs:
        for p, v in (docs[0].get("spec.pillars") or {}).items():
            score = v.get("score") if isinstance(v, dict) else v
            if isinstance(score, (int, float)):
                out[p] = float(score)
    return out


REFERENCE_STATE = "productivo"


def reference(res):
    """El score mide madurez absoluta (19 §11): se evalúa como si el producto estuviera en `productivo`,
    aunque el gate del estado actual exija menos. Evita que un esqueleto temprano aparezca como 'avanzado'."""
    if res.ctx.stage == REFERENCE_STATE or getattr(res, "is_reference", False):
        return res
    cached = getattr(res, "_reference", None)
    if cached is None:
        from govkit.engine import Engine
        from govkit.repo import RepoContext

        ctx = RepoContext(res.ctx.root, res.catalog, stage_override=REFERENCE_STATE, base_ref=res.ctx.base_ref,
                          today=res.ctx.today)
        cached = Engine(ctx, res.catalog, packs=["dp"], skip_posts=True).run()
        cached.is_reference = True
        res._reference = cached
    return cached


def compute(res) -> Dict[str, Any]:
    res = reference(res)
    reg = registry("scoring")
    rules = {r.id: r for r in res.catalog["_rules"]}
    blockers = {v.rule_id for v in res.counting if v.severity == "BLOCKER"}
    acc: Dict[str, Dict[str, float]] = {p: {"total": 0.0, "passed": 0.0, "evaluated": 0, "failed": 0, "catalog": 0}
                                        for p in reg["pillars"]}
    for r in rules.values():
        if r.pillar in acc and r.pack == "dp":
            acc[r.pillar]["catalog"] += 1
    capped = set()
    for rid, out in res.outcomes.items():
        r = rules.get(rid)
        if not r or r.summary or r.pillar not in acc or out.status not in ("pass", "fail"):
            continue
        w = SEV_WEIGHT.get(r.severity, 1) or 1
        a = acc[r.pillar]
        a["total"] += w
        a["evaluated"] += 1
        if out.status == "pass":
            a["passed"] += w
        else:
            a["failed"] += 1
            if rid in blockers:
                capped.add(r.pillar)
    dp_type = res.ctx.dp_get("spec.type")
    weights = weights_for(dp_type)
    declared = declared_scores(res.ctx)
    pillars: Dict[str, Any] = {}
    num = den = 0.0
    for p, a in acc.items():
        score = None
        if a["total"] > 0:
            score = round(1 + 4 * a["passed"] / a["total"], 1)
            if p in capped:
                score = min(score, float(reg.get("blocker_cap", 2.0)))
            num += weights[p] * score
            den += weights[p]
        pillars[p] = {"label": reg["pillars"][p]["label"], "score": score, "weight": round(weights[p], 2),
                      "rules_evaluated": a["evaluated"], "rules_failed": a["failed"],
                      "automation_coverage": round(a["evaluated"] / a["catalog"], 2) if a["catalog"] else 0.0,
                      "blocker_cap": p in capped, "declared": declared.get(p)}
    glob = round(num / den, 2) if den else None
    dims = {}
    for d, ps in reg["dimensions"].items():
        vals = [pillars[p]["score"] for p in ps if pillars[p]["score"] is not None]
        dims[d] = round(sum(vals) / len(vals), 2) if vals else None
    return {"pillars": pillars, "global": glob, "classification": classify(glob), "dimensions": dims,
            "reference_state": REFERENCE_STATE,
            "note": "pre-score determinista basado en evidencia automatizada, evaluado contra el estándar de "
                    "`productivo` (no reemplaza la evaluación colaborativa)"}
