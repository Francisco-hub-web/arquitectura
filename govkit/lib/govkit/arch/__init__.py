"""Capa de memoria arquitectónica (`govkit arch`, ADR-008).

Convierte los repositorios corporativos de arquitectura (governance, platform-core, ArchiMate, metadata-catalog) en
conocimiento operacional, trazable y actualizado:
  · índice por repo@commit (archivos, secciones, estado normativo, referencias) leído en SOLO LECTURA (git o snapshot);
  · mapa de contexto "qué debo mirar si analizo esta ruta" y mini-resúmenes por unidad arquitectónica;
  · detección incremental de cambios (NEW/UPDATED/DEPRECATED/CONFLICTING/UNKNOWN) con impacto y alertas;
  · hechos verificables, contradicciones (CONFLICT DETECTED), inventario de ADR y Potential ADR;
  · diseño ArchiMate aprobado vs implementación del Data Product.

Todo el estado generado vive fuera de cualquier repositorio: ~/.govkit/arch (o $GOVKIT_ARCH_HOME).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any, Dict

EPISTEMIC = {
    "DOC": "DOCUMENTADO",
    "COD": "EVIDENCIADO EN CÓDIGO",
    "INF": "INFERIDO",
    "PROP": "PROPUESTO",
    "DESC": "DESCONOCIDO",
    "CONF": "CONFLICTIVO",
}
NORMATIVE = ("REQUIRED", "APPROVED", "RECOMMENDED", "IMPLEMENTED", "DEPRECATED", "UNKNOWN")
IMPACT = ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
IMPACT_RANK = {k: i for i, k in enumerate(IMPACT)}
CHANGE_TYPES = ("NEW", "UPDATED", "DEPRECATED", "CONFLICTING", "UNKNOWN")
NOT_DETERMINED = "NO DETERMINADO"


def home() -> Path:
    """Directorio de estado local de la capa (nunca dentro de un repo)."""
    return Path(os.environ.get("GOVKIT_ARCH_HOME") or (Path.home() / ".govkit" / "arch")).expanduser()


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _state_path() -> Path:
    return home() / "state.json"


def load_state() -> Dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {"version": 1, "sources": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "sources": {}}
    data.setdefault("sources", {})
    return data


def save_state(state: Dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def max_impact(a: str, b: str) -> str:
    return a if IMPACT_RANK.get(a, 0) >= IMPACT_RANK.get(b, 0) else b
