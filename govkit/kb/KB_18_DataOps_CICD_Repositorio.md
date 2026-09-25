---
id: KB_18
slug: dataops_cicd
title: DataOps, CI/CD, GitHub y estructura del repositorio
version: 1.0.0
status: vigente
tier: 6
sources: ["15-dataops-cicd.md §3-§29", "lineamientos/estructura-repositorio.md"]
applies_to: [data_product_maestro, consumo, ai_ml]
triggers:
  tasks: [pipeline_cicd_repo, nuevo_data_product, evolucionar_version, hotfix]
  paths: [".github/**", "CODEOWNERS", "README.md", "CHANGELOG.md", "tests/**", "src/**", "pipelines/**", ".govkit.yaml", "docs/adr/**"]
  rules: ["GOV-STR-*", "GOV-OPS-*", "GOV-NAM-001", "GOV-NAM-003", "GOV-NAM-004", "GOV-NAM-007", "GOV-NAM-008", "GOV-SEC-014"]
  keywords: [dataops, ci, cd, github, pull request, pr, rama, branch, commit, versionamiento, release, tag, workflow, codeowners, runbook, adr, hotfix, repositorio, estructura, trunk]
depends_on: [KB_00]
related: [KB_05, KB_11, KB_17]
token_budget: 1100
deterministic_rules: [GOV-STR-001, GOV-STR-002, GOV-STR-003, GOV-STR-004, GOV-STR-013, GOV-OPS-001, GOV-OPS-002, GOV-OPS-003, GOV-OPS-004, GOV-OPS-005, GOV-OPS-006, GOV-OPS-007, GOV-NAM-001, GOV-NAM-003, GOV-NAM-007, GOV-NAM-008]
---
# KB_18 · DataOps y repositorio
> Los Data Products se construyen, prueban, despliegan y operan como software, respetando contratos, calidad, metadata, linaje y seguridad.

## R · Reglas canónicas
- **KB18.R1 [MUST]** GitHub es el system of record del cambio técnico (código, contratos, metadata, quality rules, IaC, config, runbooks, ADRs, workflows); OpenMetadata es la capa de gobierno. (15 §8-§9)
- **KB18.R2 [MUST]** Organización global (estándares, templates, módulos, base-workflows) + organizaciones por país (repos operativos de Data Products). (15 §10-§12)
- **KB18.R3 [MUST]** Repositorio = unidad autónoma de cambio y despliegue: propósito, consumidores, contrato propio, ownership; nunca por dashboard, tabla, script o capa técnica. (15 §13)
- **KB18.R4 [MUST]** Estructura fija: `.github/workflows`, `contracts/{bronze,silver,gold/dim,gold/fact,semantic,input,output,policies}`, `docs/{adr,architecture,dbdiagram,engineering}`, `metadata`, `modeling/dbt`, `observability`, `pipelines/orchestration/step_function`, `publishing`, `quality`, `shared`, `src/<capa y transición>`, `tests/{contract,data_quality,integration,smoke,unit}`, CODEOWNERS, README. Nombre `{domain}-{subdomain}-{type}-dp-{country}`. (Estructura de Repositorio)
- **KB18.R5 [MUST]** Todo cambio por PR con: lint, unit tests, contratos, metadata, IaC, calidad, security scans, firma de commits y documentación; template de PR con impacto, contratos, metadata, runbook y breaking change. (15 §16)
- **KB18.R6 [MUST]** Testing en 5 niveles: unit, integration, contract, data quality, smoke. (15 §19)
- **KB18.R7 [MUST]** Semver + Conventional Commits + tags; IaC sin recursos manuales en producción; configuración externa por país/BU/ambiente; runbook y ADRs. (15 §20-§23)
- **KB18.R8 [MUST]** CODEOWNERS: contracts, modeling, quality, tests, pipelines, src, docs y .github requieren Data Architects + Tech Leaders. (Estructura de Repositorio)

## H · Heurísticas de decisión
- **KB18.H1** Hotfix de un solo producto sin arrastrar otros dominios ni países (bajo blast radius). (15 §26)
- **KB18.H2** Estrategia de ramas: el framework (15 §15) recomienda trunk-based; el estándar operativo usa develop/staging/main por ambiente. Hasta resolver el ADR, seguir `policies.branching` del repo y no mezclar.

## A · Anti-patrones
- **KB18.A1** Repos monolíticos o por tabla. · **KB18.A2** Ramas largas. · **KB18.A3** Metadata fuera del repo. · **KB18.A4** Credenciales en código.

## V · Preguntas de verificación
1. **KB18.V1** ¿El repo representa una unidad real de valor con ownership y contrato propios?
2. **KB18.V2** ¿El cambio es pequeño, trazable y con impacto declarado?

## D · Ya verificado por el motor determinista
Estructura, archivos raíz, workflows, CODEOWNERS, nomenclatura de repo/jobs/lambdas/ramas/commits, tests, dbt, ASL, waivers, template de PR, config externalizada.
