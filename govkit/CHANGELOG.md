# Changelog — govkit

## 1.1.2 — 2026-09-29
### Corregido
- `govkit fix` en repos con nombre no estándar (p. ej. `forecast-derived-mdh-dp-cl`): las plantillas (ficha,
  CODEOWNERS, CHANGELOG, workflows, contrato, calidad…) ya no quedan como "manual". Toma dominio/subdominio del
  nombre si termina en `-dp-{país}`, o de `--domain/--subdomain/--type/--country/--owner` (también en la
  herramienta MCP `fix`). Los archivos generados usan el nombre real del repo.
- La ficha creada por `fix` en un repo existente nace en el estado evaluado (`en_desarrollo` por defecto o
  `--stage`), no en `en_definicion`, para no relajar severidades de un producto que ya tiene código.

## 1.1.1 — 2026-09-29
### Corregido
- GOV-SEC-006 detecta secretos en constantes y claves con prefijo/sufijo (`DB_PASSWORD = "…"`, `SNOWFLAKE_PWD`,
  `"ApiKey": "…"`) y en opciones Spark/JDBC (`.option("password", "…")`, `spark.conf.set("fs.s3a.secret.key", "…")`);
  ignora nombres que referencian al secreto (`secret_id`, `secret_arn`, `password_param`, `*_header`…).
- GOV-IAM-004: una acción destructiva (`Delete*`, `s3:*`, `*`) con wildcard sobre el path de un bucket compartido es
  BLOCKER (Regla 2 del lineamiento IAM); la escritura no destructiva sigue siendo HIGH.

## 1.1.0 — 2026-09-25
### Agregado
- `govkit mcp`: servidor MCP stdio sin dependencias para agentes de código (Claude Code, Cursor, Claude Desktop).
  10 herramientas (`lint`, `gate`, `score`, `fix`, `explain_rule`, `search_rules`, `kb_context`,
  `semantic_review_plan`, `verify_semantic_findings`, `init_data_product`), recursos `govkit://kb/KB_nn`, matriz y
  SAD, y 3 prompts guiados. Los hallazgos semánticos del agente pasan por el mismo verificador que Ollama (ADR-007).
- `govkit fix`: auto-remediación determinista y segura (carpetas, plantillas corporativas, valores deterministas,
  bump semver, esqueleto `<COMPLETAR>`), con edición de YAML que conserva comentarios y verificación post-edición.
- `--format html`: reporte autocontenido (claro/oscuro, filtros por severidad, pre-score por pilar); el workflow
  reusable de CI lo adjunta como artefacto.
- Instalador: registra el MCP en Claude Code si existe el CLI `claude` (`--no-mcp` para omitir) y copia el kit según
  `MANIFEST` (restos de extracciones anteriores no se instalan). Desinstalador: quita el registro MCP.

### Cambiado
- Tarball versionado: `dist/govkit-v<versión>.tar.gz` (desde 1.1.1 incluye el patch para evitar colisiones en Descargas).
- Pista `shape` en los `fix` de tipo `set` (lista / mapa) para generar esqueletos con la forma correcta.

## 1.0.0 — 2026-09-25
- Versión inicial: motor determinista (259 reglas, packs dp/omd/docs/portfolio), KB modular de 22 mini-contextos,
  enrutador, revisor Ollama con verificación, pre-score, scaffold, instalador para lakehousev2.
- Corrección posterior (mismo número de versión): reglas basadas en git (rama, commits, remoto) acotadas a la raíz
  del repo evaluado; diff correcto en monorepos (p. ej. `lakehousev2/products/<dp>`).
