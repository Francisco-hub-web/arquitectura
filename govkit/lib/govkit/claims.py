"""`govkit verificar "lo que escuché"`: ¿existe ese criterio en el Data & AI Discipline Framework?

1. Recuperación determinista (BM25, sin LLM): los criterios KB (reglas, heurísticas y anti-patrones) y las reglas GOV-*
   más cercanos a la afirmación, cada uno con documento § sección y cita.
2. Veredicto del LLM (Claude Code, no interactivo) restringido a esa evidencia: EXISTE · EXISTE CON MATICES ·
   NO EXISTE · CONTRADICE.
3. Control determinista de la salida: fuentes resueltas por govkit y alerta si el LLM cita IDs que no existen.
Sin Claude Code (o con --sin-ia) se muestran solo los criterios más cercanos para que el usuario juzgue.
"""
from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from govkit import sources
from govkit.kb.bm25 import BM25

LETTERS = ("R", "H", "A")  # reglas canónicas, heurísticas y anti-patrones (no preguntas ni ejemplos)

CLAIM_GUIDE = """# Verificación de una afirmación contra el Data & AI Discipline Framework (Cencosud)
El usuario escuchó algo (p.ej. en una reunión) y quiere saber si ese criterio EXISTE en el framework.
Tienes CANDIDATOS recuperados por búsqueda determinista (con ID, texto y fuente). Puedes buscar más con las
herramientas `kb_context` (query) y `search_rules`, y resolver fuentes con `sources`. No corras `lint` ni leas el repo.

Responde en español, con este formato exacto:
Veredicto: <EXISTE | EXISTE CON MATICES | NO EXISTE | CONTRADICE> — <una línea>
Qué dice el framework: 2-5 viñetas, cada una con el ID (KBnn.Xn o GOV-XXX-NNN) y lo que exige, citando textual lo clave.
Diferencias con lo que escuchaste: qué parte de la afirmación no está respaldada, está exagerada o es distinta
(p.ej. obligatorio vs recomendado, umbrales, alcance). Si todo coincide, dilo en una línea.
Para confirmar: a quién o qué documento consultar si hay ambigüedad (solo si aplica).

Reglas: usa SOLO IDs que existan (los candidatos o los que devuelvan las herramientas); nunca inventes criterios,
números ni documentos. [PRÁCTICA] y SHOULD no son obligatorios: dilo. Si ningún candidato respalda la afirmación,
el veredicto es NO EXISTE (menciona el criterio más cercano si ayuda). No escribas la sección de fuentes: govkit la agrega.
"""


# Sinónimos frecuentes en conversaciones de datos (español/inglés) para acercar lo escuchado al vocabulario del
# framework; la búsqueda sigue siendo léxica y determinista.
SYNONYMS = {
    "columna": "campo field schema", "columnas": "campos fields schema", "mayor": "major", "menor": "minor",
    "elimina": "eliminar breaking", "eliminar": "breaking", "borrar": "eliminar delete breaking",
    "comodin": "wildcard", "wildcard": "comodin", "dueno": "owner", "responsable": "owner",
    "correo": "buzon", "mail": "buzon", "email": "buzon", "tabla": "dataset", "tablero": "dashboard consumo",
    "dashboard": "tablero consumo", "cambio": "change", "cambiar": "change", "pii": "personal sensible", "personales": "pii sensible",
    "obligatorio": "must", "recomendado": "should", "cifrado": "kms encryption", "encriptar": "kms cifrado",
}
_TOKEN = __import__("re").compile(r"[a-z0-9_]{2,}")


def _stem(word: str) -> str:
    if len(word) > 5 and word.endswith("es"):
        return word[:-2]
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word


def normalize(text: str, expand: bool = False) -> str:
    """minúsculas sin tildes + plural→singular (buzones→buzon); `expand` agrega sinónimos (solo a la consulta)."""
    from govkit.kb.bm25 import tokenize
    words = tokenize(text)
    extra = [w for t in words for w in SYNONYMS.get(t, "").split()] if expand else []
    return " ".join(_stem(w) for w in words + extra)


@lru_cache(maxsize=1)
def _indexes():
    kb, rules = {}, {}
    for cid, e in sources._kb_lines().items():  # noqa: SLF001
        if cid.split(".")[1][0] in LETTERS:
            kb[cid] = normalize(f"{e['text']} {e['chunk_title']}")
    for rid, r in sources._catalog().items():  # noqa: SLF001
        src = r.source or {}
        rules[rid] = normalize(f"{r.title} {src.get('quote', '')} {r.remediation}")
    return BM25(kb), BM25(rules)


