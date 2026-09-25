---
id: KB_01
slug: alineamiento_negocio
title: Alineamiento capacidad → dominio → Data Product
version: 1.0.0
status: vigente
tier: 1
sources: ["02-data-strategy.md §10, §17-§22", "02.1-business-capability-alignment.md §3-§21"]
applies_to: [data_product_maestro, consumo, portafolio]
triggers:
  tasks: [nuevo_data_product, caso_de_uso, priorizar]
  paths: ["metadata/catalog/data_product.yaml"]
  rules: ["GOV-BIZ-*", "GOV-ARC-006"]
  keywords: [capacidad, mapa de capacidades, dominio, subdominio, estrategia, priorización, sponsor, alineamiento]
depends_on: [KB_00]
related: [KB_02, KB_03]
token_budget: 900
deterministic_rules: [GOV-BIZ-001, GOV-BIZ-005, GOV-ARC-006, GOV-MET-004, GOV-MET-005]
---
# KB_01 · Alineamiento de negocio
> Toda iniciativa de datos se traza a una capacidad de negocio; si no, no es estratégica.

## R · Reglas canónicas
- **KB01.R1 [MUST]** Cadena de trazabilidad: Capacidad → cluster → dominio → subdominio → caso de uso → Data Product → métrica/decisión/automatización. (02.1 §6)
- **KB01.R2 [MUST]** Un Data Product pertenece a un dominio principal aunque sirva a varias capacidades. (02.1 §7)
- **KB01.R3 [SHOULD]** No forzar correspondencia 1:1 entre subcapacidad y dominio si rompe la gobernabilidad. (02.1 §7)
- **KB01.R4 [MUST]** Una capacidad se vuelve dominio si: agrupa entidades coherentes, tiene ownership funcional claro, genera varias necesidades de consumo, sostiene >1 Data Product y es un boundary útil. (02.1 §9)
- **KB01.R5 [MUST]** Un subdominio exige separación clara en entidades, procesos, ownership, consumidores o semántica. (02.1 §10)
- **KB01.R6 [MUST]** Una necesidad se vuelve Data Product si habilita una decisión/proceso concreto, tiene consumidores identificables, requiere datos curados, admite SLA/SLO y su valor es medible. (02.1 §11)
- **KB01.R7 [SHOULD]** Tipificar la capacidad: consumidora, generadora, analítica o habilitadora; Data & Analytics es habilitadora y no concentra el ownership funcional. (02.1 §12, §14)
- **KB01.R8 [MUST]** El owner del dominio tiene legitimidad de negocio (Customer→CRM/Marketing/Loyalty, Sales→Comercial/Ecommerce, Pricing→Pricing, Supply/Inventory→Logística, Finance→Finanzas). (02.1 §15)

## H · Heurísticas de decisión
- **KB01.H1** Priorización: Customer, Sales y Product habilitan muchos productos posteriores; Pricing y Supply Chain tienen alto impacto económico; Semantic/Metrics depende de dominios estabilizados. (02.1 §17)
- **KB01.H2** Roadmap por olas: capacidades prioritarias → dominios foco → Data Products concretos. (02.1 §18)
- **KB01.H3** Primero se valida el modelo con productos priorizados, luego se expande (enfoque incremental, 02 §18).

## A · Anti-patrones (señales)
- **KB01.A1** Dominio por sistema fuente ("sap", "oracle", "legacy"). · **KB01.A2** Dominios técnicos ("Big Data", "Integraciones").
- **KB01.A3** Data Product sin capacidad asociada. · **KB01.A4** Ownership funcional centralizado en Data & Analytics.
- **KB01.A5** Semantic layer sin trazabilidad a capacidades o dominios. · **KB01.A6** Priorizar por disponibilidad técnica. (02 §20, 02.1 §19)

## V · Preguntas de verificación
1. **KB01.V1** ¿La capacidad declarada explica por qué existe el producto y quién depende de él?
2. **KB01.V2** ¿El dominio principal es el que naturalmente posee las entidades del producto?
3. **KB01.V3** ¿El owner funcional tiene legitimidad de negocio sobre esa capacidad?

## D · Ya verificado por el motor determinista
Capacidad declarada y registrada (si el mapa está vigente), dominio/subdominio registrados, nombres de dominio no técnicos.

## G · Glosario
- **Capability cluster**: grupo de subcapacidades relacionadas (nivel 2).
- **Habilitador corporativo**: capacidad transversal (gobierno, plataforma, integración).
