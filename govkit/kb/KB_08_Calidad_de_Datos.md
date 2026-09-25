---
id: KB_08
slug: calidad_datos
title: Calidad de datos — dimensiones, reglas, severidades y quality gates
version: 1.0.0
status: vigente
tier: 4
sources: ["01-data-principles.md §4", "08-data-quality-framework.md §6-§29"]
applies_to: [data_product_maestro, consumo, ai_ml]
triggers:
  tasks: [reglas_calidad, promover_a_produccion, modelar_silver_odm, modelar_gold_dimensional]
  paths: ["quality/**", "tests/data_quality/**"]
  rules: ["GOV-QLT-*", "GOV-ARC-007", "GOV-CNS-009", "GOV-CNS-010"]
  keywords: [calidad, completitud, unicidad, consistencia, validez, integridad referencial, freshness, exactitud, trazabilidad, umbral, severidad, quality gate, incidente, cuadratura]
depends_on: [KB_00]
related: [KB_17, KB_06, KB_05]
token_budget: 1050
deterministic_rules: [GOV-QLT-001, GOV-QLT-002, GOV-QLT-003, GOV-QLT-004, GOV-QLT-006, GOV-QLT-007, GOV-QLT-008, GOV-QLT-009, GOV-QLT-010, GOV-QLT-011, GOV-QLT-013]
---
# KB_08 · Calidad de datos
> La calidad es un requisito funcional transversal al ciclo de vida, contextual al uso, y nunca una corrección manual en el consumo.

## R · Reglas canónicas
- **KB08.R1 [MUST]** Calidad = grado en que el dato cumple expectativas explícitas para el propósito que habilita; un dato apto para exploración puede no serlo para reporting ejecutivo, pricing o AI. (08 §6)
- **KB08.R2 [MUST]** 8 dimensiones: completitud, unicidad, consistencia, validez, integridad referencial, freshness, exactitud, trazabilidad; cada producto elige las que aplican a su propósito. (08 §9)
- **KB08.R3 [MUST]** Por capa: Bronze (esquema, recepción, volumen, parsing) · Silver (integridad referencial, dedup, conformidad, claves) · Gold (reglas de negocio, consistencia semántica, freshness SLA) · Semantic (métricas y KPIs validados) · Serving (SLA de entrega, RLS efectiva) · Feature (batch/online, leakage, estabilidad). (08 §10)
- **KB08.R4 [MUST]** Cada regla: nombre, descripción, dimensión, capa, objeto, umbral, severidad, acción, owner. (08 §12)
- **KB08.R5 [MUST]** Severidad crítica invalida el consumo o la promoción; alta permite disponibilidad condicionada; media continúa con backlog; baja se monitorea. Acciones: bloquear pipeline, bloquear promoción, publicar con warning, alertar, registrar incidente, abrir backlog. (08 §13)
- **KB08.R6 [MUST]** Quality gates obligatorios en Pricing, Supply, Finance, Customer y productos que alimenten AI o decisiones ejecutivas; todo gate tiene criterio de aprobación. (08 §14)
- **KB08.R7 [MUST]** SLOs cuantificados en ≥3 dimensiones y al menos una regla crítica; sin reglas críticas no hay industrialización. (01 §4, 08 §12)
- **KB08.R8 [MUST]** Incidentes: detección, clasificación, impacto, contención, remediación, comunicación, causa raíz, mejora preventiva. (08 §22)

## H · Heurísticas de decisión
- **KB08.H1** Severidad = impacto del incumplimiento en la decisión que habilita el producto, no la dificultad técnica.
- **KB08.H2** Productos inmaduros: empezar por reglas críticas; no imponer reglas particulares sin distinguir lo crítico (08 §27).
- **KB08.H3** Umbral 100% solo donde el negocio no tolera excepciones (claves); en montos o referencias externas, usar umbrales realistas con alerta.

## A · Anti-patrones
- **KB08.A1** Validar solo al final en BI. · **KB08.A2** Umbrales implícitos o de "sentido común". · **KB08.A3** No distinguir severidades.
- **KB08.A4** Calidad desconectada de observabilidad. · **KB08.A5** Filtros en el tablero para ocultar errores del maestro. (08 §27, 14 §8.8)

## V · Preguntas de verificación
1. **KB08.V1** ¿Umbrales y severidades son coherentes con el consumo (ejecutivo, operacional, AI) y la criticidad?
2. **KB08.V2** ¿Las reglas críticas cubren lo que invalidaría la decisión de negocio?
3. **KB08.V3** ¿Cada regla está en la capa correcta?

## D · Ya verificado por el motor determinista
Ficha de calidad, 9 atributos por regla, enums, ≥3 dimensiones cuantificadas, regla crítica, coherencia severidad-acción, gates, alertas, objetos resolubles contra contratos, tests ejecutables.
