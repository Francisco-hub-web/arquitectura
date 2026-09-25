---
id: KB_04
slug: definicion_data_product
title: Definición del Data Product (ficha maestra, DoR, DoD, niveles)
version: 1.0.0
status: vigente
tier: 2
sources: ["06-data-product-definition.md §6-§30", "14-data-consumption-exploitation-framework.md §8.3"]
applies_to: [data_product_maestro, consumo]
triggers:
  tasks: [nuevo_data_product, promover_a_produccion, evolucionar_version]
  paths: ["metadata/catalog/data_product.yaml", "README.md"]
  rules: ["GOV-DPD-*", "GOV-STR-007"]
  keywords: [ficha, data product, definition of ready, definition of done, bloque, tipo, estado, mvp, industrializado, estratégico]
depends_on: [KB_00]
related: [KB_03, KB_05, KB_19, KB_20]
token_budget: 1000
deterministic_rules: [GOV-DPD-001, GOV-DPD-002, GOV-DPD-004, GOV-DPD-005, GOV-DPD-013, GOV-DPD-018, GOV-DPD-019, GOV-DPD-027, GOV-DPD-028]
---
# KB_04 · Definición del Data Product
> Un Data Product está definido cuando su valor, contrato, calidad, metadata, linaje, seguridad y operación son suficientemente claros para implementarlo y gobernarlo.

## R · Reglas canónicas
- **KB04.R1 [MUST]** No es solo un dataset ni un pipeline: es una unidad de entrega con propósito, owner, consumidores, contrato, calidad, metadata/linaje, seguridad, observabilidad y lifecycle. (06 §6)
- **KB04.R2 [MUST]** Tipos: Analytical, Operational, SaaS-driven, AI/ML, Semantic/Metrics. Rol: maestro (publica datos de dominio) o analítico de consumo (tablero/API/export/activación). (06 §7, 14 §8.3)
- **KB04.R3 [MUST]** La ficha cubre 20 bloques: identificación, contexto de negocio, problema/valor, ownership, contrato, inputs, outputs, modelo/semántica, transformaciones, calidad, metadata, linaje, seguridad, observabilidad, semantic layer, AI readiness, SLA/retención, dependencias, certificación, DoR/DoD.
- **KB04.R4 [MUST]** Bloque 9 (transformaciones): documentar reglas de negocio, deduplicaciones, unificaciones, supuestos e inclusión/exclusión — crítico en Customer 360, Promotion Effectiveness, Demand Forecast, Executive KPI Layer, Pricing Elasticity. (06 §15)
- **KB04.R5 [MUST]** Definition of Ready: capacidad y dominio claros, caso de uso estructurado, owner funcional, inputs/outputs, hipótesis de valor, contrato base, arquitectura definida (final o transicional), dependencias críticas conocidas. (06 §26)
- **KB04.R6 [MUST]** Definition of Done: ownership, dominio/alcance, contrato, metadata, linaje, calidad, acceso/seguridad, observabilidad, semántica/consumo, SLA/SLO, retención/lifecycle, DataOps y modularización. (06 §26)
- **KB04.R7 [MUST]** Niveles objetivo: MVP, Industrializado, Estratégico; la certificación exige owner, metadata mínima, contrato, reglas críticas, clasificación, linaje mínimo, observabilidad básica, consumidor activo/validado y cumplimiento del playbook. (06 §25)
- **KB04.R8 [MUST NOT]** No aplica a tablas temporales, datasets internos de transformación ni salidas efímeras. (06 §4)

## H · Heurísticas de decisión
- **KB04.H1** Si el producto tiene más de un dominio principal o consumidores con contratos incompatibles, evaluar dividirlo.
- **KB04.H2** Si dos productos comparten la mayor parte de sus outputs y consumidores, evaluar consolidación (18 §19).
- **KB04.H3** La descripción debe permitir a un consumidor entender en <1 minuto qué es, qué decisión habilita y qué NO incluye.

## A · Anti-patrones
- **KB04.A1** Data Product = tabla. · **KB04.A2** Sin contrato. · **KB04.A3** Sin calidad o sensibilidad definidas.
- **KB04.A4** Sin nivel de madurez. · **KB04.A5** Productos tan amplios que no se pueden implementar ni gobernar. (06 §29)

## V · Preguntas de verificación
1. **KB04.V1** ¿Las reglas de transformación (Bloque 9) son suficientes para que negocio y datos entiendan cómo se forma el significado?
2. **KB04.V2** ¿El alcance está delimitado (qué incluye y qué excluye) y es implementable?
3. **KB04.V3** ¿El nivel objetivo es coherente con la criticidad y el consumo declarados?

## D · Ya verificado por el motor determinista
Existencia y esquema de la ficha, ID, versión, tipo, rol, SLA, inputs/outputs, DoR y DoD (compuestos), costos, retención.
