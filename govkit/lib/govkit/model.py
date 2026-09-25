"""Modelo de dominio del motor: severidades, ubicaciones, hallazgos y reglas."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SEVERITIES = ["INFO", "LOW", "MEDIUM", "HIGH", "BLOCKER"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
# Peso para el pre-score por pilar (19-scoring-model §24) y para ordenar reportes.
SEV_WEIGHT = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BLOCKER": 5}
# Equivalencia con las severidades del Data Quality Framework (08 §13).
DQ_SEVERITY = {"critica": "BLOCKER", "alta": "HIGH", "media": "MEDIUM", "baja": "LOW"}

NATURES = {
    "D": "Determinista",
    "H": "Híbrida (presencia determinista + adecuación semántica)",
    "S": "Semántica (LLM + KB)",
    "O": "Organizacional / proceso (revisión humana)",
}


def max_sev(a: str, b: str) -> str:
    return a if SEV_RANK[a] >= SEV_RANK[b] else b


@dataclass
class Location:
    file: str
    line: int = 1
    column: int = 1
    json_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"file": self.file, "line": self.line, "column": self.column}
        if self.json_path:
            d["json_path"] = self.json_path
        return d


@dataclass
class Finding:
    """Borrador de hallazgo emitido por un check (el motor lo convierte en Violation)."""

    message: str
    location: Location
    evidence: Dict[str, Any] = field(default_factory=dict)
    fix: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None  # override opcional del check (p.ej. BLOCKER si criticidad=critica)


@dataclass
class Violation:
    rule_id: str
    title: str
    nature: str
    category: str
    pillar: str
    severity: str
    base_severity: str
    message: str
    location: Location
    remediation: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    fix: Optional[Dict[str, Any]] = None
    source: Dict[str, Any] = field(default_factory=dict)
    kb: List[str] = field(default_factory=list)
    escalated_by: Optional[str] = None
    waived: Optional[Dict[str, Any]] = None
    baselined: bool = False

    @property
    def fingerprint(self) -> str:
        anchor = self.location.json_path or f"L{self.location.line}"
        raw = f"{self.rule_id}|{self.location.file}|{anchor}|{self.evidence.get('key', '')}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def counts(self) -> bool:
        """Cuenta para el veredicto si no está exceptuada ni en baseline."""
        return self.waived is None and not self.baselined

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "rule_id": self.rule_id,
            "title": self.title,
            "nature": self.nature,
            "category": self.category,
            "pillar": self.pillar,
            "severity": self.severity,
            "base_severity": self.base_severity,
            "message": self.message,
            "location": self.location.to_dict(),
            "remediation": {"summary": self.remediation, "autofixable": self.fix is not None},
            "references": {"source": self.source, "kb": self.kb},
            "fingerprint": self.fingerprint,
        }
        if self.fix:
            d["remediation"]["fix"] = self.fix
        if self.evidence:
            d["evidence"] = self.evidence
        if self.escalated_by:
            d["escalated_by"] = self.escalated_by
        if self.waived:
            d["waived"] = self.waived
        if self.baselined:
            d["baselined"] = True
        return d


class Rule:
    """Vista tipada de una entrada del catálogo `rules/catalog.yaml`."""

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.id: str = raw["id"]
        self.title: str = raw["title"]
        self.nature: str = raw.get("nature", "D")
        self.category: str = raw.get("category", "general")
        self.pillar: str = raw.get("pillar", "product_definition")
        self.severity: str = raw.get("severity", "MEDIUM")
        self.stages: Dict[str, str] = raw.get("stages") or {}
        self.pack: str = raw.get("pack", "dp")
        self.enforcement: List[str] = raw.get("enforcement") or ["pr"]
        self.technique: str = raw.get("technique", "schema")
        self.source: Dict[str, Any] = raw.get("source") or {}
        self.kb: List[str] = raw.get("kb") or []
        self.check: Optional[Dict[str, Any]] = raw.get("check")
        self.remediation: str = raw.get("remediation", "")
        self.semantic_question: Optional[str] = raw.get("semantic_question")
        self.summary: bool = bool(raw.get("summary", False))

    @property
    def automated(self) -> bool:
        return self.nature in ("D", "H") and self.check is not None

    def severity_for(self, stage_group: Optional[str], override: Optional[str] = None) -> str:
        base = override or self.severity
        if stage_group and stage_group in self.stages:
            val = self.stages[stage_group]
            return "OFF" if val is False else str(val)  # YAML 1.1: OFF sin comillas se lee como booleano
        return base
