"""`govkit init`: genera un repositorio de Data Product conforme al estándar corporativo."""
from __future__ import annotations

import datetime as _dt
import os
import stat
from pathlib import Path
from typing import Dict, Optional

from govkit.paths import TEMPLATES_DIR, registry

# Carpetas estándar sin contenido inicial (se versionan con .gitkeep) — lineamiento Estructura de Repositorio.
EMPTY_DIRS = [
    "contracts/bronze", "contracts/silver", "contracts/gold/dim", "contracts/gold/fact", "contracts/semantic",
    "contracts/input", "contracts/policies", "metadata/lineage", "metadata/tags",
    "modeling/dbt/macros", "modeling/dbt/models/silver/odm", "modeling/dbt/models/silver/dictionary",
    "modeling/dbt/models/gold", "observability/dashboards", "observability/notifications",
    "pipelines/orchestration/step_function", "publishing/views", "publishing/api", "publishing/subscriptions",
    "quality/thresholds", "quality/reports", "shared/libraries", "shared/configs", "shared/templates",
    "src/bronze/glue", "src/bronze/lambda", "src/bronze_to_silver", "src/silver/glue", "src/silver/lambda",
    "src/silver/dictionary", "src/silver_to_gold", "src/gold/glue", "src/gold_to_semantic", "src/semantic",
    "src/common/triggers", "tests/contract", "tests/data_quality", "tests/integration", "tests/smoke", "tests/unit",
]
TYPE_MAP = {"anl": "analytical", "txd": "operational"}


def variables(domain: str, subdomain: str, type_code: str, country: str, owner: Optional[str]) -> Dict[str, str]:
    reg = registry("domains").get("domains", {})
    code = reg.get(domain, {}).get("code", domain[:3])
    sub_snake = subdomain.replace("-", "_")
    repo = f"{domain.replace('_', '-')}-{subdomain.replace('_', '-')}-{type_code}-dp-{country}"
    owner_email = owner or "owner@cencosud.com"
    return {
        "repo": repo, "domain": domain, "subdomain": sub_snake, "subdomain_snake": sub_snake, "country": country,
        "type_code": type_code, "dp_type": TYPE_MAP.get(type_code, "analytical"), "domain_code": code,
        "dp_id": f"DP-{code.upper()}-{sub_snake.replace('_', '').upper()}-{country.upper()}-001",
        "dp_name": f"{domain.replace('_', '-')}-{subdomain.replace('_', '-')}",
        "owner": owner or '"<COMPLETAR: email del business owner>"', "owner_email": owner_email,
        "today": _dt.date.today().isoformat(),
    }


def _render(text: str, vars_: Dict[str, str]) -> str:
    for k, v in vars_.items():
        text = text.replace(f"%%{k}%%", v)
    return text


def scaffold(domain: str, subdomain: str, type_code: str, country: str, dest: str = ".",
             owner: Optional[str] = None, force: bool = False) -> Path:
    vars_ = variables(domain, subdomain, type_code, country, owner)
    root = Path(dest).resolve() / vars_["repo"]
    if root.exists() and any(root.iterdir()) and not force:
        raise SystemExit(f"govkit: {root} ya existe y no está vacío (usar --force)")
    src_root = TEMPLATES_DIR / "data-product"
    for src in sorted(src_root.rglob("*")):
        if src.is_dir():
            continue
        rel = _render(str(src.relative_to(src_root)), vars_)
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_render(src.read_text(encoding="utf-8"), vars_), encoding="utf-8")
    for d in EMPTY_DIRS:
        p = root / d
        p.mkdir(parents=True, exist_ok=True)
        if not any(p.iterdir()):
            (p / ".gitkeep").write_text("", encoding="utf-8")
    return root


HOOK = """#!/usr/bin/env bash
# govkit pre-commit: perfil rápido (sintaxis, secretos, nomenclatura, esquemas) sobre el repo.
command -v govkit >/dev/null 2>&1 || { echo "govkit no está en PATH (source ~/.zshrc)"; exit 0; }
govkit lint . --profile pre-commit --fail-on BLOCKER || {
  echo ""; echo "⛔ govkit bloqueó el commit (hallazgos BLOCKER). Detalle: govkit lint -v"; exit 1; }
"""


def install_hook(path: str = ".") -> Path:
    git_dir = Path(path).resolve() / ".git"
    if not git_dir.is_dir():
        raise SystemExit(f"govkit: {path} no es un repositorio git")
    hook = git_dir / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() and "govkit" not in hook.read_text(encoding="utf-8", errors="ignore"):
        hook.rename(hook.with_suffix(".pre-govkit"))
    hook.write_text(HOOK, encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook
