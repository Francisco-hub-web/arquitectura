---
id: KB_21
slug: openmetadata_aws
title: OpenMetadata — conexiones AWS con cross-account role
version: 1.0.0
status: borrador
tier: 7
sources: ["lineamientos/openmetadata-guia-rapida-aws.md (v0.1 lite)", "lineamientos/openmetadata-cross-account-role.md (v0.2, con pendientes)"]
applies_to: [plataforma, catalogo]
triggers:
  tasks: [catalogar_openmetadata, conexion_omd]
  paths: ["**/roles.json", "**/*omdata-policy*.json", "**/*ingestion*.yaml", "metadata/catalog/openmetadata.yaml"]
  rules: ["GOV-OMD-*", "GOV-MET-011", "GOV-MET-012"]
  keywords: [openmetadata, omd, glue, dynamodb, s3, redshift, cross-account, assume role, access-analyzer, test connection, agente, ingesta, filtro, lake formation]
depends_on: [KB_00]
related: [KB_09, KB_11]
token_budget: 1100
deterministic_rules: [GOV-OMD-001, GOV-OMD-002, GOV-OMD-003, GOV-OMD-004, GOV-OMD-005, GOV-OMD-006, GOV-OMD-008, GOV-OMD-009, GOV-OMD-010, GOV-OMD-011, GOV-OMD-012, GOV-OMD-013]
---
# KB_21 · OpenMetadata con cross-account role
> OpenMetadata lee cada cuenta de datos asumiendo `openmetadata-readonly`; sin llaves estáticas y sin cruzar ambientes.

## R · Reglas canónicas
- **KB21.R1 [MUST]** Cadena: pod de ingesta (role `cct-plataforma-pod-omdata` en DG Corp del ambiente) → `sts:AssumeRole` + `sts:TagSession` → `openmetadata-readonly` en la cuenta de datos → Get/List de metadata.
- **KB21.R2 [MUST]** TEST con TEST (omd-test.cencosud.com, DG Corp 970641057631) y PROD con PROD (omd.cencosud.com, DG Corp 463953283464); cruzar ambientes falla por diseño.
- **KB21.R3 [MUST]** Formulario: solo AWS Region (región, no zona) y Role ARN; Enable IAM Auth OFF; llaves (Access Key, Secret, Session Token) vacías — si se llenan, reemplazan al rol y expiran.
- **KB21.R4 [MUST]** Alta de rol: MR en `access-analyzer` con entrada en roles.json (nombre exacto, principal del mismo ambiente, AssumeRole+TagSession, policy `2057-omdata-policy-{test|prod}`), ARNs Glue (catalog/database/table) y DynamoDB en la policy del ambiente; vigente solo tras aprobación de Seguridad Informática.
- **KB21.R5 [MUST]** Glue: Database OMD = Catalog ID; Schema = database Glue; filtros `re.match` anclados al inicio, no al final → exacto con `^nombre$`. Lake Formation puede ocultar tablas aunque el test esté en verde.
- **KB21.R6 [MUST]** DynamoDB: database/schema `default`; cada ejecución hace Scan de hasta 1000 ítems por tabla → filtrar tablas y programar fuera de horario punta.
- **KB21.R7 [MUST]** S3: conector Storage (containers + manifiesto `openmetadata.json`) vs Datalake (tablas inferidas) — estándar pendiente; filtro `^cencosud-`; GetMetrics puede fallar (CloudWatch no incluido).
- **KB21.R8 [MUST]** El acceso lee datos (GetObject, Scan) además de metadata: declararlo ante Seguridad.

## H · Heurísticas de decisión (troubleshooting)
- **KB21.H1** AccessDenied en AssumeRole → MR no aprobado, principal de otro ambiente, nombre distinto o falta TagSession.
- **KB21.H2** AccessDenied en GetTables/ListTables con AssumeRole OK → faltan ARNs de la cuenta/región en la policy del ambiente.
- **KB21.H3** ExpiredTokenException → hay llaves estáticas en el servicio: vaciarlas y usar solo el Role ARN.
- **KB21.H4** Session name por servicio (`omd-<servicio>`) para atribuir llamadas en CloudTrail.

## V · Preguntas de verificación
1. **KB21.V1** ¿El servicio se crea en la instancia del mismo ambiente que la cuenta?
2. **KB21.V2** ¿Se declaró ante Seguridad la lectura de datos (GetObject/Scan)?

## D · Ya verificado por el motor determinista
Pack `omd`: nombre del rol, aislamiento de ambientes, trust actions, policy del ambiente, cuenta gestionada, ARNs por cuenta, llaves estáticas, región, instancia vs cuenta, filtros anclados, DynamoDB/S3.
