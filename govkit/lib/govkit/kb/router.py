"""Enrutador de contexto: decide QUÉ mini-contextos cargar y CUÁNTO de cada uno, dentro de un presupuesto de tokens.

Señales (de mayor a menor prioridad): kernel → tarea (core) → reglas violadas → archivos tocados → consulta
BM25 → tarea (plus) → relacionados. Luego: cierre de dependencias duras, proyección de secciones por modo y
empaquetado greedy con degradación (si no cabe completo, se carga solo la sección R · Reglas).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from govkit.kb.bm25 import BM25
from govkit.kb.store import KnowledgeBase, estimate_tokens


@dataclass
class Item:
    id: str
    priority: float
    reasons: List[str] = field(default_factory=list)
    sections: Optional[List[str]] = None
    tokens: int = 0
    degraded: bool = False


@dataclass
class Pack:
    kb: KnowledgeBase
    items: List[Item]
    dropped: List[Item]
    budget: int
    mode: str

    @property
    def used(self) -> int:
        return sum(i.tokens for i in self.items)

    @property
    def ids(self) -> List[str]:
        return [i.id for i in self.items]

    def rule_ids(self) -> List[str]:
        """IDs de reglas KB efectivamente visibles para el LLM (para validar sus citas)."""
        out: List[str] = []
        for i in self.items:
            from govkit.kb.store import RULE_ID
            out += RULE_ID.findall(self.kb.chunks[i.id].render(i.sections))
        return out

    def text(self) -> str:
        head = (f"CONTEXTO NORMATIVO · Data & AI Discipline Framework (govkit KB) · modo={self.mode} · "
                f"{len(self.items)} mini-contextos · ~{self.used} tokens\n"
                "Cita siempre los IDs (KBnn.Xn). [MUST]=obligatorio · [SHOULD]=recomendado · [PRÁCTICA]=no normativo.\n")
        blocks = [f"<<< {i.id} >>>\n{self.kb.chunks[i.id].render(i.sections)}" for i in self.items]
        return head + "\n\n".join(blocks) + "\n"

    def manifest(self) -> Dict:
        def row(i: Item) -> Dict:
            return {"id": i.id, "title": self.kb.chunks[i.id].title, "tokens": i.tokens,
                    "sections": i.sections or "todas", "priority": round(i.priority, 1), "reasons": i.reasons,
                    "degraded": i.degraded}
        return {"mode": self.mode, "budget": self.budget, "used": self.used,
                "items": [row(i) for i in self.items], "dropped": [row(i) for i in self.dropped]}

    def explain(self) -> str:
        lines = [f"Paquete de contexto · modo `{self.mode}` · {self.used}/{self.budget} tokens · {len(self.items)} mini-contextos", ""]
        for i in self.items:
            sec = ",".join(i.sections) if i.sections else "todas"
            flag = "  (degradado a R)" if i.degraded else ""
            lines.append(f"  {i.id}  {i.tokens:>5} tok  [{sec}]  prio {i.priority:>5.1f}  ← {'; '.join(i.reasons)}{flag}")
        if self.dropped:
            lines += ["", "Descartados por presupuesto:"]
            lines += [f"  {i.id}  ← {'; '.join(i.reasons)}" for i in self.dropped]
        return "\n".join(lines)


def route(kb: KnowledgeBase, task: Optional[str] = None, query: Optional[str] = None,
          paths: Optional[List[str]] = None, rule_ids: Optional[List[str]] = None,
          budget: int = 6000, mode: str = "assist") -> Pack:
    pr = kb.graph.get("priorities", {})
    cands: Dict[str, Item] = {}

    def add(cid: str, prio: float, reason: str) -> None:
        if cid not in kb.chunks:
            return
        it = cands.setdefault(cid, Item(cid, prio))
        it.priority = max(it.priority, prio)
        if reason not in it.reasons:
            it.reasons.append(reason)

    add(kb.graph.get("kernel", "KB_00"), pr.get("kernel", 100), "kernel")
    tasks = kb.graph.get("tasks", {})
    if task:
        if task not in tasks:
            raise SystemExit(f"govkit: tarea desconocida `{task}` (ver `govkit kb route --help` y kb/_graph.yaml)")
        for cid in tasks[task].get("core", []):
            add(cid, pr.get("task_core", 90), f"tarea:{task}")
        for cid in tasks[task].get("plus", []):
            add(cid, pr.get("task_plus", 60), f"tarea+:{task}")
    for rid in rule_ids or []:
        for cid in kb.by_rule(rid):
            add(cid, pr.get("rule", 85), f"regla:{rid}")
    for p in paths or []:
        for cid in kb.by_path(p):
            add(cid, pr.get("path", 80), f"archivo:{p}")
    if query:
        docs = {c.id: f"{c.title} {c.title} " + " ".join(str(k) for k in (c.meta.get('triggers', {}) or {}).get('keywords', []) * 3)
                + " " + c.body for c in kb.chunks.values()}
        hits = BM25(docs).search(query, k=4)
        top = hits[0][1] if hits else 1.0
        for cid, score in hits:
            add(cid, max(35.0, pr.get("query", 70) * score / top), f"consulta:{score:.2f}")
    kernel = kb.graph.get("kernel", "KB_00")
    for cid in list(cands):
        if cid != kernel and cands[cid].priority >= pr.get("task_plus", 60):
            for rel in kb.chunks[cid].meta.get("related", []) or []:
                add(rel, pr.get("related", 40), f"relacionado:{cid}")

    projection = kb.graph.get("projections", {}).get(mode)
    order = sorted(cands.values(), key=lambda i: (-i.priority, kb.chunks[i.id].tier, i.id))
    chosen: Dict[str, Item] = {}
    sequence: List[str] = []
    dropped: List[Item] = []
    used = 0
    for it in order:
        if it.id in chosen:
            continue
        group = [g for g in kb.closure(it.id) if g not in chosen]
        cost = sum(kb.chunks[g].tokens_for(projection) for g in group)
        sections = projection
        degraded = False
        if used + cost > budget:
            cost = sum(kb.chunks[g].tokens_for(["R"]) for g in group)
            sections, degraded = ["R"], True
            if used + cost > budget:
                dropped.append(it)
                continue
        for g in group:
            node = cands.get(g) or Item(g, it.priority - 1)
            if g != it.id and f"dependencia:{it.id}" not in node.reasons:
                node.reasons.append(f"dependencia:{it.id}")
            node.sections = sections
            node.degraded = degraded
            node.tokens = kb.chunks[g].tokens_for(sections)
            chosen[g] = node
            sequence.append(g)
            used += node.tokens
    return Pack(kb, [chosen[i] for i in sequence], dropped, budget, mode)
