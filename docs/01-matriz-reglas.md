# Matriz de Reglas de Gobernanza (generada)

> Generado con `govkit rules --format md` desde `rules/catalog.yaml` · ruleset `2026.09.1` · 259 reglas. No editar a mano: el catálogo es la fuente única de verdad.

## 1. Matriz de dos ejes: dominio de gobierno × naturaleza de validación

| Dominio | D · Determinista | H · Híbrida | S · Semántica | O · Organizacional | Total | % automatizable (D+H) |
|---|---:|---:|---:|---:|---:|---:|
| Estructura de repositorio | 12 | 1 | 0 | 0 | 13 | 100% |
| Nomenclatura | 14 | 0 | 0 | 0 | 14 | 100% |
| Definición de Data Product | 27 | 1 | 0 | 0 | 28 | 100% |
| Data Contracts | 13 | 1 | 1 | 0 | 15 | 93% |
| Metadata y catálogo | 15 | 1 | 1 | 1 | 18 | 89% |
| Calidad de datos | 13 | 2 | 1 | 1 | 17 | 88% |
| Seguridad y privacidad | 12 | 2 | 2 | 2 | 18 | 78% |
| IAM | 14 | 1 | 0 | 0 | 15 | 100% |
| DataOps y CI/CD | 12 | 0 | 0 | 1 | 13 | 92% |
| Arquitectura y modelado | 8 | 1 | 5 | 0 | 14 | 64% |
| Semantic layer y métricas | 7 | 1 | 1 | 1 | 10 | 80% |
| Consumo y explotación | 11 | 1 | 2 | 0 | 14 | 86% |
| AI / ML / GenAI | 10 | 0 | 2 | 0 | 12 | 83% |
| Observabilidad | 7 | 0 | 1 | 0 | 8 | 88% |
| Ciclo de vida | 5 | 0 | 1 | 1 | 7 | 71% |
| Scoring | 5 | 0 | 0 | 0 | 5 | 100% |
| Negocio y casos de uso | 7 | 1 | 2 | 2 | 12 | 67% |
| OpenMetadata (pack omd) | 14 | 0 | 0 | 1 | 15 | 93% |
| Documentación del framework (pack docs) | 5 | 0 | 0 | 0 | 5 | 100% |
| Portafolio cross-repo (pack portfolio) | 6 | 0 | 0 | 0 | 6 | 100% |
| **Total** | **217** | **13** | **19** | **10** | **259** | **89%** |

Naturalezas: **D** = Determinista · **H** = Híbrida (presencia determinista + adecuación semántica) · **S** = Semántica (LLM + KB) · **O** = Organizacional / proceso (revisión humana)

## 2. Matriz de técnica de verificación × punto de control

| Técnica | pre-commit | pr | gate | catalog | periodic | runtime |
|---|---:|---:|---:|---:|---:|---:|
| `ast` | 2 | 2 | 0 | 0 | 0 | 0 |
| `count` | 0 | 7 | 7 | 1 | 0 | 0 |
| `diff` | 0 | 3 | 0 | 0 | 0 | 0 |
| `graph` | 0 | 29 | 12 | 7 | 6 | 0 |
| `human` | 0 | 1 | 0 | 0 | 5 | 4 |
| `llm` | 0 | 19 | 0 | 0 | 0 | 0 |
| `path` | 0 | 21 | 10 | 2 | 0 | 0 |
| `policy` | 1 | 11 | 0 | 0 | 0 | 0 |
| `regex` | 10 | 48 | 1 | 3 | 1 | 0 |
| `schema` | 11 | 83 | 25 | 7 | 1 | 0 |
| `threshold` | 1 | 1 | 0 | 0 | 3 | 0 |

## 3. Catálogo completo por dominio

### Estructura de repositorio

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-STR-001` | Carpetas raíz estándar del repositorio | D | HIGH | — | path | pr | lineamientos/estructura-repositorio.md Importante | KB_18 |
| `GOV-STR-002` | Subcarpetas estándar (contracts, docs, tests, src, pipelines) | D | MEDIUM | ideacion:LOW | path | pr | lineamientos/estructura-repositorio.md Detalle por Carpeta | KB_18 |
| `GOV-STR-003` | Archivos raíz obligatorios (README.md, CODEOWNERS) | D | HIGH | — | path | pr | lineamientos/estructura-repositorio.md Archivos Raíz | KB_18 |
| `GOV-STR-004` | Workflows CI/CD pr.yml y deploy.yml | D | HIGH | ideacion:MEDIUM | path | pr | lineamientos/estructura-repositorio.md .github/workflows/ | KB_18 |
| `GOV-STR-005` | Carpetas raíz no estándar | D | LOW | — | path | pr | lineamientos/estructura-repositorio.md Importante | KB_18 |
| `GOV-STR-006` | CHANGELOG.md del producto | D | MEDIUM | ideacion:OFF, diseno:LOW | path | pr | 15-dataops-cicd.md §14, §23 | KB_18 |
| `GOV-STR-007` | README con secciones mínimas | H | MEDIUM | — | regex | pr | 15-dataops-cicd.md §23 | KB_18, KB_04 |
| `GOV-STR-008` | Runbook operativo | D | HIGH | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | path | pr, gate | 15-dataops-cicd.md §23 | KB_18, KB_17 |
| `GOV-STR-009` | Proyecto dbt completo | D | MEDIUM | — | path | pr | lineamientos/estructura-repositorio.md modeling/ | KB_18, KB_07 |
| `GOV-STR-010` | Definiciones Step Functions válidas | D | HIGH | — | schema | pre-commit, pr | lineamientos/estructura-repositorio.md pipelines/ | KB_18 |
| `GOV-STR-011` | Formato de ADRs | D | LOW | — | regex | pr | lineamientos/estructura-repositorio.md docs/ | KB_18 |
| `GOV-STR-012` | Modelo lógico/físico documentado (DBML) | D | MEDIUM | ideacion:OFF, salida:LOW | path | pr | lineamientos/estructura-repositorio.md docs/dbdiagram | KB_07 |
| `GOV-STR-013` | Artefactos YAML/JSON sintácticamente válidos | D | BLOCKER | — | schema | pre-commit, pr | 15-dataops-cicd.md §16 | KB_18 |

### Nomenclatura

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-NAM-001` | Nombre de repositorio {domain}-{subdomain}-{type}-dp-{country} | D | HIGH | — | regex | pr | lineamientos/estructura-repositorio.md Convención de nombre del repositorio | KB_18 |
| `GOV-NAM-002` | Dominio del repositorio registrado | D | HIGH | — | graph | pr | 01-data-principles.md §7 | KB_03 |
| `GOV-NAM-003` | Nomenclatura de Glue jobs | D | MEDIUM | — | regex | pre-commit, pr | lineamientos/estructura-repositorio.md src/ · Regla de nomenclatura de jobs | KB_18 |
| `GOV-NAM-004` | Nomenclatura de Lambdas | D | MEDIUM | — | regex | pre-commit, pr | lineamientos/estructura-repositorio.md src/ · Regla de nomenclatura de lambdas | KB_18 |
| `GOV-NAM-005` | Modelos Gold dbt dim_* / fact_* | D | MEDIUM | — | regex | pre-commit, pr | lineamientos/estructura-repositorio.md modeling/ · models/gold | KB_07 |
| `GOV-NAM-006` | Contratos Gold ubicados según tipo (dim/fact) | D | LOW | — | regex | pr | lineamientos/estructura-repositorio.md contracts/gold/dim · contracts/gold/fact | KB_05 |
| `GOV-NAM-007` | Convención de ramas <tipo>/<dominio>/<descripcion> | D | MEDIUM | — | regex | pr | lineamientos/estructura-repositorio.md Convención de branches | KB_18 |
| `GOV-NAM-008` | Conventional Commits | D | MEDIUM | — | regex | pr | 15-dataops-cicd.md §20 | KB_18, KB_05 |
| `GOV-NAM-009` | Nombre del rol IAM cencosud-role-{repo} | D | HIGH | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Convención de Nombres | KB_11 |
| `GOV-NAM-010` | Nombres de policies cencosud-policy-{repo}-data\|infra | D | HIGH | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Convención de Nombres | KB_11 |
| `GOV-NAM-011` | Buckets del lakehouse cencosud-{pais}-dlk-{zona}-{dominio}-* | D | MEDIUM | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Policy DATA · Ejemplo | KB_11 |
| `GOV-NAM-012` | Databases Glue dlk_{zona}_{pais}_{dominio}_{nombre} | D | MEDIUM | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Regla de Wildcard | KB_11 |
| `GOV-NAM-013` | Nombre del Data Product en kebab-case | D | LOW | — | regex | pr | 09-metadata-governance.md §16 | KB_09 |
| `GOV-NAM-014` | Campos de contratos en snake_case | D | LOW | ideacion:LOW, diseno:MEDIUM | regex | pre-commit, pr | 06-data-product-definition.md §11 | KB_05 |

