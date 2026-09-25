---
id: KB_13
slug: consumo_patrones
title: Consumo — 12 patrones de Data Product Analítico y selección
version: 1.0.0
status: vigente
tier: 5
sources: ["14-data-consumption-exploitation-framework.md §3, §7-§9, §13-§15"]
applies_to: [consumo]
triggers:
  tasks: [exponer_consumo, caso_de_uso]
  paths: ["publishing/**"]
  rules: ["GOV-CNS-001", "GOV-CNS-002", "GOV-CNS-003", "GOV-CNS-004", "GOV-CNS-012", "GOV-CNS-013", "GOV-CNS-014", "GOV-DPD-006", "GOV-PRT-004"]
  keywords: [consumo, dashboard, bi ejecutivo, reporting, autoservicio, exploración, api, embebida, extracción, excel, reverse etl, activación, patrón, plataforma, power bi, microstrategy, looker]
depends_on: [KB_00]
related: [KB_14, KB_12]
token_budget: 1100
deterministic_rules: [GOV-CNS-001, GOV-CNS-002, GOV-CNS-003, GOV-CNS-004, GOV-CNS-012]
---
# KB_13 · Patrones de consumo
> Todo mecanismo de consumo responde al caso de uso, la audiencia y el patrón de explotación — no a la inercia tecnológica.

## R · Reglas canónicas
- **KB13.R1 [MUST]** Secuencia obligatoria: Caso de uso → Objetivo → Tipo de consumidor → Patrón → Requerimientos no funcionales → Data Product maestro / Serving → Plataforma. (14 §8.4)
- **KB13.R2 [MUST]** El Data Product analítico de consumo es el activo (con contrato, SLA, ownership y metadata); la herramienta es solo plataforma de exposición. (14 §8.4)
- **KB13.R3 [MUST]** Solo se alimenta de Data Products maestros certificados; nunca de fuentes transaccionales, Bronze ni archivos locales. (14 §8.2)
- **KB13.R4 [MUST]** Clasificar en 12 dimensiones: audiencia, objetivo, interacción, volumen, granularidad, latencia, frecuencia, concurrencia, acción, criticidad, seguridad, reutilización. (14 §13)
- **KB13.R5 [MUST]** Patrón → plataforma: BI ejecutivo (Power BI/Looker/MicroStrategy) · BI de gestión (Power BI/Looker) · Reporting administrado (MicroStrategy/PBI Paginated) · Regulatorio (plataformas financieras/MicroStrategy) · Self-service (PBI Shared Datasets/Looker Explores) · Exploración alto volumen (Databricks SQL/Athena/BigQuery/Snowflake) · App operacional (web app + Serving DB) · API operacional (REST/gRPC + clave-valor, <100 ms) · Embebida (PBI/Looker Embedded) · Extracción masiva (S3/ADLS/SFTP, Parquet) · Reverse ETL (Census/Hightouch) · AI/ML (Feature Store/Delta). (14 §9, §14)
- **KB13.R6 [MUST]** Reglas de decisión: BI solo para visualizar/monitorear; editar o aprobar ⇒ app operacional; SQL complejo ⇒ exploración; descargas masivas ⇒ extracción asíncrona (prohibido Power BI/MicroStrategy); integración entre sistemas ⇒ API o eventos; activación ⇒ reverse ETL validado. (14 §15)
- **KB13.R7 [MUST]** Reutilizar antes de crear: no se autorizan productos redundantes si existe uno publicado o un modelo semántico certificado adecuado. (14 §8.6)

## H · Heurísticas de decisión
- **KB13.H1** "Necesito exportar a Excel" casi nunca es BI: es extracción masiva o exploración.
- **KB13.H2** Si el usuario "filtra por país" duplicando dashboards → RLS en la serving layer.
- **KB13.H3** Detalle transaccional no justifica un dashboard; resumir en la serving layer.

## A · Anti-patrones
- **KB13.A1** BI como almacén de datos. · **KB13.A2** Exportaciones manuales como integración. · **KB13.A3** Copias de un dashboard por filtro.

## V · Preguntas de verificación
1. **KB13.V1** Dadas audiencia, interacción, volumen, latencia y acción, ¿el patrón elegido es el de la matriz?
2. **KB13.V2** ¿Existe ya un producto o modelo semántico certificado que lo resuelva?

## D · Ya verificado por el motor determinista
Patrón declarado, 12 dimensiones, plataforma permitida/prohibida por patrón, fuentes solo maestras, granularidad transaccional en BI.
