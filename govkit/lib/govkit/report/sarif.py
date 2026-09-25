"""SARIF 2.1.0 para GitHub Code Scanning (anotaciones en el PR con línea exacta)."""
from __future__ import annotations

from typing import Any, Dict

from govkit import __version__

LEVEL = {"BLOCKER": "error", "HIGH": "error", "MEDIUM": "warning", "LOW": "note", "INFO": "note"}
SCORE = {"BLOCKER": "9.5", "HIGH": "7.5", "MEDIUM": "5.0", "LOW": "2.5", "INFO": "0.5"}


def build(res) -> Dict[str, Any]:
    rules_used = {v.rule_id: v for v in res.violations}
    catalog = {r.id: r for r in res.catalog["_rules"]}
    rules = []
    for rid in sorted(rules_used):
        r = catalog.get(rid)
        src = r.source if r else {}
        rules.append({
            "id": rid,
            "name": rid.replace("-", ""),
            "shortDescription": {"text": r.title if r else rid},
            "fullDescription": {"text": f"{src.get('doc', '')} {src.get('section', '')}: {src.get('quote', '')}".strip()},
            "help": {"text": r.remediation if r else ""},
            "properties": {"tags": [r.category, r.nature, r.pillar] if r else [],
                           "security-severity": SCORE[r.severity] if r else "5.0"},
        })
    results = []
    for v in res.violations:
        if not v.counts:
            continue
        results.append({
            "ruleId": v.rule_id,
            "level": LEVEL[v.severity],
            "message": {"text": f"[{v.severity}] {v.message} — {v.remediation}"},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": v.location.file if v.location.file != "." else "README.md"},
                "region": {"startLine": max(1, v.location.line), "startColumn": max(1, v.location.column)}}}],
            "partialFingerprints": {"govkit/v1": v.fingerprint},
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "govkit", "version": __version__,
                                      "informationUri": "https://github.com/francisco-hub-web/arquitectura",
                                      "rules": rules}},
                  "results": results}],
    }
