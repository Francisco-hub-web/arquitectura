---
id: KB_09
slug: metadata_catalogo
title: Metadata como control plane, glosario, tags y linaje
version: 1.0.0
status: vigente
tier: 4
sources: ["01-data-principles.md §3", "09-metadata-governance.md §3-§29", "15-dataops-cicd.md §9, §18", "06 §17-§18, §28"]
applies_to: [data_product_maestro, consumo, ai_ml]
triggers:
  tasks: [catalogar_openmetadata, nuevo_data_product, definir_metrica_semantica]
  paths: ["metadata/**"]
  rules: ["GOV-MET-*", "GOV-NAM-013", "GOV-LCY-004", "GOV-DPD-026"]
  keywords: [metadata, catálogo, openmetadata, glosario, término, tag, taxonomía, linaje, lineage, descripción, steward, descubrimiento]
depends_on: [KB_00]
related: [KB_21, KB_03, KB_12]
token_budget: 1000
deterministic_rules: [GOV-DPD-001, GOV-MET-001, GOV-MET-006, GOV-MET-007, GOV-MET-008, GOV-MET-009, GOV-MET-011, GOV-MET-012, GOV-MET-015]
---
# KB_09 · Metadata y catálogo
> La metadata es la capa de control del ecosistema; un usuario debe encontrar, entender, confiar y contextualizar un Data Product en pocos minutos.

## R · Reglas canónicas
- **KB09.R1 [MUST]** Tipos: técnica, de negocio, operativa, de gobierno y relacional; no separarlas hasta volverlas irreconciliables. (09 §8, §27)
- **KB09.R2 [MUST]** Metadata mínima del Data Product: nombre, descripción, capacidad, dominio, subdominio, owner de negocio, steward, consumidores, caso de uso, clasificación, datasets, glosario, linaje, SLA/freshness, estado y criticidad. (09 §10)
- **KB09.R3 [MUST]** Glosario: término, definición, contexto, owner, relacionados, métricas asociadas, dominio; un término crítico no tiene múltiples definiciones no gobernadas. (09 §12)
- **KB09.R4 [MUST]** Taxonomía de tags controlada (dominio, tipo de activo, criticidad, sensibilidad, entorno, estado, país/BU, consumo, lifecycle); sin proliferación caótica. (09 §13)
- **KB09.R5 [MUST]** Linaje mínimo: Fuente → ingestión → Bronze → Silver → Gold/Semantic/Serving → consumidor; declarado aunque aún no se capture automáticamente. (06 §18, 09 §14)
- **KB09.R6 [MUST]** Metadata as code: `domain`, `data_product`, `owners`, `glossary`, `tags`, `openmetadata`, `data_quality`, `lineage` versionados en el repo y sincronizados a OpenMetadata por proceso controlado. GitHub = cambio técnico; OpenMetadata = contexto, descubrimiento y gobierno. (15 §9, §18)
- **KB09.R7 [MUST]** Calidad de la metadata: completitud, owner vigente, descripción útil, clasificación, dominio correcto, linaje mínimo, vínculos entre activos; revisión continua por producto y periódica por dominio. (09 §22, §24)

## H · Heurísticas de decisión
- **KB09.H1** Descripción útil = qué es + para qué sirve + granularidad + exclusiones; si solo repite el nombre, no es útil.
- **KB09.H2** Si un término ya existe en el glosario corporativo, referenciarlo; si difiere, proponer la diferencia explícita al Data Steward.
- **KB09.H3** OpenMetadata no reemplaza portafolio, priorización ni roadmap: es la plataforma operativa de metadata. (09 §15)

## A · Anti-patrones
- **KB09.A1** Catálogo como inventario estático. · **KB09.A2** Descripciones vacías o sin contexto. · **KB09.A3** Linaje manual nunca revisado.
- **KB09.A4** "Instalar la plataforma" = resolver metadata governance. (09 §27)

## V · Preguntas de verificación
1. **KB09.V1** ¿La descripción de negocio, el glosario y los contratos describen el mismo objeto (granularidad, universo, exclusiones)?
2. **KB09.V2** ¿Los términos asociados son los que un consumidor buscaría para encontrar el producto?

## D · Ya verificado por el motor determinista
Ficha, glosario (estructura y resolución), tags controlados, linaje ordenado, mapeo OpenMetadata, criticidad, emails, frescura de la metadata, composite "catalogable".
