"""Reporte HTML autocontenido (sin recursos externos): artefacto de CI, adjunto de PR o evidencia para Gobierno.

Claro/oscuro por `prefers-color-scheme` (y `data-theme` si el visor lo fija). Severidad = color de estado +
ícono + etiqueta (nunca solo color). Pre-score por pilar = barras de una sola serie con valor rotulado.
"""
from __future__ import annotations

import datetime as _dt
import json
from html import escape as e
from typing import Any, Dict, List

from govkit import __version__, scoring

SEV = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]
ICON = {"BLOCKER": "⛔", "HIGH": "▲", "MEDIUM": "◆", "LOW": "●", "INFO": "ℹ"}
VERDICT = {"PASS": ("✔", "Aprobado"), "WARN": ("!", "Aprobado con observaciones"), "FAIL": ("✘", "Bloqueado")}

CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--panel:#ffffff;--line:#e4e3df;--text:#0b0b0b;--text-2:#52514e;--muted:#6f6e69;
--series-1:#2a78d6;--track:#f0efec;--critical:#d03b3b;--serious:#ec835a;--warning:#fab219;--good:#0ca30c;--neutral:#8a8983;
--chip:#f4f3f0;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface:#1a1a19;--panel:#222220;
--line:#383835;--text:#ffffff;--text-2:#c3c2b7;--muted:#9a9990;--series-1:#3987e5;--track:#2c2c2a;--chip:#2c2c2a;--neutral:#8a8983}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--panel:#222220;--line:#383835;--text:#ffffff;--text-2:#c3c2b7;
--muted:#9a9990;--series-1:#3987e5;--track:#2c2c2a;--chip:#2c2c2a}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--text);font:14px/1.5 system-ui,-apple-system,"Segoe UI",
Roboto,sans-serif}main{max-width:1180px;margin:0 auto;padding:24px 16px 48px}h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:32px 0 12px}code,.mono{font-family:var(--mono);font-size:12.5px}.sub{color:var(--text-2)}
.meta{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--text-2);font-size:13px;margin-top:6px}.meta b{color:var(--text)}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
.verdict{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:8px;font-weight:600;border:1px solid var(--line);
background:var(--panel)}.verdict i{font-style:normal;display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;
color:#fff;font-size:13px}.v-PASS i{background:var(--good)}.v-WARN i{background:var(--warning);color:#1a1a19}.v-FAIL i{background:var(--critical)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-top:20px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.tile .n{font-size:26px;font-weight:650;
font-variant-numeric:tabular-nums}.tile .l{color:var(--text-2);font-size:12.5px;display:flex;align-items:center;gap:6px}
.dot{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:5px;font-size:10px;color:#fff;flex:none}
.s-BLOCKER{background:var(--critical)}.s-HIGH{background:var(--serious)}.s-MEDIUM{background:var(--warning);color:#1a1a19}
.s-LOW{background:var(--neutral)}.s-INFO{background:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.score-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}.score-head .g{font-size:30px;font-weight:650}
.bars{display:grid;grid-template-columns:minmax(150px,230px) 1fr 72px;gap:8px 12px;align-items:center;margin-top:14px}
.bars .lab{font-size:13px}.bars .val{font-variant-numeric:tabular-nums;font-size:13px;text-align:right;color:var(--text)}
.track{position:relative;height:14px;background:var(--track);border-radius:4px}.fill{position:absolute;left:0;top:0;bottom:0;
background:var(--series-1);border-radius:0 4px 4px 0}.decl{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--text-2)}
.na .track{background:repeating-linear-gradient(45deg,var(--track),var(--track) 4px,transparent 4px,transparent 8px)}
.cap{font-size:12px;margin-left:6px}.axis{display:flex;justify-content:space-between;color:var(--muted);font-size:11px}
.note{color:var(--muted);font-size:12.5px;margin-top:10px}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--text);border-radius:999px;padding:4px 10px;font:inherit;
font-size:12.5px;cursor:pointer;display:inline-flex;gap:6px;align-items:center}.chip[aria-pressed="false"]{opacity:.45}
input[type=search]{flex:1;min-width:180px;border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:8px;
padding:6px 10px;font:inherit}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;min-width:860px;table-layout:fixed}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);
vertical-align:top;font-size:13px;overflow-wrap:anywhere}th{font-size:12px;color:var(--text-2);font-weight:600;background:var(--panel);position:sticky;top:0}
tr:last-child td{border-bottom:0}.sev{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}.rid{white-space:nowrap}
.rtitle{color:var(--text-2);font-size:12px}.loc{overflow-wrap:anywhere}.rem{color:var(--text-2)}.kb{overflow-wrap:anywhere}
.tag{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:11px;color:var(--text-2);margin:1px 2px 1px 0}
.fixable{border-color:var(--series-1);color:var(--series-1)}details{margin-top:10px}summary{cursor:pointer;color:var(--text-2)}
ul.q{padding-left:18px;margin:8px 0}ul.q li{margin:4px 0}.empty{padding:18px;color:var(--text-2)}
footer{margin-top:36px;color:var(--muted);font-size:12px}
@media (max-width:640px){.bars{grid-template-columns:1fr 52px}.bars .lab{grid-column:1/-1;margin-bottom:-6px}.bars .track{grid-column:1}}
"""

JS = """
(function(){const chips=[...document.querySelectorAll('.chip[data-sev]')],q=document.getElementById('q'),
rows=[...document.querySelectorAll('#findings tbody tr[data-sev]')],cnt=document.getElementById('shown');
function apply(){const on=new Set(chips.filter(c=>c.getAttribute('aria-pressed')==='true').map(c=>c.dataset.sev));
const t=(q.value||'').toLowerCase();let n=0;rows.forEach(r=>{const ok=on.has(r.dataset.sev)&&(!t||r.textContent.toLowerCase().includes(t));
r.hidden=!ok;if(ok)n++});if(cnt)cnt.textContent=n}
chips.forEach(c=>c.addEventListener('click',()=>{c.setAttribute('aria-pressed',c.getAttribute('aria-pressed')==='true'?'false':'true');apply()}));
if(q)q.addEventListener('input',apply);apply()})();
"""


def _sev_badge(sev: str) -> str:
    return f'<span class="sev"><span class="dot s-{sev}" aria-hidden="true">{ICON[sev]}</span>{sev}</span>'


def _pillars(sc: Dict[str, Any]) -> str:
    rows: List[str] = []
    for p in sc["pillars"].values():
        score, decl = p["score"], p["declared"]
        tip = (f"{p['label']}: pre-score {score if score is not None else 'N/A'} · declarado "
               f"{decl if decl is not None else '—'} · peso {p['weight']} · reglas {p['rules_evaluated']} evaluadas / "
               f"{p['rules_failed']} fallidas")
        cap = ('<span class="cap" title="limitado a 2.0 por un BLOCKER abierto (08 §24)" aria-label="limitado por BLOCKER">'
               '⛔</span>') if p["blocker_cap"] else ""
        if score is None:
            bar = '<div class="track" role="img" aria-label="sin evidencia automatizada"></div>'
            rows.append(f'<div class="lab na">{e(p["label"])}</div><div class="na" title="{e(tip)}">{bar}</div>'
                        f'<div class="val">N/A</div>')
            continue
        decl_mark = f'<span class="decl" style="left:calc({decl / 5 * 100:.1f}% - 1px)" title="declarado {decl}"></span>' \
            if decl is not None else ""
        rows.append(f'<div class="lab">{e(p["label"])}</div>'
                    f'<div class="track" title="{e(tip)}" role="img" aria-label="{e(tip)}">'
                    f'<span class="fill" style="width:{max(score, 0) / 5 * 100:.1f}%"></span>{decl_mark}</div>'
                    f'<div class="val">{score:.1f}{cap}</div>')
    return ('<div class="bars">' + "".join(rows) + '<div></div><div class="axis"><span>0</span><span>1</span><span>2</span>'
            '<span>3</span><span>4</span><span>5</span></div><div></div></div>')


def build(res, packs=("dp",), with_scoring: bool = True, title: str = "Gobernanza de datos") -> str:
    ctx, counts = res.ctx, res.counts()
    icon, label = VERDICT[res.verdict]
    statuses: Dict[str, int] = {}
    for o in res.outcomes.values():
        statuses[o.status] = statuses.get(o.status, 0) + 1
    evaluated = statuses.get("pass", 0) + statuses.get("fail", 0)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = sorted([v for v in res.violations if v.counts],
                  key=lambda v: (SEV.index(v.severity), v.location.file, v.location.line))
    out = [f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
           f'initial-scale=1"><title>{e(title)} · {e(ctx.repo_name)}</title><style>{CSS}</style></head><body><main>',
           '<div class="head"><div>', f"<h1>{e(title)}</h1>",
           f'<div class="sub mono">{e(ctx.repo_name)}</div><div class="meta">'
           f'<span>Data Product <b class="mono">{e(str(ctx.dp_get("metadata.id") or "—"))}</b></span>'
           f'<span>Estado <b>{e(ctx.stage)}</b> ({e(ctx.stage_group)})</span>'
           f'<span>Packs <b>{e(", ".join(packs))}</b></span><span>Umbral <b>{e(res.fail_on)}</b></span>'
           f'<span>Ruleset <b class="mono">{e(str(res.catalog.get("ruleset_version")))}</b></span></div></div>',
           f'<div class="verdict v-{res.verdict}"><i aria-hidden="true">{icon}</i>{res.verdict} · {label}</div></div>',
           '<div class="tiles">']
    for s in SEV:
        out.append(f'<div class="tile"><div class="n">{counts[s]}</div><div class="l">{_sev_badge(s)}</div></div>')
    out.append(f'<div class="tile"><div class="n">{evaluated}</div><div class="l">reglas evaluadas · '
               f'{statuses.get("fail", 0)} con hallazgos</div></div></div>')

    if with_scoring and "dp" in packs and ctx.dp:
        sc = scoring.compute(res)
        out += ['<h2>Pre-score determinista por pilar</h2><div class="card"><div class="score-head">',
                f'<span class="g">{sc["global"] if sc["global"] is not None else "N/A"}</span>'
                f'<span class="sub">{e(str(sc["classification"] or ""))} · escala 0–5 · evaluado como '
                f'<b>{e(str(sc.get("reference_state") or "productivo"))}</b></span></div>',
                _pillars(sc),
                '<div class="note">Barra = pre-score por evidencia automatizada · marca vertical = score declarado en '
                'el scorecard · ⛔ = pilar limitado a 2.0 por un BLOCKER abierto · N/A = sin artefacto evaluable. ' + e(sc.get("note", "")) + '</div></div>']

    out.append(f'<h2>Hallazgos (<span id="shown">{len(rows)}</span> de {len(rows)})</h2>')
    if rows:
        out.append('<div class="controls" role="group" aria-label="Filtrar por severidad">')
        for s in SEV:
            n = sum(1 for v in rows if v.severity == s)
            if n:
                out.append(f'<button class="chip" data-sev="{s}" aria-pressed="true">{_sev_badge(s)} {n}</button>')
        out.append('<input type="search" id="q" placeholder="Buscar regla, archivo o texto…" aria-label="Buscar"></div>')
        out.append('<div class="table-wrap"><table id="findings"><colgroup><col style="width:112px"><col style="width:190px">'
                   '<col style="width:180px"><col><col style="width:26%"><col style="width:72px"></colgroup>'
                   '<thead><tr><th>Severidad</th><th>Regla</th><th>Ubicación</th>'
                   '<th>Hallazgo</th><th>Remediación</th><th>KB</th></tr></thead><tbody>')
        for v in rows:
            loc = "(repositorio)" if v.location.file in (".", "") else f"{v.location.file}:{v.location.line}"
            fix = '<span class="tag fixable" title="govkit fix puede remediarlo">autofix</span>' if v.fix else ""
            esc = f'<div class="rtitle">escalada por {e(v.escalated_by)}</div>' if v.escalated_by else ""
            out.append(f'<tr data-sev="{v.severity}"><td>{_sev_badge(v.severity)}</td>'
                       f'<td><div class="rid mono">{e(v.rule_id)}</div><div class="rtitle">{e(v.title)}</div>{esc}</td>'
                       f'<td class="loc mono">{e(loc)}</td><td>{e(v.message)}</td>'
                       f'<td class="rem">{e(v.remediation)} {fix}</td>'
                       f'<td class="kb">{"".join(f"<span class=tag>{e(k)}</span>" for k in v.kb)}</td></tr>')
        out.append("</tbody></table></div>")
    else:
        out.append('<div class="card empty">Sin hallazgos que cuenten para el veredicto.</div>')

    suppressed = [v for v in res.violations if not v.counts]
    if suppressed:
        out.append(f"<details><summary>{len(suppressed)} hallazgo(s) exceptuados por waiver o baseline</summary><ul class=q>")
        for v in suppressed[:200]:
            why = f"waiver · ADR {v.waived['adr']} · vence {v.waived['expires']}" if v.waived else "baseline"
            out.append(f"<li><code>{e(v.rule_id)}</code> {e(v.location.file)}:{v.location.line} — {e(str(why))}</li>")
        out.append("</ul></details>")
    if res.handoff:
        out.append(f"<h2>Revisión semántica sugerida ({len(res.handoff)})</h2><div class=card><div class=note "
                   "style='margin-top:0'>Preguntas para el revisor LLM local (govkit review) o el agente vía MCP. "
                   "Consultivas: no bloquean.</div><ul class=q>")
        for h in res.handoff[:60]:
            out.append(f"<li><code>{e(h['rule_id'])}</code> {e(h['question'])} "
                       + "".join(f"<span class=tag>{e(k)}</span>" for k in h.get("kb", [])) + "</li>")
        out.append("</ul></div>")
    meta = {"run_id": res.run_id, "duration_ms": res.duration_ms, "ruleset_digest": res.catalog.get("_digest")}
    out.append(f'<footer>govkit {__version__} · {now} · run <span class="mono">{e(res.run_id)}</span> · digest '
               f'<span class="mono">{e(str(meta["ruleset_digest"]))}</span> · {res.duration_ms} ms · '
               'Los hallazgos deterministas son la fuente de verdad; la revisión semántica es consultiva.</footer>')
    out.append(f'<script type="application/json" id="govkit-meta">{e(json.dumps(meta))}</script>')
    out.append(f"<script>{JS}</script></main></body></html>")
    return "".join(out) + "\n"