### Definición de Data Product

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-DPD-001` | Ficha del Data Product versionada (metadata as code) | D | BLOCKER | — | path | pr, gate, catalog | 01-data-principles.md §3 | KB_04, KB_09 |
| `GOV-DPD-002` | Ficha conforme al esquema canónico | D | HIGH | — | schema | pre-commit, pr | 06-data-product-definition.md §7-§26 | KB_04 |
| `GOV-DPD-003` | ID único del Data Product | D | MEDIUM | — | regex | pr | 06-data-product-definition.md §7 (Bloque 1) | KB_04 |
| `GOV-DPD-004` | Versión semántica del Data Product | D | HIGH | — | regex | pr | 01-data-principles.md §1 | KB_04, KB_05 |
| `GOV-DPD-005` | Tipo de Data Product | D | HIGH | — | schema | pr | 06-data-product-definition.md §7 Tipos sugeridos | KB_04 |
| `GOV-DPD-006` | Rol del Data Product (maestro \| consumo) | D | MEDIUM | — | schema | pr | 14-data-consumption-exploitation-framework.md §8.3 | KB_04, KB_13 |
| `GOV-DPD-007` | Owner de negocio definido | D | BLOCKER | ideacion:HIGH | schema | pr, gate, catalog | 01-data-principles.md §1 | KB_03, KB_04 |
| `GOV-DPD-008` | Ownership multi-rol (Data Owner, Steward, Technical Owner, Arquitecto) | D | HIGH | ideacion:LOW, diseno:MEDIUM, salida:MEDIUM | schema | pr, gate | 06-data-product-definition.md §10 (Bloque 4) | KB_03 |
| `GOV-DPD-009` | Security contact cuando hay PII | D | HIGH | ideacion:OFF, salida:LOW | schema | pr, gate | 06-data-product-definition.md §10 | KB_03, KB_10 |
| `GOV-DPD-010` | ML/AI owner en productos AI/ML | D | HIGH | ideacion:OFF, salida:LOW | schema | pr, gate | 06-data-product-definition.md §10 | KB_03, KB_15 |
| `GOV-DPD-011` | Consumidores registrados | D | BLOCKER | ideacion:MEDIUM, diseno:HIGH, desarrollo:HIGH, salida:LOW | count | pr, gate | 01-data-principles.md §1 | KB_04 |
| `GOV-DPD-012` | Consumidor activo o validado para certificar | D | BLOCKER | ideacion:OFF, diseno:OFF, desarrollo:OFF, salida:OFF | schema | gate | 06-data-product-definition.md §25 (Bloque 19) | KB_04, KB_20 |
| `GOV-DPD-013` | SLA declarado (frecuencia, freshness, disponibilidad) | D | HIGH | ideacion:LOW, diseno:MEDIUM, desarrollo:HIGH, gate:BLOCKER, operacion:BLOCKER, salida:LOW | schema | pr, gate | 06-data-product-definition.md §23 (Bloque 17) | KB_04, KB_17 |
| `GOV-DPD-014` | Métricas de uso activo declaradas | D | HIGH | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, salida:LOW | count | pr, gate | 01-data-principles.md §1 | KB_04, KB_20 |
| `GOV-DPD-015` | Responsable por fase del ciclo de datos | D | HIGH | ideacion:LOW, salida:LOW | schema | pr | 01-data-principles.md §2 | KB_04, KB_19 |
| `GOV-DPD-016` | Retención y eliminación definidas | D | HIGH | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, gate:BLOCKER, operacion:BLOCKER, salida:LOW | schema | pr, gate | 10-data-security-framework.md §24 | KB_10, KB_19 |
| `GOV-DPD-017` | Nivel objetivo de madurez | D | MEDIUM | ideacion:LOW | schema | pr | 06-data-product-definition.md §25 (Bloque 19) | KB_04, KB_20 |
| `GOV-DPD-018` | Inputs documentados (Bloque 6) | D | HIGH | ideacion:LOW, diseno:HIGH, salida:LOW | schema | pr | 06-data-product-definition.md §12 (Bloque 6) | KB_04 |
| `GOV-DPD-019` | Outputs y modo de consumo (Bloque 7) | D | HIGH | ideacion:LOW, diseno:HIGH, salida:LOW | schema | pr | 06-data-product-definition.md §13 (Bloque 7) | KB_04, KB_13 |
| `GOV-DPD-020` | Relación con ARTS declarada | D | MEDIUM | ideacion:OFF, salida:LOW | schema | pr | 06-data-product-definition.md §14 (Bloque 8) | KB_07 |
| `GOV-DPD-021` | Capas del lakehouse declaradas | D | HIGH | ideacion:OFF, salida:LOW | schema | pr | 06-data-product-definition.md §14 Layer esperada | KB_06 |
| `GOV-DPD-022` | Interfaz semántica obligatoria con consumo analítico (Bloque 15) | D | HIGH | ideacion:OFF, salida:LOW | schema | pr, gate | 06-data-product-definition.md §21 (Bloque 15) | KB_12 |
| `GOV-DPD-023` | Bloque AI/ML readiness en productos AI/ML (Bloque 16) | D | HIGH | ideacion:OFF, salida:LOW | schema | pr | 06-data-product-definition.md §22 (Bloque 16) | KB_15 |
| `GOV-DPD-024` | Dependencias declaradas (Bloque 18) | D | LOW | ideacion:OFF, salida:LOW | schema | pr | 06-data-product-definition.md §24 (Bloque 18) | KB_04 |
| `GOV-DPD-025` | Monitoreo de costos con owner (FinOps) | D | HIGH | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, salida:LOW | schema | pr, gate | 01-data-principles.md §12 | KB_04, KB_17 |
| `GOV-DPD-026` | Descripción funcional útil | H | MEDIUM | operacion:HIGH, gate:HIGH | regex | pr, catalog | 09-metadata-governance.md §22 | KB_09, KB_04 |
| `GOV-DPD-027` | Definition of Ready (entrada a desarrollo) | D | BLOCKER | ideacion:OFF, diseno:MEDIUM, salida:OFF | graph | gate | 06-data-product-definition.md §26 Definition of Ready | KB_04, KB_19 |
| `GOV-DPD-028` | Definition of Done (listo para producción) | D | BLOCKER | ideacion:OFF, diseno:OFF, desarrollo:LOW, salida:OFF | graph | gate | 06-data-product-definition.md §26 Definition of Done | KB_04, KB_19, KB_20 |

### Data Contracts

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-CTR-001` | Contrato de salida definido | D | BLOCKER | ideacion:OFF, diseno:MEDIUM, desarrollo:HIGH, gate:BLOCKER, operacion:BLOCKER, salida:LOW | path | pr, gate | 01-data-principles.md §6 | KB_05 |
| `GOV-CTR-002` | Contrato de entrada por cada input | D | HIGH | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, salida:OFF | graph | pr, gate | lineamientos/estructura-repositorio.md contracts/input | KB_05 |
| `GOV-CTR-003` | Contrato conforme al esquema (campos mínimos) | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pre-commit, pr | 15-dataops-cicd.md §17 | KB_05 |
| `GOV-CTR-004` | Versión semántica del contrato | D | HIGH | ideacion:LOW, diseno:MEDIUM | regex | pre-commit, pr | 15-dataops-cicd.md §20 | KB_05 |
| `GOV-CTR-005` | Compatibilidad y política de cambios declaradas | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pr | 06-data-product-definition.md §11 Campos recomendados | KB_05 |
| `GOV-CTR-006` | Granularidad y claves de negocio del contrato de salida | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pr | 06-data-product-definition.md §11, §14 | KB_05, KB_07 |
| `GOV-CTR-007` | Breaking change sin versión MAJOR | D | BLOCKER | — | diff | pr | 15-dataops-cicd.md §20 | KB_05 |
| `GOV-CTR-008` | Cambio de contrato registrado en CHANGELOG | D | MEDIUM | — | diff | pr | 15-dataops-cicd.md §16 | KB_05, KB_18 |
| `GOV-CTR-009` | Contrato referencia al Data Product del repositorio | D | HIGH | — | graph | pr | 15-dataops-cicd.md §17 | KB_05 |
| `GOV-CTR-010` | Cada modelo Gold tiene contrato | D | HIGH | ideacion:OFF, diseno:OFF, salida:LOW | graph | pr, gate | lineamientos/estructura-repositorio.md contracts/ | KB_05, KB_07 |
| `GOV-CTR-011` | Tests de contrato implementados | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | path | pr, gate | lineamientos/estructura-repositorio.md tests/contract | KB_05, KB_18 |
| `GOV-CTR-012` | SLA del contrato coherente con el del Data Product | D | LOW | — | graph | pr | 06-data-product-definition.md §11, §23 | KB_05 |
| `GOV-CTR-013` | Campos del contrato descritos | H | MEDIUM | ideacion:LOW, diseno:MEDIUM | schema | pr | 06-data-product-definition.md §11 | KB_05, KB_09 |
| `GOV-CTR-014` | Cambio semántico no declarado | S | HIGH | — | llm | pr | 15-dataops-cicd.md §17, §20 | KB_05 |
| `GOV-CTR-015` | Dependencias entre productos por contrato versionado | D | HIGH | — | graph | pr | 15-dataops-cicd.md §17 | KB_05 |

