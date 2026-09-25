---
id: KB_02
slug: casos_de_uso
title: Definición de casos de uso de datos
version: 1.0.0
status: vigente
tier: 1
sources: ["02.2-use-case-definition.md §3-§21"]
applies_to: [portafolio, data_product_maestro, consumo]
triggers:
  tasks: [caso_de_uso, nuevo_data_product, priorizar]
  paths: ["**/use_cases/*.yaml"]
  rules: ["GOV-BIZ-002", "GOV-BIZ-003", "GOV-BIZ-004", "GOV-BIZ-006", "GOV-BIZ-007", "GOV-BIZ-008"]
  keywords: [caso de uso, kpi, decisión, problema, oportunidad, valor, dashboard, workshop]
depends_on: [KB_00]
related: [KB_01, KB_04]
token_budget: 850
deterministic_rules: [GOV-BIZ-002, GOV-BIZ-003, GOV-BIZ-004, GOV-BIZ-006, GOV-BIZ-007, GOV-BIZ-008]
---
# KB_02 · Casos de uso
> Un caso de uso se justifica por la decisión, proceso o resultado que mejora, no por la tecnología.

## R · Reglas canónicas
- **KB02.R1 [MUST]** Estructura: capacidad → problema/oportunidad → decisión o proceso → KPI → necesidad de datos → Data Product(s) → consumo/activación. (02.2 §7)
- **KB02.R2 [MUST]** Mínimo para pasar a priorización: problema explícito, capacidad, dominio, decisión/proceso, KPI o resultado, consumidores identificados e hipótesis de Data Product. (02.2 §10)
- **KB02.R3 [MUST]** Tipos: informacional, decisional, operacional, AI/predictivo. (02.2 §8)
- **KB02.R4 [MUST]** Calidad del caso: específico, trazable, valioso, implementable y medible. (02.2 §15)
- **KB02.R5 [MUST]** Un caso tiene un dominio principal aunque cruce varios. (02.2 §12)
- **KB02.R6 [MUST]** Regla final: si no explica qué problema resuelve, qué decisión mejora y qué KPI impacta, no está listo para ser Data Product. (02.2 §21)

## H · Heurísticas de decisión
- **KB02.H1** "Necesitamos un dashboard" → preguntar: ¿qué decisión?, ¿quién la toma?, ¿con qué frecuencia?, ¿qué KPI cambia?
- **KB02.H2** Un caso puede requerir varios Data Products (ej. Promotion Effectiveness = Sales Transactions + Product Catalog + Pricing Elasticity). Reutiliza antes de crear.
- **KB02.H3** En workshops no abrir discusión técnica: mantener foco en valor y decisiones. (02.2 §17)

## A · Anti-patrones (señales)
- **KB02.A1** Formulación como herramienta sin decisión ni KPI. · **KB02.A2** "Hacer AI" sin problema concreto.
- **KB02.A3** Sin capacidad o dominio. · **KB02.A4** Sin consumidores. · **KB02.A5** Casos tan amplios que no se pueden medir. (02.2 §19)

## E · Ejemplo mínimo
✔ "Pricing necesita decidir semanalmente qué promociones extender; KPI: uplift y margen promocional; DP: Promotion Effectiveness."
✘ "Queremos un tablero de promociones con todos los datos."

## V · Preguntas de verificación
1. **KB02.V1** ¿El problema describe una situación de negocio medible (línea base) y no una herramienta?
2. **KB02.V2** ¿La decisión tiene actor, frecuencia y acción concretos?
3. **KB02.V3** ¿La hipótesis de valor tiene meta y horizonte?

## D · Ya verificado por el motor determinista
Presencia de caso de uso, KPI, hipótesis, problema y decisión; tipo válido; detección léxica de "necesitamos un dashboard/hacer AI".
