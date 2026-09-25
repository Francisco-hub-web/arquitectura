"""CLI `govkit` — punto de entrada único del Sistema de Gobernanza Híbrido.

Códigos de salida: 0 = PASS/WARN · 1 = FAIL (hallazgos ≥ --fail-on) · 2 = error de uso/config · 3 = error interno.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from govkit import __version__

PACK_COMMANDS = {"omd-lint": "omd", "docs-lint": "docs", "portfolio": "portfolio"}


def _engine(args, packs, stage=None):
    from govkit.engine import Engine, load_baseline, load_catalog
    from govkit.repo import RepoContext

    catalog = load_catalog(getattr(args, "catalog", None))
    ctx = RepoContext(args.path, catalog, stage_override=stage or getattr(args, "stage", None),
                      base_ref=getattr(args, "base", None))
    baseline = load_baseline(args.baseline) if getattr(args, "baseline", None) else None
    only = [r.strip() for r in args.rules.split(",")] if getattr(args, "rules", None) else None
    return Engine(ctx, catalog, packs=packs, only=only, profile=getattr(args, "profile", None), baseline=baseline,
                  fail_on=getattr(args, "fail_on", "BLOCKER"), changed_only=getattr(args, "changed_only", False))


def _emit(res, args, packs):
    from govkit.report import console, jsonr, markdown, sarif

    fmt = args.format
    if fmt == "json":
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
    from govkit.scaffold import scaffold

    dest = scaffold(args.domain, args.subdomain, args.type, args.country, args.dest, owner=args.owner, force=args.force)
    print(f"✅ Data Product creado en {dest}\n   Siguiente paso: cd {dest} && govkit lint")
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
    return 0


def cmd_hooks(args):
    from govkit.scaffold import install_hook

    path = install_hook(args.path)
    print(f"✅ pre-commit instalado en {path}")
    return 0


def cmd_baseline(args):
    from govkit.report import jsonr

    res = _engine(args, ["dp"]).run()
    data = jsonr.build(res)
    Path(args.output).write_text(json.dumps({"violations": [{"fingerprint": v["fingerprint"], "rule_id": v["rule_id"],
                                                              "file": v["location"]["file"]} for v in data["violations"]]},
                                            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline con {len(data['violations'])} hallazgos → {args.output} (úsalo con --baseline para adopción brownfield)")
    return 0


def cmd_selftest(args):
    import unittest

    from govkit.paths import KIT_HOME

    suite = unittest.defaultTestLoader.discover(str(KIT_HOME / "tests"), top_level_dir=str(KIT_HOME))
    result = unittest.TextTestRunner(verbosity=1 if not args.verbose else 2).run(suite)
    return 0 if result.wasSuccessful() else 1


def _common_lint(p, with_path=True):
    if with_path:
        p.add_argument("path", nargs="?", default=".", help="raíz del repositorio (default: .)")
    p.add_argument("--format", choices=["console", "json", "sarif", "md"], default="console")
    p.add_argument("--output", "-o", help="escribir el reporte en archivo")
    p.add_argument("--stage", help="forzar estado del ciclo de vida (p.ej. listo_para_produccion)")
    p.add_argument("--base", help="ref git base para checks de diff (breaking changes, transiciones, commits)")
    p.add_argument("--changed-only", action="store_true", help="solo hallazgos en archivos cambiados vs --base")
    p.add_argument("--rules", help="filtrar reglas (glob, separadas por coma): GOV-SEC-*,GOV-IAM-004")
    p.add_argument("--profile", choices=["pre-commit", "pr", "gate", "catalog", "periodic", "runtime"],
                   help="evaluar solo reglas de ese punto de control")
    p.add_argument("--fail-on", choices=["BLOCKER", "HIGH", "MEDIUM", "LOW"], default="BLOCKER")
    p.add_argument("--baseline", help="archivo baseline (hallazgos preexistentes que no bloquean)")
    p.add_argument("--gh-summary", action="store_true", help="agregar resumen Markdown a $GITHUB_STEP_SUMMARY")
    p.add_argument("--verbose", "-v", action="store_true")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="govkit", description="Sistema de Gobernanza Híbrido de Datos: motor determinista "
                                 "(reglas como código) + base de conocimiento modular para LLM local.")
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
    p.add_argument("--type", choices=["txd", "anl"], default="anl")
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
    p.add_argument("--output", "-o", default=".govkit-baseline.json")
    p.add_argument("--stage")
    p.set_defaults(fn=cmd_baseline, format="json")

    p = sub.add_parser("selftest", help="ejecutar la suite de pruebas del kit")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(fn=cmd_selftest)
    return ap


def main(argv=None) -> int:
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