### Metadata y catálogo

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-MET-001` | Glosario del producto con términos gobernados | D | MEDIUM | — | schema | pr, catalog | 09-metadata-governance.md §12 | KB_09 |
| `GOV-MET-002` | Criticidad declarada | D | HIGH | ideacion:MEDIUM | schema | pr, catalog | 09-metadata-governance.md §10 | KB_09 |
| `GOV-MET-003` | Dominio de datos declarado | D | BLOCKER | — | schema | pr, catalog | 01-data-principles.md §7 | KB_03 |
| `GOV-MET-004` | Dominio registrado en el modelo de dominios | D | HIGH | — | graph | pr, catalog | 01-data-principles.md §7 | KB_03 |
| `GOV-MET-005` | Subdominio declarado y registrado | D | MEDIUM | — | graph | pr, catalog | 02.1-business-capability-alignment.md §10 | KB_03, KB_01 |
| `GOV-MET-006` | Términos de glosario asociados | D | MEDIUM | ideacion:OFF, diseno:LOW, gate:HIGH, operacion:HIGH, salida:LOW | count | pr, catalog | 09-metadata-governance.md §10 | KB_09 |
| `GOV-MET-007` | Términos de glosario resolubles | D | MEDIUM | — | graph | pr, catalog | 09-metadata-governance.md §12 | KB_09 |
| `GOV-MET-008` | Tags de taxonomía controlada | D | MEDIUM | — | graph | pr, catalog | 09-metadata-governance.md §13 | KB_09 |
| `GOV-MET-009` | Linaje esperado de fuente a consumo | D | HIGH | ideacion:OFF, diseno:MEDIUM, desarrollo:MEDIUM, salida:LOW | graph | pr, catalog | 06-data-product-definition.md §18 (Bloque 12) | KB_09, KB_06 |
| `GOV-MET-010` | Emails corporativos en ownership | D | HIGH | — | regex | pr, catalog | 09-metadata-governance.md §22 | KB_03, KB_09 |
| `GOV-MET-011` | Mapeo OpenMetadata-ready | D | MEDIUM | ideacion:OFF, diseno:LOW, gate:HIGH, operacion:HIGH, salida:MEDIUM | schema | pr, catalog | 06-data-product-definition.md §17 OpenMetadata readiness | KB_09, KB_21 |
| `GOV-MET-012` | Archivo de mapeo OpenMetadata presente | D | MEDIUM | ideacion:OFF, diseno:LOW, gate:HIGH, operacion:HIGH | path | pr, catalog | 15-dataops-cicd.md §18 | KB_09 |
| `GOV-MET-013` | Metadata revisada periódicamente | D | LOW | ideacion:OFF, diseno:OFF, desarrollo:OFF, gate:OFF, salida:OFF | threshold | periodic | 09-metadata-governance.md §24 | KB_09 |
| `GOV-MET-014` | Fechas de la ficha coherentes | D | LOW | — | schema | pr | 06-data-product-definition.md §7 | KB_04 |
| `GOV-MET-015` | Data Product catalogable (metadata mínima 09 §10) | D | HIGH | ideacion:OFF, diseno:MEDIUM, gate:BLOCKER, operacion:BLOCKER, salida:MEDIUM | graph | gate, catalog | 09-metadata-governance.md §10 | KB_09 |
| `GOV-MET-016` | Descripción útil de contratos | H | MEDIUM | ideacion:LOW, diseno:MEDIUM | regex | pr, catalog | 09-metadata-governance.md §22 | KB_09, KB_05 |
| `GOV-MET-017` | Consistencia entre metadata técnica y de negocio | S | MEDIUM | — | llm | pr | 09-metadata-governance.md §27 | KB_09 |
| `GOV-MET-018` | Proceso de mantenimiento de metadata por dominio | O | MEDIUM | — | human | periodic | 09-metadata-governance.md §24 | KB_09 |

### Calidad de datos

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-QLT-001` | Reglas de calidad definidas | D | BLOCKER | ideacion:OFF, diseno:MEDIUM, desarrollo:HIGH, gate:BLOCKER, operacion:BLOCKER, salida:LOW | path | pr, gate | 08-data-quality-framework.md §12 | KB_08 |
| `GOV-QLT-002` | Estructura mínima de cada regla de calidad | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pre-commit, pr | 08-data-quality-framework.md §12 Estructura mínima | KB_08 |
| `GOV-QLT-003` | Dimensión de calidad canónica | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pre-commit, pr | 08-data-quality-framework.md §9 | KB_08 |
| `GOV-QLT-004` | Severidad y acción del catálogo de calidad | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pre-commit, pr | 08-data-quality-framework.md §13 | KB_08 |
| `GOV-QLT-005` | Capa de aplicación válida | D | MEDIUM | — | schema | pr | 08-data-quality-framework.md §10 | KB_08, KB_06 |
| `GOV-QLT-006` | SLOs cuantificados en ≥3 dimensiones | D | HIGH | ideacion:OFF, diseno:MEDIUM, desarrollo:HIGH, gate:BLOCKER, operacion:BLOCKER, salida:LOW | count | pr, gate | 01-data-principles.md §4 | KB_08 |
| `GOV-QLT-007` | Al menos una regla crítica | D | HIGH | ideacion:OFF, diseno:MEDIUM, desarrollo:HIGH, gate:BLOCKER, operacion:BLOCKER, salida:LOW | count | pr, gate | 08-data-quality-framework.md §26 Reglas críticas | KB_08 |
| `GOV-QLT-008` | Umbrales cuantificables | D | MEDIUM | — | regex | pre-commit, pr | 08-data-quality-framework.md §27 | KB_08 |
| `GOV-QLT-009` | Coherencia severidad ↔ acción | D | MEDIUM | — | schema | pr | 08-data-quality-framework.md §13 | KB_08 |
| `GOV-QLT-010` | Quality gates Silver, Gold y Serving | D | HIGH | ideacion:OFF, diseno:LOW, salida:OFF | schema | pr, gate | 08-data-quality-framework.md §14 | KB_08 |
| `GOV-QLT-011` | Operación de alertas de calidad | D | HIGH | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, salida:OFF | schema | pr, gate | 08-data-quality-framework.md §26 Operación | KB_08, KB_17 |
| `GOV-QLT-012` | Objeto de la regla resoluble contra contratos | D | MEDIUM | — | graph | pr | 08-data-quality-framework.md §12 | KB_08, KB_05 |
| `GOV-QLT-013` | Reglas derivadas a tests ejecutables | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | path | pr, gate | 08-data-quality-framework.md §26 | KB_08, KB_18 |
| `GOV-QLT-014` | Reglas de negocio fuera de Bronze | H | LOW | — | schema | pr | 08-data-quality-framework.md §10.1 | KB_08, KB_06 |
| `GOV-QLT-015` | Umbrales adecuados al uso del producto | S | HIGH | — | llm | pr | 08-data-quality-framework.md §6 | KB_08 |
| `GOV-QLT-016` | Gestión de incidentes de calidad | O | MEDIUM | — | human | runtime | 08-data-quality-framework.md §22 | KB_08, KB_17 |
| `GOV-QLT-017` | Controles de calidad para features AI | H | HIGH | ideacion:OFF, diseno:OFF, salida:LOW | schema | pr, gate | 08-data-quality-framework.md §10.5, §19 | KB_08, KB_15 |

