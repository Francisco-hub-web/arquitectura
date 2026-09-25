"""Almacén de mini-contextos: parseo de front-matter y secciones, estimación de tokens y validación."""
from __future__ import annotations

import fnmatch
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from govkit.minischema import validate
from govkit.paths import KB_DIR, SCHEMAS_DIR, load_yaml_file, yaml

SECTION = re.compile(r"^## ([A-Z]) · (.+)$", re.MULTILINE)
RULE_ID = re.compile(r"\*\*(KB\d{2}\.[RAHV]\d+)\b")
CHARS_PER_TOKEN = 3.6  # aproximación conservadora para Qwen/Llama en español


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


@dataclass
class Chunk:
    id: str
    path: str
    meta: Dict
    header: str
    sections: Dict[str, str] = field(default_factory=dict)  # letra → texto completo de la sección

    @property
    def title(self) -> str:
        return self.meta.get("title", self.id)

    @property
    def tier(self) -> int:
        return int(self.meta.get("tier", 9))

    @property
    def body(self) -> str:
        return self.header + "\n" + "\n".join(self.sections.values())

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.body)

    @property
    def rule_ids(self) -> List[str]:
        return RULE_ID.findall(self.body)

    def render(self, sections: Optional[str] = None) -> str:
        wanted = [s.strip().upper() for s in sections.split(",")] if isinstance(sections, str) and sections else sections
        parts = [self.header.strip()]
        for letter, text in self.sections.items():
            if not wanted or letter in wanted:
                parts.append(text.strip())
        return "\n\n".join(parts)

    def tokens_for(self, sections: Optional[List[str]]) -> int:
        return estimate_tokens(self.render(sections))


def parse_chunk(path) -> Chunk:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        raise ValueError(f"{path}: falta front-matter")
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    matches = list(SECTION.finditer(body))
    header = body[:matches[0].start()] if matches else body
    sections: Dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[m.group(1)] = body[m.start():end].strip()
    return Chunk(id=meta.get("id", ""), path=str(path), meta=meta, header=header.strip(), sections=sections)


class KnowledgeBase:
    def __init__(self, chunks: Dict[str, Chunk], graph: Dict):
        self.chunks = chunks
        self.graph = graph

    def closure(self, cid: str, seen=None) -> List[str]:
        """Dependencias duras en orden topológico (primero las bases)."""
        seen = seen if seen is not None else []
        for dep in self.chunks[cid].meta.get("depends_on", []) or []:
            if dep not in seen and dep in self.chunks:
                self.closure(dep, seen)
        if cid not in seen:
            seen.append(cid)
        return seen

    def by_path(self, rel: str) -> List[str]:
        return [c.id for c in self.chunks.values()
                if any(fnmatch.fnmatch(rel, p) for p in (c.meta.get("triggers", {}) or {}).get("paths", []) or [])]

    def by_rule(self, rule_id: str) -> List[str]:
        return [c.id for c in self.chunks.values()
                if any(fnmatch.fnmatch(rule_id.upper(), p) for p in (c.meta.get("triggers", {}) or {}).get("rules", []) or [])]

    def validate(self, catalog=None) -> List[str]:
        import json
        errors: List[str] = []
        schema = json.loads((SCHEMAS_DIR / "kb_chunk.schema.json").read_text(encoding="utf-8"))
        all_rule_ids: Dict[str, str] = {}
        for c in self.chunks.values():
            for path, msg in validate(c.meta, schema):
                errors.append(f"{c.id}: front-matter `{path}` {msg}")
            for letter in ("R", "V", "D"):
                if letter not in c.sections:
                    errors.append(f"{c.id}: falta sección obligatoria `## {letter} · ...`")
            for dep in (c.meta.get("depends_on") or []) + (c.meta.get("related") or []):
                if dep not in self.chunks:
                    errors.append(f"{c.id}: referencia a mini-contexto inexistente {dep}")
            budget = int(c.meta.get("token_budget", 1000))
            if c.tokens > budget * 1.15:
                errors.append(f"{c.id}: {c.tokens} tokens excede el presupuesto declarado {budget} (+15%)")
            prefix = c.id.replace("_", "")
            for rid in c.rule_ids:
                if not rid.startswith(prefix):
                    errors.append(f"{c.id}: ID de regla {rid} no corresponde al mini-contexto")
                if rid in all_rule_ids:
                    errors.append(f"{c.id}: ID de regla duplicado {rid} (también en {all_rule_ids[rid]})")
                all_rule_ids[rid] = c.id
        # ciclos en dependencias duras
        for cid in self.chunks:
            stack, seen = [(cid, [cid])], set()
            while stack:
                node, trail = stack.pop()
                for dep in self.chunks[node].meta.get("depends_on", []) or []:
                    if dep == cid:
                        errors.append(f"Ciclo de dependencias: {' → '.join(trail + [dep])}")
                    elif dep in self.chunks and dep not in seen:
                        seen.add(dep)
                        stack.append((dep, trail + [dep]))
        for task, spec in (self.graph.get("tasks") or {}).items():
            for cid in (spec.get("core") or []) + (spec.get("plus") or []):
                if cid not in self.chunks:
                    errors.append(f"_graph.yaml: tarea {task} apunta a {cid} inexistente")
        if catalog is not None:
            ids = {r.id for r in catalog["_rules"]}
            for c in self.chunks.values():
                for rid in c.meta.get("deterministic_rules", []) or []:
                    if rid not in ids:
                        errors.append(f"{c.id}: deterministic_rules referencia {rid} inexistente en el catálogo")
                for pat in (c.meta.get("triggers", {}) or {}).get("rules", []) or []:
                    if not any(fnmatch.fnmatch(i, pat) for i in ids):
                        errors.append(f"{c.id}: triggers.rules `{pat}` no coincide con ninguna regla")
            for r in catalog["_rules"]:
                for k in r.kb:
                    if k not in self.chunks:
                        errors.append(f"Regla {r.id} referencia mini-contexto inexistente {k}")
        return errors

    def ascii_graph(self) -> str:
        lines = ["Dependencias duras (hijo ──► base) y tier:"]
        for c in sorted(self.chunks.values(), key=lambda c: (c.tier, c.id)):
            deps = c.meta.get("depends_on") or []
            rel = c.meta.get("related") or []
            lines.append(f"  [T{c.tier}] {c.id} {c.title[:52]:<52} ──► {', '.join(deps) or '—'}"
                         + (f"   ·· {', '.join(rel)}" if rel else ""))
        return "\n".join(lines)


_CACHE: Dict[str, KnowledgeBase] = {}


def load(kb_dir=None) -> KnowledgeBase:
    key = str(kb_dir or KB_DIR)
    if key not in _CACHE:
        base = kb_dir or KB_DIR
        chunks = {}
        for p in sorted(base.glob("KB_*.md")):
            c = parse_chunk(p)
            chunks[c.id] = c
        graph = load_yaml_file(base / "_graph.yaml") or {}
        _CACHE[key] = KnowledgeBase(chunks, graph)
    return _CACHE[key]
