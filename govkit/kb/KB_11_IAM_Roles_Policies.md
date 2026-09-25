---
id: KB_11
slug: iam_roles_policies
title: IAM por Data Product — 1 rol, 2 policies, aislamiento total
version: 1.0.0
status: vigente
tier: 4
sources: ["lineamientos/iam-roles-policies.md"]
applies_to: [data_product_maestro, consumo]
triggers:
  tasks: [iam_policies, pipeline_cicd_repo]
  paths: ["infra/iam/**", "**/roles.json", "**/policy-*.json"]
  rules: ["GOV-IAM-*", "GOV-NAM-009", "GOV-NAM-010", "GOV-NAM-011", "GOV-NAM-012"]
  keywords: [iam, rol, policy, permisos, wildcard, kms, s3, glue, athena, least privilege, tags, "6144"]
depends_on: [KB_00]
related: [KB_10, KB_18]
token_budget: 950
deterministic_rules: [GOV-IAM-001, GOV-IAM-002, GOV-IAM-003, GOV-IAM-004, GOV-IAM-005, GOV-IAM-006, GOV-IAM-007, GOV-IAM-008, GOV-IAM-009, GOV-IAM-010, GOV-IAM-011, GOV-IAM-012, GOV-IAM-013, GOV-IAM-014]
---
# KB_11 · IAM por Data Product
> Cada producto tiene sus recursos IAM aislados; eliminarlo o modificarlo no afecta a otros productos.

## R · Reglas canónicas
- **KB11.R1 [MUST]** 1 rol (`cencosud-role-{repo}`) + 2 policies: `-data` (S3, Glue Catalog, KMS, Athena) y `-infra` (Logs, EC2, Secrets, ECR, EMR, STS/IAM). La división responde al límite de 6144 caracteres por managed policy con criterio semántico.
- **KB11.R2 [MUST]** Sin roles ni policies compartidos entre productos.
- **KB11.R3 [MUST]** Regla de wildcard: en recursos EXCLUSIVOS del producto (bucket/database con prefijo del dominio del producto) el wildcard en read/write/delete está permitido; en recursos COMPARTIDOS (paths dentro de bucket compartido) el recurso debe ser explícito.
- **KB11.R4 [MUST]** KMS siempre con account y key ID explícitos, restringido por `kms:ViaService`.
- **KB11.R5 [MUST]** Lectura y escritura en statements separados (`{Servicio}Read` / `{Servicio}Write`); Write y Delete pueden compartir statement sobre los mismos recursos exclusivos.
- **KB11.R6 [MUST]** Región fija us-east-1; account ID `*` para la misma policy en dev y prod (excepto KMS); S3 sin región/cuenta.
- **KB11.R7 [MUST]** 19 tags obligatorios en rol y policies (ceco, ambiente, pais, unidad-negocio, bandera, propietario, creado-por, aplicacion, plataforma, proyecto, nombre, Name, cuenta, repo, tf-pipeline, tf-module, by, pep, apl).
- **KB11.R8 [MUST]** Ciclo de vida por PR → review de seguridad → CI despliega; nuevo recurso exclusivo = wildcard permitido.

## H · Heurísticas de decisión
- **KB11.H1** ¿Es exclusivo? Si el nombre del bucket/database contiene el código de dominio del producto → exclusivo por nomenclatura; si otro producto escribe ahí → compartido.
- **KB11.H2** Leer datos de otro dominio vía S3 suele indicar consumo por conocimiento implícito: preferir su Data Product/serving con contrato.
- **KB11.H3** Si la policy se acerca a 6144 caracteres, consolidar statements por recurso exclusivo antes de crear policies nuevas.

## A · Anti-patrones
- **KB11.A1** `Resource: "*"` con escritura. · **KB11.A2** KMS con wildcard. · **KB11.A3** Mezclar servicios de datos en la policy infra.

## V · Preguntas de verificación
1. **KB11.V1** ¿Los recursos marcados como exclusivos lo son realmente (ningún otro producto escribe en ellos)?
2. **KB11.V2** ¿Los accesos cross-dominio están respaldados por un input con contrato?

## D · Ya verificado por el motor determinista
Casi todo este mini-contexto es determinista (nombres, tamaño, R/W, wildcards, KMS, región, account, trust, tags, alcance, Sid). Úsalo para explicar y remediar, no para re-auditar.
