# Changelog — govkit

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
- Tarball versionado por MAJOR.MINOR: `dist/govkit-v1.1.tar.gz`.
- Pista `shape` en los `fix` de tipo `set` (lista / mapa) para generar esqueletos con la forma correcta.

## 1.0.0 — 2026-09-25
- Versión inicial: motor determinista (259 reglas, packs dp/omd/docs/portfolio), KB modular de 22 mini-contextos,
  enrutador, revisor Ollama con verificación, pre-score, scaffold, instalador para lakehousev2.
- Corrección posterior (mismo número de versión): reglas basadas en git (rama, commits, remoto) acotadas a la raíz
  del repo evaluado; diff correcto en monorepos (p. ej. `lakehousev2/products/<dp>`).
