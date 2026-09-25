"""Contexto de un repositorio de Data Product: descubrimiento, artefactos, git y configuración."""
from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from govkit.paths import load_yaml_file, registry
from govkit.yamlloc import Doc, dig, parse_text

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "target", "dbt_packages",
                "logs", ".idea", ".vscode", ".pytest_cache", ".mypy_cache", "dist", "build"}
TEXT_EXT = {".py", ".sql", ".yml", ".yaml", ".json", ".md", ".txt", ".cfg", ".ini", ".toml", ".sh",
            ".tf", ".tfvars", ".csv", ".lkml", ".dax", ".tmdl", ".bim", ".env", ".properties", ".conf", ".js",
            ".dbml", ".asl", ""}
MAX_TEXT_BYTES = 2_000_000

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "pack": "dp",
    "policies": {
        "branching": "env-branches",  # env-branches (Estructura de Repositorio) | trunk (15-dataops-cicd §15)
        "protected_branches": ["main", "staging", "develop"],
        "allowed_email_domains": ["cencosud.com", "cencosud.cl", "cencosud.com.pe", "cencosud.com.co",
                                  "cencosud.com.br", "cencosud.com.ar"],
        "codeowners": {"architects": r"(?i)architect", "tech_leaders": r"(?i)tech[-_]?lead"},
        "allowed_extra_top_level": ["infra", "config", "scripts", "artifacts", "notebooks_sandbox"],
        "trust_services": ["glue.amazonaws.com", "lakeformation.amazonaws.com"],
        "iam_region": "us-east-1",
        "metadata_max_age_days": 180,
        "scorecard_max_age_days": 100,
        "inactivity_days": 60,
    },
    "artifacts": {},
    "rules": {"disable": [], "severity": {}},
    "waivers": [],
}


def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    i, out = 0, ""
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        out += {"*": "[^/]*", "?": "[^/]"}.get(c, re.escape(c))
        i += 1
    return re.compile(f"^{out}$")


