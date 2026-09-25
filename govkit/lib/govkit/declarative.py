"""Checks declarativos: la mayoría de las reglas del catálogo se expresan como datos.

Tipos (`check.kind`): exists · field · each · count · filename · regex_scan · composite · plugin.
Esta separación ("reglas como datos, checks complejos como plugins") permite que el
equipo de Arquitectura agregue o ajuste reglas sin tocar código Python.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, Iterable, List, Optional

from govkit.minischema import _EMAIL, _SEMVER
from govkit.model import Finding, Location
from govkit.repo import RepoContext
from govkit.yamlloc import Doc, dig, expand

PLACEHOLDER = re.compile(
    r"(?i)^\s*(todo|tbd|tbc|x{2,}|n/?a|-+|\.{2,}|pendiente|por definir|completar|placeholder|lorem.*|"
    r"descripci[oó]n|description|\?+|<[^>]*>|\{\{.*\}\})\s*$")
PLACEHOLDER_INLINE = re.compile(r"(?i)<\s*completar[^>]*>|\{\{\s*[a-z_]+\s*\}\}|lorem ipsum")


def is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return bool(PLACEHOLDER.match(value)) or bool(PLACEHOLDER_INLINE.search(value)) or not value.strip()
    return False


def _as_str(v: Any) -> str:
    return v.isoformat() if isinstance(v, (_dt.date, _dt.datetime)) else str(v)


def check_value(value: Any, found: bool, spec: Dict[str, Any], ctx: RepoContext) -> Optional[str]:
    """Evalúa aserciones sobre un valor. Retorna mensaje de error o None."""
    if not found or value is None or (isinstance(value, str) and not value.strip()):
        return "campo obligatorio ausente o vacío" if spec.get("required", True) else None
    if spec.get("not_placeholder") and is_placeholder(value):
        return f"valor de relleno ('{_as_str(value)[:40]}') — debe completarse con información real"
    t = spec.get("type")
    if t:
        ok = {"string": isinstance(value, (str, _dt.date)), "list": isinstance(value, list),
              "map": isinstance(value, dict), "boolean": isinstance(value, bool),
              "number": isinstance(value, (int, float)) and not isinstance(value, bool)}.get(t, True)
        if not ok:
            return f"tipo esperado {t}"
    if "enum" in spec:
        allowed = [str(a).lower() for a in spec["enum"]]
        vals = value if isinstance(value, list) else [value]
        bad = [v for v in vals if str(v).lower() not in allowed]
        if bad:
            return f"valor(es) {bad} fuera del catálogo permitido {spec['enum']}"
    if "equals" in spec and value != spec["equals"]:
        return f"debe ser {spec['equals']!r} (actual: {value!r})"
    if spec.get("is_true") and value is not True:
        return "debe ser true"
    if "regex" in spec and not re.search(spec["regex"], _as_str(value)):
        return f"'{_as_str(value)}' no cumple el patrón {spec['regex']}"
    if "min_length" in spec and len(_as_str(value).strip()) < spec["min_length"]:
        return f"texto demasiado corto ({len(_as_str(value).strip())} < {spec['min_length']} caracteres)"
    if "min_items" in spec and (not isinstance(value, list) or len(value) < spec["min_items"]):
        return f"requiere al menos {spec['min_items']} elemento(s)"
    if spec.get("semver") and not _SEMVER.match(_as_str(value)):
        return f"'{value}' no es versión semántica MAJOR.MINOR.PATCH"
    if spec.get("date") and not isinstance(value, _dt.date) and not re.match(r"^\d{4}-\d{2}-\d{2}$", _as_str(value)):
        return f"'{value}' no es fecha ISO (YYYY-MM-DD)"
    if spec.get("email"):
        vals = value if isinstance(value, list) else [value]
        domains = [d.lower() for d in ctx.policies.get("allowed_email_domains", [])]
        for v in vals:
            s = _as_str(v)
            if not _EMAIL.match(s):
                return f"'{s}' no es un email válido"
            if domains and s.split("@")[-1].lower() not in domains:
                return f"'{s}' no pertenece a un dominio corporativo permitido {domains}"
    if "min" in spec and isinstance(value, (int, float)) and value < spec["min"]:
        return f"valor {value} menor al mínimo {spec['min']}"
    if "max" in spec and isinstance(value, (int, float)) and value > spec["max"]:
        return f"valor {value} mayor al máximo {spec['max']}"
    if "keys" in spec:
        if not isinstance(value, dict):
            return "se esperaba un mapa"
        missing = [k for k in spec["keys"] if k not in value or value[k] in (None, "", [])]
        if missing:
            return f"faltan claves {missing}"
    return None


# ---------------------------------------------------------------------- condiciones
def _cond_value(cond: Dict[str, Any], ctx: RepoContext, doc: Optional[Doc], item: Any):
    if "dp" in cond:
        return dig(ctx.dp.data, cond["dp"]) if ctx.dp and isinstance(ctx.dp.data, dict) else (False, None)
    if "item" in cond:
        return dig(item, cond["item"])
    if "file" in cond:
        return dig(doc.data, cond["file"]) if doc else (False, None)
    return False, None


def when_ok(conds: Any, ctx: RepoContext, doc: Optional[Doc] = None, item: Any = None) -> bool:
    for cond in conds or []:
        if "exists" in cond:
            if not ctx.glob(cond["exists"]) and not ctx.is_dir(cond["exists"]):
                return False
            continue
        if "not_exists" in cond:
            if ctx.glob(cond["not_exists"]) or ctx.is_dir(cond["not_exists"]):
                return False
            continue
        if "stage_at_least" in cond:
            if ctx.stage_rank() < ctx.stage_rank(cond["stage_at_least"]):
                return False
            continue
        if "stage_in" in cond:
            if ctx.stage not in cond["stage_in"]:
                return False
            continue
        found, value = _cond_value(cond, ctx, doc, item)
        vals = value if isinstance(value, list) else [value]
        norm = [str(v).lower() for v in vals]
        if "equals" in cond and not (found and value == cond["equals"]):
            return False
        if "in" in cond and not (found and any(v in [str(x).lower() for x in cond["in"]] for v in norm)):
            return False
        if "not_in" in cond and found and any(v in [str(x).lower() for x in cond["not_in"]] for v in norm):
            return False
        if cond.get("truthy") and not (found and value):
            return False
        if cond.get("falsy") and found and value:
            return False
        if cond.get("present") and not (found and value not in (None, "", [])):
            return False
        if cond.get("absent") and found and value not in (None, "", []):
            return False
    return True


def _loc(doc: Doc, path: Optional[str]) -> Location:
    line, col = doc.pos(path)
    return Location(doc.path, line, col, path)


# ---------------------------------------------------------------------- kinds
def _first_marker_line(text: str) -> int:
    m = PLACEHOLDER_INLINE.search(text)
    return text.count("\n", 0, m.start()) + 1 if m else 1


def run_exists(ctx: RepoContext, chk: Dict[str, Any]) -> Iterable[Finding]:
    for rel in chk.get("all", []):
        is_dir = rel.endswith("/")
        ok = ctx.is_dir(rel.rstrip("/")) if is_dir else (ctx.exists(rel) or bool(ctx.glob(rel)))
        if not ok:
            kind = "directorio" if is_dir else "archivo"
            yield Finding(f"Falta el {kind} estándar `{rel}`", Location(rel.rstrip("/")),
                          evidence={"key": rel, "expected": rel}, fix={"type": "create", "path": rel})
    anys = chk.get("any")
    if anys:
        found = [f for p in anys for f in ctx.glob(p)]
        anchor = anys[0].split("*")[0].rsplit("/", 1)[0] if "*" in anys[0] else anys[0]
        if found and chk.get("complete", False) and all(PLACEHOLDER_INLINE.search(ctx.text(f) or "") for f in found):
            # Existe, pero solo como esqueleto: un archivo con marcas <COMPLETAR> no satisface la regla.
            yield Finding(f"`{found[0]}` existe pero conserva marcas <COMPLETAR>: aún no está completado",
                          Location(found[0], _first_marker_line(ctx.text(found[0]) or "")),
                          evidence={"key": found[0], "incomplete": found})
        elif not found and not any(ctx.is_dir(p.rstrip("/")) for p in anys):
            yield Finding(chk.get("message") or f"No se encontró ninguno de: {', '.join(anys)}",
                          Location(anchor or "."),
                          evidence={"key": anys[0], "expected_any": anys},
                          fix={"type": "create", "path": anys[0].replace("**/", "").replace("*", "<nombre>")})


def run_field(ctx: RepoContext, chk: Dict[str, Any]) -> Iterable[Finding]:
    docs = ctx.artifact(chk["target"])
    if chk.get("fields"):  # aserciones distintas por ruta: {ruta: aserción}
        pairs = list(chk["fields"].items())
    else:
        pairs = [(p, chk.get("assert", {})) for p in (chk.get("paths") or [chk["path"]])]
    for doc in docs:
        if doc.error or not when_ok(chk.get("when"), ctx, doc):
            continue
        for path, spec in pairs:
            targets = expand(doc.data, path) if "[*]" in path else [(path, dig(doc.data, path))]
            for concrete, res in targets:
                found, value = res if isinstance(res, tuple) else (True, res)
                err = check_value(value, found, spec or {}, ctx)
                if err:
                    fix = {"type": "set", "path": concrete}
                    if "enum" in (spec or {}):
                        fix["allowed"] = spec["enum"]
                    yield Finding(f"`{concrete}`: {err}", _loc(doc, concrete),
                                  evidence={"key": concrete, "actual": None if not found else _as_str(value)[:120]},
                                  fix=fix)


def run_each(ctx: RepoContext, chk: Dict[str, Any]) -> Iterable[Finding]:
    for doc in ctx.artifact(chk["target"]):
        if doc.error or not when_ok(chk.get("when"), ctx, doc):
            continue
        found, items = dig(doc.data, chk["path"])
        if not found or not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not when_ok(chk.get("when_item"), ctx, doc, item):
                continue
            label = item.get(chk.get("label_key", "name")) or f"#{i}"
            for key, spec in (chk.get("keys") or {}).items():
                ipath = f"{chk['path']}[{i}].{key}"
                f2, v2 = dig(item, key)
                err = check_value(v2, f2, spec or {}, ctx)
                if err:
                    yield Finding(f"{chk.get('noun', 'elemento')} '{label}' → `{key}`: {err}", _loc(doc, ipath),
                                  evidence={"key": ipath, "item": str(label)},
                                  fix={"type": "set", "path": ipath, **({"allowed": spec["enum"]} if spec and "enum" in spec else {})})


def run_count(ctx: RepoContext, chk: Dict[str, Any]) -> Iterable[Finding]:
    docs = [d for d in ctx.artifact(chk["target"]) if not d.error]
    if not docs:
        return
    total = 0
    for doc in docs:
        found, items = dig(doc.data, chk["path"])
        for item in (items if found and isinstance(items, list) else []):
            if isinstance(item, dict) and when_ok(chk.get("where"), ctx, doc, item):
                total += 1
    if total < chk.get("min", 1):
        yield Finding(chk.get("message", "Cantidad insuficiente") + f" (encontrados: {total}, mínimo: {chk.get('min', 1)})",
                      _loc(docs[0], chk["path"]), evidence={"key": chk["path"], "count": total})


def run_filename(ctx: RepoContext, chk: Dict[str, Any]) -> Iterable[Finding]:
    for pat in chk.get("patterns", []):
        rx = re.compile(pat["regex"])
        for rel in ctx.glob(pat["glob"], pat.get("exclude")):
            name = rel.rsplit("/", 1)[-1]
            if name in ("__init__.py", ".gitkeep") or rx.match(name):
                continue
            yield Finding(f"`{name}` no cumple la convención {pat.get('convention', pat['regex'])}", Location(rel),
                          evidence={"key": rel, "expected": pat.get("convention", pat["regex"])},
                          fix={"type": "rename", "path": rel})


def run_regex_scan(ctx: RepoContext, chk: Dict[str, Any]) -> Iterable[Finding]:
    flags = re.IGNORECASE if "i" in chk.get("flags", "") else 0
    rx = re.compile(chk["pattern"], flags | re.MULTILINE)
    for rel in ctx.text_files(chk.get("globs", "**"), chk.get("exclude")):
        text = ctx.text(rel)
        if not text:
            continue
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
            yield Finding(chk.get("message", "Patrón prohibido") + f": `{m.group(0).strip()[:80]}`",
                          Location(rel, line, col), evidence={"key": f"{rel}:{line}", "match": m.group(0).strip()[:80]})
            if chk.get("first_only", True):
                break


KINDS = {"exists": run_exists, "field": run_field, "each": run_each, "count": run_count,
         "filename": run_filename, "regex_scan": run_regex_scan}


def dispatch(ctx: RepoContext, chk: Dict[str, Any]) -> List[Finding]:
    kind = chk.get("kind")
    if kind not in KINDS:
        raise ValueError(f"check.kind desconocido: {kind}")
    return list(KINDS[kind](ctx, chk))
