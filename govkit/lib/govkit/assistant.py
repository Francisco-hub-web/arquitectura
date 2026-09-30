"""`govkit "texto"`: Claude Code + govkit desde la terminal.

  govkit "¿qué le falta a mi data product?"        # sesión interactiva (puedes seguir conversando)
  govkit -p "¿qué le falta a mi data product?"     # solo la respuesta, con fuentes, guardada como nota
  govkit -p --nota 3 "arma el correo al owner"     # reutiliza la nota 3 como contexto
  govkit -p --sumar 3 "agrega lo del arquitecto"   # usa la nota 3 y le suma la nueva respuesta
  pbpaste | govkit                                  # pega un error de CI, un SQL, un YAML…

Modo `-p`: `claude -p` (sin interfaz ni diálogo de confianza) con herramientas de LECTURA preaprobadas; muestra una
línea de progreso y al final solo la respuesta + «Fuentes para verificar» (resueltas por govkit, no por el LLM).
En ambos modos Claude recibe el MCP `govkit`, el contexto del repo y las reglas de privacidad.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from govkit.paths import KIT_HOME

READONLY = ["mcp__govkit__lint", "mcp__govkit__gate", "mcp__govkit__score", "mcp__govkit__explain_rule",
            "mcp__govkit__search_rules", "mcp__govkit__kb_context", "mcp__govkit__semantic_review_plan",
            "mcp__govkit__verify_semantic_findings", "Bash(govkit lint:*)", "Bash(govkit gate:*)",
            "Bash(govkit score:*)", "Bash(govkit explain:*)", "Bash(govkit rules:*)", "Bash(govkit kb:*)",
            "Bash(govkit fix)", "Bash(govkit privado --check:*)", "Bash(govkit fuentes:*)", "Bash(govkit notas:*)",
            "mcp__govkit__sources", "mcp__govkit__criteria_search", "mcp__govkit__notes_list", "mcp__govkit__notes_get", "mcp__govkit__notes_save",
            "mcp__govkit__notes_append", "mcp__govkit__arch_status", "mcp__govkit__arch_context",
            "mcp__govkit__arch_summary", "mcp__govkit__arch_search", "mcp__govkit__arch_conflicts",
            "mcp__govkit__arch_adrs", "mcp__govkit__arch_dp", "mcp__govkit__arch_relations", "mcp__govkit__arch_facts",
            "mcp__govkit__arch_changes", "mcp__govkit__arch_sync", "Bash(govkit arch:*)"]
DIRECT_EXTRA = ["Read", "Grep", "Glob", "Bash(git status:*)", "Bash(git log:*)", "Bash(git diff:*)",
                "Bash(git branch:*)", "Bash(ls:*)"]
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
0. Preguntas libres (p.ej. «en la reunión dijeron que X, ¿existe ese criterio?»): NO corras `lint`; usa
   `criteria_search` (y `kb_context` con query) y responde con «Veredicto: EXISTE | EXISTE CON MATICES | NO EXISTE |
   CONTRADICE», qué dice exactamente el framework (IDs y cita textual) y en qué difiere de lo escuchado.
1. Si la pregunta es sobre el repo y la carpeta es un Data Product, parte con `lint` y resume por severidad.
2. Si el usuario pega un error, log de CI, SQL, YAML o política IAM: relaciónalo con las reglas (`search_rules`,
   `kb_context` con query) y con los hallazgos de `lint`; propone el cambio exacto (archivo:línea).
3. Nunca inventes valores de negocio (owners, SLA, KPIs, clasificación): pregúntalos.
4. Responde en español, conciso, citando GOV-* y KBnn.Xn.
5. Verificabilidad: todo criterio que cites debe poder revisarse en el framework. Al final de cada respuesta con citas
   agrega «Fuentes para verificar» usando la herramienta `sources` con los IDs citados (documento § sección y cita
   textual). Nunca inventes documentos ni secciones.
6. Notas: si el usuario pide guardar, retomar o sumar algo, usa `notes_save`, `notes_append`, `notes_list`, `notes_get`
   (se guardan fuera del repo, en ~/.govkit/notas).

MEMORIA ARQUITECTÓNICA (govkit arch: governance, platform-core, ArchiMate, metadata-catalog, indexados en local):
7. Si la pregunta es de arquitectura, estándares, una ruta, un componente o "qué cambió": llama primero `arch_context`
   (ruta del repo o `global-…/ruta`) y/o `arch_search`; para cambios `arch_changes` (o `arch_sync` si el usuario pide
   actualizar: hace fetch de refs remotas, nunca pull); contradicciones `arch_conflicts`; decisiones `arch_adrs`;
   diseño aprobado del DP `arch_dp`.
8. Estructura de un análisis: Contexto · Evidencia · Arquitectura esperada · Arquitectura observada · Diferencias ·
   Impacto · Confianza (ALTA/MEDIA/BAJA) · Recomendación técnica (separada de los hechos).
9. Etiqueta cada afirmación arquitectónica: [DOCUMENTADO] [EVIDENCIADO EN CÓDIGO] [INFERIDO] [PROPUESTO] [DESCONOCIDO]
   [CONFLICTIVO], y distingue REQUIRED / APPROVED / RECOMMENDED / IMPLEMENTED / DEPRECATED / UNKNOWN (implementado ≠
   aprobado). Cita la traza `repo@commit:ruta §sección` que devuelven las herramientas.
10. Nunca conviertas una inferencia en regla oficial ni completes vacíos inventando: escribe "NO DETERMINADO" y qué
   evidencia falta. Ante contradicciones, reporta ambas fuentes (CONFLICT DETECTED) sin decidir cuál gana.
11. Nunca hagas `git pull`, checkout, reset ni stash en los repos corporativos; nunca restaures `.github/setup.js`. Si ves
   un secreto: "SECRET DETECTED" con archivo, ruta y tipo, jamás el valor.

PRIVACIDAD (obligatorio): govkit es una herramienta local y privada del usuario.
- Nunca escribas "govkit" ni referencias a él en archivos del repo, comentarios, mensajes de commit, nombres de rama,
  descripciones de PR ni issues. Los cambios deben verse como trabajo normal del usuario sobre el estándar corporativo.
- No crees `.govkit.yaml`, reportes ni archivos de govkit dentro del repo: la configuración personal va en
  `.git/govkit/config.yaml` y los reportes fuera del repo (p.ej. ~/Desktop o /tmp).
- No hagas commit, push ni abras PRs salvo que el usuario lo pida explícitamente.
"""


