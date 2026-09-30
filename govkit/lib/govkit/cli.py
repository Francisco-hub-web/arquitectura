"""CLI `govkit` — punto de entrada único del Sistema de Gobernanza Híbrido.

Códigos de salida: 0 = PASS/WARN · 1 = FAIL (hallazgos ≥ --fail-on) · 2 = error de uso/config · 3 = error interno.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from govkit import __version__

PACK_COMMANDS = {"omd-lint": "omd", "docs-lint": "docs", "portfolio": "portfolio"}


def _engine(args, packs, stage=None):
    from govkit.engine import Engine, load_baseline, load_catalog
    from govkit.repo import RepoContext

    catalog = load_catalog(getattr(args, "catalog", None))
    if getattr(args, "cenco_dc", False):
        os.environ["GOVKIT_CENCO_DC"] = "1"
    ctx = RepoContext(args.path, catalog, stage_override=stage or getattr(args, "stage", None),
                      base_ref=getattr(args, "base", None), standard=getattr(args, "estandar", None))
    baseline = load_baseline(args.baseline) if getattr(args, "baseline", None) else None
    if baseline is None and getattr(args, "baseline", "") is not False:
        from govkit.privacy import private_dir
        pdir = private_dir(ctx.root) if ctx.is_git else None
        if pdir and (pdir / "baseline.json").exists():
            baseline = load_baseline(str(pdir / "baseline.json"))
            print(f"govkit: baseline personal activo ({len(baseline)} hallazgos preexistentes no cuentan · "
                  f"{pdir / 'baseline.json'})", file=sys.stderr)
    only = [r.strip() for r in args.rules.split(",")] if getattr(args, "rules", None) else None
    return Engine(ctx, catalog, packs=packs, only=only, profile=getattr(args, "profile", None), baseline=baseline,
                  fail_on=getattr(args, "fail_on", "BLOCKER"), changed_only=getattr(args, "changed_only", False))


def _emit(res, args, packs):
    from govkit.report import console, html, jsonr, markdown, sarif

    fmt = args.format
    if fmt == "html":
        text = html.build(res, packs=packs, with_scoring="dp" in packs)
    elif fmt == "json":
        text = json.dumps(jsonr.build(res, packs=packs, profile=getattr(args, "profile", None)), ensure_ascii=False, indent=2)
    elif fmt == "sarif":
        text = json.dumps(sarif.build(res), ensure_ascii=False, indent=2)
    elif fmt == "md":
        text = markdown.build(res, with_scoring="dp" in packs)
    else:
        text = console.render(res, verbose=args.verbose, show_score="dp" in packs, packs=packs)
    if args.output:
        Path(args.output).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        if fmt != "console":
            print(console.render(res, show_score=False, packs=packs), end="", file=sys.stderr)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file and getattr(args, "gh_summary", False):
        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.write(markdown.build(res, with_scoring="dp" in packs))


def cmd_lint(args, packs=None):
    packs = packs or [p.strip() for p in args.pack.split(",")]
    res = _engine(args, packs).run()
    _emit(res, args, packs)
    return res.exit_code


def cmd_pack(args):
    args.pack = PACK_COMMANDS[args.cmd]
    return cmd_lint(args, [PACK_COMMANDS[args.cmd]])


def cmd_gate(args):
    from govkit.report import console

    res = _engine(args, ["dp"], stage=args.to).run()
    res.fail_on = args.fail_on
    _emit(res, args, ["dp"])
    ok = res.verdict != "FAIL"
    print(("✅" if ok else "❌") + f" Gate hacia `{args.to}`: {'APROBADO' if ok else 'BLOQUEADO'} "
          f"({res.counts()['BLOCKER']} BLOCKER, {res.counts()['HIGH']} HIGH)", file=sys.stderr)
    return res.exit_code


def cmd_score(args):
    from govkit import scoring

    res = _engine(args, ["dp"]).run()
    sc = scoring.compute(res)
    if args.format == "json":
        print(json.dumps(sc, ensure_ascii=False, indent=2))
        return 0
    print(f"Pre-score determinista · {res.ctx.repo_name} · estado {res.ctx.stage}\n")
    print(f"{'Pilar':<30}{'Pre':>6}{'Decl.':>7}{'Peso':>7}{'Eval/Fall':>11}{'Cobertura':>11}")
    for p in sc["pillars"].values():
        s = "N/A" if p["score"] is None else f"{p['score']:.1f}"
        d = "—" if p["declared"] is None else f"{p['declared']:.1f}"
        cap = " ⛔" if p["blocker_cap"] else ""
        print(f"{p['label']:<30}{s:>6}{d:>7}{p['weight']:>7}{p['rules_evaluated']:>6}/{p['rules_failed']:<4}"
              f"{int(p['automation_coverage'] * 100):>9}%{cap}")
    print(f"\nGlobal: {sc['global']} → {sc['classification']}")
    print("Dimensiones: " + " · ".join(f"{k}: {v}" for k, v in sc["dimensions"].items()))
    print("⛔ = pilar limitado por un BLOCKER abierto (08 §24). " + sc["note"])
    return 0


def cmd_fix(args):
    from govkit import fixer

    engine = _engine(args, ["dp"])
    before = engine.run()
    overrides = {"domain": args.domain, "subdomain": args.subdomain, "type": args.type, "country": args.country,
                 "owner": args.owner}
    actions = fixer.plan(before, placeholders=not args.no_placeholders, overrides=overrides)
    if args.apply:
        fixer.apply(before.ctx, actions, overrides=overrides)
        after = _engine(args, ["dp"]).run()
    if args.format == "json":
        out = {"mode": "apply" if args.apply else "plan", "target": before.ctx.repo_name,
               "actions": [a.to_dict() for a in actions], "before": before.counts()}
        if args.apply:
            out["after"] = after.counts()
            out["verdict_after"] = after.verdict
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    icon = {"mkdir": "📁", "template": "📄", "pc_ficha": "📄", "set": "✎ ", "placeholder": "➕", "bump": "⬆ ", "manual": "✋"}
    state = {"planned": "", "applied": " ✔", "failed": " ✘", "manual": ""}
    auto = [a for a in actions if a.kind in fixer.AUTO_KINDS]
    manual = [a for a in actions if a.kind == "manual"]
    print(f"govkit fix · {before.ctx.repo_name} · {'APLICAR' if args.apply else 'SIMULACIÓN (usa --apply para escribir)'}\n")
    if auto:
        print(f"Automáticas ({len(auto)}):")
        for a in auto:
            print(f"  {icon[a.kind]} {a.file}: {a.detail}{state[a.status]}"
                  + (f"  ({a.reason})" if a.reason else "") + f"   [{', '.join(a.rules)}]")
    if manual and (args.verbose or not auto):
        print(f"\nRequieren decisión humana ({len(manual)}):")
        for a in manual:
            print(f"  {icon['manual']} {a.file}{' · ' + a.key if a.key else ''}: {a.detail}   [{', '.join(a.rules)}]")
    elif manual:
        print(f"\n{len(manual)} hallazgo(s) con remediación manual (ver con -v).")
    if not actions:
        print("Sin remediaciones automáticas pendientes.")
    if args.apply:
        b, a_ = before.counts(), after.counts()
        print("\nAntes → después: " + " · ".join(f"{k} {b[k]}→{a_[k]}" for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW"))
              + f" · veredicto {before.verdict}→{after.verdict}")
        failed = [a for a in actions if a.status == "failed"]
        if failed:
            print(f"⚠️  {len(failed)} acción(es) no aplicadas de forma segura: revisar a mano.")
    elif auto:
        print("\nLas marcas <COMPLETAR> dejan el esqueleto explícito; el hallazgo sigue abierto hasta completarlo.")
    return 0


def cmd_rules(args):
    from govkit.engine import load_catalog
    from govkit.model import NATURES

    cat = load_catalog()
    rules = [r for r in cat["_rules"] if (not args.nature or r.nature in args.nature.upper())
             and (not args.pack or r.pack == args.pack)]
    if args.format == "json":
        print(json.dumps([r.raw for r in rules], ensure_ascii=False, indent=2, default=str))
        return 0
    if args.format == "md":
        from govkit.docgen import rules_markdown
        print(rules_markdown(cat))
        return 0
    for r in rules:
        print(f"{r.id}  [{r.nature}] {r.severity:<7} {r.title}  ({r.source.get('doc', '')} {r.source.get('section', '')})")
    print(f"\n{len(rules)} reglas · " + " · ".join(f"{k}={sum(1 for r in rules if r.nature == k)} ({v})" for k, v in NATURES.items()))
    return 0


def cmd_explain(args):
    from govkit.engine import load_catalog

    cat = load_catalog()
    rule = next((r for r in cat["_rules"] if r.id == args.rule.upper()), None)
    if not rule:
        print(f"Regla desconocida: {args.rule}", file=sys.stderr)
        return 2
    print(f"{rule.id} · {rule.title}\n")
    print(f"  Naturaleza : {rule.nature}   Severidad base: {rule.severity}   Pilar: {rule.pillar}   Pack: {rule.pack}")
    print(f"  Técnica    : {rule.technique}   Puntos de control: {', '.join(rule.enforcement)}")
    if rule.stages:
        print("  Escalamiento por etapa: " + ", ".join(f"{k}={v}" for k, v in rule.stages.items()))
    src = rule.source
    print(f"  Fuente     : {src.get('doc')} {src.get('section', '')}")
    if src.get("quote"):
        print(f"               «{src['quote']}»")
    print(f"  Remediación: {rule.remediation}")
    if rule.semantic_question:
        print(f"  Pregunta semántica (LLM): {rule.semantic_question}")
    print(f"  KB         : {', '.join(rule.kb)}  →  govkit kb show {rule.kb[0] if rule.kb else ''}")
    if rule.check:
        print(f"  Check      : {json.dumps(rule.check, ensure_ascii=False, default=str)}")
    return 0


def cmd_init(args):
    from govkit.scaffold import scaffold, scaffold_platform_core

    std = args.estandar
    if std == "auto":
        from govkit.arch import index as _I
        from govkit.arch import registry as _R
        std = "platform-core" if (_I.load("platform-core") or _R.get("platform-core").path.is_dir()) else "lineamientos"
    if std == "platform-core":
        dest = scaffold_platform_core(args.domain, args.subdomain, args.type, args.country, args.dest, force=args.force)
        print(f"✅ Data Product (estándar platform-core) creado en {dest}\n"
              f"   Copia desde el baseline oficial (global-data-platform-core/data-products-baseline): contracts/_schema/, "
              f"scripts/ y .github/workflows/ (bootstrap.sh)\n   Siguiente paso: cd {dest} && govkit lint")
        return 0
    if args.type not in ("txd", "anl"):
        print("govkit: con el estándar lineamientos el tipo debe ser txd | anl", file=sys.stderr)
        return 2
    dest = scaffold(args.domain, args.subdomain, args.type, args.country, args.dest, owner=args.owner, force=args.force)
    print(f"✅ Data Product (estándar lineamientos) creado en {dest}\n   Siguiente paso: cd {dest} && govkit lint")
    return 0


def cmd_kb(args):
    from govkit.kb import store
    from govkit.kb.router import route

    kb = store.load()
    if args.kb_cmd == "list":
        total = 0
        for c in kb.chunks.values():
            total += c.tokens
            print(f"{c.id}  tier {c.tier}  {c.tokens:>5} tok  {len(c.rule_ids):>3} reglas  {c.title}")
        print(f"\n{len(kb.chunks)} mini-contextos · {total} tokens totales (estimados)")
        return 0
    if args.kb_cmd == "show":
        c = kb.chunks.get(args.id.upper())
        if not c:
            print(f"Mini-contexto desconocido: {args.id}", file=sys.stderr)
            return 2
        print(c.render(sections=args.sections))
        return 0
    if args.kb_cmd == "validate":
        errors = kb.validate()
        for e in errors:
            print("✗", e)
        print("✅ KB válida" if not errors else f"{len(errors)} problema(s)")
        return 1 if errors else 0
    if args.kb_cmd == "graph":
        print(kb.ascii_graph())
        return 0
    files = args.files.split(",") if args.files else []
    rules = args.rules.split(",") if args.rules else []
    pack = route(kb, task=args.task, query=args.query, paths=files, rule_ids=rules, budget=args.budget, mode=args.mode)
    if args.kb_cmd == "route":
        if args.format == "json":
            print(json.dumps(pack.manifest(), ensure_ascii=False, indent=2))
        else:
            print(pack.explain())
        return 0
    print(pack.text())  # kb pack
    return 0


def cmd_review(args):
    from govkit.llm.review import review

    return review(args)


def cmd_ask(args):
    from govkit.llm.review import ask

    return ask(args)


def cmd_doctor(args):
    from govkit.llm.ollama import Ollama
    from govkit.paths import KIT_HOME, yaml

    print(f"govkit {__version__} · KIT_HOME={KIT_HOME}")
    print(f"Python {sys.version.split()[0]} ({sys.executable}) · PyYAML {yaml.__version__} "
          f"({'libyaml' if getattr(yaml, '__with_libyaml__', False) else 'puro Python'})")
    client = Ollama(model=args.model)
    ok, detail = client.health()
    print(("✅" if ok else "⚠️ ") + f" Ollama {client.host}: {detail}")
    if ok:
        models = client.models()
        has = any(m.split(":")[0] == client.model.split(":")[0] and (":" not in client.model or m == client.model)
                  for m in models)
        print(("✅" if has else "⚠️ ") + f" Modelo `{client.model}` " + ("disponible" if has else
              f"no descargado → ollama pull {client.model}"))
    else:
        print("   El motor determinista funciona sin LLM. Para revisión semántica: https://ollama.com → "
              f"`ollama pull {client.model}`")
    try:
        from govkit.arch import gitio, home, load_state, registry
        st = load_state()["sources"]
        for src in registry.sources().values():
            s = st.get(src.id) or {}
            clon = "clon ✔" if gitio.is_repo(src.path) else "sin clon"
            ana = f"analizado @{str(s['commit'])[:7]} ({s.get('origin')})" if s.get("commit") else "sin analizar"
            print(("✅" if s.get("commit") else "⚠️ ") + f" arch · {src.repo}: {clon} ({src.path}) · {ana}")
        print(f"   Memoria arquitectónica en {home()} · `govkit arch sync` / `govkit arch ingest --snapshot`")
    except Exception as exc:  # noqa: BLE001 - diagnóstico no crítico
        print(f"⚠️  arch: {type(exc).__name__}: {exc}")
    return 0


def cmd_hooks(args):
    from govkit.privacy import install_hooks

    from govkit.privacy import VersionedHooksError
    try:
        hooks = install_hooks(Path(args.path), lint=True)
    except VersionedHooksError as exc:
        print(f"govkit: el repo usa hooks versionados ({exc}); no se instala para no modificar archivos que se suben.",
              file=sys.stderr)
        return 2
    print(f"✅ pre-commit (lint BLOCKER) instalado en {hooks[0]} · hooks previos encadenados")
    return 0


def cmd_privado(args):
    from govkit import privacy

    root = Path(args.path).resolve()
    if args.check:
        issues = privacy.check(root)
        if not issues:
            print("✅ Sin rastros de govkit en archivos versionados, stage, ramas ni commits sin subir.")
            return 0
        print("⚠️  Rastros de govkit que podrían verse en el remoto:")
        for i in issues:
            print("   - " + i)
        return 1
    info = privacy.setup(root)
    print(f"🔒 Modo privado activo en {root.name}")
    print(f"   Config y baseline personales: {info['private_dir']}  (dentro de .git/: nunca se sube)")
    print("   .git/info/exclude: " + (", ".join(info["excludes"]) if info["excludes"] else "ya configurado"))
    if info.get("hooks_skipped"):
        print(f"   ⚠️  Guardias NO instalados: el repo usa hooks versionados ({info['hooks_skipped']}); instalarlos\n"
              "      modificaría archivos que se suben. Usa `govkit privado --check` antes de cada push.")
    else:
        print("   Guardias locales: " + ", ".join(h.name for h in info["hooks"])
              + " → bloquean commits/push que mencionen govkit (hooks previos encadenados)")
    print("   Verificar en cualquier momento: govkit privado --check")
    return 0


def cmd_baseline(args):
    from govkit import privacy
    from govkit.report import jsonr

    args.baseline = False  # el baseline se calcula sobre TODOS los hallazgos actuales
    res = _engine(args, ["dp"]).run()
    data = jsonr.build(res)
    if not args.output:
        pdir = privacy.private_dir(res.ctx.root) if res.ctx.is_git else None
        if pdir:
            pdir.mkdir(parents=True, exist_ok=True)
            privacy.ensure_excludes(res.ctx.root)
            args.output = str(pdir / "baseline.json")
        else:
            args.output = ".govkit-baseline.json"
    Path(args.output).write_text(json.dumps({"violations": [{"fingerprint": v["fingerprint"], "rule_id": v["rule_id"],
                                                              "file": v["location"]["file"]} for v in data["violations"]]},
                                            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline con {len(data['violations'])} hallazgos → {args.output} (úsalo con --baseline para adopción brownfield)")
    return 0


def cmd_mcp(args):
    if args.print_config:
        from govkit.paths import KIT_HOME

        exe = str(KIT_HOME / "bin" / "govkit")
        print("# Claude Code (todas tus sesiones):\n"
              f"claude mcp add --scope user govkit -- {exe} mcp\n\n"
              "# Otros clientes MCP (Cursor, Claude Desktop, etc.) — bloque mcpServers:\n"
              + json.dumps({"mcpServers": {"govkit": {"command": exe, "args": ["mcp"]}}}, indent=2))
        return 0
    from govkit.mcpserver import serve

    return serve()


def cmd_notas(args):
    import shutil
    import subprocess

    from govkit import notes

    action, nid = args.accion, args.id
    if action == "lista":
        items = notes.all_notes()
        if not items:
            print('Sin notas aún. Se crean con: govkit -p "tu consulta"   (carpeta: ' + str(notes.notes_dir()) + ")")
            return 0
        for n in items:
            print(f"#{n['id']:<4} {str(n.get('fecha', '')):<17} {str(n.get('repo', '')):<30.30} {n.get('titulo', '')}")
        print(f"\n{len(items)} nota(s) · {notes.notes_dir()} · govkit notas ver N · copiar N · exportar")
        return 0
    if action == "abrir":
        opener = shutil.which("open") or shutil.which("xdg-open")
        target = str(notes.notes_dir() if nid is None else notes.get(nid)["path"])
        return subprocess.call([opener, target]) if opener else (print(target) or 0)
    if action == "exportar":
        items = notes.all_notes() if nid is None else [notes.get(nid)]
        text = notes.export([n for n in items if n])
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"✅ {len(items)} nota(s) → {args.output}")
        else:
            sys.stdout.write(text)
        return 0
    if nid is None:
        print(f"govkit: indica el número de nota: govkit notas {action} N", file=sys.stderr)
        return 2
    note = notes.get(nid)
    if not note:
        print(f"govkit: no existe la nota {nid}", file=sys.stderr)
        return 2
    if action == "ver":
        print(f"# #{note['id']} · {note.get('titulo', '')}  ({note.get('fecha', '')} · {note.get('repo', '')})\n")
        sys.stdout.write(str(note["body"]))
        return 0
    if action == "copiar":
        copier = shutil.which("pbcopy") or shutil.which("wl-copy") or shutil.which("xclip")
        body = str(note["body"])
        if not copier:
            sys.stdout.write(body)
            return 0
        cmd = [copier] + (["-selection", "clipboard"] if copier.endswith("xclip") else [])
        subprocess.run(cmd, input=body, text=True, check=False)
        print(f"📋 Nota #{nid} copiada al portapapeles")
        return 0
    if action == "borrar":
        notes.delete(nid)
        print(f"🗑  Nota #{nid} eliminada")
        return 0
    return 2


def cmd_fuentes(args):
    from govkit import sources

    text = " ".join(args.ids) if args.ids else (sys.stdin.read() if not sys.stdin.isatty() else "")
    entries = sources.resolve_all(sources.extract_ids(text))
    if not entries:
        print("govkit: no encontré IDs de reglas (GOV-XXX-NNN) ni criterios (KBnn.Xn) que resolver.", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(sources.render(entries, markdown=False))
    return 0


def cmd_verificar(args):
    from govkit import claims

    claim = " ".join(args.afirmacion).strip() or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    if not claim:
        print('govkit: indica la afirmación. Ej.: govkit verificar "el owner puede ser un buzón genérico"',
              file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({"afirmacion": claim, "candidatos": claims.candidates(claim)}, ensure_ascii=False, indent=2))
        return 0
    return claims.verify(claim, use_llm=not args.sin_ia, save=not args.no_guardar)


def cmd_arch(args):
    from govkit.arch import cli as arch_cli

    return arch_cli.main(args.args or ["-h"])


def cmd_selftest(args):
    import unittest

    from govkit.paths import KIT_HOME

    suite = unittest.defaultTestLoader.discover(str(KIT_HOME / "tests"), top_level_dir=str(KIT_HOME))
    result = unittest.TextTestRunner(verbosity=1 if not args.verbose else 2).run(suite)
    return 0 if result.wasSuccessful() else 1


def _common_lint(p, with_path=True):
    if with_path:
        p.add_argument("path", nargs="?", default=".", help="raíz del repositorio (default: .)")
    p.add_argument("--format", choices=["console", "json", "sarif", "md", "html"], default="console")
    p.add_argument("--output", "-o", help="escribir el reporte en archivo")
    p.add_argument("--stage", help="forzar estado del ciclo de vida (p.ej. listo_para_produccion)")
    p.add_argument("--base", help="ref git base para checks de diff (breaking changes, transiciones, commits)")
    p.add_argument("--changed-only", action="store_true", help="solo hallazgos en archivos cambiados vs --base")
    p.add_argument("--rules", help="filtrar reglas (glob, separadas por coma): GOV-SEC-*,GOV-IAM-004")
    p.add_argument("--profile", choices=["pre-commit", "pr", "gate", "catalog", "periodic", "runtime"],
                   help="evaluar solo reglas de ese punto de control")
    p.add_argument("--fail-on", choices=["BLOCKER", "HIGH", "MEDIUM", "LOW"], default="BLOCKER")
    p.add_argument("--estandar", "--standard", dest="estandar", choices=["auto", "platform-core", "lineamientos"],
                   help="estándar normativo (default auto: platform-core si el repo tiene sus marcadores)")
    p.add_argument("--cenco-dc", action="store_true",
                   help="además ejecutar el validador oficial cenco_dc desde el clon local de platform-core")
    p.add_argument("--baseline", help="archivo baseline (hallazgos preexistentes que no bloquean)")
    p.add_argument("--gh-summary", action="store_true", help="agregar resumen Markdown a $GITHUB_STEP_SUMMARY")
    p.add_argument("--verbose", "-v", action="store_true")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="govkit", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Sistema de Gobernanza Híbrido de Datos: motor determinista (reglas como código) + base de "
                    "conocimiento modular para LLM local.",
        epilog='Consultas con Claude Code:\n'
               '  govkit "¿qué le falta a mi data product?"      sesión interactiva\n'
               '  govkit -p "¿qué le falta a mi data product?"   solo la respuesta + fuentes (se guarda en govkit notas)\n'
               '  govkit -p --sumar 3 "y qué le pido a cada uno" retoma la nota 3 y le suma la respuesta\n'
               '  pbpaste | govkit -p                            pega un error, SQL o YAML\n'
               '  govkit verificar "lo que escuché en la reu"    ¿existe ese criterio? veredicto + fuentes')
    ap.add_argument("--version", action="version", version=f"govkit {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lint", help="validar un repositorio de Data Product (motor determinista)")
    _common_lint(p)
    p.add_argument("--pack", default="dp", help="packs de reglas: dp,omd,docs,portfolio")
    p.set_defaults(fn=cmd_lint)

    for name, helptext in (("omd-lint", "validar roles access-analyzer y conexiones de ingesta OpenMetadata"),
                           ("docs-lint", "validar consistencia de la documentación del framework"),
                           ("portfolio", "auditoría cross-repo de un directorio con N Data Products")):
        p = sub.add_parser(name, help=helptext)
        _common_lint(p)
        p.set_defaults(fn=cmd_pack)

    p = sub.add_parser("gate", help="pre-flight de promoción: evalúa el repo como si estuviera en el estado destino")
    _common_lint(p)
    p.add_argument("--to", required=True, help="estado destino (p.ej. listo_para_produccion)")
    p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("score", help="pre-score determinista por pilar (19-scoring-model)")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--format", choices=["table", "json"], default="table")
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser("fix", help="auto-remediación segura (simulación por defecto; --apply para escribir)")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--apply", action="store_true", help="escribir los cambios (sin esto solo muestra el plan)")
    p.add_argument("--stage", help="planificar contra un estado destino (p.ej. listo_para_produccion)")
    p.add_argument("--rules", help="limitar a reglas (glob, coma)")
    p.add_argument("--no-placeholders", action="store_true", help="no insertar claves ausentes como <COMPLETAR>")
    p.add_argument("--domain", help="dominio para las plantillas (si el nombre del repo no es estándar)")
    p.add_argument("--subdomain", help="subdominio para las plantillas")
    p.add_argument("--type", choices=["anl", "txd"], help="tipo de Data Product para las plantillas")
    p.add_argument("--country", help="país (cl, pe, co, br, ar, uy, reg)")
    p.add_argument("--owner", help="email del business owner para la ficha")
    p.add_argument("--format", choices=["console", "json"], default="console")
    p.add_argument("--verbose", "-v", action="store_true", help="listar también las remediaciones manuales")
    p.set_defaults(fn=cmd_fix)

    p = sub.add_parser("rules", help="listar el catálogo de reglas")
    p.add_argument("--format", choices=["table", "json", "md"], default="table")
    p.add_argument("--nature", help="filtrar por naturaleza: D, H, S, O (combinables: DH)")
    p.add_argument("--pack")
    p.set_defaults(fn=cmd_rules)

    p = sub.add_parser("explain", help="explicar una regla (fuente, severidad, remediación, KB)")
    p.add_argument("rule")
    p.set_defaults(fn=cmd_explain)

    p = sub.add_parser("init", help="crear un repositorio de Data Product conforme al estándar")
    p.add_argument("--domain", required=True)
    p.add_argument("--subdomain", required=True)
    p.add_argument("--type", choices=["txd", "anl", "mdh", "sm", "none"], default="anl",
                   help="código de tipo (lineamiento: txd|anl; en ArchiMate aprobado también mdh|sm o sin tipo)")
    p.add_argument("--estandar", "--standard", dest="estandar", choices=["auto", "platform-core", "lineamientos"],
                   default="auto", help="estructura a generar (auto: platform-core si está ingerido/clonado)")
    p.add_argument("--country", default="cl")
    p.add_argument("--owner", default=None, help="email del business owner")
    p.add_argument("--dest", default=".", help="directorio padre")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("kb", help="base de conocimiento: list | show | route | pack | graph | validate")
    p.add_argument("kb_cmd", choices=["list", "show", "route", "pack", "graph", "validate"])
    p.add_argument("id", nargs="?", help="ID del mini-contexto (para show)")
    p.add_argument("--task", help="tarea del desarrollador (ver kb/_graph.yaml → tasks)")
    p.add_argument("--query", "-q", help="consulta libre (BM25)")
    p.add_argument("--files", help="archivos tocados (coma)")
    p.add_argument("--rules", help="IDs de reglas violadas (coma)")
    p.add_argument("--budget", type=int, default=6000, help="presupuesto de tokens del contexto")
    p.add_argument("--mode", choices=["review", "assist", "qa"], default="assist")
    p.add_argument("--sections", help="secciones a proyectar (p.ej. R,A,V)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(fn=cmd_kb)

    p = sub.add_parser("review", help="revisión semántica con LLM local (Ollama) sobre la superficie no determinista")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--model", default=os.environ.get("GOVKIT_MODEL", "qwen2.5:7b-instruct"))
    p.add_argument("--task", help="forzar tarea para el enrutamiento de KB")
    p.add_argument("--base", help="ref git base (revisar solo artefactos cambiados)")
    p.add_argument("--budget", type=int, default=int(os.environ.get("GOVKIT_CTX", "8192")), help="num_ctx del modelo")
    p.add_argument("--max-artifacts", type=int, default=6)
    p.add_argument("--dry-run", action="store_true", help="mostrar prompts sin llamar al modelo")
    p.add_argument("--format", choices=["console", "json", "md"], default="console")
    p.add_argument("--output", "-o")
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("ask", help="preguntar a la base de conocimiento (RAG local)")
    p.add_argument("question")
    p.add_argument("--model", default=os.environ.get("GOVKIT_MODEL", "qwen2.5:7b-instruct"))
    p.add_argument("--budget", type=int, default=3500)
    p.add_argument("--no-llm", action="store_true", help="solo imprimir el contexto recuperado")
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser("doctor", help="verificar instalación, Python, PyYAML y Ollama")
    p.add_argument("--model", default=os.environ.get("GOVKIT_MODEL", "qwen2.5:7b-instruct"))
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("hooks", help="instalar hook git pre-commit (perfil rápido)")
    p.add_argument("action", choices=["install"])
    p.add_argument("path", nargs="?", default=".")
    p.set_defaults(fn=cmd_hooks)

    p = sub.add_parser("baseline", help="generar baseline de hallazgos existentes (adopción brownfield)")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--output", "-o", help="default: .git/govkit/baseline.json (personal, se carga solo)")
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_baseline, format="json")

    p = sub.add_parser("privado", aliases=["private"],
                       help="uso local sin rastro en el remoto: config en .git/, exclude y guardias de commit/push")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--check", action="store_true", help="buscar rastros de govkit que podrían llegar al remoto")
    p.set_defaults(fn=cmd_privado)

    p = sub.add_parser("notas", aliases=["notes"], help="respuestas guardadas: lista | ver N | copiar N | borrar N | "
                       "exportar [N] | abrir [N]")
    p.add_argument("accion", nargs="?", default="lista",
                   choices=["lista", "ver", "copiar", "borrar", "exportar", "abrir"])
    p.add_argument("id", nargs="?", type=int)
    p.add_argument("--output", "-o", help="archivo destino para exportar")
    p.set_defaults(fn=cmd_notas)

    p = sub.add_parser("fuentes", aliases=["sources"], help="documento § sección y cita de reglas/criterios citados "
                       "(IDs o texto pegado por stdin)")
    p.add_argument("ids", nargs="*", help="GOV-XXX-NNN, KBnn.Xn o KB_nn (o texto que los contenga)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(fn=cmd_fuentes)

    p = sub.add_parser("verificar", aliases=["existe"],
                       help="¿existe este criterio en el framework? (algo que escuchaste en una reunión)")
    p.add_argument("afirmacion", nargs="*", help='p.ej. "el business owner puede ser un buzón genérico"')
    p.add_argument("--sin-ia", action="store_true", help="solo búsqueda determinista (sin Claude Code)")
    p.add_argument("--no-guardar", action="store_true", help="no guardar como nota")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(fn=cmd_verificar)

    p = sub.add_parser("mcp", help="servidor MCP (stdio) para agentes: Claude Code, Cursor, Claude Desktop")
    p.add_argument("--print-config", action="store_true", help="mostrar cómo registrarlo en los clientes")
    p.set_defaults(fn=cmd_mcp)

    p = sub.add_parser("arch", add_help=False, help="memoria arquitectónica: repos corporativos (governance, platform-core, ArchiMate, "
                                    "metadata-catalog) → contexto por ruta, cambios, conflictos, ADR")
    p.add_argument("args", nargs=argparse.REMAINDER, help="subcomando de arch (govkit arch -h)")
    p.set_defaults(fn=cmd_arch)

    p = sub.add_parser("selftest", help="ejecutar la suite de pruebas del kit")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_selftest)
    return ap


def _free_text(argv) -> Optional[int]:
    """`govkit "texto"` → Claude Code interactivo con govkit · `-p` → solo la respuesta (con fuentes, guardada como
    nota) · `--nota N` reutiliza una nota como contexto · `--sumar N` además le agrega la respuesta. None si es un
    comando normal."""
    from govkit import assistant

    opts = {"interactive": True, "note_ids": [], "sumar": None, "guardar": True}
    rest = list(argv)
    try:
        while rest and rest[0].startswith("-") and rest[0] not in ("-h", "--help", "--version"):
            flag = rest.pop(0)
            if flag in ("-p", "--print", "--solo"):
                opts["interactive"] = False
            elif flag in ("-i", "--interactivo", "--chat"):
                opts["interactive"] = True
            elif flag == "--nota":
                opts["note_ids"].append(int(rest.pop(0)))
            elif flag == "--sumar":
                opts["sumar"] = int(rest.pop(0))
                opts["interactive"] = False
            elif flag == "--no-guardar":
                opts["guardar"] = False
            else:
                return None  # opción de otro comando → argparse
    except (IndexError, ValueError):
        print("govkit: --nota y --sumar requieren el número de nota (govkit notas para verlas)", file=sys.stderr)
        return 2
    had_flag = len(rest) != len(argv)
    commands = {name for a in parser()._actions if isinstance(a, argparse._SubParsersAction)  # noqa: SLF001
                for name in a.choices}
    if not rest and (had_flag or not sys.stdin.isatty()):
        text = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
        if text:
            return assistant.launch(text, **opts)
        if had_flag:
            print('govkit: falta la consulta. Ej.: govkit -p "¿qué le falta a mi data product?"', file=sys.stderr)
            return 2
        return None
    if not rest or rest[0] in commands or rest[0].startswith("-"):
        return None
    text = " ".join(rest).strip()
    if len(text.split()) < 2:
        print(f"govkit: comando desconocido `{text}`. Para consultar usa una frase entre comillas:\n"
              f'        govkit "¿qué le falta a mi data product?"      (govkit --help para ver los comandos)',
              file=sys.stderr)
        return 2
    return assistant.launch(text, **opts)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["arch"]:  # subcomandos propios (incluido -h) sin pasar por el parser principal
        from govkit.arch import cli as arch_cli
        try:
            return arch_cli.main(argv[1:] or ["-h"])
        except SystemExit as exc:
            return int(exc.code or 0)
        except FileNotFoundError as exc:
            print(f"govkit arch: {exc}", file=sys.stderr)
            return 2
    try:
        free = _free_text(argv)
    except KeyboardInterrupt:
        return 130
    if free is not None:
        return free
    args = parser().parse_args(argv)
    try:
        return args.fn(args)
    except FileNotFoundError as exc:
        print(f"govkit: archivo no encontrado: {exc.filename}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover
        if os.environ.get("GOVKIT_DEBUG"):
            raise
        print(f"govkit: error interno: {type(exc).__name__}: {exc} (GOVKIT_DEBUG=1 para traza)", file=sys.stderr)
        return 3
