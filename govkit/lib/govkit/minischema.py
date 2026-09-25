"""Validador de un subconjunto de JSON Schema (draft-07) sin dependencias.

Soporta: type, required, properties, additionalProperties, enum, const, pattern,
minLength, maxLength, minimum, maximum, items, patternProperties, minItems, maxItems, uniqueItems,
anyOf, $ref local (#/definitions/*, #/$defs/*) y format (date, email, semver, uri).
Suficiente para los contratos del kit; evita arrastrar `jsonschema` (+ rpds/Rust).
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, List, Tuple

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _fmt_ok(fmt: str, value: Any) -> bool:
    if fmt == "date":
        return isinstance(value, (_dt.date,)) or (isinstance(value, str) and bool(_DATE.match(value)))
    if not isinstance(value, str):
        return True
    if fmt == "email":
        return bool(_EMAIL.match(value))
    if fmt == "semver":
        return bool(_SEMVER.match(value))
    if fmt == "uri":
        return "://" in value
    return True


def _type_ok(expected: Any, value: Any) -> bool:
    if isinstance(value, _dt.date) and ("string" in (expected if isinstance(expected, list) else [expected])):
        return True  # YAML convierte fechas ISO en date: se aceptan como string
    types = expected if isinstance(expected, list) else [expected]
    return any(_TYPES[t](value) for t in types)


def _path(base: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{base}[{key}]"
    return f"{base}.{key}" if base else str(key)


def validate(instance: Any, schema: Dict[str, Any], root: Dict[str, Any] = None, path: str = "") -> List[Tuple[str, str]]:
    """Retorna lista de (ruta, mensaje)."""
    root = root or schema
    errors: List[Tuple[str, str]] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        target: Any = root
        for part in ref.lstrip("#/").split("/"):
            target = target[part]
        return validate(instance, target, root, path)
    if "anyOf" in schema:
        if all(validate(instance, s, root, path) for s in schema["anyOf"]):
            errors.append((path, "no cumple ninguna de las alternativas permitidas (anyOf)"))
    if "type" in schema and not _type_ok(schema["type"], instance):
        errors.append((path, f"tipo esperado {schema['type']}, recibido {type(instance).__name__}"))
        return errors
    if "enum" in schema and instance not in schema["enum"]:
        errors.append((path, f"valor '{instance}' fuera de {schema['enum']}"))
    if "const" in schema and instance != schema["const"]:
        errors.append((path, f"debe ser '{schema['const']}'"))
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append((path, f"no cumple el patrón {schema['pattern']}"))
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append((path, f"longitud mínima {schema['minLength']}"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append((path, f"longitud máxima {schema['maxLength']}"))
    if "format" in schema and not _fmt_ok(schema["format"], instance):
        errors.append((path, f"formato {schema['format']} inválido"))
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append((path, f"mínimo {schema['minimum']}"))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append((path, f"máximo {schema['maximum']}"))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append((path, f"requiere al menos {schema['minItems']} elemento(s)"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append((path, f"admite como máximo {schema['maxItems']} elemento(s)"))
        if schema.get("uniqueItems"):
            seen = [repr(i) for i in instance]
            if len(seen) != len(set(seen)):
                errors.append((path, "elementos duplicados"))
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], root, _path(path, i)))
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append((_path(path, req), "campo obligatorio ausente"))
        props = schema.get("properties", {})
        patterns = schema.get("patternProperties", {})
        for key, value in instance.items():
            pat = next((p for p in patterns if re.search(p, str(key))), None)
            if key in props:
                errors.extend(validate(value, props[key], root, _path(path, key)))
            elif pat is not None:
                errors.extend(validate(value, patterns[pat], root, _path(path, key)))
            elif schema.get("additionalProperties") is False:
                errors.append((_path(path, key), "campo no permitido por el esquema"))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(validate(value, schema["additionalProperties"], root, _path(path, key)))
    return errors
