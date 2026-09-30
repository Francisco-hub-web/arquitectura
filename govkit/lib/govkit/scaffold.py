"""`govkit init`: genera un repositorio de Data Product conforme al estándar corporativo."""
from __future__ import annotations

import datetime as _dt
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


PC_README = """# {repo}

> Data Product (estándar platform-core). Completa las marcas <COMPLETAR> antes de promover.

## Propósito / descripción
<COMPLETAR: qué decisión o proceso habilita y para quién>

## Owners / ownership
- Data Owner / Steward: <COMPLETAR>
- Technical Owner: <COMPLETAR @org/team>

## Inputs / outputs
- Inputs (bronze/landing): <COMPLETAR fuentes y contratos>
- Outputs (silver/odm, gold/dim|fact, semantic): <COMPLETAR>

## SLA
<COMPLETAR frescura / disponibilidad>

## Branches / flujo de trabajo
<COMPLETAR según el estándar vigente>

## Runbook / operación
Ver docs/engineering/runbook.md
"""


def scaffold_platform_core(domain: str, subdomain: str, type_code: Optional[str], country: str, dest: str = ".",
                           force: bool = False) -> Path:
    """Repo de Data Product con la estructura del baseline platform-core (carpetas + ficha + README/CHANGELOG).
    No genera workflows ni CODEOWNERS (afectan el GitHub corporativo): se copian desde el baseline oficial."""
    from govkit.plugins.platform_core import _baseline_dirs, ficha_template
    parts = [domain.replace("_", "-"), subdomain.replace("_", "-")] + ([type_code] if type_code and type_code != "none" else [])
    repo = "-".join(parts) + f"-dp-{country}"
    root = Path(dest).resolve() / repo
    if root.exists() and any(root.iterdir()) and not force:
        raise SystemExit(f"govkit: {root} ya existe y no está vacío (usar --force)")
    for d in _baseline_dirs():
        (root / d).mkdir(parents=True, exist_ok=True)
        keep = root / d / ".gitkeep"
        if not any((root / d).iterdir()):
            keep.write_text("", encoding="utf-8")
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "metadata" / "data_product.yaml").write_text(ficha_template(repo, domain, country), encoding="utf-8")
    (root / "README.md").write_text(PC_README.format(repo=repo), encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## [0.1.0] - {_dt.date.today().isoformat()}\n- Estructura inicial.\n",
                                       encoding="utf-8")
    (root / "docs" / "engineering").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "engineering" / "runbook.md").write_text("# Runbook\n\n<COMPLETAR: operación, alertas y "
                                                              "recuperación>\n", encoding="utf-8")
    return root
