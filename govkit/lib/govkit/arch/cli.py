"""`govkit arch …` — capa de memoria arquitectónica desde la terminal."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

from govkit.arch import NOT_DETERMINED, gitio, home, load_state, registry


def _json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_status(a) -> int:
    from govkit.arch import index as I
    state = load_state()
    rows = []
    for src in registry.sources().values():
        s = state["sources"].get(src.id) or {}
        path = src.path
        row = {"fuente": src.id, "repo": src.repo, "ruta": str(path), "clon": gitio.is_repo(path)}
        if row["clon"]:
            st = gitio.status(path)
            ref = f"origin/{src.branch}"
            origin = gitio.resolve(path, ref)
            row.update({"rama_local": gitio.current_branch(path), "working_tree": "limpio" if st.get("clean") else
                        ", ".join(f"{x.strip()} {p}" for x, p in st.get("changes", [])[:4]),
                        "origin": (origin or "")[:7] or "—"})
            if s.get("commit") and origin and s["commit"] != origin:
                n = gitio.count_between(path, s["commit"], origin) if gitio.resolve(path, s["commit"]) else None
                row["pendiente"] = f"{n if n is not None else '?'} commit(s) nuevos sin analizar (govkit arch sync)"
        idx = I.load(src.id)
        row.update({"analizado": (str(s.get("commit") or "")[:7] or "nunca"), "fecha_commit": s.get("commit_date"),
                    "origen_indice": s.get("origin"), "analizado_el": s.get("analyzed_at"),
                    "sync": s.get("synced_at"),
                    "secretos": len(idx.get("secrets") or []) if idx else None})
        rows.append(row)
    if a.json:
        _json({"home": str(home()), "fuentes": rows})
        return 0
    print(f"govkit arch · estado local en {home()}")
    for r in rows:
        clon = "clon ✔" if r["clon"] else "sin clon"
        print(f"\n● {r['repo']} ({r['fuente']}) · {clon} · {r['ruta']}")
        if r["clon"]:
            print(f"  rama local: {r.get('rama_local')} · origin/main: {r.get('origin')} · working tree: {r.get('working_tree')}")
        print(f"  analizado: {r['analizado']} ({r.get('fecha_commit') or '—'}) vía {r.get('origen_indice') or '—'}"
              f" · último sync: {r.get('sync') or '—'}")
        if r.get("pendiente"):
            print(f"  ⚠️ {r['pendiente']}")
        if r.get("secretos"):
            print(f"  ⚠️ SECRET DETECTED: {r['secretos']} (govkit arch secretos)")
    if not any(r["clon"] for r in rows) and not any(r["analizado"] != "nunca" for r in rows):
        print("\nSiguiente paso: `govkit arch sync` (con los clones en ~/global-*) o "
              "`govkit arch ingest --snapshot <archivo.txt>`.")
    return 0


def cmd_config(a) -> int:
    if a.fuente and a.ruta:
        p = registry.set_path(a.fuente, a.ruta)
        print(f"govkit arch: {registry.get(a.fuente).repo} → {registry.get(a.fuente).path} (guardado en {p})")
        return 0
    for s in registry.sources().values():
        print(f"{s.id:18} {s.short:4} {s.repo:32} {s.path}")
    return 0


def cmd_ingest(a) -> int:
    from govkit.arch import changes, ingest
    if a.snapshot:
        for f in a.snapshot:
            rep = changes.ingest_snapshot_with_diff(Path(f), min_impact=a.umbral)
            _report(rep, a)
        return 0
    srcs = [registry.get(a.fuente)] if a.fuente else list(registry.sources().values())
    rc = 0
    for src in srcs:
        try:
            if a.dir:
                idx = ingest.ingest_dir(src, a.dir)
            else:
                idx = ingest.ingest_git(src, a.ref)
            m = idx["meta"]
            print(f"✔ {src.repo}: {len(idx['files'])} archivos indexados @ {str(m.get('commit'))[:7]} ({m.get('ref') or m.get('origin')})")
        except (FileNotFoundError, gitio.GitError) as exc:
            print(f"✘ {src.repo}: {exc}", file=sys.stderr)
            rc = 2
    return rc


def _report(rep: dict, a) -> None:
    from govkit.arch import changes
    if getattr(a, "json", False):
        slim = dict(rep)
        for al in slim.get("alerts", []):
            al.pop("items", None)
        slim.pop("previous", None)
        slim.pop("current", None)
        _json(slim)
        return
    if rep.get("skipped"):
        print(f"○ {rep['repo']}: {rep['skipped']}")
        return
    wt = rep.get("working_tree") or {}
    head = f"● {rep['repo']}"
    if rep.get("fetch"):
        head += f" · fetch {rep['fetch']}"
    print(head)
    if wt and not wt.get("clean"):
        print(f"  working tree con cambios locales (no se tocan): {', '.join(wt.get('changes', [])[:4])}")
    if rep.get("up_to_date"):
        print(f"  al día @ {str(rep.get('commit'))[:7]} — sin cambios desde el último análisis")
    elif rep.get("first_ingest"):
        cur = rep.get("current") or {}
        print(f"  primera ingesta @ {str(cur.get('commit'))[:7]} ({cur.get('commit_date')}): línea base establecida "
              f"({rep.get('files_analyzed')} archivos)")
    else:
        ch = rep.get("changes") or []
        print(f"  {len(ch)} archivo(s) cambiados · {len(rep.get('alerts') or [])} alerta(s) · "
              f"{len(rep.get('fact_changes') or [])} hecho(s) que cambiaron")
        for al in rep.get("alerts") or []:
            print()
            print(changes.render_alert(al))
        st = rep.get("stale") or {}
        if any(st.values()):
            print(f"  Análisis posiblemente obsoletos → reglas: {', '.join(st.get('rules') or []) or '—'} · "
                  f"KB: {', '.join(st.get('kb') or []) or '—'} · notas: {', '.join(st.get('notes') or []) or '—'}")
    for s in rep.get("signals") or []:
        print(f"  ◌ señal: rama {s['branch']} ({s['status']}, {s['date'][:10]}) · {s['n_files']} archivo(s) · "
              f"impacto potencial {s['impact']} · {s['note']}")
    if rep.get("pull_advice"):
        print(f"  ℹ️ {rep['pull_advice']}")
    if rep.get("changelog"):
        print(f"  changelog: {rep['changelog']}")


def cmd_sync(a) -> int:
    from govkit.arch import changes
    reps = changes.sync([a.fuente] if a.fuente else None, fetch=not a.sin_fetch, min_impact=a.umbral)
    if a.json:
        out = []
        for r in reps:
            r = dict(r)
            for al in r.get("alerts", []):
                al.pop("items", None)
            r.pop("previous", None)
            r.pop("current", None)
            out.append(r)
        _json(out)
        return 0
    for r in reps:
        _report(r, a)
        print()
    if all(r.get("skipped") for r in reps):
        print("govkit arch: no hay clones locales de las fuentes. Clónalos (solo lectura) en ~/ o usa "
              "`govkit arch config <fuente> <ruta>`; alternativa: `govkit arch ingest --snapshot <archivo.txt>`.")
        return 2
    return 0


def cmd_cambios(a) -> int:
    from govkit.arch import changes
    logs = changes.list_changelogs(50)
    if a.n is None:
        if not logs:
            print("Sin changelogs todavía (govkit arch sync).")
        for i, p in enumerate(logs, 1):
            print(f"{i:3}. {p.name}")
        return 0
    if a.n < 1 or a.n > len(logs):
        print(f"govkit arch: no existe el changelog {a.n}", file=sys.stderr)
        return 2
    p = logs[a.n - 1]
    print(p.with_suffix(".json").read_text(encoding="utf-8") if a.json else p.read_text(encoding="utf-8"))
    return 0


def cmd_contexto(a) -> int:
    from govkit.arch import context
    ctx = context.context(a.ruta)
    if a.json:
        _json(ctx)
    else:
        sys.stdout.write(context.render(ctx))
    return 0


def cmd_resumen(a) -> int:
    from govkit.arch import index as I
    from govkit.arch import summaries
    from govkit.arch.context import resolve_target
    if a.todos:
        srcs = [registry.get(a.fuente)] if a.fuente else list(registry.sources().values())
        out_dir = home() / "summaries"
        n = 0
        for src in srcs:
            idx = I.load(src.id)
            if not idx:
                print(f"○ {src.repo}: no ingerido")
                continue
            text = [f"# Mini-resúmenes · {idx['meta']['repo']}@{str(idx['meta'].get('commit'))[:7]}\n"]
            for u in summaries.units(idx):
                text.append(summaries.render(summaries.summarize(idx, u)))
                n += 1
            body = "\n".join(text)
            if a.escribir:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / f"{src.id}.md").write_text(body, encoding="utf-8")
            else:
                print(body)
        if a.escribir:
            print(f"✔ {n} mini-resúmenes en {out_dir}")
        return 0
    if not a.ruta:
        print("govkit arch resumen <repo/ruta> | --todos", file=sys.stderr)
        return 2
    t = resolve_target(a.ruta)
    if t["mode"] != "corp":
        print("govkit arch: `resumen` es para rutas de los repos corporativos; para tu repo usa `govkit arch contexto`.",
              file=sys.stderr)
        return 2
    idx = I.load(t["source"].id)
    if not idx:
        print(f"{NOT_DETERMINED}: {t['source'].repo} no está ingerido (govkit arch sync / ingest)", file=sys.stderr)
        return 2
    s = summaries.summarize(idx, summaries.unit_for(idx, t["rel"]))
    _json(s) if a.json else sys.stdout.write(summaries.render(s))
    return 0


def cmd_conflictos(a) -> int:
    from govkit.arch import facts as F
    states = F.conflict_states()
    if a.id:
        states = [c for c in states if c["id"].upper() == a.id.upper()]
    if a.json:
        _json(states)
        return 0
    for c in states:
        print(f"### CONFLICT DETECTED · {c['id']} [{c['state']}] — {c['title']}")
        print(f"Source A: {c['source_a']}\nSource B: {c['source_b']}\n\nConflict: {c['conflict']}\n")
        print("Evidence:")
        for r in c["fact_results"]:
            mark = "✔" if r["holds"] else "✘" if r["holds"] is False else "?"
            print(f"  {mark} {r['id']} {r.get('statement', '')} — {r.get('trace') or r.get('detail')}")
        for e in c.get("evidence") or []:
            print(f"  · {e}")
        print(f"\nPossible explanation: {c.get('explanation')}\nWhat needs confirmation: {c.get('confirm')}")
        if c.get("rules"):
            print(f"Reglas govkit afectadas: {', '.join(c['rules'])}")
        if c.get("mitigation"):
            print(f"Mitigación en govkit: {c['mitigation']}")
        print(f"Hallazgo: {c.get('hallazgo')} · Potential ADR: {c.get('potential_adr') or '—'}\n")
    return 0


def cmd_hechos(a) -> int:
    from govkit.arch import facts as F
    res = F.evaluate_all()
    if a.json:
        _json(res)
        return 0
    for fid, r in res.items():
        mark = "✔" if r["holds"] else "✘" if r["holds"] is False else "?"
        print(f"{mark} {fid} [{r.get('label')}/{r.get('status')}] {r['statement']} — {r['detail']} · {r['trace']}")
    return 0


def cmd_adr(a) -> int:
    from govkit.arch import adr as A
    repo = Path(a.repo).resolve() if a.repo else None
    inv = A.inventory(repo=repo)
    pots = A.potentials(adrs=[x for x in inv if x["source"] not in ("govkit",)])
    if a.json:
        _json({"adrs": inv, "potential_adrs": pots})
        return 0
    if not a.potenciales:
        print(f"ADR registrados ({len(inv)}):")
        for x in inv:
            tpl = " (plantilla)" if x.get("template") else ""
            print(f"- {x['id']}{tpl} · {x['title']} · estado: {x.get('status') or '?'} · fecha: {x.get('date') or '?'} · {x['trace']}")
            if x.get("decision") and a.verbose:
                print(f"    decisión: {x['decision'][:300]}")
            if x.get("related"):
                print(f"    relacionados: {', '.join(x['related'])}")
        corp = [x for x in inv if x["source"] not in ("govkit", "repo") and not x.get("template")]
        if not corp:
            print("  → En los repos corporativos ingeridos no hay ADR formales (solo plantillas).")
    print(f"\nPotential ADR ({len(pots)}) — decisiones de facto sin ADR (no se crean automáticamente):")
    for p in pots:
        tag = " [auto]" if p.get("auto") else ""
        cov = f" · cubierto por {', '.join(p['adr'])}" if p.get("adr") else ""
        print(f"- {p['id']}{tag} [{p.get('label')}] {p['decision']}{cov}\n    por qué: {p['why']}\n    evidencia: {p['evidence']}")
    return 0


def cmd_relaciones(a) -> int:
    from govkit.arch import graph
    from govkit.arch.summaries import context_map
    edges = graph.current()
    if a.fuente:
        sid = registry.get(a.fuente).id
        edges = [e for e in edges if e["src"]["source"] == sid or e["dst"].get("source") == sid]
    if a.rotas:
        edges = [e for e in edges if e["type"] == "reference_broken"]
    if a.json:
        _json({"curated": context_map().get("relations") or [], "edges": edges})
        return 0
    if not a.rotas:
        print("Matriz de relaciones entre repositorios (curada + derivada):\n")
        print("| # | Fuente | Se relaciona con | Tipo de relación | Evidencia | Etiqueta |\n|---|---|---|---|---|---|")
        for r in context_map().get("relations") or []:
            print(f"| {r['id']} | {r['from']} | {r['to']} | {r['type']} | {r['evidence']} | {r['label']} |")
        from collections import Counter
        cross = Counter((e["src"]["source"], e["dst"].get("source") or e["dst"].get("repo") or "?", e["type"])
                        for e in edges if e["src"]["source"] != (e["dst"].get("source") or ""))
        print("\nRelaciones derivadas del contenido (entre fuentes):")
        for (s, d, t), n in sorted(cross.items()):
            print(f"- {s} → {d}: {t} ×{n}")
        from collections import Counter as C2
        print("\nTotales:", dict(C2(e["type"] for e in edges)))
        for e in edges:
            if e["type"] == "duplicate_divergent":
                print(f"\n⚠️ Duplicado divergente: {e['evidence']}")
                for d in e.get("diff_sample") or []:
                    print(f"    {d[:160]}")
        return 0
    from collections import defaultdict
    by_target = defaultdict(list)
    for e in edges:
        by_target[(e["dst"].get("source"), e["dst"].get("path"))].append(e)
    print(f"Referencias rotas ({len(edges)}), agrupadas por destino:")
    for (s, p), es in sorted(by_target.items(), key=lambda kv: -len(kv[1])):
        print(f"- {s}:{p} ← {len(es)} referencia(s): " + ", ".join(sorted({x['src']['path'].rsplit('/', 1)[-1] for x in es}))[:200])
    return 0


def cmd_buscar(a) -> int:
    from govkit.arch import search
    hits = search.search(" ".join(a.texto), k=a.k, source=registry.get(a.fuente).id if a.fuente else "")
    if a.json:
        _json(hits)
        return 0
    if not hits:
        print("Sin resultados (¿fuentes ingeridas? govkit arch status)")
    for h in hits:
        print(f"- [{h['label']}/{h['status']}] {h['trace']} (score {h['score']})\n    «{h['snippet'][:220]}»")
    return 0


def cmd_dp(a) -> int:
    from govkit.arch import archimate
    from govkit.arch import index as I
    am = I.load("archimate")
    if not am:
        print(f"{NOT_DETERMINED}: el modelo ArchiMate no está ingerido (govkit arch sync / ingest)", file=sys.stderr)
        return 2
    if not a.repo:
        inv = archimate.dp_inventory(am)
        if a.json:
            _json(inv)
            return 0
        print(f"Data Products modelados en {I.trace(am, 'model')} ({len(inv)}):")
        for d in inv:
            lv = ", ".join(f"{k}:{v}" for k, v in d["levels"].items()) or "sin vistas"
            print(f"- {d['name']} ({d['country']}) · {d['views']} vista(s) [{lv}] · niveles declarados: "
                  f"{', '.join(d['declared_levels']) or '—'}")
        return 0
    repo = Path(a.repo).resolve()
    res = archimate.compare(am, repo, a.nombre)
    if a.json:
        _json(res)
        return 0
    print(f"## Diseño aprobado (ArchiMate) vs implementación · {res['repo']}\nFuente: {res['trace']}")
    if res["found"]["dp"]:
        des = res.get("design") or {}
        print(f"Vistas: " + ", ".join(f"{v['name']} [{v['level']}]{' (vacía)' if v['empty'] else ''}" for v in des.get("views", [])))
        if des.get("technologies"):
            print(f"Tecnologías modeladas: {', '.join(des['technologies'])}")
        if des.get("processes"):
            print(f"Procesos modelados: {', '.join(des['processes'][:12])}")
        if res["rows"]:
            print("\n| Capa | Modelada (APPROVED) | Implementada (IMPLEMENTED) | Estado |\n|---|---|---|---|")
            for r in res["rows"]:
                print(f"| {r['layer']} | {'sí' if r['modeled'] else 'no'} | {', '.join(r['implemented']) or 'no'} | {r['state']} |")
    print(f"\nConclusión: {res['verdict']}")
    return 0


def cmd_trazabilidad(a) -> int:
    from govkit.arch import tracecheck
    res = tracecheck.check()
    if a.json:
        _json(res)
    else:
        sys.stdout.write(tracecheck.render(res))
    return 1 if res["rules_unknown_doc"] or res["kb_unknown_doc"] else 0


def cmd_secretos(a) -> int:
    from govkit.arch import index as I
    found = 0
    for sid, idx in I.all_current().items():
        for s in idx.get("secrets") or []:
            found += 1
            print(f"SECRET DETECTED · archivo: {s['file'].rsplit('/', 1)[-1]} · ruta: {idx['meta']['repo']}/{s['file']} · "
                  f"tipo potencial: {s['type']}")
        ids = idx.get("masked_account_ids") or {}
        if ids:
            print(f"ℹ️ {idx['meta']['repo']}: {sum(ids.values())} identificador(es) de cuenta AWS enmascarados en "
                  f"{len(ids)} archivo(s) (dato sensible, no secreto)")
    if not found:
        print("SECRET DETECTED: ninguno en las fuentes ingeridas (los valores nunca se muestran ni se guardan).")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="govkit arch", description="Memoria arquitectónica: repos corporativos como "
                                 "conocimiento trazable, actualizado y accionable (solo lectura).")
    sub = ap.add_subparsers(dest="sub", required=True)

    def add(name, fn, help_, aliases=()):
        p = sub.add_parser(name, help=help_, aliases=list(aliases))
        p.set_defaults(fn=fn)
        p.add_argument("--json", action="store_true", help="salida JSON")
        return p

    add("estado", cmd_status, "fuentes, clones, commits analizados y pendientes", ["status"])
    p = add("config", cmd_config, "ver/fijar la ruta local de una fuente: config <fuente> <ruta>")
    p.add_argument("fuente", nargs="?")
    p.add_argument("ruta", nargs="?")
    p = add("ingest", cmd_ingest, "indexar desde el clon git (origin/main), un snapshot .txt o un directorio")
    p.add_argument("--snapshot", nargs="+", help="snapshot(s) .txt (actualización incremental sin git)")
    p.add_argument("--fuente", help="governance | platform-core | archimate | metadata-catalog (o repo/sigla)")
    p.add_argument("--ref", help="ref git a analizar (default origin/<rama principal>)")
    p.add_argument("--dir", help="indexar un directorio (sin git)")
    p.add_argument("--umbral", default="MEDIUM", choices=["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
    p = add("sync", cmd_sync, "fetch (solo refs remotas) + diff incremental + alertas + changelog (nunca pull)")
    p.add_argument("--fuente")
    p.add_argument("--sin-fetch", action="store_true", help="no contactar el remoto (usa lo ya descargado)")
    p.add_argument("--umbral", default="MEDIUM", choices=["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
                   help="impacto mínimo para emitir alerta (default MEDIUM)")
    p = add("cambios", cmd_cambios, "changelogs ARCHITECTURAL KNOWLEDGE UPDATE: lista | cambios N", ["changes"])
    p.add_argument("n", nargs="?", type=int)
    p = add("contexto", cmd_contexto, "qué debo mirar si analizo esta ruta (corporativa o de tu Data Product)",
            ["context", "que-mirar"])
    p.add_argument("ruta")
    p = add("resumen", cmd_resumen, "mini-resumen arquitectónico de una ruta corporativa (o --todos)", ["summary"])
    p.add_argument("ruta", nargs="?")
    p.add_argument("--todos", action="store_true")
    p.add_argument("--fuente")
    p.add_argument("--escribir", action="store_true", help="guardar en ~/.govkit/arch/summaries/")
    p = add("conflictos", cmd_conflictos, "contradicciones CONFLICT DETECTED y su estado (VIGENTE/REVISAR)", ["conflicts"])
    p.add_argument("id", nargs="?")
    add("hechos", cmd_hechos, "hechos verificables re-evaluados contra el índice", ["facts"])
    p = add("adr", cmd_adr, "inventario de ADR y Potential ADR")
    p.add_argument("--potenciales", action="store_true", help="solo Potential ADR")
    p.add_argument("--repo", help="incluir los ADR de un repo de Data Product")
    p.add_argument("--verbose", "-v", action="store_true")
    p = add("relaciones", cmd_relaciones, "matriz de relaciones entre repos (--rotas: referencias rotas)", ["relations"])
    p.add_argument("--rotas", action="store_true")
    p.add_argument("--fuente")
    p = add("buscar", cmd_buscar, "búsqueda en las fuentes corporativas con trazabilidad", ["search"])
    p.add_argument("texto", nargs="+")
    p.add_argument("-k", type=int, default=8)
    p.add_argument("--fuente")
    p = add("dp", cmd_dp, "Data Products modelados en ArchiMate · dp <repo>: diseño aprobado vs implementación")
    p.add_argument("repo", nargs="?")
    p.add_argument("--nombre", help="nombre del Data Product si difiere de la carpeta")
    add("trazabilidad", cmd_trazabilidad, "validar que las fuentes citadas por reglas/KB existen", ["trace"])
    add("secretos", cmd_secretos, "SECRET DETECTED (solo archivo/ruta/tipo; nunca el valor)", ["secrets"])
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    return args.fn(args)
