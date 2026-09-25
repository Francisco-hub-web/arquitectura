---
id: KB_12
slug: semantic_layer
title: Semantic layer, métricas y dimensiones gobernadas
version: 1.0.0
status: vigente
tier: 3
sources: ["01-data-principles.md §9", "11-semantic-layer-framework.md §3-§30", "14 §12, §15.7"]
applies_to: [data_product_maestro, semantic_metrics, consumo]
triggers:
  tasks: [definir_metrica_semantica, exponer_consumo, modelar_gold_dimensional]
  paths: ["modeling/dbt/models/semantic/**", "**/*.lkml", "**/*.dax", "**/*.tmdl", "metadata/catalog/semantic/**", "publishing/**"]
  rules: ["GOV-SML-*", "GOV-DPD-022", "GOV-SEC-010", "GOV-PRT-005"]
  keywords: [semantic layer, métrica, kpi, dimensión, jerarquía, fórmula, glosario, bi, power bi, looker, dax, lookml, metricflow, autoservicio]
depends_on: [KB_00, KB_09]
related: [KB_07, KB_13, KB_14]
token_budget: 1000
deterministic_rules: [GOV-SML-001, GOV-SML-002, GOV-SML-003, GOV-SML-004, GOV-SML-005, GOV-SML-006, GOV-SML-007, GOV-SML-008, GOV-DPD-022]
---
# KB_12 · Semantic layer y métricas
> Los usuarios no consumen tablas: consumen significado de negocio gobernado. Una métrica = una definición oficial.

## R · Reglas canónicas
- **KB12.R1 [MUST]** BI, autoservicio y APIs analíticas no consumen tablas físicas; el Ad Hoc certificado se hace sobre vistas semánticas. (01 §9)
- **KB12.R2 [MUST]** Ficha de métrica: nombre, descripción, tag, fórmula, unidad, granularidad base, agregación, filtros incluidos/excluidos, Data Product fuente, campos usados, owner, término de glosario, sensibilidad. (11 §15)
- **KB12.R3 [MUST]** Ficha de dimensión: nombre, descripción, niveles de jerarquía, clave de negocio, dominio, relaciones entre dominios, Data Product fuente, owner, notas de uso. (11 §16)
- **KB12.R4 [MUST]** Niveles: semántica del maestro (física) → corporativa (KPIs regionales: venta neta, margen, EBITDA, LFL) → de dominio (fill rate, CAC) → del producto analítico (formato, filtros visuales). La corporativa no se modifica unilateralmente. (14 §12)
- **KB12.R5 [MUST]** El BI consume, presenta y explora; no es la fuente de definición de métricas críticas. Cuanto más estratégica la métrica, menos debe depender de un dashboard. (11 §19)
- **KB12.R6 [MUST]** KPIs ejecutivos: definición oficial, owner, glosario, Data Product fuente, linaje y calidad reforzada. (11 §20)
- **KB12.R7 [MUST]** La gobernanza semántica no depende de una herramienta (OSI, dbt, vistas gobernadas, semantic APIs). (11 §26)
- **KB12.R8 [MUST]** Regla final: dos consumidores con valores distintos para la misma métrica sin diferencia justificada = falla. (11 §30)

## H · Heurísticas de decisión
- **KB12.H1** "Ventas" ambiguas: exigir si incluye IVA, anulaciones, devoluciones, marketplace y la fecha de corte (emisión vs negocio).
- **KB12.H2** Variante legítima de una métrica → nombre distinto + justificación explícita, nunca el mismo nombre.
- **KB12.H3** La semantic layer evoluciona incrementalmente: no esperar un modelo total perfecto. (11 §28)

## A · Anti-patrones
- **KB12.A1** Fórmulas duplicadas en dashboards. · **KB12.A2** Semantic layer "solo en Power BI" sin metadata. · **KB12.A3** Métricas sin owner. · **KB12.A4** Jerarquías improvisadas por tablero.

## V · Preguntas de verificación
1. **KB12.V1** ¿La fórmula, filtros y granularidad permiten calcular la métrica de una sola forma?
2. **KB12.V2** ¿La métrica coincide con su término de glosario?
3. **KB12.V3** ¿Alguna medida BI reimplementa lógica que debería vivir en la semantic layer?

## D · Ya verificado por el motor determinista
Ficha de métrica, unicidad (repo y portafolio), no redefinición de corporativas, glosario resoluble, fichas de dimensión y jerarquía, publicación solo desde capas certificadas, medidas corporativas en LookML/DAX/TMDL.
