"""`govkit fix`: auto-remediación determinista y segura de los hallazgos que traen `fix`.

Principio: solo se automatiza lo que no requiere juicio humano. Nunca se sobrescribe contenido escrito por una
persona; los valores de negocio se insertan como marcas `<COMPLETAR>` (el hallazgo sigue abierto, pero el
esqueleto queda explícito en el archivo correcto). Cada edición se verifica re-parseando el archivo: si el
resultado no es válido o no contiene la clave esperada, la acción se revierte y queda como manual.

Acciones:  mkdir (carpeta estándar + .gitkeep) · template (archivo desde la plantilla corporativa) ·
           set (valor determinista conocido) · placeholder (clave ausente → <COMPLETAR>) · bump (semver) ·
           manual (requiere decisión: renombrar, mover, completar contenido existente).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from govkit.paths import TEMPLATES_DIR, SafeLoader, registry, yaml
from govkit.repo import glob_to_regex
from govkit.scaffold import EMPTY_DIRS, _render, variables
from govkit.yamlloc import dig, split_path

PLACEHOLDER = "<COMPLETAR>"
_PLAIN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./@:+-]*$")
_YAML_SPECIAL = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}
AUTO_KINDS = ("mkdir", "template", "set", "placeholder", "bump")


@dataclass
class Action:
    kind: str
    file: str
    detail: str
    rules: List[str] = field(default_factory=list)
    key: Optional[str] = None
    value: Any = None
    status: str = "planned"  # planned | applied | failed | manual
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {"kind": self.kind, "file": self.file, "detail": self.detail, "rules": self.rules, "status": self.status}
        if self.key:
            d["key"] = self.key
        if self.value is not None:
            d["value"] = self.value
        if self.reason:
            d["reason"] = self.reason
        return d


# ============================================================== edición de YAML conservando comentarios
def render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(render_scalar(v) for v in value) + "]"
    if isinstance(value, dict) and not value:
        return "{}"
    s = str(value)
    if _PLAIN.match(s) and s.lower() not in _YAML_SPECIAL and not re.match(r"^[-+]?[\d.]+$", s):
        return s
    return json.dumps(s, ensure_ascii=False)  # doble comilla YAML ≡ JSON para cadenas


def _last_line(node: Any) -> int:
    """Índice (0-based) de la línea ANTES de la cual se inserta un hermano posterior del nodo."""
    if isinstance(node, yaml.MappingNode) and node.value:
        return _last_line(node.value[-1][1])
    if isinstance(node, yaml.SequenceNode) and node.value:
        return _last_line(node.value[-1])
    m = node.end_mark
    return m.line if m.column == 0 else m.line + 1


def yaml_set(text: str, path: str, value: Any, overwrite: bool = False) -> Optional[str]:
    """Inserta (o reemplaza si `overwrite`) `path: value` en YAML de bloque. None si no es seguro."""
    parts = split_path(path)
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)  # parser puro: índices de texto exactos
    except yaml.YAMLError:
        return None
    lines = text.splitlines(keepends=True)
    if root is None:
        root_indent, insert_at, node, key_node, i = 0, len(lines), None, None, 0
    else:
        node, key_node, i = root, None, 0
        while i < len(parts):
            p = parts[i]
            if isinstance(p, int):
                if isinstance(node, yaml.SequenceNode) and p < len(node.value):
                    node, key_node, i = node.value[p], None, i + 1
                    continue
                return None  # no se crean elementos de lista
            if isinstance(node, yaml.MappingNode):
                if node.flow_style:
                    return None
                hit = next(((k, v) for k, v in node.value if getattr(k, "value", None) == p), None)
                if hit:
                    key_node, node = hit
                    i += 1
                    continue
            break
        if i == len(parts):  # la clave ya existe
            if not overwrite or not isinstance(node, yaml.ScalarNode):
                return None
            s, e = node.start_mark.index, node.end_mark.index
            if s == e:  # `clave:` sin valor
                ln = key_node.start_mark.line
                lines[ln] = re.sub(r"^(\s*(?:-\s+)?[^#\n]*?:)[ \t]*", lambda m: m.group(1) + " " + render_scalar(value),
                                   lines[ln], count=1)
                return "".join(lines)
            return text[:s] + render_scalar(value) + text[e:]
        if any(isinstance(r, int) for r in parts[i:]):
            return None
        if isinstance(node, yaml.MappingNode) and node.value:
            root_indent = node.value[0][0].start_mark.column
            insert_at = _last_line(node)
        elif (isinstance(node, yaml.ScalarNode) and key_node is not None and node.tag.endswith(":null")
              and node.start_mark.index == node.end_mark.index):
            root_indent = key_node.start_mark.column + 2
            insert_at = key_node.start_mark.line + 1
        else:
            return None
    rest = parts[i:]
    block = [" " * (root_indent + 2 * d) + f"{k}:\n" for d, k in enumerate(rest[:-1])]
    block.append(" " * (root_indent + 2 * (len(rest) - 1)) + f"{rest[-1]}: {render_scalar(value)}\n")
    if insert_at > 0 and insert_at <= len(lines) and not lines[insert_at - 1].endswith("\n"):
        lines[insert_at - 1] += "\n"
    lines[insert_at:insert_at] = block
    return "".join(lines)


def json_set(text: str, path: str, value: Any, overwrite: bool = False) -> Optional[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    parts = split_path(path)
    cur = data
    for p in parts[:-1]:
        if isinstance(p, int):
            if not isinstance(cur, list) or p >= len(cur):
                return None
            cur = cur[p]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.setdefault(p, {})
    last = parts[-1]
    if not isinstance(cur, dict) or isinstance(last, int) or (last in cur and not overwrite):
        return None
    cur[last] = value
    m = re.search(r"\n([ \t]+)\S", text)
    indent = len(m.group(1)) if m else 2
    return json.dumps(data, ensure_ascii=False, indent=indent) + ("\n" if text.endswith("\n") else "")


def set_in_text(rel: str, text: str, path: str, value: Any, overwrite: bool = False) -> Optional[str]:
    """Edición verificada: aplica, re-parsea y confirma que la clave quedó con el valor y sin perder claves."""
    is_json = rel.endswith(".json")
    new = (json_set if is_json else yaml_set)(text, path, value, overwrite)
    if new is None:
        return None
    try:
        before = json.loads(text) if is_json else yaml.load(text, Loader=SafeLoader)
        after = json.loads(new) if is_json else yaml.load(new, Loader=SafeLoader)
    except (json.JSONDecodeError, yaml.YAMLError):
        return None
    found, got = dig(after, path)
    if not found or got != value or not _keys_preserved(before, after):
        return None
    return new


def _keys_preserved(a: Any, b: Any) -> bool:
    if isinstance(a, dict):
        return isinstance(b, dict) and all(k in b and _keys_preserved(v, b[k]) for k, v in a.items())
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(_keys_preserved(x, y) for x, y in zip(a, b))
    return True


def bump(version: Any, part: str) -> Optional[str]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", str(version or ""))
    if not m:
        return None
    ma, mi, pa = (int(x) for x in m.groups())
    return {"major": f"{ma + 1}.0.0", "minor": f"{ma}.{mi + 1}.0", "patch": f"{ma}.{mi}.{pa + 1}"}.get(part)


# ============================================================== plantillas corporativas
def repo_vars(ctx) -> Optional[Dict[str, str]]:
    """Variables de plantilla derivadas del repo existente (ficha o nombre estándar)."""
    m = re.match(r"^(?P<body>[a-z0-9-]+)-(?P<type>txd|anl)-dp-(?P<country>[a-z]{2})$", ctx.repo_name or "")
    domain, sub = ctx.dp_get("spec.domain"), ctx.dp_get("spec.subdomain")
    if not (domain and sub) and m:
        body = m.group("body")
        known = sorted(registry("domains").get("domains", {}), key=len, reverse=True)
        dom = next((d for d in known if body.startswith(d.replace("_", "-") + "-")), body.split("-", 1)[0])
        domain, sub = dom, body[len(dom.replace("_", "-")) + 1:] or None
    if not (domain and sub):
        return None
    dp_type = ctx.dp_get("spec.type")
    type_code = m.group("type") if m else ("txd" if dp_type == "operational" else "anl")
    countries = ctx.dp_get("spec.scope.countries") or []
    country = m.group("country") if m else (str(countries[0]) if countries else "cl")
    owner = ctx.dp_get("spec.ownership.business_owner")
    owner = owner if isinstance(owner, str) and "@" in owner and "<" not in owner else None
    return variables(str(domain), str(sub).replace("_", "-"), type_code, country, owner)


def template_map(vars_: Optional[Dict[str, str]]) -> Dict[str, Path]:
    if not vars_:
        return {}
    src_root = TEMPLATES_DIR / "data-product"
    return {_render(str(p.relative_to(src_root)).replace("\\", "/"), vars_): p
            for p in sorted(src_root.rglob("*")) if p.is_file()}


# ============================================================== planificación
def plan(res, placeholders: bool = True) -> List[Action]:
    ctx = res.ctx
    vars_ = repo_vars(ctx)
    templates = template_map(vars_)
    actions: Dict[Tuple[str, str, str], Action] = {}

    def add(a: Action, rule_id: str) -> None:
        k = (a.kind, a.file, a.key or "")
        if k in actions:
            if rule_id not in actions[k].rules:
                actions[k].rules.append(rule_id)
        else:
            a.rules = [rule_id]
            actions[k] = a

    for v in res.violations:
        fx = v.fix
        if not fx or not v.counts:
            continue
        t, rel = fx.get("type"), v.location.file
        if t == "create":
            target = fx.get("path", "")
            expected = (v.evidence or {}).get("expected_any") or [target]
            if target.endswith("/") or target.rstrip("/") in EMPTY_DIRS:
                add(Action("mkdir", target.rstrip("/"), "crear carpeta estándar (+ .gitkeep)"), v.rule_id)
                continue
            rx = [glob_to_regex(g) for g in expected]
            hit = next((p for p in templates if any(r.match(p) for r in rx) and not ctx.exists(p)), None)
            if hit:
                add(Action("template", hit, f"crear desde la plantilla corporativa `{hit}`"), v.rule_id)
            else:
                add(Action("manual", target, "crear el archivo: no hay plantilla determinista para su contenido",
                           status="manual"), v.rule_id)
        elif t == "set":
            key = fx.get("path")
            doc = ctx.doc(rel)
            found, cur = dig(doc.data, key) if not doc.error else (False, None)
            if "value" in fx:
                if cur == fx["value"]:
                    continue
                add(Action("set", rel, f"`{key}` → {render_scalar(fx['value'])}", key=key, value=fx["value"]), v.rule_id)
            elif not found and placeholders and not doc.error:
                shape = fx.get("shape")
                hint = f"{PLACEHOLDER[:-1]}: {' | '.join(map(str, fx['allowed']))}>" if fx.get("allowed") else PLACEHOLDER
                val: Any = [hint] if shape == "list" else hint
                add(Action("placeholder", rel, f"agregar `{key}` como esqueleto", key=key, value=val), v.rule_id)
            else:
                add(Action("manual", rel, f"completar `{key}` con información real (contenido humano: no se sobrescribe)",
                           key=key, status="manual"), v.rule_id)
        elif t == "bump":
            cur = ctx.doc(rel).get("metadata.version")
            new = bump(cur, fx.get("part", "minor"))
            if new:
                add(Action("bump", rel, f"`metadata.version` {cur} → {new} ({fx.get('part')})", key="metadata.version",
                           value=new), v.rule_id)
        elif t == "rename":
            name = rel.rsplit("/", 1)[-1]
            stem, dot, ext = name.partition(".")
            snake = re.sub(r"[^a-z0-9_]", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", stem).lower()).strip("_")
            add(Action("manual", rel, f"renombrar a `{snake}{dot}{ext}` y actualizar referencias (dbt ref, imports)",
                       status="manual"), v.rule_id)
        else:
            add(Action("manual", rel, v.remediation or f"acción `{t}` requiere decisión humana", status="manual"), v.rule_id)
    order = {"template": 0, "mkdir": 1, "set": 2, "bump": 3, "placeholder": 4, "manual": 5}
    return sorted(actions.values(), key=lambda a: (order[a.kind], a.file, a.key or ""))


# ============================================================== aplicación
def apply(ctx, actions: List[Action]) -> List[Action]:
    root: Path = ctx.root
    vars_ = repo_vars(ctx)
    templates = template_map(vars_)
    for a in actions:
        if a.kind == "manual":
            continue
        target = (root / a.file).resolve()
        if root.resolve() not in target.parents and target != root.resolve():
            a.status, a.reason = "failed", "ruta fuera del repositorio"
            continue
        try:
            if a.kind == "mkdir":
                target.mkdir(parents=True, exist_ok=True)
                if not any(target.iterdir()):
                    (target / ".gitkeep").write_text("", encoding="utf-8")
                a.status = "applied"
            elif a.kind == "template":
                if target.exists():
                    a.status, a.reason = "failed", "el archivo ya existe"
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(_render(templates[a.file].read_text(encoding="utf-8"), vars_ or {}), encoding="utf-8")
                a.status = "applied"
            else:
                text = target.read_text(encoding="utf-8")
                new = set_in_text(a.file, text, a.key, a.value, overwrite=a.kind in ("set", "bump"))
                if new is None:
                    a.status, a.reason = "failed", "edición no segura (estilo flow, lista o YAML inválido): aplicar a mano"
                    continue
                target.write_text(new, encoding="utf-8")
                a.status = "applied"
        except OSError as exc:
            a.status, a.reason = "failed", str(exc)
    return actions
