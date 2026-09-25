"""Markdown para comentario de PR / $GITHUB_STEP_SUMMARY."""
from __future__ import annotations

from govkit import scoring

ICON = {"BLOCKER": "⛔", "HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡", "INFO": "🔵"}
VERDICT = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL"}


def build(res, max_rows: int = 60, with_scoring: bool = True) -> str:
    ctx, counts = res.ctx, res.counts()
    out = [f"## Gobernanza de datos · {VERDICT[res.verdict]}",
           "",
           f"**Repo:** `{ctx.repo_name}` · **Data Product:** `{ctx.dp_get('metadata.id') or '—'}` · "
           f"**Estado:** `{ctx.stage}` (grupo `{ctx.stage_group}`) · **Ruleset:** `{res.catalog.get('ruleset_version')}`",
           "",
           "| " + " | ".join(f"{ICON[s]} {s}" for s in counts) + " |",
           "|" + "---|" * len(counts),
           "| " + " | ".join(str(counts[s]) for s in counts) + " |", ""]
    rows = [v for v in res.violations if v.counts][:max_rows]
    if rows:
        out += ["| Sev | Regla | Ubicación | Hallazgo | Remediación |", "|---|---|---|---|---|"]
        for v in rows:
            loc = f"`{v.location.file}:{v.location.line}`"
            msg = v.message.replace("|", "\\|")
            rem = v.remediation.replace("|", "\\|")
            out.append(f"| {ICON[v.severity]} | `{v.rule_id}` | {loc} | {msg} | {rem} |")
        hidden = len([v for v in res.violations if v.counts]) - len(rows)
        if hidden > 0:
            out.append(f"\n_… y {hidden} hallazgo(s) más (ver reporte JSON/SARIF)._")
    suppressed = [v for v in res.violations if not v.counts]
    if suppressed:
        out.append(f"\n<details><summary>{len(suppressed)} hallazgo(s) exceptuados por waiver/baseline</summary>\n")
        for v in suppressed[:40]:
            why = f"waiver ADR {v.waived['adr']} (vence {v.waived['expires']})" if v.waived else "baseline"
            out.append(f"- `{v.rule_id}` {v.location.file}:{v.location.line} — {why}")
        out.append("</details>")
    if with_scoring and ctx.dp:
        sc = scoring.compute(res)
        out += ["", f"### Pre-score determinista: **{sc['global']}** · {sc['classification']}", "",
                "| Pilar | Pre-score | Declarado | Reglas evaluadas / fallidas |", "|---|---|---|---|"]
        for p in sc["pillars"].values():
            out.append(f"| {p['label']} | {p['score'] if p['score'] is not None else 'N/A'} | "
                       f"{p['declared'] if p['declared'] is not None else '—'} | {p['rules_evaluated']} / {p['rules_failed']} |")
    if res.handoff:
        out += ["", "<details><summary>Revisión semántica sugerida (LLM local, consultiva)</summary>", ""]
        for h in res.handoff[:25]:
            out.append(f"- `{h['rule_id']}` {h['question']} _(KB: {', '.join(h['kb'])})_")
        out.append("</details>")
    return "\n".join(out) + "\n"