DIRECT = """
MODO RESPUESTA DIRECTA (no interactivo): el usuario hizo UNA consulta en la terminal y verá solo tu respuesta final.
- Usa primero las herramientas de govkit (lint, gate, kb_context, explain_rule) y lee los archivos que necesites.
- Responde en español, directo y accionable: empieza por la conclusión; luego una lista corta y priorizada
  (BLOCKER/HIGH primero) con archivo:línea y qué poner. Máximo ~30 líneas salvo que pida detalle. Sin tablas anchas.
- No puedes modificar archivos ni pedir confirmaciones en este modo. Da el cambio exacto o el comando
  (p.ej. `govkit fix --apply`), o sugiere `govkit -i "…"` para hacerlo juntos en modo interactivo.
- Si faltan datos de negocio (owners, SLA, KPIs, consumidores), termina con una sección "Necesito de ti:" con preguntas
  concretas.
- Cita siempre los IDs (GOV-*, KBnn.Xn) pero NO escribas la sección de fuentes ni guardes notas: govkit agrega las
  fuentes y guarda la respuesta automáticamente.
"""


def _context(cwd: Path) -> str:
    lines = [f"\n# Contexto de la sesión\n- Carpeta: {cwd}"]
    try:
        from govkit.engine import load_catalog
        from govkit.privacy import git_path, is_git
        from govkit.repo import RepoContext

        ctx = RepoContext(cwd, load_catalog())
        ficha = ctx.dp_file
        lines.append(f"- Repo: {ctx.repo_name} · estándar: {ctx.standard} ({ctx.standard_reason}) · ficha: "
                     f"{ficha or 'NO (' + ctx.expected_dp_file + ')'} · estado evaluado: {ctx.stage}")
        if is_git(cwd):
            hook = git_path(cwd, "hooks/pre-push")
            guarded = bool(hook and hook.exists() and "govkit-hook" in hook.read_text(errors="ignore"))
            lines.append(f"- Modo privado: {'activo (guardias locales instaladas)' if guarded else 'NO activo → sugiere `govkit privado`'}")
    except Exception as exc:  # noqa: BLE001 - el contexto es opcional
        lines.append(f"- (sin contexto de repo: {type(exc).__name__})")
    try:
        from govkit.arch import load_state
        st = load_state()["sources"]
        if st:
            lines.append("- Memoria arquitectónica: " + "; ".join(
                f"{k}@{str(v.get('commit') or '?')[:7]} ({v.get('origin')})" for k, v in sorted(st.items())))
        else:
            lines.append("- Memoria arquitectónica: sin ingerir (sugiere `govkit arch sync` o `govkit arch ingest --snapshot`)")
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines) + "\n"


