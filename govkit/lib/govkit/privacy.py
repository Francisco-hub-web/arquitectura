"""Modo privado: govkit como apoyo LOCAL del desarrollador, sin rastro en el repositorio remoto.

Todo lo que govkit necesita guardar de un repo vive dentro de `.git/` (nunca se versiona ni se sube):
  · `.git/govkit/config.yaml`   configuración y waivers personales (alternativa a `.govkit.yaml`)
  · `.git/govkit/baseline.json` baseline personal (se carga solo)
  · `.git/info/exclude`         ignora localmente cualquier archivo con nombre de govkit
  · `.git/hooks/*`              guardias locales: pre-commit (contenido), commit-msg (mensaje) y pre-push (ramas,
                                mensajes y contenido de los commits a subir) bloquean cualquier mención a govkit.
Los hooks existentes se conservan y se encadenan (`<hook>.pre-govkit`).
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

EXCLUDES = [".govkit.yaml", ".govkit-baseline.json", ".govkit/", "govkit-report.*", "*.govkit.html",
            "*.govkit.json", "*.govkit.sarif"]
EXCLUDE_MARK = "# govkit (herramienta local; no versionar)"
HOOK_MARK = "# govkit-hook"

_CHAIN = 'prev="$0.pre-govkit"\nif [ -x "$prev" ]; then exec "$prev" "$@"; fi\nexit 0\n'

PRE_COMMIT = """#!/bin/sh
# govkit-hook · pre-commit (local, no versionado)
GOVKIT_GUARD={guard}
GOVKIT_LINT={lint}
if [ "$GOVKIT_GUARD" = 1 ]; then
  files=$(git diff --cached --name-only --diff-filter=ACMR | grep -iE '(^|/)[^/]*govkit[^/]*$')
  lines=$(git diff --cached -U0 --no-color --no-ext-diff | grep -v '^+++ ' | grep -i '^+.*govkit' | head -5)
  if [ -n "$files$lines" ]; then
    echo "⛔ Commit bloqueado: incluye rastros de govkit (herramienta local privada)."
    [ -n "$files" ] && printf '   archivo: %s\\n' $files
    [ -n "$lines" ] && printf '%s\\n' "$lines" | sed 's/^/   línea: /'
    echo "   Quita esas menciones o saca los archivos del stage (git restore --staged <archivo>)."
    exit 1
  fi
fi
if [ "$GOVKIT_LINT" = 1 ] && command -v govkit >/dev/null 2>&1; then
  govkit lint . --profile pre-commit --fail-on BLOCKER >/dev/null 2>&1 || {{
    echo "⛔ Commit bloqueado por hallazgos BLOCKER (detalle: govkit lint)"; exit 1; }}
fi
""" + _CHAIN

COMMIT_MSG = """#!/bin/sh
# govkit-hook · commit-msg (local, no versionado)
if grep -v '^#' "$1" | grep -qi govkit; then
  echo "⛔ El mensaje de commit menciona govkit (herramienta local privada): edítalo."
  exit 1
fi
""" + _CHAIN

PRE_PUSH = """#!/bin/sh
# govkit-hook · pre-push (local, no versionado): última barrera antes del GitHub corporativo
z=0000000000000000000000000000000000000000
input=$(cat)
while read -r lref lsha rref rsha; do
  [ -z "$lref" ] && continue
  case "$lref $rref" in *[Gg][Oo][Vv][Kk][Ii][Tt]*)
    echo "⛔ Push bloqueado: la rama/ref '$lref' menciona govkit. Renómbrala (git branch -m)."; exit 1;; esac
  [ "$lsha" = "$z" ] && continue
  if [ "$rsha" = "$z" ]; then range="$lsha --not --remotes"; else range="$rsha..$lsha"; fi
  if git log --format=%B $range | grep -qi govkit; then
    echo "⛔ Push bloqueado: algún mensaje de commit menciona govkit (git rebase -i para editarlo)."; exit 1
  fi
  if git log -p --format= --no-color --no-ext-diff $range | grep -v '^+++ ' | grep -qi '^+.*govkit'; then
    echo "⛔ Push bloqueado: los commits agregan contenido que menciona govkit."; exit 1
  fi
