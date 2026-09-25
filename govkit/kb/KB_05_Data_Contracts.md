---
id: KB_05
slug: data_contracts
title: Data Contracts, versionado y breaking changes
version: 1.0.0
status: vigente
tier: 2
sources: ["01-data-principles.md §6", "06 §11", "15-dataops-cicd.md §17, §20", "lineamientos/estructura-repositorio.md contracts/"]
applies_to: [data_product_maestro, consumo, integraciones]
triggers:
  tasks: [disenar_contrato, cambio_schema, evolucionar_version, integrar_consumidor]
  paths: ["contracts/**"]
  rules: ["GOV-CTR-*", "GOV-NAM-006", "GOV-NAM-014", "GOV-ARC-002", "GOV-PRT-003"]
  keywords: [contrato, schema, esquema, breaking change, compatibilidad, versión, semver, major, consumidor, productor]
depends_on: [KB_00]
related: [KB_04, KB_18, KB_07]
token_budget: 950
deterministic_rules: [GOV-CTR-001, GOV-CTR-003, GOV-CTR-004, GOV-CTR-005, GOV-CTR-006, GOV-CTR-007, GOV-CTR-008, GOV-CTR-010, GOV-CTR-015]
---
# KB_05 · Data Contracts
> El contrato es el acuerdo explícito entre productor y consumidor; las relaciones entre productos se basan en contratos versionados, no en conocimiento implícito de tablas.

## R · Reglas canónicas
- **KB05.R1 [MUST]** Ninguna integración ni consumo de un producto crítico sin contrato, aun si el mecanismo técnico es simple. (01 §6, 06 §11)
- **KB05.R2 [MUST]** Contenido: nombre, versión, dominio, Data Product, descripción, owners, esquema, semántica mínima, granularidad, claves de negocio, obligatoriedad/nullability, formatos, frecuencia, SLA, reglas críticas de calidad, clasificación, compatibilidad, política de breaking changes y de notificación. (06 §11, 15 §17)
- **KB05.R3 [MUST]** Contratos de entrada (lo que el producto espera) y de salida (lo que garantiza) en `contracts/input` y `contracts/output`; cada tabla principal tiene su contrato por capa. (Estructura de Repositorio)
- **KB05.R4 [MUST]** Semver: MAJOR = rompiente, MINOR = capacidad compatible, PATCH = corrección; lo gatillan Conventional Commits (`feat!:` o `BREAKING CHANGE:` → MAJOR) y se congela con tag git. (15 §20)
- **KB05.R5 [MUST]** Los breaking changes son explícitos, justificados y comunicados a los consumidores según la política de notificación. (15 §20)

## H · Heurísticas de decisión (¿es breaking?)
- **KB05.H1** Rompiente en salida: eliminar/renombrar campo, cambiar tipo, relajar obligatoriedad (consumidores asumen no-nulo), cambiar clave de negocio o granularidad.
- **KB05.H2** Rompiente en entrada: exigir un nuevo campo obligatorio al productor.
- **KB05.H3** Rompiente SEMÁNTICO (el linter no lo ve): mismo nombre y tipo pero distinto significado — unidad, moneda, zona horaria, universo, tratamiento de devoluciones/anulaciones, regla de cálculo. Se trata como MAJOR o como campo nuevo.
- **KB05.H4** Agregar campo opcional o nuevo output = MINOR; corregir descripción o bug sin cambio de interfaz = PATCH.

## A · Anti-patrones
- **KB05.A1** Consumir tablas internas de otro producto sin contrato. · **KB05.A2** Cambiar semántica sin versionar.
- **KB05.A3** Contratos sin granularidad ni claves. · **KB05.A4** Cambios de contrato sin CHANGELOG ni aviso.

## E · Ejemplo mínimo
✔ `net_amount_clp: decimal(18,2) — monto neto en CLP sin IVA, después de descuentos` · ✘ `amount: number — monto`

## V · Preguntas de verificación
1. **KB05.V1** ¿Algún campo cambió de significado manteniendo nombre y tipo?
2. **KB05.V2** ¿Las descripciones precisan unidad, moneda, zona horaria y reglas?
3. **KB05.V3** ¿La compatibilidad declarada coincide con la naturaleza del cambio?

## D · Ya verificado por el motor determinista
Existencia, esquema, semver, compatibilidad, granularidad/claves, breaking change estructural vs versión (diff git), CHANGELOG, cobertura de modelos Gold, referencias entre productos.