def _mcp_registered(claude: str) -> bool:
    try:
        return subprocess.run([claude, "mcp", "get", "govkit"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_command(claude: str, prompt: str, cwd: Path, interactive: bool = False,
                  registered: Optional[bool] = None) -> List[str]:
    if prompt.startswith("-"):
        prompt = "Consulta: " + prompt  # que el CLI no lo interprete como opción
    cmd = [claude] + ([] if interactive else ["-p"]) + [prompt]  # posicional ANTES de opciones variádicas
    if not (registered if registered is not None else _mcp_registered(claude)):
        exe = str(KIT_HOME / "bin" / "govkit")
        cmd += ["--mcp-config", json.dumps({"mcpServers": {"govkit": {"command": exe, "args": ["mcp"]}}})]
    cmd += ["--append-system-prompt", GUIDE + ("" if interactive else DIRECT) + _context(cwd)]
    if not interactive:
        cmd += ["--output-format", "stream-json", "--verbose"]
    tools = READONLY if interactive else [t for t in READONLY + DIRECT_EXTRA if not t.startswith("mcp__govkit__notes_s")
                                          and not t.endswith("notes_append")]  # en -p govkit guarda la nota
    return cmd + ["--allowedTools", ",".join(tools)]  # último: la opción variádica no se traga nada


# ------------------------------------------------------------------ salida en terminal
def _style(on: bool):
    def s(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if on else text
    return s


def render(md: str, color: bool) -> str:
    """Markdown mínimo → terminal: títulos en negrita, **negrita**, `código` y viñetas; sin símbolos sueltos."""
    st = _style(color)
    out, in_code = [], False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append("    " + st("2", line))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            title = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(2))
            out.append(st("1;36" if len(m.group(1)) <= 2 else "1", title))
            continue
        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            out.append(st("2", "─" * 40))
            continue
        line = re.sub(r"^(\s*)[-*] ", r"\1• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", lambda mm: st("1", mm.group(1)), line)
        line = re.sub(r"`([^`]+)`", lambda mm: st("36", mm.group(1)), line)
        out.append(line)
    return "\n".join(out).strip() + "\n"


TOOL_LABEL = {"lint": "validando el repo", "gate": "evaluando el gate", "score": "calculando el score",
              "fix": "planificando correcciones", "explain_rule": "explicando regla", "search_rules": "buscando reglas",
              "kb_context": "consultando el framework", "semantic_review_plan": "preparando revisión",
              "verify_semantic_findings": "verificando hallazgos", "Read": "leyendo", "Grep": "buscando en el código",
              "Glob": "listando archivos", "Bash": "ejecutando"}


def _label(block: dict) -> str:
    name = str(block.get("name", ""))
    short = name.split("__")[-1]
    inp = block.get("input") or {}
    extra = inp.get("file_path") or inp.get("pattern") or inp.get("command") or inp.get("rule_id") or ""
    extra = os.path.basename(str(extra)) if block.get("name") == "Read" else str(extra)
    return (TOOL_LABEL.get(short, short) + (f" {extra[:40]}" if extra else "")).strip()


def run_direct(cmd: List[str], cwd: Path) -> Tuple[int, Optional[str]]:
    """Ejecuta `claude -p … --output-format stream-json`: progreso en una línea (stderr); devuelve la respuesta final."""
    tty_err = sys.stderr.isatty()
    t0, steps, final, error, raw = time.time(), [], None, None, []

    def status(msg: str) -> None:
        if tty_err:
            sys.stderr.write("\r\033[2K\033[2m⏳ " + msg[:100] + "\033[0m")
            sys.stderr.flush()

    status("consultando… (Ctrl+C para cancelar)")
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace")
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                raw.append(line)
                continue
            if ev.get("type") == "assistant":
                for block in (ev.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        steps.append(_label(block))
                        status(f"{steps[-1]}… ({int(time.time() - t0)} s)")
            elif ev.get("type") == "result":
                final = ev.get("result")
                if ev.get("is_error") or ev.get("subtype") not in (None, "success"):
                    error = final or ev.get("subtype") or "error"
        rc = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        if tty_err:
            sys.stderr.write("\r\033[2K")
        return 130, None
    if tty_err:
        sys.stderr.write("\r\033[2K")
        sys.stderr.flush()
    if error:
        print(f"govkit: Claude Code no pudo completar la consulta: {error}", file=sys.stderr)
        return 1, None
    if final is None:  # versión de Claude Code sin stream-json: usar lo que haya
        text = "".join(raw).strip()
        return (rc or (0 if text else 1)), (text or None)
    return 0, final


def launch(prompt: str, interactive: bool = True, cwd: Optional[Path] = None, note_ids: Optional[List[int]] = None,
           sumar: Optional[int] = None, guardar: bool = True) -> int:
    from govkit import notes, sources

    cwd = Path(cwd or os.getcwd()).resolve()
    claude = os.environ.get("GOVKIT_CLAUDE") or shutil.which("claude")
    if not claude:
        print("govkit: no encontré Claude Code (`claude`). Instálalo: https://claude.com/claude-code\n"
              "        Mientras tanto: govkit ask \"tu pregunta\" (KB local + Ollama) o govkit lint.", file=sys.stderr)
        return 2
    ids = list(note_ids or []) + ([sumar] if sumar else [])
    missing = [i for i in ids if not notes.get(i)]
    if missing:
        print(f"govkit: no existe la nota {missing[0]} (govkit notas para ver la lista)", file=sys.stderr)
        return 2
    full = notes.as_context(ids) + prompt
    if interactive:
        cmd = build_command(claude, full, cwd, True)
        stdin = None
        if not sys.stdin.isatty():
            try:
                stdin = open("/dev/tty")  # el texto vino por tubería: la sesión interactiva necesita el teclado
            except OSError:
                interactive = False
        if interactive:
            try:
                return subprocess.call(cmd, cwd=str(cwd), stdin=stdin)
            finally:
                if stdin:
                    stdin.close()
    rc, answer = run_direct(build_command(claude, full, cwd, False), cwd)
    if not answer:
        return rc or 1
    block = sources.render(sources.resolve_all(sources.extract_ids(answer)))
    text = answer.strip() + ("\n\n" + block if block else "\n")
    sys.stdout.write(render(text, sys.stdout.isatty() and not os.environ.get("NO_COLOR")))
    note = None
    if sumar:
        note = notes.append(sumar, prompt, text)
    elif guardar:
        note = notes.save(prompt, text, repo=cwd.name, folder=str(cwd))
    if note:
        dim = sys.stderr.isatty() and not os.environ.get("NO_COLOR")
        msg = (f"💾 {'sumada a la' if sumar else 'guardada como'} nota #{note['id']} · govkit notas ver {note['id']} · "
               f'govkit -p --sumar {note["id"]} "…"')
        print(("\033[2m" + msg + "\033[0m") if dim else msg, file=sys.stderr)
    return rc
