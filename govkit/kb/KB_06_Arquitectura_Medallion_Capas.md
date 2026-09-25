---
id: KB_06
slug: arquitectura_capas
title: Lakehouse Medallion, serving y desacople
version: 1.0.0
status: vigente
tier: 3
sources: ["02-data-strategy.md §11-§12", "08 §10", "10 §16", "14 §8.2, §11", "lineamientos/estructura-repositorio.md src/, pipelines/", "01 §5, §8, §11"]
applies_to: [data_product_maestro, consumo]
triggers:
  tasks: [modelar_silver_odm, modelar_gold_dimensional, pipeline_cicd_repo, exponer_consumo]
  paths: ["src/**", "pipelines/**", "modeling/**"]
  rules: ["GOV-ARC-001", "GOV-ARC-002", "GOV-ARC-004", "GOV-ARC-005", "GOV-ARC-011", "GOV-ARC-014", "GOV-DPD-021", "GOV-QLT-005", "GOV-QLT-014"]
  keywords: [bronze, silver, gold, semantic, serving, capa, medallion, lakehouse, time travel, iceberg, delta, batch, streaming, particionamiento]
depends_on: [KB_00]
related: [KB_07, KB_14, KB_08]
token_budget: 950
deterministic_rules: [GOV-ARC-001, GOV-ARC-002, GOV-ARC-004, GOV-ARC-005, GOV-OPS-007, GOV-OPS-011]
---
# KB_06 · Arquitectura por capas
> Almacenamiento, procesamiento y consumo son capas independientes; el consumidor nunca depende de estructuras físicas.

## R · Reglas canónicas
- **KB06.R1 [MUST]** Bronze: crudo, auditable, inmutable respecto al origen, acceso muy restringido; calidad = esquema, recepción, volumen, parsing. (02 §12, 08 §10.1, 10 §16.1)
- **KB06.R2 [MUST]** Silver: normalización, limpieza y canonicidad (ARTS ODM cuando aplique); integridad referencial, deduplicación, claves de negocio, consistencia entre fuentes. (08 §10.2)
- **KB06.R3 [MUST]** Gold: Data Products orientados a consumo, reglas de negocio completas, métricas validadas, freshness según SLA. (08 §10.3)
- **KB06.R4 [MUST]** Semantic: métricas y dimensiones gobernadas; Serving: 6 tipos (analítica, semántica, operacional, exportación, activación, ML). (14 §11)
- **KB06.R5 [MUST NOT]** Ningún consumo desde Bronze ni desde tablas temporales de ingesta; APIs nunca directo sobre Delta/Parquet en object storage. (14 §8.2, §10.5)
- **KB06.R6 [MUST]** Datos críticos sin sobrescritura destructiva; formatos con Time Travel (Iceberg/Delta/Hudi). (01 §5)
- **KB06.R7 [MUST]** Silver→Gold se transforma en dbt (fuente de verdad); orquestación versionada en Step Functions. (Estructura de Repositorio)
- **KB06.R8 [MUST]** Batch, streaming o CDC se elige por el valor de negocio del caso de uso. (01 §11)

## H · Heurísticas de decisión
- **KB06.H1** Si la decisión se toma una vez al día, la latencia horaria o real-time no se justifica: exige evidencia de valor.
- **KB06.H2** Reproceso seguro = MERGE idempotente + time travel, no overwrite.
- **KB06.H3** [PRÁCTICA] Particionar por la columna de filtro dominante (fecha de negocio) y, en exportación, por `año/mes/día/país` (14 §11.4). El framework no norma una política general de particionamiento (ver hallazgo documental).

## A · Anti-patrones
- **KB06.A1** Saltar capas (Gold desde Bronze). · **KB06.A2** Lógica de negocio en Bronze. · **KB06.A3** `SELECT *` como interfaz.
- **KB06.A4** Dashboards conectados a capas técnicas. · **KB06.A5** Real-time "por si acaso".

## V · Preguntas de verificación
1. **KB06.V1** ¿Cada transformación está en la capa que corresponde a su propósito?
2. **KB06.V2** ¿La latencia elegida está justificada por la decisión de negocio?
3. **KB06.V3** ¿El reproceso preserva historia (sin pérdida destructiva)?

## D · Ya verificado por el motor determinista
Lectura de Bronze desde Gold/Semantic, `SELECT *`, overwrite/truncate/drop (AST y SQL), formato con Time Travel, dbt como única vía Silver→Gold, ASL versionado.
