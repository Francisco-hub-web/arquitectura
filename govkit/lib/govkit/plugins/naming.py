"""Nomenclatura: repositorio, ramas y commits (Estructura de Repositorio; 15-dataops-cicd §15, §20)."""
from __future__ import annotations

import re
from typing import Dict, Optional

from govkit.paths import registry
from govkit.plugins import at_file, plugin

CONVENTIONAL = re.compile(r"^(feat|fix|chore|docs|refactor|test|ci|perf|build|style|revert)(\([a-z0-9_\-/.]+\))?!?: .{3,}")
BRANCH = re.compile(r"^(feat|feature|fix|hotfix|chore)/[a-z0-9_]+(-[a-z0-9_]+)*/[a-z0-9._-]+$")


def parse_repo_name(name: str) -> Optional[Dict[str, str]]:
    reg = registry("domains")
    parts = name.split("-")
    if len(parts) < 5 or parts[-2] != "dp":
        return None
    head, typ, country = parts[:-3], parts[-3], parts[-1]
    domain, sub = head[0], head[1:]
    for n in range(len(head) - 1, 0, -1):  # dominios compuestos: supply-chain → supply_chain
        cand = "_".join(head[:n])
        if cand in reg.get("domains", {}):
            domain, sub = cand, head[n:]
            break
    if not sub:
        return None
    return {"domain": domain, "subdomain": "_".join(sub), "type": typ, "country": country}


@plugin("naming.repo_name")
def repo_name(ctx, rule):
    reg = registry("domains")
    name = ctx.repo_name
    parsed = parse_repo_name(name)
    types, countries = list(reg.get("repo_type_codes", {})), reg.get("countries", [])
    if not parsed or parsed["type"] not in types or parsed["country"] not in countries:
        yield at_file(".", f"Nombre de repo `{name}` no cumple `{{domain}}-{{subdomain}}-{{type}}-dp-{{country}}` "
                           f"(type ∈ {types}, country ∈ {countries})", key=name,
                      fix={"type": "rename_repo", "example": "product-master-txd-dp-cl"})
        return
    dp_domain = ctx.dp_get("spec.domain")
    if dp_domain and str(dp_domain) != parsed["domain"]:
        yield at_file(ctx.dp.path if ctx.dp else ".", f"El dominio del repo (`{parsed['domain']}`) no coincide con "
                      f"spec.domain (`{dp_domain}`)", key="domain-mismatch")


@plugin("naming.repo_domain")
def repo_domain(ctx, rule):
    parsed = parse_repo_name(ctx.repo_name)
    if parsed and parsed["domain"] not in registry("domains").get("domains", {}):
        yield at_file(".", f"Dominio `{parsed['domain']}` del nombre de repo no está en el registro canónico "
                           "(requiere aprobación del Data Council)", key=parsed["domain"])


@plugin("naming.branch")
def branch(ctx, rule):
    name = ctx.current_branch()
    if not name:
        return
    protected = set(ctx.policies.get("protected_branches", []))
    if ctx.policies.get("branching") == "trunk":
        protected = {"main"}
    exempt = tuple(ctx.policies.get("branch_exempt_prefixes", ["dependabot/", "renovate/"]))
    if name in protected or name.startswith(exempt):
        return
    if not BRANCH.match(name):
        yield at_file(".", f"Rama `{name}` no cumple `<tipo>/<dominio>/<descripcion>` "
                           "(tipo ∈ feat|fix|hotfix|chore)", key=name)


@plugin("naming.commits")
def commits(ctx, rule):
    for msg in ctx.commit_messages():
        if msg.startswith("Merge ") or msg.startswith("Revert \""):
            continue
        if not CONVENTIONAL.match(msg):
            yield at_file(".", f"Commit no convencional: `{msg[:70]}` (esperado `tipo(scope): descripción`; "
                               "`!` o BREAKING CHANGE para MAJOR)", key=msg[:70])
