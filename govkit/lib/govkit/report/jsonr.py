"""Reporte JSON conforme a schemas/report.schema.json."""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

from govkit import __version__, scoring


def build(res, packs=("dp",), profile=None, include_scoring=True) -> Dict[str, Any]:
    ctx = res.ctx
    statuses: Dict[str, int] = {}
    for o in res.outcomes.values():
        statuses[o.status] = statuses.get(o.status, 0) + 1
    report: Dict[str, Any] = {
        "schema_version": "1.0",
        "tool": {"name": "govkit", "version": __version__, "ruleset_version": res.catalog.get("ruleset_version"),
                 "ruleset_digest": res.catalog.get("_digest")},
        "run": {"id": res.run_id, "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                "duration_ms": res.duration_ms, "mode": res.mode, "base_ref": ctx.base_ref, "packs": list(packs),
                "profile": profile},
        "target": {"repo": ctx.repo_name, "path": str(ctx.root), "data_product_id": ctx.dp_get("metadata.id"),
                   "lifecycle_state": ctx.stage, "stage_group": ctx.stage_group, "type": ctx.dp_get("spec.type")},
        "summary": {"verdict": res.verdict, "fail_on": res.fail_on, "counts": res.counts(), "rules": statuses,
                    "files_scanned": len(ctx.files),
                    "suppressed": {"waived": sum(1 for v in res.violations if v.waived),
                                   "baselined": sum(1 for v in res.violations if v.baselined)}},
        "violations": [v.to_dict() for v in res.violations],
        "waivers_applied": res.waivers_applied,
        "semantic_handoff": {
            "note": "Reglas semánticas/híbridas para el revisor LLM local (consultivo). Ver `govkit review`.",
            "kb_suggested": sorted({k for h in res.handoff for k in h.get("kb", [])}),
            "questions": res.handoff,
        },
    }
    if include_scoring and "dp" in packs:
        report["scoring"] = scoring.compute(res)
    return report
