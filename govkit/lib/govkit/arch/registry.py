"""Registro de fuentes arquitectónicas (rules/registry/arch_sources.yaml + rutas locales del usuario)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from govkit.arch import home
from govkit.paths import REGISTRY_DIR, load_yaml_file, yaml
from govkit.repo import glob_to_regex


@lru_cache(maxsize=1024)
def _rx(pattern: str):
    return glob_to_regex(pattern)


def gmatch(pattern: str, path: str) -> bool:
    return bool(_rx(pattern).match(path))


@dataclass
class Source:
    id: str
    repo: str
    short: str
    role: str
    branch: str = "main"
    default_path: str = ""
    main_status: str = "OFFICIAL"
    kinds: List[Dict[str, str]] = field(default_factory=list)
    impact: List[Dict[str, str]] = field(default_factory=list)
    signal_branches: List[str] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        override = (user_config().get("paths") or {}).get(self.id) or os.environ.get(
            "GOVKIT_ARCH_PATH_" + self.id.upper().replace("-", "_"))
        return Path(os.path.expanduser(override or self.default_path or f"~/{self.repo}"))

    def classify(self, rel: str) -> Tuple[str, int]:
        """(tipo, autoridad) de un archivo según los globs del registro."""
        for k in self.kinds:
            if gmatch(k["glob"], rel):
                kind = k["kind"]
                return kind, hierarchy().get(kind, 9)
        name = rel.rsplit("/", 1)[-1].lower()
        kind = "repo_doc" if name.endswith(".md") else "code" if name.endswith((".py", ".sh", ".js")) else "asset"
        return kind, hierarchy().get(kind, 9)

    def impact_for(self, rel: str) -> Tuple[str, str]:
        for i in self.impact:
            if gmatch(i["glob"], rel) or gmatch(i["glob"], rel.rstrip("/") + "/_"):
                return i["level"], i.get("why", "")
        return "LOW", "archivo sin clasificación de impacto"

    def is_signal_branch(self, name: str) -> bool:
        pats = self.signal_branches or _raw().get("signal_branches") or []
        return any(gmatch(p, name) for p in pats)


@lru_cache(maxsize=1)
def _raw() -> Dict[str, Any]:
    return load_yaml_file(REGISTRY_DIR / "arch_sources.yaml") or {}


def hierarchy() -> Dict[str, int]:
    return dict(_raw().get("hierarchy") or {})


def user_config() -> Dict[str, Any]:
    p = home() / "config.yaml"
    if not p.exists():
        return {}
    try:
        return load_yaml_file(p) or {}
    except Exception:  # noqa: BLE001 - config corrupta: se ignora y se informa en `arch status`
        return {}


def set_path(source_id: str, path: str) -> Path:
    src = get(source_id)
    cfg = user_config()
    cfg.setdefault("paths", {})[src.id] = str(Path(os.path.expanduser(path)).resolve())
    p = home() / "config.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=True), encoding="utf-8")
    return p


def sources() -> Dict[str, Source]:
    out: Dict[str, Source] = {}
    for s in _raw().get("sources") or []:
        out[s["id"]] = Source(id=s["id"], repo=s["repo"], short=s.get("short", s["id"][:3].upper()),
                              role=s.get("role", ""), branch=s.get("branch", "main"),
                              default_path=s.get("default_path", ""), main_status=s.get("main_status", "OFFICIAL"),
                              kinds=s.get("kinds") or [], impact=s.get("impact") or [],
                              signal_branches=s.get("signal_branches") or [], documents=s.get("documents") or [],
                              raw=s)
    return out


def get(name: str) -> Source:
    """Acepta id (`platform-core`), nombre del repo (`global-data-platform-core`) o sigla (`PC`)."""
    found = find(name)
    if not found:
        valid = ", ".join(f"{s.id} ({s.short})" for s in sources().values())
        raise KeyError(f"Fuente desconocida `{name}`. Válidas: {valid}")
    return found


def find(name: Optional[str]) -> Optional[Source]:
    if not name:
        return None
    key = name.strip().rstrip("/").lower()
    for s in sources().values():
        if key in (s.id.lower(), s.repo.lower(), s.short.lower()):
            return s
    return None


def source_for_path(abs_path: Path) -> Optional[Tuple[Source, str]]:
    """Si `abs_path` está dentro del clon local de una fuente → (fuente, ruta relativa)."""
    try:
        target = abs_path.resolve()
    except OSError:
        return None
    for s in sources().values():
        try:
            root = s.path.resolve()
        except OSError:
            continue
        if target == root or root in target.parents:
            rel = target.relative_to(root).as_posix()
            return s, "" if rel == "." else rel
    return None