@lru_cache(maxsize=512)
def _glob_re(pattern: str) -> "re.Pattern[str]":
    return glob_to_regex(pattern)


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class RepoContext:
    def __init__(self, root: os.PathLike, catalog: Dict[str, Any], stage_override: Optional[str] = None,
                 base_ref: Optional[str] = None, today: Optional[_dt.date] = None):
        self.root = Path(root).resolve()
        self.catalog = catalog
        self.base_ref = base_ref
        self.today = today or _dt.date.today()
        cfg_path = self.root / ".govkit.yaml"
        user_cfg = load_yaml_file(cfg_path) if cfg_path.exists() else {}
        self.config = _deep_merge(DEFAULT_CONFIG, user_cfg or {})
        self.config_path = ".govkit.yaml" if cfg_path.exists() else None
        self.artifact_globs: Dict[str, List[str]] = dict(catalog.get("artifacts", {}))
        self.artifact_globs.update(self.config.get("artifacts") or {})
        self.lifecycle = registry("lifecycle")
        self._files: Optional[List[str]] = None
        self._text: Dict[str, Optional[str]] = {}
        self._docs: Dict[str, Doc] = {}
        self._stage_override = stage_override
        self.cache: Dict[str, Any] = {}  # memo compartido entre plugins

    # ------------------------------------------------------------------ archivos
    @property
    def files(self) -> List[str]:
        if self._files is None:
            found: List[str] = []
            for dirpath, dirnames, filenames in os.walk(self.root):
                dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
                rel_dir = os.path.relpath(dirpath, self.root)
                for name in sorted(filenames):
                    rel = name if rel_dir == "." else f"{rel_dir}/{name}"
                    found.append(rel.replace(os.sep, "/"))
            self._files = found
        return self._files

    def dirs(self) -> List[str]:
        out = set()
        for dirpath, dirnames, _ in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            rel = os.path.relpath(dirpath, self.root).replace(os.sep, "/")
            if rel != ".":
                out.add(rel)
        return sorted(out)

    def glob(self, patterns: Any, exclude: Any = None) -> List[str]:
        pats = [patterns] if isinstance(patterns, str) else list(patterns or [])
        excl = [exclude] if isinstance(exclude, str) else list(exclude or [])
        res = [f for f in self.files if any(_glob_re(p).match(f) for p in pats)]
        return [f for f in res if not any(_glob_re(e).match(f) for e in excl)]

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def is_dir(self, rel: str) -> bool:
        return (self.root / rel).is_dir()

    def dir_has_files(self, rel: str, patterns: Any = "**") -> bool:
        prefix = rel.rstrip("/") + "/"
        return any(f.startswith(prefix) and not f.endswith(".gitkeep") for f in self.glob(
            [prefix + p for p in ([patterns] if isinstance(patterns, str) else patterns)]))

    def text(self, rel: str) -> Optional[str]:
        if rel not in self._text:
            p = self.root / rel
            try:
                if p.stat().st_size > MAX_TEXT_BYTES:
                    self._text[rel] = None
                else:
                    self._text[rel] = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                self._text[rel] = None
        return self._text[rel]

    def text_files(self, patterns: Any = "**", exclude: Any = None) -> List[str]:
        return [f for f in self.glob(patterns, exclude) if Path(f).suffix.lower() in TEXT_EXT]

    def doc(self, rel: str) -> Doc:
        if rel not in self._docs:
            self._docs[rel] = parse_text(rel, self.text(rel) or "")
        return self._docs[rel]

    # ------------------------------------------------------------------ artefactos
    def artifact(self, name: str) -> List[Doc]:
        globs = self.artifact_globs.get(name)
        if globs is None:
            raise KeyError(f"Artefacto lógico desconocido: {name}")
        return [self.doc(f) for f in self.glob(globs)]

    @property
    def dp(self) -> Optional[Doc]:
        docs = self.artifact("data_product")
        return docs[0] if docs else None

    def dp_get(self, path: str, default: Any = None) -> Any:
        dp = self.dp
        if dp is None or not isinstance(dp.data, dict):
            return default
        found, value = dig(dp.data, path)
        return value if found else default

    # ------------------------------------------------------------------ ciclo de vida
    @property
    def stage(self) -> str:
        if self._stage_override:
            return self._stage_override
        state = self.dp_get("spec.lifecycle.state")
        return state if state in self.lifecycle.get("states", {}) else self.lifecycle.get("default_state", "en_desarrollo")

    @property
    def stage_group(self) -> str:
        return self.lifecycle["states"].get(self.stage, {}).get("group", "desarrollo")

    def stage_rank(self, state: Optional[str] = None) -> int:
        return self.lifecycle["states"].get(state or self.stage, {}).get("order", 0)

    # ------------------------------------------------------------------ identidad
    @property
    def repo_name(self) -> str:
        if self.config.get("repo_name"):
            return self.config["repo_name"]
        url = self.git("config", "--get", "remote.origin.url")
        if url:
            name = url.strip().rstrip("/").split("/")[-1]
            return name[:-4] if name.endswith(".git") else name
        return self.root.name

    @property
    def policies(self) -> Dict[str, Any]:
        return self.config["policies"]

    # ------------------------------------------------------------------ git
    def git(self, *args: str) -> Optional[str]:
        try:
            out = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout if out.returncode == 0 else None

    @property
    def is_git(self) -> bool:
        return self.git("rev-parse", "--is-inside-work-tree") is not None

    def changed_files(self) -> Optional[List[str]]:
        if not self.base_ref:
            return None
        # commits del PR (merge-base…HEAD) ∪ cambios sin commitear ∪ archivos nuevos no rastreados
        parts = [self.git("diff", "--name-only", f"{self.base_ref}...HEAD") or "",
                 self.git("diff", "--name-only", "HEAD") or "",
                 self.git("ls-files", "--others", "--exclude-standard") or ""]
        seen: List[str] = []
        for line in "\n".join(parts).splitlines():
            if line.strip() and line.strip() not in seen:
                seen.append(line.strip())
        return seen

    def base_text(self, rel: str) -> Optional[str]:
        if not self.base_ref:
            return None
        return self.git("show", f"{self.base_ref}:{rel}")

    def current_branch(self) -> Optional[str]:
        env = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GOVKIT_BRANCH")
        if env:
            return env
        out = self.git("rev-parse", "--abbrev-ref", "HEAD")
        return out.strip() if out and out.strip() != "HEAD" else None

    def commit_messages(self) -> List[str]:
        if not self.base_ref:
            return []
        out = self.git("log", "--format=%s", f"{self.base_ref}..HEAD")
        return [l for l in (out or "").splitlines() if l.strip()]
