"""Carga de YAML/JSON conservando la posición (línea/columna) de cada ruta de datos.

El motor necesita reportar la *línea exacta* de cada violación. PyYAML expone
`start_mark` en el grafo de nodos; aquí se construye un índice `ruta -> (línea, col)`
con la misma sintaxis de rutas que usan las reglas: `spec.inputs[0].type`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from govkit.paths import SafeLoader, yaml

_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+|\*)\]")


def split_path(path: str) -> List[Any]:
    parts: List[Any] = []
    for name, idx in _TOKEN.findall(path or ""):
        if name:
            parts.append(name)
        else:
            parts.append("*" if idx == "*" else int(idx))
    return parts


def join_path(parts: List[Any]) -> str:
    out = ""
    for p in parts:
        if isinstance(p, int):
            out += f"[{p}]"
        else:
            out += ("." if out else "") + str(p)
    return out


def dig(data: Any, path: str) -> Tuple[bool, Any]:
    """Navega `data` por una ruta. Retorna (encontrado, valor)."""
    cur = data
    for part in split_path(path):
        if isinstance(part, int):
            if not isinstance(cur, list) or part >= len(cur):
                return False, None
            cur = cur[part]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return False, None
            cur = cur[part]
    return True, cur


def expand(data: Any, path: str) -> List[Tuple[str, Any]]:
    """Expande comodines `[*]` → lista de (ruta_concreta, valor)."""
    results: List[Tuple[List[Any], Any]] = [([], data)]
    for part in split_path(path):
        nxt: List[Tuple[List[Any], Any]] = []
        for prefix, cur in results:
            if part == "*":
                if isinstance(cur, list):
                    nxt.extend((prefix + [i], v) for i, v in enumerate(cur))
            elif isinstance(part, int):
                if isinstance(cur, list) and part < len(cur):
                    nxt.append((prefix + [part], cur[part]))
            elif isinstance(cur, dict) and part in cur:
                nxt.append((prefix + [part], cur[part]))
        results = nxt
    return [(join_path(p), v) for p, v in results]


@dataclass
class Doc:
    path: str  # relativo a la raíz del repo, formato posix
    text: str
    data: Any = None
    positions: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    error: Optional[str] = None
    error_line: int = 1

    def pos(self, path: Optional[str]) -> Tuple[int, int]:
        """Posición de la ruta; si no existe, la del ancestro más cercano."""
        if not path:
            return (1, 1)
        parts = split_path(path)
        while parts:
            key = join_path(parts)
            if key in self.positions:
                return self.positions[key]
            parts = parts[:-1]
        return (1, 1)

    def get(self, path: str, default: Any = None) -> Any:
        found, value = dig(self.data, path)
        return value if found else default


def _index(node: Any, parts: List[Any], out: Dict[str, Tuple[int, int]]) -> None:
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = getattr(key_node, "value", None)
            if not isinstance(key, str):
                continue
            child = parts + [key]
            out[join_path(child)] = (key_node.start_mark.line + 1, key_node.start_mark.column + 1)
            _index(value_node, child, out)
    elif isinstance(node, yaml.SequenceNode):
        for i, item in enumerate(node.value):
            child = parts + [i]
            out[join_path(child)] = (item.start_mark.line + 1, item.start_mark.column + 1)
            _index(item, child, out)


def parse_text(rel_path: str, text: str) -> Doc:
    doc = Doc(path=rel_path, text=text)
    is_json = rel_path.endswith(".json")
    try:
        doc.data = json.loads(text) if is_json else yaml.load(text, Loader=SafeLoader)
    except json.JSONDecodeError as exc:
        doc.error, doc.error_line = f"JSON inválido: {exc.msg}", exc.lineno
        return doc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        doc.error = f"YAML inválido: {getattr(exc, 'problem', exc)}"
        doc.error_line = (mark.line + 1) if mark else 1
        return doc
    try:
        node = yaml.compose(text, Loader=SafeLoader)
        if node is not None:
            _index(node, [], doc.positions)
    except yaml.YAMLError:
        pass  # JSON válido que YAML 1.1 no compone: sin posiciones finas
    return doc