def candidates(claim: str, k: int = 10) -> List[Dict[str, object]]:
    """Mitad criterios KB (lo que dice el framework) y mitad reglas GOV-* (lo que se valida), ordenados por puntaje."""
    kb_idx, rule_idx = _indexes()
    q = normalize(claim, expand=True)
    hits = kb_idx.search(q, k=(k + 1) // 2) + rule_idx.search(q, k=k // 2)
    out = []
    for ident, score in sorted(hits, key=lambda h: -h[1]):
        e = sources.resolve(ident)
        if e:
            text = e["title"] if e["kind"] == "regla" else e.get("quote", "")
            out.append({**e, "text": text, "score": round(score, 2)})
    return out


def _cand_block(cands: List[Dict[str, object]]) -> str:
    lines = []
    for c in cands:
        tag = f" [{c['strength']}]" if c.get("strength") else ""
        lines.append(f"- {c['id']}{tag} (similitud {c['score']}) {c['text']} — fuente: {c['where']}")
    return "\n".join(lines) or "- (sin coincidencias en el framework)"


def render_candidates(claim: str, cands: List[Dict[str, object]]) -> str:
    lines = [f"Afirmación: {claim}", "",
             "Criterios más cercanos en el framework (búsqueda por palabras, sin IA: juzga si alguno la respalda):"]
    for c in cands[:8]:
        tag = f" [{c['strength']}]" if c.get("strength") else ""
        lines.append(f"- {c['id']}{tag} → {c['where']}\n    «{c['text']}»")
    if not cands:
        lines.append("- (sin coincidencias: probablemente no existe tal cual en el framework)")
    return "\n".join(lines) + "\n"


def verify(claim: str, use_llm: bool = True, save: bool = True, cwd: Optional[Path] = None) -> int:
    from govkit import assistant, notes

    cands = candidates(claim)
    claude = os.environ.get("GOVKIT_CLAUDE") or shutil.which("claude")
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    if not use_llm or not claude:
        if use_llm and not claude:
            print("govkit: sin Claude Code instalado muestro solo los criterios más cercanos (búsqueda determinista).",
                  file=sys.stderr)
        text = render_candidates(claim, cands)
        sys.stdout.write(text)
        if save:
            _saved(notes.save(f"Verificación: {claim}", text, repo=Path(cwd or os.getcwd()).name))
        return 0
    prompt = (f"Afirmación escuchada: «{claim}»\n\nCANDIDATOS del framework (búsqueda determinista):\n"
              f"{_cand_block(cands)}\n\nEmite el veredicto con el formato indicado.")
    tools = ["mcp__govkit__kb_context", "mcp__govkit__search_rules", "mcp__govkit__explain_rule",
             "mcp__govkit__sources"]
    cmd = [claude, "-p", prompt]
    if not assistant._mcp_registered(claude):  # noqa: SLF001
        from govkit.paths import KIT_HOME
        import json
        cmd += ["--mcp-config", json.dumps({"mcpServers": {"govkit": {"command": str(KIT_HOME / "bin" / "govkit"),
                                                                      "args": ["mcp"]}}})]
    cmd += ["--append-system-prompt", CLAIM_GUIDE, "--output-format", "stream-json", "--verbose",
            "--allowedTools", ",".join(tools)]
    rc, answer = assistant.run_direct(cmd, Path(cwd or os.getcwd()))
    if not answer:
        sys.stdout.write(render_candidates(claim, cands))
        return rc or 1
    cited = sources.extract_ids(answer)
    unknown = [i for i in cited if sources.resolve(i) is None]
    block = sources.render(sources.resolve_all(cited))
    text = f"Afirmación: {claim}\n\n{answer.strip()}\n"
    if unknown:
        text += f"\n⚠️ Citado pero NO existe en el framework (descártalo): {', '.join(unknown)}\n"
    if block:
        text += "\n" + block
    sys.stdout.write(assistant.render(text, color))
    if save:
        _saved(notes.save(f"Verificación: {claim}", text, repo=Path(cwd or os.getcwd()).name, tags="verificacion"))
    return 0


def _saved(note: Dict[str, object]) -> None:
    dim = sys.stderr.isatty() and not os.environ.get("NO_COLOR")
    msg = f"💾 guardada como nota #{note['id']} · govkit notas ver {note['id']}"
    print(("\033[2m" + msg + "\033[0m") if dim else msg, file=sys.stderr)