### Seguridad y privacidad

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-SEC-001` | Clasificación de seguridad explícita | D | BLOCKER | ideacion:HIGH | schema | pre-commit, pr, gate, catalog | 10-data-security-framework.md §10 | KB_10 |
| `GOV-SEC-002` | Atributos de clasificación explícitos | D | HIGH | ideacion:MEDIUM | schema | pr, gate | 10-data-security-framework.md §10 Campos recomendados | KB_10 |
| `GOV-SEC-003` | PII ⇒ clasificación sensible y masking | D | BLOCKER | — | schema | pre-commit, pr, gate | 10-data-security-framework.md §11, §15 | KB_10 |
| `GOV-SEC-004` | Privacy Impact Assessment completado antes de producción | D | BLOCKER | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, gate:BLOCKER, operacion:BLOCKER, salida:LOW | schema | gate | 01-data-principles.md §13 | KB_10 |
| `GOV-SEC-005` | Política de acceso declarada | D | HIGH | ideacion:OFF, salida:LOW | schema | pr, gate | 10-data-security-framework.md §12 | KB_10 |
| `GOV-SEC-006` | Sin secretos ni credenciales hardcodeadas | D | BLOCKER | — | ast | pre-commit, pr | 10-data-security-framework.md §23 | KB_10, KB_18 |
| `GOV-SEC-007` | Campos con apariencia de PII sin marcar | H | HIGH | — | regex | pr | 10-data-security-framework.md §11 | KB_10 |
| `GOV-SEC-008` | Datos de muestra sin PII real | D | HIGH | — | regex | pre-commit, pr | 10-data-security-framework.md §11, §28 | KB_10 |
| `GOV-SEC-009` | Exposición a terceros gobernada | D | HIGH | — | graph | pr, gate | 10-data-security-framework.md §17 | KB_10, KB_14 |
| `GOV-SEC-010` | RLS en consumo BI de datos sensibles | D | HIGH | ideacion:OFF, salida:LOW | graph | pr, gate | 10-data-security-framework.md §18 | KB_10, KB_12 |
| `GOV-SEC-011` | Derecho al olvido en productos con PII | D | MEDIUM | ideacion:OFF, salida:LOW | schema | pr, gate | 10-data-security-framework.md §24 | KB_10 |
| `GOV-SEC-012` | Campos PII del contrato con técnica de protección | D | HIGH | — | schema | pre-commit, pr | 10-data-security-framework.md §15 | KB_10, KB_05 |
| `GOV-SEC-013` | Vistas de consumo no exponen PII sin enmascarar | H | HIGH | — | regex | pr | 10-data-security-framework.md §16.4, §18 | KB_10, KB_12 |
| `GOV-SEC-014` | Validación automatizada de seguridad en CI/CD | D | MEDIUM | ideacion:OFF, diseno:OFF, gate:BLOCKER, operacion:BLOCKER, salida:OFF | regex | pr, gate | 10-data-security-framework.md §23 | KB_10, KB_18 |
| `GOV-SEC-015` | Proporcionalidad de controles a la sensibilidad | S | HIGH | — | llm | pr | 10-data-security-framework.md §8, §28 | KB_10 |
| `GOV-SEC-016` | Exposición indirecta de PII vía joins o filtros | S | HIGH | — | llm | pr | 10-data-security-framework.md §18 | KB_10, KB_12 |
| `GOV-SEC-017` | Certificación de uso responsable (self-service) | O | MEDIUM | — | human | runtime | 01-data-principles.md §14 | KB_10 |
| `GOV-SEC-018` | Revisión periódica de accesos | O | MEDIUM | — | human | periodic | 10-data-security-framework.md §12 | KB_10 |

### IAM

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-IAM-001` | 1 rol + 2 policies (data + infra) por producto | D | HIGH | ideacion:OFF, diseno:OFF, salida:LOW | path | pr | lineamientos/iam-roles-policies.md Principio General | KB_11 |
| `GOV-IAM-002` | Tamaño de policy ≤ 6144 caracteres | D | BLOCKER | ideacion:LOW, diseno:MEDIUM | threshold | pre-commit, pr | lineamientos/iam-roles-policies.md ¿Por qué 2 policies? | KB_11 |
| `GOV-IAM-003` | Separación de lectura y escritura en statements | D | HIGH | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Regla 3 | KB_11 |
| `GOV-IAM-004` | Wildcard de escritura solo sobre recursos exclusivos | D | BLOCKER | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Regla 2 (la más importante) | KB_11 |
| `GOV-IAM-005` | KMS con key ID y cuenta explícitos | D | BLOCKER | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Regla 2 y 4 | KB_11 |
| `GOV-IAM-006` | KMS condicionado por kms:ViaService | D | MEDIUM | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Regla 5 | KB_11 |
| `GOV-IAM-007` | Región fija us-east-1 en ARNs de datos | D | MEDIUM | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Regla 4 | KB_11 |
| `GOV-IAM-008` | Account ID comodín para multi-ambiente | D | LOW | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Regla 4 | KB_11 |
| `GOV-IAM-009` | Sin acciones comodín globales | D | HIGH | ideacion:LOW, diseno:MEDIUM | policy | pre-commit, pr | lineamientos/iam-roles-policies.md Reglas de Seguridad | KB_11, KB_10 |
| `GOV-IAM-010` | Trust policy limitada a servicios autorizados | D | HIGH | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Estructura del Role | KB_11 |
| `GOV-IAM-011` | Tags obligatorios del recurso IAM | D | HIGH | ideacion:LOW, diseno:MEDIUM | schema | pr | lineamientos/iam-roles-policies.md Tags obligatorios | KB_11 |
| `GOV-IAM-012` | Alcance semántico de cada policy (data vs infra) | D | MEDIUM | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md ¿Por qué 2 policies? | KB_11 |
| `GOV-IAM-013` | Sid descriptivo y único | D | LOW | ideacion:LOW, diseno:MEDIUM | regex | pr | lineamientos/iam-roles-policies.md Statements esperados | KB_11 |
| `GOV-IAM-014` | Secrets y Logs acotados al producto | D | HIGH | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Policy INFRA · Ejemplo | KB_11 |
| `GOV-IAM-015` | Lectura cross-dominio respaldada por contrato | H | MEDIUM | ideacion:LOW, diseno:MEDIUM | policy | pr | lineamientos/iam-roles-policies.md Principio General | KB_11, KB_05 |

