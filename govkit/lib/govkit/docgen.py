"""Generación de documentación desde el catálogo (fuente única de verdad → docs/01-matriz-reglas.md)."""
from __future__ import annotations

from collections import Counter, OrderedDict
from typing import Any, Dict

from govkit.model import NATURES

CATEGORY_LABEL = OrderedDict([
    ("estructura", "Estructura de repositorio"), ("nomenclatura", "Nomenclatura"), ("data_product", "Definición de Data Product"),
    ("contratos", "Data Contracts"), ("metadata", "Metadata y catálogo"), ("calidad", "Calidad de datos"),
    ("seguridad", "Seguridad y privacidad"), ("iam", "IAM"), ("dataops", "DataOps y CI/CD"),
    ("arquitectura", "Arquitectura y modelado"), ("semantica", "Semantic layer y métricas"), ("consumo", "Consumo y explotación"),
    ("ai_ml", "AI / ML / GenAI"), ("observabilidad", "Observabilidad"), ("lifecycle", "Ciclo de vida"), ("scoring", "Scoring"),
    ("negocio", "Negocio y casos de uso"), ("openmetadata", "OpenMetadata (pack omd)"),
    ("documentacion", "Documentación del framework (pack docs)"), ("portafolio", "Portafolio cross-repo (pack portfolio)"),
])


def _esc(s: Any) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def rules_markdown(catalog: Dict[str, Any]) -> str:
    rules = catalog["_rules"]
    out = ["# Matriz de Reglas de Gobernanza (generada)", "",
           f"> Generado con `govkit rules --format md` desde `rules/catalog.yaml` · ruleset `{catalog.get('ruleset_version')}` · "
           f"{len(rules)} reglas. No editar a mano: el catálogo es la fuente única de verdad.", "",
           "## 1. Matriz de dos ejes: dominio de gobierno × naturaleza de validación", "",
           "| Dominio | D · Determinista | H · Híbrida | S · Semántica | O · Organizacional | Total | % automatizable (D+H) |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    tot = Counter()
    for cat, label in CATEGORY_LABEL.items():
        c = Counter(r.nature for r in rules if r.category == cat)
        if not c:
            continue
        n = sum(c.values())
        tot.update(c)
        out.append(f"| {label} | {c['D']} | {c['H']} | {c['S']} | {c['O']} | {n} | {round(100 * (c['D'] + c['H']) / n)}% |")
    n = sum(tot.values())
    out.append(f"| **Total** | **{tot['D']}** | **{tot['H']}** | **{tot['S']}** | **{tot['O']}** | **{n}** | "
               f"**{round(100 * (tot['D'] + tot['H']) / n)}%** |")
    out += ["", "Naturalezas: " + " · ".join(f"**{k}** = {v}" for k, v in NATURES.items()), "",
            "## 2. Matriz de técnica de verificación × punto de control", "",
            "| Técnica | pre-commit | pr | gate | catalog | periodic | runtime |", "|---|---:|---:|---:|---:|---:|---:|"]
    techs = sorted({r.technique for r in rules})
    for t in techs:
        row = [sum(1 for r in rules if r.technique == t and e in r.enforcement)
               for e in ("pre-commit", "pr", "gate", "catalog", "periodic", "runtime")]
        out.append(f"| `{t}` | " + " | ".join(str(x) for x in row) + " |")
    out += ["", "## 3. Catálogo completo por dominio", ""]
    for cat, label in CATEGORY_LABEL.items():
        rs = [r for r in rules if r.category == cat]
        if not rs:
            continue
        out += [f"### {label}", "", "| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |",
                "|---|---|:-:|---|---|---|---|---|---|"]
        for r in rs:
            st = ", ".join(f"{k}:{v}" for k, v in r.stages.items()) if r.stages else "—"
            src = f"{r.source.get('doc', '')} {r.source.get('section', '')}"
            out.append(f"| `{r.id}` | {_esc(r.title)} | {r.nature} | {r.severity} | {_esc(st)} | {r.technique} | "
                       f"{', '.join(r.enforcement)} | {_esc(src)} | {', '.join(r.kb)} |")
        out.append("")
    out += ["## 4. Preguntas semánticas (reglas S e H) entregadas al revisor LLM", ""]
    for r in rules:
        if r.semantic_question:
            out.append(f"- `{r.id}` ({r.nature}) — {_esc(r.semantic_question)}")
    return "\n".join(out) + "\n"
