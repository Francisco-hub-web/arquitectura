"""Salida de consola legible (colores ANSI si es TTY y NO_COLOR no está definido)."""
from __future__ import annotations

import os
import sys

from govkit import scoring

COLORS = {"BLOCKER": "\033[1;97;41m", "HIGH": "\033[1;31m", "MEDIUM": "\033[33m", "LOW": "\033[36m",
          "INFO": "\033[2m", "PASS": "\033[1;32m", "WARN": "\033[1;33m", "FAIL": "\033[1;31m", "dim": "\033[2m",
          "bold": "\033[1m"}
RESET = "\033[0m"


def _c(key: str, text: str, enabled: bool) -> str:
    return f"{COLORS[key]}{text}{RESET}" if enabled else text


def render(res, verbose: bool = False, show_score: bool = True, stream=None, packs=("dp",)) -> str:
    stream = stream or sys.stdout
    color = hasattr(stream, "isatty") and stream.isatty() and not os.environ.get("NO_COLOR")
    ctx = res.ctx
    scope = (f"estado: {ctx.stage} · grupo: {ctx.stage_group}" if "dp" in packs
             else f"pack: {', '.join(packs)} · {ctx.root.name}")
    lines = [_c("bold", f"govkit · {ctx.repo_name if 'dp' in packs else ctx.root.name}", color) +
             _c("dim", f"  ({scope} · ruleset {res.catalog.get('ruleset_version')} · {res.duration_ms} ms)", color)]
    current = None
    for v in res.violations:
        if not v.counts and not verbose:
            continue
        if v.location.file != current:
            current = v.location.file
            lines.append("\n" + _c("bold", current, color))
        tag = _c(v.severity, f" {v.severity:<7}", color)
        extra = _c("dim", f" [{'waiver' if v.waived else 'baseline'}]", color) if not v.counts else ""
        lines.append(f"  {v.location.line:>4}:{v.location.column:<3}{tag} {v.rule_id}  {v.message}{extra}")
        if verbose:
            lines.append(_c("dim", f"             ↳ {v.remediation}  ({v.source.get('doc', '')} {v.source.get('section', '')})", color))
    counts = res.counts()
    summary = "  ".join(f"{k}: {n}" for k, n in counts.items())
    lines += ["", _c(res.verdict, f"Veredicto: {res.verdict}", color) + f"   {summary}   (falla en ≥ {res.fail_on})"]
    if show_score and ctx.dp:
        sc = scoring.compute(res)
        lines.append(_c("dim", f"Pre-score determinista: {sc['global']} · {sc['classification']}  (govkit score para detalle)", color))
    if res.handoff:
        lines.append(_c("dim", f"{len(res.handoff)} pregunta(s) para revisión semántica → govkit review", color))
    return "\n".join(lines) + "\n"
