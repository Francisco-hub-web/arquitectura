"""Resolución de rutas del kit y carga de YAML (con fallback al PyYAML vendorizado)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

KIT_HOME = Path(__file__).resolve().parents[2]
RULES_DIR = KIT_HOME / "rules"
REGISTRY_DIR = RULES_DIR / "registry"
SCHEMAS_DIR = KIT_HOME / "schemas"
KB_DIR = KIT_HOME / "kb"
TEMPLATES_DIR = KIT_HOME / "templates"
DOCS_DIR = KIT_HOME / "docs"

try:  # PyYAML del sistema (con libyaml si existe) tiene prioridad sobre el vendorizado
    import yaml  # noqa: F401
except ImportError:  # pragma: no cover - depende del entorno
    sys.path.append(str(KIT_HOME / "vendor"))
    import yaml  # noqa: F401

SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def load_yaml_file(path: os.PathLike) -> object:
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=SafeLoader)


def registry(name: str) -> dict:
    """Carga un registro corporativo (dominios, tags, métricas, cuentas...)."""
    data = load_yaml_file(REGISTRY_DIR / f"{name}.yaml")
    return data or {}
