# Hallazgos de Auditoría Documental del Data & AI Discipline Framework

Versión: 1.0
Estado: Propuesta para revisión (Arquitectura de Datos Regional · Gobierno de Datos)
Fecha: 2026-09-25
Alcance: Documentos 01, 02, 02.1, 02.2, 06, 08–15, 18, 19 y lineamientos IAM, Estructura de Repositorio y OpenMetadata

---

## 1. Por qué importa

Una regla determinista necesita un criterio **único y cerrado**. Al convertir cada lineamiento en una regla del catálogo
(`govkit/rules/catalog.yaml`) aparecieron contradicciones, referencias rotas y definiciones incompletas. Mientras no se
resuelvan, el motor aplica la interpretación indicada en la columna "Tratamiento en govkit" (configurable) y la KB
instruye al LLM a **reportar** los conflictos, nunca a resolverlos (KB00.H3).

Cómo re-ejecutar esta auditoría sobre el repositorio real del framework:

```bash
govkit docs-lint <carpeta-con-los-.md-del-framework>     # referencias, encabezados, numeración, pendientes
```

## 2. Hallazgos

Severidad: **A** = bloquea una validación exacta · **M** = genera ambigüedad · **B** = editorial.

| ID | Sev. | Hallazgo | Evidencia | Tratamiento en govkit | Resolución propuesta |
|---|:-:|---|---|---|---|
| H-01 | A | **Estrategia de ramas contradictoria** | 15 §15: trunk-based, "No se recomienda usar ramas por ambiente como dev, qa, prod". Estructura de Repositorio: `develop`→DATA TEST, `staging`→STAGING, `main`→PROD; `deploy.yml` se dispara en push a las 3 ramas. | `policies.branching: env-branches` por defecto (refleja la operación actual); `trunk` disponible; regla `GOV-OPS-008` valida coherencia de `deploy.yml` con la política declarada. | ADR-006: decidir un único modelo. Recomendación: trunk-based + promoción por pipeline con *environments* de GitHub (aprobación manual para prod), que cumple 15 §15 y mantiene el mapeo de cuentas AWS. |
| H-02 | A | **Estructura de repositorio divergente** | 15 §14: `CHANGELOG.md`, `infra/`, `config/`, `scripts/`, `artifacts/`, `models/`. Estructura de Repositorio ("nombres fijos"): sin esas carpetas, `modeling/dbt`, `metadata/{catalog,lineage,tags}`. 15 §18: `metadata/domain.yaml`, `data_product.yaml`, … planos; y `data_quality.yaml` en metadata vs `quality/expectations/`. Lineamiento IAM no indica dónde viven `roles.json`/`policy-*.json`. | Estándar fijo como normativo; `infra/`, `config/`, `scripts/`, `artifacts/` permitidos como extensiones (`allowed_extra_top_level`); `CHANGELOG.md` exigido (`GOV-STR-006`); metadata canónica en `metadata/catalog/*.yaml`; IAM en `infra/iam/`; calidad en `quality/expectations/` (acepta `metadata/data_quality.yaml`). | Actualizar el lineamiento de estructura: incorporar `CHANGELOG.md` e `infra/iam/`, y fijar la ubicación de cada archivo de metadata-as-code. |
| H-03 | A | **Referencias cruzadas renumeradas** | Tras insertar `14-data-consumption-exploitation-framework.md`, DataOps pasó a `15-dataops-cicd.md` y Scoring a `19-scoring-model.md`, pero 06, 08, 10, 12, 13, 18 y 19 citan `14-dataops-cicd.md`; 06, 08-13, 15 y 18 citan `15-scoring-model.md` (15 se cita a sí mismo como scoring). 18 y 19 citan `15.1-data-value-metrics.md`. | Pack `docs` (`GOV-DOC-001`) detecta referencias inexistentes y sugiere el archivo con igual *slug*. Las reglas del catálogo citan los nombres reales. | Renumerar referencias en un solo PR; decidir si `15.1-data-value-metrics.md` pasa a `19.1-…`. |
| H-04 | A | **Tipos de Data Product vs código de tipo del repo** | 06 §7: Analytical, Operational, SaaS-driven, AI/ML, Semantic/Metrics. Nombre de repo: `{type}` ∈ `txd` (transaccional) \| `anl` (analítico). En el ejemplo de jobs `job_slv_prd_txd_…`, `txd` ocupa la posición de `{domain}`. Ejemplo IAM `customer-master-dp-pe` omite `{type}`. | `repo_type_codes: {txd, anl}` en registro; `spec.type` usa los 5 tipos de 06; `scaffold` mapea `txd→operational`, `anl→analytical`. | Definir tabla oficial tipo 06 ↔ código de repo (p.ej. `anl`, `opr`, `saa`, `aiml`, `sem`) y corregir el ejemplo de jobs. |
| H-05 | M | **Número de dimensiones de calidad** | 01 §4: 5 dimensiones. 06 Bloque 10: 6 (agrega integridad referencial). 08 §9: 8 (agrega exactitud y trazabilidad). | Enum de 8 (08 §9); exigencia de ≥3 SLOs cuantificados (01 §4). | Alinear 01 §4 y 06 §16 a las 8 dimensiones de 08. |
| H-06 | M | **Estados del ciclo de vida** | 06 §7: 7 estados. 18 §9: 12 estados. 18 §27 (catálogo): `candidate, active, in production, evolving, deprecated, retired`. | 12 estados canónicos + alias de 06 + mapeo a estado de catálogo (`rules/registry/lifecycle.yaml`, `GOV-LCY-004`). | Declarar 18 §9 como fuente única y referenciarla desde 06 §7. |
| H-07 | M | **System of record del código** | 15 §8: GitHub es el system of record. Tag IAM `repo`: "URL del repositorio en GitLab"; `access-analyzer` vive en GitLab (Seguridad). | El tag `repo` solo exige URL https. | Aclarar: repos de Data Products en GitHub; repos de Seguridad pueden seguir en GitLab. Ajustar la descripción del tag. |
| H-08 | M | **Credenciales nominales vs identidades de servicio** | 10 §23: "preferir credenciales individuales o nominales por sobre usuarios de servicios o aplicaciones". Lineamiento IAM: rol de servicio por producto; OpenMetadata: rol del pod. | Se interpreta §23 como aplicable a accesos humanos; los pipelines usan identidades de carga de trabajo (roles), sin llaves estáticas (`GOV-SEC-006`, `GOV-OMD-008`). | Precisar 10 §23: "personas: credenciales nominales; cargas de trabajo: roles/identidades federadas, nunca llaves estáticas". |
| H-09 | M | **Wildcards no exclusivos en el ejemplo IAM** | Ejemplo de policy data: `athena:…` sobre `workgroup/Data*` (compartido); infra: `ecr:…` sobre `repository/*`. Contrasta con "aislamiento total entre productos". | Son lecturas/ejecución (no escritura): no violan `GOV-IAM-004`; la plantilla de `govkit init` usa `workgroup/{repo}` y `repository/{repo}*`. | Actualizar el ejemplo del lineamiento con recursos acotados al producto. |
| H-10 | M | **Ambiente en el nombre de los archivos de jobs** | `job_{zone}_{env}_{domain}_…` (p.ej. `_prd_`). El mismo código se despliega a dev/staging/prod (15 §22 config externa; IAM "misma policy en dev y prod"). | `GOV-NAM-003/004` validan la convención vigente. | Evaluar quitar `{env}` del nombre del archivo (el ambiente lo inyecta el deploy) para evitar duplicación por ambiente. |
| H-11 | M | **Particionamiento no normado** | Solo ejemplos (`año/mes/día/país` en 14 §11.4); 09 lo lista como metadata técnica. | KB_06 lo trata como `[PRÁCTICA]` (severidad máx. LOW en revisión semántica). | Incorporar lineamiento de particionamiento y compactación (Iceberg) si se requiere enforcement. |
| H-12 | M | **Registros referenciados pero no definidos** | Códigos de dominio de 3 letras usados en S3/Glue (solo aparece `cus`); lista de métricas corporativas (solo ejemplos en 11 §14.1 y 14 §12.2); mapa de capacidades pendiente (12 §11); tabla de alineamiento 02.1 §13-§14 comentada "Revisar más adelante". | Registros en `rules/registry/*.yaml` marcados `status: propuesta/pendiente`; reglas dependientes informativas (`GOV-BIZ-005`) o configurables. | Oficializar: registro de dominios (Data Council), métricas corporativas (Gobierno de Datos), mapa de capacidades (negocio). |
| H-13 | M | **Ponderación por tipo no cuantificada** | 19 §25: "mayor peso relativo" por tipo sin valores. | Multiplicador 1.5 propuesto y renormalizado (`registry/scoring.yaml`, marcado "a calibrar"). | Calibrar con la Planilla de Certificación (19 está en Draft). |
| H-14 | M | **Criterio de niveles de certificación** | 06 §25: "clasificación de niveles en base a los criterios de certificación de TOGAF". TOGAF no define niveles de certificación de Data Products. | Niveles `mvp | industrializado | estrategico` + mínimos de 19 §27. | Reemplazar por referencia a la Planilla de Certificación / Certification Gates propia. |
| H-15 | B | **Numeración de secciones** | 08: §10.6 antes de §10.5. 14: salta de §18 a §21 (§17 comentado). 19: bloques §23-§25 comentados y §23 repetida; salta a §39. | `GOV-DOC-003` los detecta. | Renumerar: las reglas citan `§N`, la numeración es parte de la trazabilidad. |
| H-16 | B | **Pendientes abiertos que afectan reglas** | 09 (pendiente validación Gobierno de Datos), 10 (pendiente Seguridad Informática), 12 §19, 19 (Draft), 02.2 (Draft v2.0), OMD v0.2 (conector S3, CloudWatch/KMS, nomenclatura de servicios, Redshift, Lake Formation). | KB_20 y KB_21 con `status: borrador`; `GOV-DOC-005` inventaría pendientes. | Asignar owner y fecha a cada pendiente. |
| H-17 | B | **Conceptos de consumo no reflejados en la ficha** | 14 §8.3 introduce "Data Product Maestro" vs "Analítico de Consumo" y 12 patrones con 12 dimensiones obligatorias; 06 no los incluye. | `spec.role`, `spec.consumption_pattern`, `spec.consumption.*` en la ficha canónica. | Agregar a 06 un bloque de "rol y patrón de consumo". |

## 3. Impacto en el catálogo

| Hallazgo | Reglas afectadas |
|---|---|
| H-01 | GOV-NAM-007, GOV-OPS-008 |
| H-02 | GOV-STR-001, GOV-STR-005, GOV-STR-006, artefactos `metadata/*`, `quality_rules`, `iam_*` |
| H-03 | GOV-DOC-001 |
| H-04 | GOV-NAM-001, GOV-NAM-003, GOV-DPD-005 |
| H-05 | GOV-QLT-003, GOV-QLT-006 |
| H-06 | GOV-LCY-001, GOV-LCY-004 |
| H-12 | GOV-NAM-002, GOV-MET-004/005, GOV-SML-003, GOV-BIZ-005, GOV-IAM-004 (códigos de dominio) |
| H-13 | Pre-score (`govkit score`), GOV-LCY-005, GOV-SCO-002 |
