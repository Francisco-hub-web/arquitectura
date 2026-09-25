---
id: KB_17
slug: observabilidad
title: Observabilidad de Data Products — 5 pilares, impacto e incidentes
version: 1.0.0
status: vigente
tier: 4
sources: ["13-data-observability.md §3-§30", "08 §17, §22"]
applies_to: [data_product_maestro, consumo, ai_ml]
triggers:
  tasks: [observabilidad_alertas, promover_a_produccion]
  paths: ["observability/**", "docs/engineering/runbook*.md"]
  rules: ["GOV-OBS-*", "GOV-STR-008", "GOV-DPD-013", "GOV-DPD-025", "GOV-AIM-006"]
  keywords: [observabilidad, monitoreo, alerta, freshness, volumen, esquema, drift, linaje, impacto, incidente, runbook, sla, slo, health, costo]
depends_on: [KB_00]
related: [KB_08, KB_18]
token_budget: 900
deterministic_rules: [GOV-OBS-001, GOV-OBS-002, GOV-OBS-003, GOV-OBS-004, GOV-OBS-005, GOV-OBS-006, GOV-OBS-007, GOV-STR-008]
---
# KB_17 · Observabilidad
> No se puede confiar en un Data Product que no puede observarse: del síntoma al impacto y del impacto a la acción.

## R · Reglas canónicas
- **KB17.R1 [MUST]** 5 pilares base: freshness, volumen, esquema/contrato, calidad, linaje/impacto. (13 §9)
- **KB17.R2 [MUST]** Un pipeline exitoso no garantiza un producto confiable: observar pipelines, datasets, el producto como unidad, el consumo y la semántica. (13 §8-§12)
- **KB17.R3 [MUST]** Freshness se mide respecto al propósito (ventana de negocio), no solo al último timestamp. (13 §13)
- **KB17.R4 [MUST]** Poder responder qué upstream falló, qué downstream depende, qué dashboards/APIs/modelos se afectan. (13 §17)
- **KB17.R5 [MUST]** Alertas con severidad (crítico, alto, medio, bajo), owner y canal; flujo: detección, clasificación, impacto, notificación, contención, remediación, cierre. (13 §24)
- **KB17.R6 [MUST]** Health indicators del producto (freshness, disponibilidad, reglas críticas, volumen en rango, schema drift, error rate, consumo). (13 §25)
- **KB17.R7 [MUST]** Seguridad observable (accesos anómalos, extracciones masivas) y costos visibles por producto. (13 §22, 01 §12)

## H · Heurísticas de decisión
- **KB17.H1** Umbral de volumen: comparar contra estacionalidad (media móvil del mismo día de semana), no contra un valor fijo.
- **KB17.H2** Si una alerta no tiene acción asociada en el runbook, probablemente es ruido.

## A · Anti-patrones
- **KB17.A1** Monitorear solo infraestructura. · **KB17.A2** Declarar éxito porque el job terminó. · **KB17.A3** Alertas sin severidad ni owner. · **KB17.A4** Herramienta = disciplina.

## V · Preguntas de verificación
1. **KB17.V1** ¿Los umbrales reflejan el propósito del producto y evitan ruido?
2. **KB17.V2** ¿Ante una falla, se puede identificar a los consumidores impactados?

## D · Ya verificado por el motor determinista
Monitores definidos, cobertura de 5 pilares, severidad/owner/canal, health indicators, runbook enlazado, monitores de uso, seguridad y drift.
