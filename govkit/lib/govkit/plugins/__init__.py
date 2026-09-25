"""Registro de plugins: checks que requieren lógica (AST, grafo, diff, políticas IAM...)."""
from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Iterable, Optional

from govkit.model import Finding, Location
from govkit.yamlloc import Doc

PLUGINS: Dict[str, Callable[..., Iterable[Finding]]] = {}
_MODULES = ("structure", "business", "naming", "product", "contracts", "metadata", "quality", "security", "iam",
            "sql", "pyjobs", "semantic", "consumption", "observability", "aiml", "lifecycle",
            "scoring_rules", "dataops", "omd", "docs", "portfolio")
_loaded = False


def plugin(name: str, needs_dp: bool = False):
    """Registra un check. `needs_dp=True`: no aplica si el repo aún no tiene ficha de Data Product."""
    def deco(fn):
        fn.needs_dp = needs_dp
        PLUGINS[name] = fn
        return fn
    return deco


def load_all() -> None:
    global _loaded
    if not _loaded:
        for mod in _MODULES:
            importlib.import_module(f"govkit.plugins.{mod}")
        _loaded = True


def at(doc: Doc, path: Optional[str], message: str, severity: Optional[str] = None,
       fix: Optional[Dict[str, Any]] = None, **evidence: Any) -> Finding:
    line, col = doc.pos(path)
    evidence.setdefault("key", path or doc.path)
    return Finding(message, Location(doc.path, line, col, path), evidence=evidence, fix=fix, severity=severity)


def at_file(rel: str, message: str, line: int = 1, col: int = 1, severity: Optional[str] = None,
            fix: Optional[Dict[str, Any]] = None, **evidence: Any) -> Finding:
    evidence.setdefault("key", f"{rel}:{line}")
    return Finding(message, Location(rel, line, col), evidence=evidence, fix=fix, severity=severity)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1