### DataOps y CI/CD

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-OPS-001` | CODEOWNERS con Data Architects + Tech Leaders por carpeta | D | HIGH | — | regex | pr | lineamientos/estructura-repositorio.md CODEOWNERS — Gobierno de Código | KB_18 |
| `GOV-OPS-002` | pr.yml se ejecuta en pull_request | D | HIGH | — | schema | pr | lineamientos/estructura-repositorio.md .github/workflows/ | KB_18 |
| `GOV-OPS-003` | Workflows reutilizan base-workflows | D | MEDIUM | — | regex | pr | lineamientos/estructura-repositorio.md .github/workflows/ | KB_18 |
| `GOV-OPS-004` | El PR valida lint, tests, contratos, metadata y seguridad | D | MEDIUM | — | regex | pr | 15-dataops-cicd.md §16 | KB_18 |
| `GOV-OPS-005` | Tests unitarios para el código del producto | D | MEDIUM | ideacion:OFF, diseno:OFF, salida:LOW | path | pr | 15-dataops-cicd.md §19 | KB_18 |
| `GOV-OPS-006` | Smoke tests post-deploy | D | HIGH | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | path | gate | 15-dataops-cicd.md §19, §26 | KB_18 |
| `GOV-OPS-007` | Silver→Gold solo en dbt | D | HIGH | — | path | pr | lineamientos/estructura-repositorio.md modeling/ | KB_18, KB_07 |
| `GOV-OPS-008` | deploy.yml coherente con la política de ramas | D | MEDIUM | — | schema | pr | 15-dataops-cicd.md §15 | KB_18 |
| `GOV-OPS-009` | Waivers válidos y vigentes | D | HIGH | — | schema | pr, periodic | 15-dataops-cicd.md §8 | KB_18 |
| `GOV-OPS-010` | Template de PR con campos de gobierno | D | MEDIUM | ideacion:LOW | regex | pr | 15-dataops-cicd.md §16 | KB_18 |
| `GOV-OPS-011` | Orquestación versionada en Step Functions | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | path | pr, gate | lineamientos/estructura-repositorio.md pipelines/ | KB_18 |
| `GOV-OPS-012` | Configuración de ambiente externalizada | D | MEDIUM | — | regex | pr | 15-dataops-cicd.md §22 | KB_18 |
| `GOV-OPS-013` | Sin recursos productivos creados manualmente | O | HIGH | — | human | runtime | 15-dataops-cicd.md §21 | KB_18 |

### Arquitectura y modelado

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-ARC-001` | Modelos de consumo no leen Bronze | D | HIGH | — | regex | pre-commit, pr | 14-data-consumption-exploitation-framework.md §8.2 | KB_06 |
| `GOV-ARC-002` | Sin SELECT * en capas de consumo | D | MEDIUM | — | regex | pre-commit, pr | 01-data-principles.md §8 | KB_06, KB_05 |
| `GOV-ARC-003` | dbt con ref()/source() (sin relaciones físicas hardcodeadas) | D | MEDIUM | — | regex | pr | 01-data-principles.md §8 | KB_07 |
| `GOV-ARC-004` | Sin sobrescritura destructiva en datos críticos | D | HIGH | — | ast | pre-commit, pr | 01-data-principles.md §5 | KB_06 |
| `GOV-ARC-005` | Almacenamiento con Time Travel | D | HIGH | ideacion:OFF, salida:LOW | schema | pr, gate | 01-data-principles.md §5 | KB_06 |
| `GOV-ARC-006` | Dominios de negocio, no de tecnología | D | HIGH | — | regex | pr | 01-data-principles.md §7 | KB_03, KB_01 |
| `GOV-ARC-007` | Modelos Gold con tests de claves | D | MEDIUM | — | schema | pr | 08-data-quality-framework.md §10.2-§10.3 | KB_07, KB_08 |
| `GOV-ARC-008` | Modelos dbt documentados | H | MEDIUM | — | schema | pr | 09-metadata-governance.md §22 | KB_07, KB_09 |
| `GOV-ARC-009` | Modelado dimensional correcto | S | HIGH | — | llm | pr | 06-data-product-definition.md §14 (Bloque 8) | KB_07 |
| `GOV-ARC-010` | Uso apropiado de ARTS | S | MEDIUM | — | llm | pr | 06-data-product-definition.md §14 Relación con ARTS | KB_07 |
| `GOV-ARC-011` | Patrón batch / real-time justificado por valor | S | MEDIUM | — | llm | pr | 01-data-principles.md §11 | KB_06 |
| `GOV-ARC-012` | Límites de dominio respetados | S | HIGH | — | llm | pr | 02.1-business-capability-alignment.md §7 | KB_03, KB_01 |
| `GOV-ARC-013` | Diseño AI-ready (feature reuse) | S | LOW | — | llm | pr | 01-data-principles.md §10 | KB_15 |
| `GOV-ARC-014` | Arquitectura de datos documentada | D | MEDIUM | ideacion:OFF, diseno:MEDIUM, desarrollo:HIGH, gate:HIGH, operacion:HIGH, salida:OFF | path | pr, gate | 06-data-product-definition.md §26 DoR | KB_06 |

