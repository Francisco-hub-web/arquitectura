---
id: KB_10
slug: seguridad_privacidad
title: Seguridad, privacidad y compliance del Data Product
version: 1.0.0
status: vigente
tier: 4
sources: ["01-data-principles.md §13-§14", "10-data-security-framework.md §3-§30"]
applies_to: [data_product_maestro, consumo, ai_ml, integraciones]
triggers:
  tasks: [clasificar_seguridad_pii, exponer_consumo, promover_a_produccion, rag_genai]
  paths: ["infra/**", "publishing/**", "contracts/**"]
  rules: ["GOV-SEC-*", "GOV-DPD-009", "GOV-DPD-016", "GOV-CNS-006", "GOV-OBS-007", "GOV-AIM-007"]
  keywords: [seguridad, privacidad, pii, dato personal, clasificación, masking, tokenización, rls, cls, acceso, pia, retención, derecho al olvido, cifrado, secreto, auditoría]
depends_on: [KB_00]
related: [KB_11, KB_16, KB_12]
token_budget: 1050
deterministic_rules: [GOV-SEC-001, GOV-SEC-002, GOV-SEC-003, GOV-SEC-004, GOV-SEC-005, GOV-SEC-006, GOV-SEC-008, GOV-SEC-009, GOV-SEC-010, GOV-SEC-012, GOV-SEC-014]
---
# KB_10 · Seguridad y privacidad
> Seguridad y privacidad embebidas desde el diseño y proporcionales a la sensibilidad; la meta es habilitar el uso correcto y seguro del dato.

## R · Reglas canónicas
- **KB10.R1 [MUST]** Clasificación explícita: Público, Interno, Confidencial, Sensible/PII (según regulación de cada país) + atributos: PII, financiero, exposición a terceros, retención especial, masking. (10 §10)
- **KB10.R2 [MUST]** Evaluar sensibilidad del contenido, criticidad del uso, superficie de exposición (BI, API, SaaS, multi-dominio) y riesgo de impacto. (10 §9)
- **KB10.R3 [MUST]** Least privilege y need-to-know con RBAC/ABAC, revisión periódica y revocación; ningún acceso manual informal o no auditable. (10 §8, §12)
- **KB10.R4 [MUST]** Si el uso no requiere el dato sensible completo: masking (dinámico/estático), tokenización, hashing, seudonimización o reducción de granularidad; incluye ambientes no productivos. (10 §15)
- **KB10.R5 [MUST]** Por capa: Bronze muy restringido; Silver por dominio/producto; Gold con controles finos; Semantic con RLS/CLS y protección ante exposición indirecta; AI con control de training e inferencia. (10 §16)
- **KB10.R6 [MUST]** Integraciones externas (API, SaaS, reverse ETL): contrato, autenticación/autorización, cifrado, validación de payload, logging, control de destinatarios y monitoreo. (10 §17)
- **KB10.R7 [MUST]** PIA completado antes de producción; política de retención, archivado, eliminación y derecho al olvido. (01 §13, 10 §24)
- **KB10.R8 [MUST]** Sin credenciales hardcodeadas; secretos gestionados; validación automatizada de seguridad en CI/CD antes de producción. (10 §23)
- **KB10.R9 [MUST]** Auditoría: quién, qué, cuándo, desde dónde, con qué rol, resultado, datos sensibles afectados, eventos fallidos. (10 §20)

## H · Heurísticas de decisión
- **KB10.H1** Cuasi-identificadores (comuna + fecha de nacimiento + género) combinados pueden reidentificar: evaluar agregación o k-anonimato en vistas de consumo.
- **KB10.H2** Si un tablero replica el mismo dashboard por país para "filtrar", usar RLS en la serving layer (14 §21).
- **KB10.H3** Seguridad tan rígida que inutiliza el producto empuja a soluciones paralelas no gobernadas: buscar proporcionalidad. (10 §28)

## A · Anti-patrones
- **KB10.A1** Tratar todo con la misma sensibilidad. · **KB10.A2** Acceso amplio "por conveniencia". · **KB10.A3** PII en ambientes no productivos.
- **KB10.A4** Ignorar la semantic layer o la AI en el modelo de seguridad. · **KB10.A5** Confiar en que la plataforma resuelve sin gobierno.

## V · Preguntas de verificación
1. **KB10.V1** ¿Los controles son proporcionales (ni sobre- ni sub-protección) a sensibilidad y criticidad?
2. **KB10.V2** ¿Alguna vista permite reidentificar personas combinando atributos no PII?
3. **KB10.V3** ¿La exposición a terceros tiene justificación de negocio y mínimo necesario?

## D · Ya verificado por el motor determinista
Clasificación y atributos, coherencia PII⇒sensible+masking, PIA, política de acceso, secretos (regex + AST), PII en datos de muestra (RUT/CPF/Luhn/email), campos PII con técnica, RLS con consumo BI, paso de seguridad en CI.
