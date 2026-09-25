---
id: KB_03
slug: dominios_ownership
title: Dominios de datos y ownership multi-rol
version: 1.0.0
status: vigente
tier: 1
sources: ["01-data-principles.md §7", "02.1 §15", "06 §10", "08 §15", "09 §11", "18 §24"]
applies_to: [data_product_maestro, consumo]
triggers:
  tasks: [nuevo_data_product, definir_ownership, retirar_consolidar]
  paths: ["metadata/catalog/data_product.yaml", "CODEOWNERS"]
  rules: ["GOV-DPD-007", "GOV-DPD-008", "GOV-DPD-009", "GOV-DPD-010", "GOV-MET-003", "GOV-MET-004", "GOV-MET-010", "GOV-NAM-002", "GOV-ARC-012"]
  keywords: [owner, steward, dominio, ownership, responsable, data council, boundary]
depends_on: [KB_00]
related: [KB_01, KB_19]
token_budget: 850
deterministic_rules: [GOV-DPD-007, GOV-DPD-008, GOV-MET-003, GOV-MET-004, GOV-MET-010]
---
# KB_03 · Dominios y ownership
> El dominio es la unidad de ownership y gobierno; el ownership es explícito y multi-rol.

## R · Reglas canónicas
- **KB03.R1 [MUST]** Los límites de dominio los define y mantiene el Data Council corporativo. (01 §7)
- **KB03.R2 [MUST]** Roles del Data Product: Business Owner (dueño del valor), Data Owner (dueño del dato en el dominio), Data Steward (custodia reglas, términos, remediación), Technical Owner (implementa), Arquitecto; Security contact si hay PII; BI lead y ML owner si aplica. (06 §10)
- **KB03.R3 [MUST]** Debe quedar claro quién es dueño del valor, del dato, quién implementa, quién gobierna y quién consume; sin esto el producto no avanza. (06 §10)
- **KB03.R4 [MUST]** La calidad y la metadata no se definen unilateralmente: participan negocio, datos, ingeniería, arquitectura y gobierno. (08 §15, 09 §11)
- **KB03.R5 [MUST]** El ownership cambia de énfasis por etapa del lifecycle pero nunca queda ambiguo. (18 §24)
- **KB03.R6 [MUST]** Un producto no redefine entidades de otro dominio: las consume por contrato desde el Data Product del dominio dueño. (02.1 §7)

## H · Heurísticas de decisión
- **KB03.H1** Si el Business Owner es un rol técnico, probablemente el producto está mal fundado.
- **KB03.H2** Si dos dominios reclaman la misma entidad, escalar al Data Council; mientras tanto, un solo productor y el resto consumidores.
- **KB03.H3** [PRÁCTICA] Owners nominales (personas), no buzones genéricos, para asegurar responsabilidad.

## A · Anti-patrones
- **KB03.A1** Ownership ambiguo o delegado al equipo técnico. · **KB03.A2** Data & Analytics como dueño de todo.
- **KB03.A3** Dominios por conveniencia técnica. · **KB03.A4** Productos en producción sin owner vigente. (18 §30)

## V · Preguntas de verificación
1. **KB03.V1** ¿Cada rol tiene una persona con legitimidad para decidir en su ámbito?
2. **KB03.V2** ¿El producto crea copias o versiones propias de entidades de otro dominio (cliente, producto, tienda)?

## D · Ya verificado por el motor determinista
Presencia de roles, emails corporativos, dominio declarado y registrado, CODEOWNERS.