### Semantic layer y métricas

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-SML-001` | Ficha de métrica completa | D | HIGH | — | schema | pr | 11-semantic-layer-framework.md §15 | KB_12 |
| `GOV-SML-002` | Una métrica, una definición | D | BLOCKER | — | graph | pr | 11-semantic-layer-framework.md §30 | KB_12 |
| `GOV-SML-003` | No redefinir métricas corporativas localmente | D | BLOCKER | — | graph | pr | 14-data-consumption-exploitation-framework.md §12.2 | KB_12, KB_14 |
| `GOV-SML-004` | Métrica mapeada a término de glosario existente | D | MEDIUM | — | graph | pr | 11-semantic-layer-framework.md §11 | KB_12, KB_09 |
| `GOV-SML-005` | Ficha de dimensión compartida | D | MEDIUM | — | schema | pr | 11-semantic-layer-framework.md §16 | KB_12 |
| `GOV-SML-006` | Jerarquías gobernadas | D | LOW | — | schema | pr | 11-semantic-layer-framework.md §17 | KB_12 |
| `GOV-SML-007` | Publicación a consumidores solo desde capas certificadas | D | HIGH | — | regex | pr | 01-data-principles.md §9 | KB_12, KB_14 |
| `GOV-SML-008` | Métricas estratégicas fuera de la herramienta BI | H | HIGH | — | regex | pr | 11-semantic-layer-framework.md §19 | KB_12, KB_14 |
| `GOV-SML-009` | Definición de métrica inequívoca | S | HIGH | — | llm | pr | 11-semantic-layer-framework.md §15, §22 | KB_12 |
| `GOV-SML-010` | Reconciliación de KPIs entre consumidores | O | HIGH | — | human | runtime | 08-data-quality-framework.md §18 | KB_12, KB_17 |

### Consumo y explotación

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-CNS-001` | Patrón de consumo declarado (12 tipologías) | D | HIGH | — | schema | pr | 14-data-consumption-exploitation-framework.md §9 | KB_13 |
| `GOV-CNS-002` | Clasificación en las 12 dimensiones de consumo | D | HIGH | ideacion:OFF, salida:LOW | schema | pr | 14-data-consumption-exploitation-framework.md §13 | KB_13 |
| `GOV-CNS-003` | Plataforma de exposición acorde al patrón | D | HIGH | — | graph | pr | 14-data-consumption-exploitation-framework.md §10, §14, §15 | KB_13, KB_14 |
| `GOV-CNS-004` | Consumo solo desde Data Products maestros | D | BLOCKER | — | graph | pr | 14-data-consumption-exploitation-framework.md §8.2, §16.1 | KB_13 |
| `GOV-CNS-005` | API operacional sobre serving operacional | D | HIGH | — | graph | pr | 14-data-consumption-exploitation-framework.md §10.5 | KB_14 |
| `GOV-CNS-006` | Reverse ETL con consentimiento y auditoría | D | BLOCKER | — | schema | pr, gate | 14-data-consumption-exploitation-framework.md §10.6 | KB_14, KB_10 |
| `GOV-CNS-007` | Extracción masiva con formato y controles de entrega | D | MEDIUM | — | schema | pr | 14-data-consumption-exploitation-framework.md §9.10 | KB_14 |
| `GOV-CNS-008` | Certificación de Data Product Analítico de Consumo (8 validaciones) | D | BLOCKER | ideacion:OFF, diseno:OFF, desarrollo:LOW, salida:OFF | graph | gate | 14-data-consumption-exploitation-framework.md §16 | KB_14 |
| `GOV-CNS-009` | Estado de calidad del maestro visible al consumidor | D | MEDIUM | — | schema | pr | 14-data-consumption-exploitation-framework.md §16.7 | KB_14, KB_08 |
| `GOV-CNS-010` | Sin filtros locales que oculten calidad del maestro | H | MEDIUM | — | regex | pr | 14-data-consumption-exploitation-framework.md §8.8 | KB_14 |
| `GOV-CNS-011` | Inactividad → candidato a retiro | D | HIGH | ideacion:OFF, diseno:OFF, desarrollo:OFF, gate:OFF, salida:OFF | threshold | periodic | 14-data-consumption-exploitation-framework.md §17, §21 | KB_14, KB_19 |
| `GOV-CNS-012` | Detalle transaccional masivo en BI | D | HIGH | — | schema | pr | 14-data-consumption-exploitation-framework.md §8.7, §15.8 | KB_13 |
| `GOV-CNS-013` | Patrón fit-for-purpose | S | HIGH | — | llm | pr | 14-data-consumption-exploitation-framework.md §3, §8.1 | KB_13 |
| `GOV-CNS-014` | Reutilizar antes de crear | S | MEDIUM | — | llm | pr | 14-data-consumption-exploitation-framework.md §8.6 | KB_13 |

### AI / ML / GenAI

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-AIM-001` | Features con ficha completa | D | HIGH | — | schema | pr | 12-ai-ml-data-framework.md §12 | KB_15 |
| `GOV-AIM-002` | Dataset de entrenamiento especificado y versionado | D | HIGH | — | schema | pr | 12-ai-ml-data-framework.md §14 | KB_15 |
| `GOV-AIM-003` | Evaluación con partición temporal y control de leakage | D | HIGH | — | schema | pr | 12-ai-ml-data-framework.md §15 | KB_15 |
| `GOV-AIM-004` | Consistencia entrenamiento ↔ inferencia | D | BLOCKER | ideacion:OFF, diseno:MEDIUM, desarrollo:HIGH | graph | pr, gate | 12-ai-ml-data-framework.md §16 | KB_15 |
| `GOV-AIM-005` | Features derivadas de Data Products declarados | D | HIGH | — | graph | pr | 12-ai-ml-data-framework.md §10 | KB_15 |
| `GOV-AIM-006` | Monitores de drift de datos y de modelo | D | HIGH | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | schema | gate | 12-ai-ml-data-framework.md §23 | KB_15, KB_17 |
| `GOV-AIM-007` | PII en features con consentimiento y minimización | D | HIGH | — | schema | pr | 12-ai-ml-data-framework.md §22 | KB_15, KB_10 |
| `GOV-AIM-008` | Corpus RAG gobernado | D | HIGH | — | schema | pr | 12-ai-ml-data-framework.md §18-§19 | KB_16 |
| `GOV-AIM-009` | Retención de prompts y embeddings | D | MEDIUM | — | schema | pr | 12-ai-ml-data-framework.md §22 | KB_16 |
| `GOV-AIM-010` | Output del modelo gobernado como Data Product | D | MEDIUM | ideacion:OFF, salida:LOW | schema | pr | 12-ai-ml-data-framework.md §17 | KB_15 |
| `GOV-AIM-011` | Riesgo de leakage en features | S | HIGH | — | llm | pr | 12-ai-ml-data-framework.md §15, §21 | KB_15 |
| `GOV-AIM-012` | Problema que requiere primero un mejor Data Product base | S | MEDIUM | — | llm | pr | 12-ai-ml-data-framework.md §28 | KB_15 |

### Observabilidad

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-OBS-001` | Monitores del Data Product definidos | D | HIGH | ideacion:OFF, diseno:LOW, desarrollo:MEDIUM, gate:BLOCKER, operacion:BLOCKER, salida:LOW | path | pr, gate | 13-data-observability.md §3 | KB_17 |
| `GOV-OBS-002` | Cobertura de los 5 pilares de observabilidad | D | HIGH | ideacion:OFF, diseno:OFF, desarrollo:MEDIUM, salida:OFF | count | pr, gate | 13-data-observability.md §9 | KB_17 |
| `GOV-OBS-003` | Monitores con severidad, owner y canal | D | HIGH | — | schema | pr | 13-data-observability.md §24, §28 | KB_17 |
| `GOV-OBS-004` | Health indicators del Data Product | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | count | pr, gate | 13-data-observability.md §25 | KB_17 |
| `GOV-OBS-005` | Monitores críticos enlazan runbook | D | MEDIUM | — | graph | pr | 13-data-observability.md §23 | KB_17, KB_18 |
| `GOV-OBS-006` | Observabilidad de uso y adopción | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | schema | gate | 13-data-observability.md §18 | KB_17, KB_20 |
| `GOV-OBS-007` | Observabilidad de seguridad para datos sensibles | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:LOW, gate:HIGH, operacion:HIGH, salida:OFF | schema | gate | 13-data-observability.md §22 | KB_17, KB_10 |
| `GOV-OBS-008` | Umbrales de alerta relevantes (sin ruido) | S | MEDIUM | — | llm | pr | 13-data-observability.md §28 | KB_17 |

