"""DataOps & CI/CD (15-dataops-cicd, Estructura de Repositorio: CODEOWNERS, workflows, ramas)."""
from __future__ import annotations

import datetime as _dt
import fnmatch
import re

from govkit.plugins import at, at_file, plugin
from govkit.plugins.structure import norm

CODEOWNED = ["contracts", "modeling", "quality", "tests", "pipelines", "src", "docs", ".github"]
PR_TEMPLATE_SECTIONS = {"resumen": ("resumen", "summary", "descripcion"), "tipo de cambio": ("tipo de cambio", "type"),
                        "impacto": ("impacto", "impact"), "contratos": ("contrato", "contract"),
                        "metadata": ("metadata",), "runbook": ("runbook",), "breaking change": ("breaking",)}


def _on(data):
    if not isinstance(data, dict):
        return None
    return data.get("on", data.get(True))  # YAML 1.1 interpreta `on` como booleano


def _pat_matches(pattern: str, d: str) -> bool:
    p = pattern.strip().lstrip("/")
    if p in ("*", "**", "**/*"):
        return True
    p = re.sub(r"/(\*\*?)?$", "", p)
    return d == p or d.startswith(p + "/") or fnmatch.fnmatch(d, p)


@plugin("dataops.codeowners")
def codeowners(ctx, rule):
    rel = next((p for p in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS") if ctx.exists(p)), None)
    if not rel:
        return
    arch = re.compile(ctx.policies["codeowners"]["architects"])
    tech = re.compile(ctx.policies["codeowners"]["tech_leaders"])
    rules = []
    for no, line in enumerate((ctx.text(rel) or "").splitlines(), 1):
        s = line.split("#", 1)[0].strip()
        if s:
            parts = s.split()
            rules.append((no, parts[0], parts[1:]))
    for d in CODEOWNED:
        match = None
        for r in rules:
            if _pat_matches(r[1], d):
                match = r  # en GitHub gana la última coincidencia
        if not match:
            yield at_file(rel, f"`{d}/` sin CODEOWNERS (requiere Data Architects + Tech Leaders)", key=d)
            continue
        owners = " ".join(match[2])
        missing = [lbl for lbl, rx in (("Data Architects", arch), ("Tech Leaders", tech)) if not rx.search(owners)]
        if missing:
            yield at_file(rel, f"`{d}/` sin revisores obligatorios {missing} (regla línea {match[0]})", line=match[0], key=d)


def workflow(ctx, name):
    rel = f".github/workflows/{name}"
    for cand in (rel, rel.replace(".yml", ".yaml")):
        if ctx.exists(cand):
            return ctx.doc(cand)
    return None


@plugin("dataops.pr_trigger")
def pr_trigger(ctx, rule):
    doc = workflow(ctx, "pr.yml")
    if not doc or doc.error:
        return
    on = _on(doc.data)
    names = on if isinstance(on, list) else (list(on) if isinstance(on, dict) else [on])
    if "pull_request" not in [str(n) for n in names] and "pull_request_target" not in [str(n) for n in names]:
        yield at(doc, "on", "pr.yml no se dispara en `pull_request`")


@plugin("dataops.reusable_workflows")
def reusable_workflows(ctx, rule):
    for name in ("pr.yml", "deploy.yml"):
        doc = workflow(ctx, name)
        if doc and not doc.error and "base-workflows" not in (doc.text or ""):
            yield at(doc, "jobs", f"{name} no reutiliza los workflows corporativos `base-workflows`")


@plugin("dataops.pr_validations")
def pr_validations(ctx, rule):
    doc = workflow(ctx, "pr.yml")
    if not doc or doc.error:
        return
    text = (doc.text or "").lower()
    if "base-workflows" in text:
        return  # el workflow reusable central es gobernado por la capa global
    checks = {"lint": ("lint", "ruff", "flake8", "sqlfluff", "govkit"), "tests": ("pytest", "unittest", "dbt test", "test"),
              "contratos": ("contract", "govkit"), "metadata": ("metadata", "govkit"),
              "seguridad": ("security", "secret", "gitleaks", "trufflehog", "checkov", "bandit", "govkit")}
    missing = [k for k, keys in checks.items() if not any(x in text for x in keys)]
    if missing:
        yield at(doc, "jobs", f"El PR no valida: {missing} (15 §16)", missing=missing)


@plugin("dataops.security_step")
def security_step(ctx, rule):
    texts = " ".join((d.text or "").lower() for d in (workflow(ctx, "pr.yml"), workflow(ctx, "deploy.yml")) if d)
    if texts and not re.search(r"base-workflows|govkit|secret|security|gitleaks|trufflehog|checkov|tfsec|bandit", texts):
        yield at_file(".github/workflows/pr.yml", "CI/CD sin validación automatizada de seguridad antes de producción (10 §23)",
                      key="security-step")


@plugin("dataops.unit_tests")
def unit_tests(ctx, rule):
    code = ctx.glob(["src/**/*.py", "shared/**/*.py"], exclude=["**/__init__.py"])
    tests = [f for f in ctx.glob("tests/unit/**") if not f.endswith(".gitkeep")]
    if code and not tests:
        yield at_file("tests/unit", f"{len(code)} archivo(s) Python en src/shared sin tests unitarios", key="unit")


@plugin("dataops.dbt_only_transforms")
def dbt_only_transforms(ctx, rule):
    if not ctx.glob("modeling/dbt/models/gold/**/*.sql"):
        return
    for rel in ctx.glob(["src/silver_to_gold/**/*.py", "src/silver_to_gold/**/*.sql"], exclude="**/__init__.py"):
        yield at_file(rel, "Transformación Silver→Gold fuera del proyecto dbt: los modelos dbt son la fuente de verdad")


@plugin("dataops.branch_strategy")
def branch_strategy(ctx, rule):
    doc = workflow(ctx, "deploy.yml")
    if not doc or doc.error:
        return
    on = _on(doc.data) or {}
    push = on.get("push") if isinstance(on, dict) else None
    branches = set(map(str, (push or {}).get("branches", []) if isinstance(push, dict) else []))
    policy = ctx.policies.get("branching")
    if policy == "trunk" and branches - {"main"}:
        yield at(doc, "on.push.branches", f"Política trunk-based: deploy solo desde `main` (encontrado {sorted(branches)}); "
                 "la promoción entre ambientes va por pipeline, no por ramas (15 §15)")
    if policy == "env-branches":
        missing = set(ctx.policies.get("protected_branches", [])) - branches
        if missing:
            yield at(doc, "on.push.branches", f"Política env-branches: deploy.yml no cubre {sorted(missing)}")


@plugin("dataops.waivers")
def waivers(ctx, rule):
    rel = ctx.config_path
    if not rel:
        return
    doc = ctx.doc(rel)
    for i, w in enumerate(ctx.config.get("waivers") or []):
        path = f"waivers[{i}]"
        if not isinstance(w, dict):
            continue
        missing = [k for k in ("rule", "reason", "owner", "adr", "expires") if not w.get(k)]
        if missing:
            yield at(doc, path, f"Waiver {w.get('rule', i)} inválido: faltan {missing} (no se aplica)")
            continue
        try:
            exp = w["expires"] if isinstance(w["expires"], _dt.date) else _dt.date.fromisoformat(str(w["expires"]))
        except ValueError:
            yield at(doc, f"{path}.expires", f"Waiver {w['rule']}: fecha de vencimiento inválida")
            continue
        if exp < ctx.today:
            yield at(doc, f"{path}.expires", f"Waiver {w['rule']} vencido el {exp}: la excepción ya no aplica")
        if not ctx.exists(str(w["adr"])):
            yield at(doc, f"{path}.adr", f"Waiver {w['rule']}: ADR `{w['adr']}` inexistente")


@plugin("dataops.pr_template")
def pr_template(ctx, rule):
    rel = next((p for p in (".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md",
                            "docs/pull_request_template.md") if ctx.exists(p)), None)
    if not rel:
        yield at_file(".github/pull_request_template.md", "Sin template de PR con campos de gobierno del cambio (15 §16)",
                      fix={"type": "create", "path": ".github/pull_request_template.md"})
        return
    body = norm(ctx.text(rel) or "")
    missing = [k for k, keys in PR_TEMPLATE_SECTIONS.items() if not any(x in body for x in keys)]
    if missing:
        yield at_file(rel, f"Template de PR sin secciones: {missing}", missing=missing)
