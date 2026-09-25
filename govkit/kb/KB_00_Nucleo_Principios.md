---
id: KB_00
slug: nucleo_principios
title: Núcleo — Principios no negociables del Data & AI Discipline Framework
version: 1.0.0
status: vigente
tier: 0
sources: ["01-data-principles.md §1-§14", "02-data-strategy.md §6-§8, §26"]
applies_to: [todos]
triggers:
  tasks: ["*"]
  paths: []
  rules: []
  keywords: [principio, data product, gobierno, regla, estrategia]
depends_on: []
related: [KB_04, KB_09]
token_budget: 900
deterministic_rules: [GOV-DPD-001, GOV-DPD-007, GOV-DPD-011, GOV-MET-003, GOV-SEC-001, GOV-CTR-001]
---
# KB_00 · Núcleo de principios
> Kernel siempre cargado: define el marco con el que se interpreta cualquier otro mini-contexto.

## R · Reglas canónicas
- **KB00.R1 [MUST]** Todo activo de datos productivo es un Data Product: propósito, owner de negocio, consumidores registrados, SLA de disponibilidad y calidad, versión semántica y métricas de uso activo. Si falta uno, el Data Product no es válido. (01 §1)
- **KB00.R2 [MUST]** El diseño cubre generación → ingestión → transformación → serving → consumo → obsolescencia, con un responsable explícito por fase; la retención y eliminación son parte del ciclo. (01 §2)
- **KB00.R3 [MUST]** Sin metadata registrada en el catálogo (schema, owner, clasificación, linaje, SLA) el dato no existe para el ecosistema. (01 §3)
- **KB00.R4 [MUST]** SLOs de calidad cuantificados en ≥3 dimensiones, con alerta al owner y monitoreo activo; sin monitoreo no hay certificación. (01 §4)
- **KB00.R5 [MUST]** Datos críticos: sin sobrescritura destructiva; almacenamiento con Time Travel. (01 §5)
- **KB00.R6 [MUST]** Ninguna integración sin Data Contract. (01 §6)
- **KB00.R7 [MUST]** Todo dataset pertenece a un dominio de negocio declarado; prohibidas estructuras orientadas a tecnología o sistema origen. (01 §7)
- **KB00.R8 [MUST]** El consumo usa interfaces estables: BI, autoservicio y APIs analíticas consumen modelos semánticos, no tablas físicas. (01 §8-§9)
- **KB00.R9 [SHOULD]** Diseñar para reutilización en AI (feature reuse). (01 §10)
- **KB00.R10 [MUST]** Batch o real-time se decide por valor de negocio, no por tecnología. (01 §11)
- **KB00.R11 [MUST]** Monitoreo de costos activo con owner (FinOps). (01 §12)
- **KB00.R12 [MUST]** Clasificación + control de acceso + PIA completado antes de producción. (01 §13)
- **KB00.R13 [MUST]** Autoservicio con guardrails: RLS, masking de PII, quotas y usuarios certificados. (01 §14)

## H · Heurísticas de decisión
- **KB00.H1** Si un requerimiento se expresa como tecnología ("un dashboard", "un pipeline", "hacer AI"), reformúlalo como decisión de negocio + KPI antes de evaluarlo.
- **KB00.H2** La estrategia no es construir plataforma: prioriza lo que habilita valor, decisiones o AI mediante dominios y Data Products gobernados. (02 §26)
- **KB00.H3** Si detectas conflicto entre dos lineamientos, NO lo resuelvas por tu cuenta: repórtalo como `insuficiente_informacion` citando ambos.

## A · Anti-patrones
- **KB00.A1** Plataforma sin casos de uso. · **KB00.A2** Data Product sin owner. · **KB00.A3** Gobierno solo documental. · **KB00.A4** Lógica de negocio dentro del BI. · **KB00.A5** No medir adopción ni valor. (02 §20)

## V · Preguntas de verificación
1. **KB00.V1** ¿El artefacto se explica como Data Product (propósito, owner, consumidores, SLA, versión, uso)?
2. **KB00.V2** ¿Pertenece a un dominio de negocio y no a un sistema o tecnología?
3. **KB00.V3** ¿El consumo previsto pasa por interfaces estables o semánticas?

## D · Ya verificado por el motor determinista
Presencia de ficha, owner, consumidores, dominio, clasificación y contrato de salida. No reevalúes su existencia: evalúa solo su adecuación.

## G · Glosario
- **Data Product maestro**: publica datos de dominio con calidad, historia y seguridad (14 §8.3).
- **Data Product analítico de consumo**: tablero, API, export o activación sobre maestros certificados.
- **SLA / SLO**: compromiso de servicio / objetivo medible que lo sustenta.