### Ciclo de vida

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-LCY-001` | Estado del ciclo de vida válido | D | BLOCKER | — | schema | pr, catalog | 18-data-product-lifecycle.md §9 | KB_19 |
| `GOV-LCY-002` | Transición de estado permitida | D | HIGH | — | diff | pr | 18-data-product-lifecycle.md §22 | KB_19 |
| `GOV-LCY-003` | Retiro gobernado | D | HIGH | — | schema | pr | 18-data-product-lifecycle.md §20 | KB_19 |
| `GOV-LCY-004` | Estado de catálogo coherente con el lifecycle | D | MEDIUM | — | graph | pr, catalog | 18-data-product-lifecycle.md §27 | KB_19, KB_09 |
| `GOV-LCY-005` | Mínimos de scoring por estado | D | HIGH | ideacion:LOW, gate:BLOCKER, salida:OFF | graph | gate | 19-scoring-model.md §27 | KB_20, KB_19 |
| `GOV-LCY-006` | Evolución coherente con el propósito | S | MEDIUM | — | llm | pr | 18-data-product-lifecycle.md §18 | KB_19 |
| `GOV-LCY-007` | Revisión periódica de valor y adopción | O | MEDIUM | — | human | periodic | 18-data-product-lifecycle.md §26 | KB_19, KB_20 |

### Scoring

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-SCO-001` | Scorecard de 11 pilares con evidencia | D | MEDIUM | ideacion:OFF, diseno:LOW, gate:HIGH, operacion:HIGH, salida:OFF | schema | gate | 19-scoring-model.md §10-§11, §28 | KB_20 |
| `GOV-SCO-002` | Score declarado respaldado por evidencia automatizada | D | MEDIUM | — | graph | gate | 19-scoring-model.md §28 | KB_20 |
| `GOV-SCO-003` | Scoring vigente (cadencia trimestral) | D | MEDIUM | ideacion:OFF, diseno:OFF, desarrollo:OFF, gate:OFF, salida:OFF | threshold | periodic | 19-scoring-model.md §30 | KB_20 |
| `GOV-SCO-004` | Evaluación colaborativa (≥2 roles) | D | LOW | — | count | gate | 19-scoring-model.md §29 | KB_20 |
| `GOV-SCO-005` | Nivel estratégico con mínimos de scoring | D | HIGH | ideacion:OFF, diseno:OFF, desarrollo:OFF, salida:OFF | graph | gate | 19-scoring-model.md §27 | KB_20 |

### Negocio y casos de uso

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-BIZ-001` | Capacidad de negocio asociada | D | BLOCKER | ideacion:HIGH | schema | pr, gate | 02.1-business-capability-alignment.md §21 Regla final | KB_01 |
| `GOV-BIZ-002` | Caso de uso asociado | D | HIGH | ideacion:MEDIUM | schema | pr | 02.2-use-case-definition.md §19 | KB_02 |
| `GOV-BIZ-003` | KPI e hipótesis de valor | D | HIGH | ideacion:MEDIUM | schema | pr | 02.2-use-case-definition.md §21 Regla final | KB_02, KB_01 |
| `GOV-BIZ-004` | Problema y decisión habilitada explícitos | D | HIGH | ideacion:MEDIUM | schema | pr | 06-data-product-definition.md §9 (Bloque 3) | KB_02 |
| `GOV-BIZ-005` | Capacidad registrada en el mapa corporativo | D | MEDIUM | — | graph | pr | 02.1-business-capability-alignment.md §3 | KB_01 |
| `GOV-BIZ-006` | Caso de uso con información mínima obligatoria | D | HIGH | — | schema | pr | 02.2-use-case-definition.md §10 | KB_02 |
| `GOV-BIZ-007` | Tipo de caso de uso | D | MEDIUM | — | schema | pr | 02.2-use-case-definition.md §8 | KB_02 |
| `GOV-BIZ-008` | Formulación orientada a herramienta (anti-patrón) | H | MEDIUM | — | regex | pr | 02.2-use-case-definition.md §2, §19 | KB_02 |
| `GOV-BIZ-009` | Valor específico y medible | S | HIGH | — | llm | pr | 02.2-use-case-definition.md §15 | KB_02 |
| `GOV-BIZ-010` | Coherencia capacidad → dominio → producto | S | HIGH | — | llm | pr | 02.1-business-capability-alignment.md §6-§11 | KB_01, KB_03 |
| `GOV-BIZ-011` | Sponsorship real de negocio y tecnología | O | MEDIUM | — | human | periodic | 02-data-strategy.md §21 | KB_01 |
| `GOV-BIZ-012` | Priorización por valor, no por disponibilidad técnica | O | MEDIUM | — | human | periodic | 02-data-strategy.md §20 | KB_01 |

### OpenMetadata (pack omd)

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-OMD-001` | Rol cross-account llamado exactamente openmetadata-readonly | D | BLOCKER | — | schema | pr | lineamientos/openmetadata-cross-account-role.md 2.3 | KB_21 |
| `GOV-OMD-002` | Aislamiento de ambientes TEST↔TEST / PROD↔PROD | D | BLOCKER | — | policy | pr | lineamientos/openmetadata-cross-account-role.md 2.1 | KB_21 |
| `GOV-OMD-003` | Trust con sts:AssumeRole y sts:TagSession | D | BLOCKER | — | policy | pr | lineamientos/openmetadata-cross-account-role.md Cómo funciona | KB_21 |
| `GOV-OMD-004` | Policy del ambiente correcto | D | BLOCKER | — | schema | pr | lineamientos/openmetadata-cross-account-role.md 2.3 | KB_21 |
| `GOV-OMD-005` | Cuenta gestionada por access-analyzer | D | HIGH | — | graph | pr | lineamientos/openmetadata-cross-account-role.md 2.2 | KB_21 |
| `GOV-OMD-006` | Policy del ambiente con ARNs de cada cuenta | D | HIGH | — | graph | pr | lineamientos/openmetadata-cross-account-role.md 2.4 | KB_21 |
| `GOV-OMD-007` | Sid descriptivo en trust | D | LOW | — | regex | pr | lineamientos/openmetadata-cross-account-role.md 5 | KB_21 |
| `GOV-OMD-008` | Conexión de ingesta sin llaves estáticas | D | BLOCKER | — | schema | pre-commit, pr | lineamientos/openmetadata-guia-rapida-aws.md 3 | KB_21 |
| `GOV-OMD-009` | Región válida (no zona de disponibilidad) | D | HIGH | — | regex | pre-commit, pr | lineamientos/openmetadata-guia-rapida-aws.md 3 | KB_21 |
| `GOV-OMD-010` | Instancia OMD y cuenta del mismo ambiente | D | BLOCKER | — | graph | pr | lineamientos/openmetadata-guia-rapida-aws.md 1 | KB_21 |
| `GOV-OMD-011` | Filtros de inclusión anclados | D | LOW | — | regex | pr | lineamientos/openmetadata-cross-account-role.md 1.2 | KB_21 |
| `GOV-OMD-012` | DynamoDB con filtro de tablas | D | MEDIUM | — | schema | pr | lineamientos/openmetadata-cross-account-role.md 1.1 | KB_21 |
| `GOV-OMD-013` | S3 Storage filtrado a ^cencosud- | D | MEDIUM | — | schema | pr | lineamientos/openmetadata-cross-account-role.md 3.5 | KB_21 |
| `GOV-OMD-014` | Session name por servicio (trazabilidad CloudTrail) | D | LOW | — | schema | pr | lineamientos/openmetadata-cross-account-role.md 5 | KB_21 |
| `GOV-OMD-015` | Aprobación de Seguridad Informática del MR | O | BLOCKER | — | human | pr | lineamientos/openmetadata-cross-account-role.md 2.6 | KB_21 |

