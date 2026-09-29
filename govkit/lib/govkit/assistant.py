"""`govkit "texto"`: abre Claude Code en la carpeta actual, ya instruido para usar govkit.

  govkit "revisa este repo y dime qué me falta para producción"
  pbpaste | govkit                      # pega un error de CI, un SQL, un YAML…
  govkit -p "¿qué exige el gate?"       # respuesta directa sin sesión interactiva

Claude recibe: el servidor MCP `govkit` (si no está registrado se inyecta con --mcp-config), permiso previo para
las herramientas de solo lectura (lint, gate, score, KB…), el contexto del repo y las reglas de privacidad:
govkit es una herramienta local y nunca debe aparecer en archivos, commits, ramas ni PRs.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from govkit.paths import KIT_HOME

READONLY = ["mcp__govkit__lint", "mcp__govkit__gate", "mcp__govkit__score", "mcp__govkit__explain_rule",
            "mcp__govkit__search_rules", "mcp__govkit__kb_context", "mcp__govkit__semantic_review_plan",
            "mcp__govkit__verify_semantic_findings", "Bash(govkit lint:*)", "Bash(govkit gate:*)",
            "Bash(govkit score:*)", "Bash(govkit explain:*)", "Bash(govkit rules:*)", "Bash(govkit kb:*)",
            "Bash(govkit fix)", "Bash(govkit privado --check:*)"]

GUIDE = """# govkit (gobierno de datos Cencosud) — herramienta LOCAL del usuario
Tienes el servidor MCP `govkit` con el Data & AI Discipline Framework como reglas ejecutables:
- `lint` / `gate` / `score`: hallazgos deterministas (regla GOV-*, archivo:línea, remediación). Son la fuente de verdad.
- `fix` (apply=false primero; muestra el plan al usuario antes de apply=true): remediaciones mecánicas seguras.
- `explain_rule`, `search_rules`: trazabilidad de reglas. `kb_context` (task/query/files/rule_ids): contexto normativo
  mínimo; cita los IDs KBnn.Xn. `semantic_review_plan` + `verify_semantic_findings`: revisión semántica verificada
  (reporta solo lo que el verificador conserve; es consultivo).
Si el MCP no responde, usa el CLI por Bash: `govkit lint --format json`, `govkit gate --to <estado>`, `govkit explain <regla>`,
`govkit kb pack -q "<consulta>"`.

Cómo trabajar:
1. Si la carpeta es un repo de Data Product, parte con `lint` y resume por severidad (BLOCKER/HIGH primero).
2. Si el usuario pega un error, log de CI, SQL, YAML o política IAM: relaciónalo con las reglas (`search_rules`,
   `kb_context` con query) y con los hallazgos de `lint`; propone el cambio exacto (archivo:línea).
3. Nunca inventes valores de negocio (owners, SLA, KPIs, clasificación): pregúntalos.
4. Responde en español, conciso, citando GOV-* y KBnn.Xn.

PRIVACIDAD (obligatorio): govkit es una herramienta local y privada del usuario.
- Nunca escribas "govkit" ni referencias a él en archivos del repo, comentarios, mensajes de commit, nombres de rama,
  descripciones de PR ni issues. Los cambios deben verse como trabajo normal del usuario sobre el estándar corporativo.
- No crees `.govkit.yaml`, reportes ni archivos de govkit dentro del repo: la configuración personal va en
  `.git/govkit/config.yaml` y los reportes fuera del repo (p.ej. ~/Desktop o /tmp).
- No hagas commit, push ni abras PRs salvo que el usuario lo pida explícitamente.
"""


def _context(cwd: Path) -> str:
    lines = [f"\n# Contexto de la sesión\n- Carpeta: {cwd}"]
    try:
        from govkit.engine import load_catalog
        from govkit.privacy import git_path, is_git
        from govkit.repo import RepoContext

        ctx = RepoContext(cwd, load_catalog())
        has_dp = ctx.dp is not None
        lines.append(f"- Repo: {ctx.repo_name} · ficha del Data Product: {'sí' if has_dp else 'NO (metadata/catalog/data_product.yaml)'}"
                     f" · estado evaluado: {ctx.stage}")
        if is_git(cwd):
            hook = git_path(cwd, "hooks/pre-push")
            guarded = bool(hook and hook.exists() and "govkit-hook" in hook.read_text(errors="ignore"))
            lines.append(f"- Modo privado: {'activo (guardias locales instaladas)' if guarded else 'NO activo → sugiere `govkit privado`'}")
    except Exception as exc:  # noqa: BLE001 - el contexto es opcional
        lines.append(f"- (sin contexto de repo: {type(exc).__name__})")
    return "\n".join(lines) + "\n"


def _mcp_registered(claude: str) -> bool:
    try:
        return subprocess.run([claude, "mcp", "get", "govkit"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_command(claude: str, prompt: str, cwd: Path, print_mode: bool = False,
                  registered: Optional[bool] = None) -> List[str]:
    if prompt.startswith("-"):
        prompt = "Consulta: " + prompt  # que el CLI no lo interprete como opción
    cmd = [claude]
    if print_mode:
        cmd.append("-p")
    cmd.append(prompt)  # posicional ANTES de las opciones variádicas (--mcp-config, --allowedTools)
    if not (registered if registered is not None else _mcp_registered(claude)):
        exe = str(KIT_HOME / "bin" / "govkit")
        cmd += ["--mcp-config", json.dumps({"mcpServers": {"govkit": {"command": exe, "args": ["mcp"]}}})]
    cmd += ["--append-system-prompt", GUIDE + _context(cwd), "--allowedTools", ",".join(READONLY)]
    return cmd


def launch(prompt: str, print_mode: bool = False, cwd: Optional[Path] = None) -> int:
    cwd = Path(cwd or os.getcwd()).resolve()
    claude = os.environ.get("GOVKIT_CLAUDE") or shutil.which("claude")
    if not claude:
        print("govkit: no encontré Claude Code (`claude`). Instálalo: https://claude.com/claude-code\n"
              "        Mientras tanto: govkit ask \"tu pregunta\" (KB local + Ollama) o govkit lint.", file=sys.stderr)
        return 2
    cmd = build_command(claude, prompt, cwd, print_mode)
    stdin = None
    if not sys.stdin.isatty() and not print_mode:
        try:
            stdin = open("/dev/tty")  # el texto vino por tubería: la sesión interactiva necesita el teclado
        except OSError:
            cmd.insert(1, "-p")
    try:
        return subprocess.call(cmd, cwd=str(cwd), stdin=stdin)
    finally:
        if stdin:
            stdin.close()
