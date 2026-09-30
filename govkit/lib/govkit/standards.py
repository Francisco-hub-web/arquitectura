"""Estándar normativo aplicable a un repo de Data Product (ADR-009).

  · platform-core → estándar ejecutable de global-data-platform-core (ODCS v3.1.0 + perfil xCencosud, carpetas
    medallion, ficha metadata/data_product.yaml). Reglas GOV-PCX-*.
  · lineamientos  → lineamiento "Estructura de Repositorio" + ficha govkit (metadata/catalog/data_product.yaml).
`auto` (por defecto) lo detecta por marcadores del repo; se puede fijar con `standard:` en la config o `--estandar`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

STANDARDS = ("platform-core", "lineamientos")
PC_MARKERS = ("contracts/_schema/profile-manifest.yaml", "contracts/_schema/cencosud-odcs-minimal.schema.json",
              "contracts/_schema/data-contracts-architecture-standard.yaml")
_ODCS = re.compile(r"^apiVersion:\s*['\"]?v3\.", re.M)
_KIND = re.compile(r"^kind:\s*['\"]?DataContract", re.M)


def detect(root: Path, configured: Optional[str] = None) -> Tuple[str, str]:
    """→ (estándar, motivo)."""
    if configured and configured != "auto":
        if configured not in STANDARDS:
            raise ValueError(f"estándar desconocido `{configured}` (válidos: auto, {', '.join(STANDARDS)})")
        return configured, "fijado en la configuración"
    for m in PC_MARKERS:
        if (root / m).is_file():
            return "platform-core", f"existe `{m}` (copia del estándar platform-core)"
    if (root / "metadata" / "data_product.yaml").is_file() and not (root / "metadata" / "catalog").is_dir():
        return "platform-core", "ficha en `metadata/data_product.yaml` (baseline platform-core)"
    contracts = root / "contracts"
    if contracts.is_dir():
        for i, p in enumerate(sorted(contracts.rglob("*.y*ml"))):
            if i > 60:
                break
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:2000]
            except OSError:
                continue
            if _ODCS.search(head) and _KIND.search(head):
                return "platform-core", f"contrato ODCS v3 en `{p.relative_to(root).as_posix()}`"
    return "lineamientos", "sin marcadores del estándar platform-core"
