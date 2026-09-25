---
id: KB_20
slug: scoring_madurez
title: Scoring de madurez, salud y readiness (11 pilares)
version: 1.0.0
status: borrador
tier: 6
sources: ["19-scoring-model.md §3-§39 (Draft, pendiente de alinear con la Planilla de Certificación)", "08 §24"]
applies_to: [data_product_maestro, consumo, ai_ml]
triggers:
  tasks: [scoring_evaluacion, promover_a_produccion]
  paths: ["metadata/catalog/scorecard.yaml"]
  rules: ["GOV-SCO-*", "GOV-LCY-005", "GOV-DPD-012", "GOV-DPD-014"]
  keywords: [scoring, score, madurez, pilar, evidencia, certificación, salud, readiness, ponderación, clasificación, estratégico]
depends_on: [KB_00]
related: [KB_19, KB_04]
token_budget: 900
deterministic_rules: [GOV-SCO-001, GOV-SCO-002, GOV-SCO-003, GOV-SCO-004, GOV-SCO-005, GOV-LCY-005]
---
# KB_20 · Scoring
> El checklist captura la evidencia; el scoring la convierte en gobierno. Producción no implica madurez.

## R · Reglas canónicas
- **KB20.R1 [MUST]** 11 pilares (peso): Business Alignment 10, Product Definition 10, Data Contract 8, Data Quality 12, Metadata & Governance 10, Security & Privacy 10, Observability & Operations 12, DataOps 10, Semantic 6, AI/ML 6, Value & Adoption 6. Escala 1-5. (19 §10-§11, §25)
- **KB20.R2 [MUST]** Clasificación global: <2 inmaduro · 2-2.9 básico · 3-3.9 gestionado · 4-4.4 avanzado · ≥4.5 estratégico/industrializado. (19 §26)
- **KB20.R3 [MUST]** Mínimos por estado: diseño (BA≥3, PD≥3); desarrollo (PD≥3, contrato/calidad/seguridad/DataOps≥2); productivo (calidad, metadata, seguridad, observabilidad, DataOps ≥3); estratégico (global≥4 y metadata, calidad, observabilidad, valor ≥4). (19 §27)
- **KB20.R4 [MUST]** Score basado en evidencia verificable; sin evidencia es provisional. Evaluación colaborativa (no unilateral), trimestral en productivo y tras incidentes mayores. (19 §28-§30)
- **KB20.R5 [MUST]** Un producto no es estratégico sin mínimos de calidad medidos (Minimum Blockers de la Certification Gate). (08 §24)

## H · Heurísticas de decisión
- **KB20.H1** Alto valor + baja madurez ⇒ foco de inversión; alto valor + baja salud ⇒ riesgo; alta madurez + baja adopción ⇒ revisar estrategia de consumo. (19 §31)
- **KB20.H2** govkit entrega un pre-score determinista por pilar evaluado contra el estándar de `productivo`; si el declarado supera la evidencia en >1 punto, el declarado es provisional.
- **KB20.H3** No castigar productos fundacionales por baja adopción final temprana. (19 §33)

## A · Anti-patrones
- **KB20.A1** Scoring como burocracia. · **KB20.A2** Inflar sin evidencia. · **KB20.A3** Reportar solo un número sin pilares.

## V · Preguntas de verificación
1. **KB20.V1** ¿Cada puntaje declarado cita evidencia versionada verificable?
2. **KB20.V2** ¿La brecha principal del producto está en el pilar con mayor peso para su tipo?

## D · Ya verificado por el motor determinista
Scorecard (11 pilares, 1-5), divergencia declarado vs pre-score, vigencia, evaluadores, mínimos por estado y nivel estratégico.
