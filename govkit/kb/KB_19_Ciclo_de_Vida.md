---
id: KB_19
slug: ciclo_de_vida
title: Ciclo de vida del Data Product (12 estados y gates)
version: 1.0.0
status: vigente
tier: 6
sources: ["18-data-product-lifecycle.md §3-§33", "06-data-product-definition.md §26"]
applies_to: [data_product_maestro, consumo, ai_ml]
triggers:
  tasks: [promover_a_produccion, evolucionar_version, retirar_consolidar, nuevo_data_product]
  paths: ["metadata/catalog/data_product.yaml"]
  rules: ["GOV-LCY-*", "GOV-DPD-015", "GOV-DPD-027", "GOV-DPD-028", "GOV-PRT-002", "GOV-PRT-006", "GOV-CNS-011"]
  keywords: [ciclo de vida, lifecycle, estado, transición, gate, producción, evolución, consolidación, retiro, deprecación, definition of ready, definition of done]
depends_on: [KB_00, KB_04]
related: [KB_20, KB_03]
token_budget: 950
deterministic_rules: [GOV-LCY-001, GOV-LCY-002, GOV-LCY-003, GOV-LCY-004, GOV-LCY-005, GOV-DPD-027, GOV-DPD-028]
---
# KB_19 · Ciclo de vida
> Un Data Product no termina cuando se construye: entra en operación, medición, mejora y eventual evolución, consolidación o retiro.

## R · Reglas canónicas
- **KB19.R1 [MUST]** 12 estados: identificado, en definición, candidato a priorización, priorizado, en diseño, en desarrollo, listo para producción, productivo, en evolución, en consolidación, en retiro, retirado. (18 §9)
- **KB19.R2 [MUST]** Transiciones con criterio explícito: identificado→definición (necesidad + sponsor); definición→candidato (capacidad, dominio, valor); priorizado→diseño (seleccionado en roadmap); diseño→desarrollo (DoR); desarrollo→listo (mínimos técnicos y de gobierno); productivo→evolución/retiro (decisión formal). (18 §22)
- **KB19.R3 [MUST]** Listo para producción exige: scoring mínimo, calidad crítica, metadata publicada, clasificación, observabilidad básica, contrato, ownership y runbook. (18 §16)
- **KB19.R4 [MUST]** Producción no es "terminado": seguimiento de salud, scoring, valor/adopción, incidentes y ownership vigente. (18 §17)
- **KB19.R5 [MUST]** Evolución: evaluar si mantiene el propósito, si es MAJOR o si amerita un nuevo producto. (18 §18)
- **KB19.R6 [MUST]** Consolidación ante solapamientos: revisar contratos/consumidores, decidir producto sobreviviente, migrar, actualizar catálogo. (18 §19)
- **KB19.R7 [MUST]** Retiro gobernado: comunicar, fechar, despublicar para usos nuevos, migrar consumidores, mantener trazabilidad; retirado = deprecated/retired en catálogo. (18 §20-§21, §27)

## H · Heurísticas de decisión
- **KB19.H1** Usar `govkit gate --to <estado>` antes de cada transición: el gate evalúa el repo con las severidades del estado destino.
- **KB19.H2** No conservar productos muertos "porque costó construirlos"; baja adopción sostenida ⇒ retiro o consolidación. (18 §31)

## A · Anti-patrones
- **KB19.A1** Producto como proyecto cerrado. · **KB19.A2** Producción sin readiness. · **KB19.A3** Limbo permanente entre definición y ejecución. · **KB19.A4** Retiros silenciosos.

## V · Preguntas de verificación
1. **KB19.V1** ¿La evolución propuesta mantiene el propósito del producto?
2. **KB19.V2** ¿El retiro deja a todos los consumidores con alternativa y comunicación?

## D · Ya verificado por el motor determinista
Estado válido, transición permitida (diff git), retiro gobernado, estado de catálogo, mínimos de scoring, DoR y DoD compuestos.