done <<EOF
$input
EOF
prev="$0.pre-govkit"
if [ -x "$prev" ]; then printf '%s\\n' "$input" | "$prev" "$@"; exit $?; fi
exit 0
"""


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_path(root: Path, what: str) -> Optional[Path]:
    """Ruta real dentro del directorio git (respeta worktrees y core.hooksPath)."""
    out = _git(root, "rev-parse", "--git-path", what)
    if not out:
        return None
    p = Path(out)
    return p if p.is_absolute() else (Path(root) / p).resolve()


def private_dir(root: Path) -> Optional[Path]:
    """`.git/govkit/` (o `.git/govkit/<subcarpeta>` si el Data Product es una carpeta de un monorepo)."""
    base = git_path(Path(root), "govkit")
    if base is None:
        return None
    prefix = (_git(Path(root), "rev-parse", "--show-prefix") or "").strip("/")
    return base / prefix.replace("/", "__") if prefix else base


def ensure_excludes(root: Path) -> List[str]:
    """Agrega los patrones de govkit a `.git/info/exclude` (ignorado local, jamás se sube). Idempotente."""
    path = git_path(Path(root), "info/exclude")
    if path is None:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    have = {line.strip() for line in current.splitlines()}
    missing = [p for p in EXCLUDES if p not in have]
    if missing:
        block = ("" if not current or current.endswith("\n") else "\n") + \
            ("" if EXCLUDE_MARK in have else EXCLUDE_MARK + "\n") + "\n".join(missing) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(block)
    return missing


def _flags(text: str) -> Dict[str, str]:
    out = {}
    for key in ("GOVKIT_GUARD", "GOVKIT_LINT"):
        for line in text.splitlines():
            if line.startswith(key + "="):
                out[key] = line.split("=", 1)[1].strip()
    return out


class VersionedHooksError(RuntimeError):
    """core.hooksPath apunta a una carpeta versionada (p.ej. .husky/): escribir ahí se subiría al remoto."""


def hooks_are_private(root: Path) -> bool:
    hooks = git_path(Path(root), "hooks")
    common = _git(Path(root), "rev-parse", "--git-common-dir")
    if hooks is None or common is None:
        return False
    common_p = Path(common) if Path(common).is_absolute() else (Path(root) / common).resolve()
    try:
        hooks.resolve().relative_to(common_p.resolve())
        return True
    except ValueError:
        return False


def _write_hook(root: Path, name: str, body: str) -> Path:
    hook = git_path(Path(root), f"hooks/{name}")
    if hook is None:
        raise SystemExit(f"govkit: {root} no es un repositorio git")
    if not hooks_are_private(root):
        raise VersionedHooksError(str(hook.parent))
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="ignore")
        if HOOK_MARK not in existing and "govkit" not in existing:
            backup = hook.with_name(name + ".pre-govkit")
            if not backup.exists():
                hook.rename(backup)  # se encadena: el hook del equipo sigue corriendo
    hook.write_text(body, encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def install_hooks(root: Path, guard: Optional[bool] = None, lint: Optional[bool] = None) -> List[Path]:
    """Escribe los hooks locales conservando la otra bandera si ya estaba activada."""
    current = git_path(Path(root), "hooks/pre-commit")
    flags = _flags(current.read_text(encoding="utf-8", errors="ignore")) if current and current.exists() else {}
    g = "1" if guard else ("0" if guard is False else flags.get("GOVKIT_GUARD", "0"))
    l_ = "1" if lint else ("0" if lint is False else flags.get("GOVKIT_LINT", "0"))
    hooks = [_write_hook(root, "pre-commit", PRE_COMMIT.format(guard=g, lint=l_))]
    if g == "1":
        hooks.append(_write_hook(root, "commit-msg", COMMIT_MSG))
        hooks.append(_write_hook(root, "pre-push", PRE_PUSH))
    return hooks


CONFIG_TEMPLATE = """# Configuración PERSONAL de govkit para este repo (vive en .git/: nunca se versiona ni se sube).
version: 1
# policies:
#   branching: env-branches        # o trunk
# rules:
#   disable: [GOV-NAM-001]         # reglas que no aplican a tu contexto
#   severity: {GOV-MET-008: HIGH}  # solo endurecer
# waivers:
#   - {rule: GOV-NAM-001, reason: "convención de nombres vigente", owner: tu.email@cencosud.com,
#      adr: "pendiente", expires: 2026-12-31}
"""


def setup(root: Path) -> Dict[str, object]:
    root = Path(root).resolve()
    pdir = private_dir(root)
    if pdir is None:
        raise SystemExit(f"govkit: {root} no es un repositorio git")
    pdir.mkdir(parents=True, exist_ok=True)
    cfg = pdir / "config.yaml"
    if not cfg.exists():
        cfg.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    info: Dict[str, object] = {"private_dir": pdir, "config": cfg, "excludes": ensure_excludes(root), "hooks": []}
    try:
        info["hooks"] = install_hooks(root, guard=True)
    except VersionedHooksError as exc:
        info["hooks_skipped"] = str(exc)
    return info


def check(root: Path) -> List[str]:
    """Rastros de govkit que podrían llegar (o ya llegaron) al remoto."""
    root = Path(root).resolve()
    issues: List[str] = []
    tracked = _git(root, "grep", "-Iil", "govkit", "--", ".")
    if tracked:
        issues += [f"archivo versionado menciona govkit: {f}" for f in tracked.splitlines()]
    names = _git(root, "ls-files", "--full-name", "--", ".") or ""
    issues += [f"archivo versionado con nombre de govkit: {f}" for f in names.splitlines()
               if "govkit" in f.rsplit("/", 1)[-1].lower()]
    staged = _git(root, "diff", "--cached", "--name-only") or ""
    issues += [f"en stage: {f}" for f in staged.splitlines() if "govkit" in f.lower()]
    branches = _git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes") or ""
    issues += [f"rama con nombre de govkit: {b}" for b in branches.splitlines() if "govkit" in b.lower()]
    msgs = _git(root, "log", "--branches", "--not", "--remotes", "--format=%h %s%n%b") or ""
    issues += [f"commit sin subir menciona govkit: {m.strip()[:90]}" for m in msgs.splitlines()
               if "govkit" in m.lower() and m.strip()]
    return issues


def is_git(root: Path) -> bool:
    return _git(Path(root), "rev-parse", "--git-dir") is not None
