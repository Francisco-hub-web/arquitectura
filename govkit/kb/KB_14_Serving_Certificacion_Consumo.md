---
id: KB_14
slug: serving_certificacion
title: Serving layers, plataformas y certificación de consumo
version: 1.0.0
status: vigente
tier: 5
sources: ["14-data-consumption-exploitation-framework.md §8.8, §10-§12, §16-§22"]
applies_to: [consumo]
triggers:
  tasks: [exponer_consumo, promover_a_produccion, retirar_consolidar]
  paths: ["publishing/**", "**/*.lkml", "**/*.dax"]
  rules: ["GOV-CNS-005", "GOV-CNS-006", "GOV-CNS-007", "GOV-CNS-008", "GOV-CNS-009", "GOV-CNS-010", "GOV-CNS-011", "GOV-SML-003", "GOV-SML-007", "GOV-SEC-009"]
  keywords: [serving, certificación, api, reverse etl, consentimiento, power bi, microstrategy, looker, huérfano, retiro, filtro local, exportación]
depends_on: [KB_00, KB_13]
related: [KB_12, KB_10, KB_17]
token_budget: 1000
deterministic_rules: [GOV-CNS-005, GOV-CNS-006, GOV-CNS-007, GOV-CNS-008, GOV-CNS-009, GOV-CNS-011]
---
# KB_14 · Serving y certificación del consumo
> El producto analítico no corrige al maestro: consume semántica gobernada desde serving layers optimizadas.

## R · Reglas canónicas
- **KB14.R1 [MUST]** 6 serving layers: analítica (star schema/tablas planas), semántica (métricas/dimensiones), operacional (clave-valor/NoSQL/relacional indexado), exportación (particionada, Parquet/CSV), activación (incremental, CDF), ML (versionado + time travel). (14 §11)
- **KB14.R2 [MUST]** Power BI: no es almacenamiento ni canal de descargas masivas. MicroStrategy: reporting administrado/regulatorio, no exploración ad-hoc nueva. Looker: pasar por la serving de BigQuery. APIs: nunca directo sobre Delta/Parquet. Reverse ETL: auditoría + consentimiento opt-in/opt-out. (14 §10)
- **KB14.R3 [MUST NOT]** Prohibido en el producto analítico corregir nulos, emparejar huérfanos o aplicar filtros de calidad permanentes: se notifica y se corrige en el maestro. (14 §8.8)
- **KB14.R4 [MUST]** Cálculos corporativos una sola vez en la semantic layer o el maestro, heredados sin redefinición local. (14 §15.7)
- **KB14.R5 [MUST]** Certificación (8 validaciones): fuente maestra, semántica, ownership funcional y técnico, arquitectura según matriz, seguridad/RLS/masking, operación con SLA, visor del estado de calidad del maestro, ciclo de vida registrado. (14 §16)
- **KB14.R6 [MUST]** Sin uso registrado en ~2 meses ⇒ candidato a retiro; la observabilidad mide consultas, cómputo y costo por producto. (14 §17, §21)

## H · Heurísticas de decisión
- **KB14.H1** Un filtro `IS NOT NULL` en el tablero es legítimo solo si responde a una regla de negocio documentada; si oculta un defecto, es anti-patrón.
- **KB14.H2** Latencia <100 ms o alta concurrencia ⇒ serving operacional con índice/caché, nunca la tabla analítica.

## A · Anti-patrones
- **KB14.A1** BI como almacén (millones de filas para bajar a Excel). · **KB14.A2** Silos de métricas en DAX/LookML. · **KB14.A3** Productos huérfanos refrescándose sin usuarios.

## V · Preguntas de verificación
1. **KB14.V1** ¿Los filtros del tablero responden a reglas de negocio o esconden problemas del maestro?
2. **KB14.V2** ¿El serving elegido cumple latencia y concurrencia sin tocar la capa analítica pesada?

## D · Ya verificado por el motor determinista
API sobre serving operacional, consentimiento y auditoría en reverse ETL, controles de extracción, visor de calidad, inactividad, composite de certificación, filtros locales (léxico).