### Documentación del framework (pack docs)

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-DOC-001` | Referencias cruzadas a documentos existentes | D | MEDIUM | — | graph | pr | 02-data-strategy.md §19 | KB_00 |
| `GOV-DOC-002` | Encabezado de documento (Versión, Estado, Alcance) | D | LOW | — | regex | pr | 01-data-principles.md Encabezado | KB_00 |
| `GOV-DOC-003` | Numeración de secciones secuencial | D | LOW | — | regex | pr | 06-data-product-definition.md estructura editorial | KB_00 |
| `GOV-DOC-004` | Regla final presente | D | LOW | — | regex | pr | 01-data-principles.md patrón editorial | KB_00 |
| `GOV-DOC-005` | Inventario de pendientes documentales | D | INFO | — | regex | periodic | 12-ai-ml-data-framework.md encabezado | KB_00 |

### Portafolio cross-repo (pack portfolio)

| ID | Regla | Nat. | Sev. base | Escalamiento por etapa | Técnica | Control | Fuente | KB |
|---|---|:-:|---|---|---|---|---|---|
| `GOV-PRT-001` | IDs de Data Product únicos en el portafolio | D | BLOCKER | — | graph | periodic | 06-data-product-definition.md §7 | KB_04 |
| `GOV-PRT-002` | Productos retirados no consumidos | D | HIGH | — | graph | periodic | 18-data-product-lifecycle.md §30 | KB_19 |
| `GOV-PRT-003` | Referencias a Data Products existentes | D | MEDIUM | — | graph | periodic | 06-data-product-definition.md §24 (Bloque 18) | KB_05 |
| `GOV-PRT-004` | DP de consumo alimentados por maestros | D | HIGH | — | graph | periodic | 14-data-consumption-exploitation-framework.md §8.2 | KB_13 |
| `GOV-PRT-005` | Una métrica, una definición (portafolio) | D | BLOCKER | — | graph | periodic | 11-semantic-layer-framework.md §30 | KB_12 |
| `GOV-PRT-006` | Solapamiento de productos (candidatos a consolidación) | D | MEDIUM | — | graph | periodic | 18-data-product-lifecycle.md §19 | KB_19 |

## 4. Preguntas semánticas (reglas S e H) entregadas al revisor LLM

- `GOV-STR-007` (H) — ¿El README explica el propósito de negocio del Data Product de forma comprensible para un consumidor no técnico?
- `GOV-DPD-026` (H) — ¿La descripción permite a un consumidor entender en menos de un minuto qué es, qué decisión habilita y qué NO incluye el Data Product?
- `GOV-CTR-013` (H) — ¿Las descripciones de los campos son inequívocas (unidad, moneda, zona horaria, reglas de cálculo) y consistentes con el glosario?
- `GOV-CTR-014` (S) — ¿Algún campo cambió de significado (regla de cálculo, unidad, universo) manteniendo nombre y tipo? Eso es breaking aunque el schema no cambie.
- `GOV-MET-016` (H) — ¿La descripción del contrato explica qué promete el productor, a quién y con qué granularidad?
- `GOV-MET-017` (S) — ¿La descripción de negocio, el glosario y los contratos describen el mismo objeto (granularidad, universo, exclusiones)?
- `GOV-QLT-014` (H) — ¿Las reglas definidas en Bronze se limitan a esquema, recepción, volumen y parsing?
- `GOV-QLT-015` (S) — ¿Los umbrales y severidades son coherentes con el consumo declarado (ejecutivo, operacional, AI) y la criticidad?
- `GOV-QLT-017` (H) — ¿Las ventanas temporales de las features evitan leakage respecto del target?
- `GOV-SEC-007` (H) — Para cada campo señalado, ¿contiene realmente un dato personal identificable o identificador indirecto?
- `GOV-SEC-013` (H) — ¿La vista necesita el dato personal completo para su propósito, o puede minimizarse?
- `GOV-SEC-015` (S) — ¿Los controles declarados (acceso, masking, RLS, exposición) son proporcionales a la sensibilidad y criticidad, sin sobre- ni sub-protección?
- `GOV-SEC-016` (S) — ¿Algún modelo o vista permite reidentificar personas combinando atributos no PII (cuasi-identificadores) o filtros de baja cardinalidad?
- `GOV-IAM-015` (H) — ¿El acceso a buckets de otro dominio corresponde a un input declarado con contrato, o expone consumo por conocimiento implícito de tablas?
- `GOV-ARC-008` (H) — ¿La descripción de cada modelo declara grano, universo y reglas de negocio principales?
- `GOV-ARC-009` (S) — ¿Cada hecho declara un grano único, sus medidas son coherentes con ese grano y las dimensiones son conformadas (tiempo, producto, tienda, canal, país)?
- `GOV-ARC-010` (S) — ¿La elección alineado/extensión/modelo propio está justificada por el lenguaje del dominio y documentada?
- `GOV-ARC-011` (S) — ¿La latencia elegida (batch/streaming/CDC) está justificada por la decisión de negocio que habilita?
- `GOV-ARC-012` (S) — ¿El producto redefine entidades de otro dominio (cliente, producto, tienda) en vez de consumirlas por contrato?
- `GOV-ARC-013` (S) — ¿Las entidades y atributos del producto permiten derivar features reutilizables (claves estables, historia, timestamps de evento)?
- `GOV-SML-008` (H) — ¿La medida BI es una presentación de la métrica oficial o reimplementa su lógica?
- `GOV-SML-009` (S) — ¿La fórmula, filtros y granularidad de cada métrica permiten calcularla de una sola forma, coherente con su término de glosario?
- `GOV-CNS-010` (H) — ¿El filtro responde a una regla de negocio documentada o está ocultando un problema de calidad del maestro?
- `GOV-CNS-013` (S) — Dadas audiencia, interacción, volumen, latencia y acción, ¿el patrón y la plataforma elegidos son los adecuados según la matriz 14 §14?
- `GOV-CNS-014` (S) — ¿Existe en el catálogo un producto o modelo semántico certificado que ya resuelva esta necesidad?
- `GOV-AIM-011` (S) — ¿Alguna feature usa información posterior al momento de predicción (ventanas que cruzan la fecha de corte del target)?
- `GOV-AIM-012` (S) — ¿El caso AI compensa con el modelo carencias de calidad o completitud del Data Product fuente?
- `GOV-OBS-008` (S) — ¿Los umbrales de los monitores reflejan el propósito del producto (p.ej. freshness relativa a la ventana de negocio) y evitan alertas irrelevantes?
- `GOV-LCY-006` (S) — ¿La evolución mantiene el propósito original o amerita versión MAJOR / nuevo Data Product?
- `GOV-BIZ-008` (H) — ¿El problema está expresado como decisión de negocio y KPI, o como solicitud de una herramienta?
- `GOV-BIZ-009` (S) — ¿La hipótesis de valor es específica (meta, horizonte, línea base) y medible con los KPIs declarados?
- `GOV-BIZ-010` (S) — ¿El dominio principal declarado es el que naturalmente corresponde a la capacidad y a las entidades del producto?

