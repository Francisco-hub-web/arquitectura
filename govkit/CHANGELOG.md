# Changelog — govkit

## 2.0.0 — 2026-09-30
### Agregado — memoria arquitectónica (`govkit arch`, ADR-008)
- **Fuentes**: los repos corporativos global-data-governance, global-data-platform-core, global-data-archimate-models
  y global-metadata-catalog se indexan por `repo@commit`, con hash, tipo, autoridad, secciones, referencias, estado
  normativo (REQUIRED/APPROVED/RECOMMENDED/IMPLEMENTED/DEPRECATED/UNKNOWN) y etiqueta epistemológica (DOC/COD/…).
  - Rutas registradas en `rules/registry/arch_sources.yaml`; clones esperados en `~/global-*`.
  - El índice vive solo en `~/.govkit/arch`.
- **Git en solo lectura**:
  - `arch sync` hace `fetch` solo de refs remotas y lee `origin/<rama>` con `ls-tree`/`cat-file`;
  - nunca hace pull, checkout, reset ni stash (hay lista blanca de subcomandos), con hooks desactivados y sin ejecutar código del repo;
  - si hay cambios locales, informa y explica cómo proceder sin restaurar archivos (p.ej. `.github/setup.js`).
- **Snapshots `.txt`**: `arch ingest --snapshot` reproduce byte a byte cada archivo (valida sha256) y hace la misma detección incremental sin git.
- **Detección de cambios**:
  - diff semántico (secciones Markdown, claves y enums de YAML/JSON, elementos, vistas y relaciones ArchiMate);
  - clasificación NEW/UPDATED/DEPRECATED/CONFLICTING/UNKNOWN e impacto NONE…CRITICAL con el porqué;
  - alertas ARCHITECTURAL CHANGE DETECTED agrupadas por unidad arquitectónica;
  - changelog ARCHITECTURAL KNOWLEDGE UPDATE en `~/.govkit/arch/changes/`;
  - reglas, KB y notas posiblemente obsoletas;
  - señales de ramas `proposal/`, `dp/`, `update/`…
- **Contexto por ruta**: `arch contexto <ruta>`, corporativa o de tu Data Product, responde "qué debo mirar si analizo esta ruta", con el porqué, el estado normativo, las reglas y la KB que aplican, los hechos verificados, las contradicciones abiertas, los ADR y el diseño ArchiMate.
- **Mini-resúmenes**: `arch resumen` sigue los campos del §6 del SUPER PROMPT, con evidencia y nivel de confianza.
- **Relaciones**: `arch relaciones` da la matriz curada R1..R16 más las relaciones derivadas del contenido:
  - referencias válidas y rotas;
  - espejos y duplicados divergentes;
  - Data Products modelados.
- **Hechos y contradicciones**:
  - 34 hechos verificables (`arch hechos`);
  - 15 contradicciones (`arch conflictos`, C-01..C-15 ↔ H-18..H-32) que pasan a REVISAR cuando su evidencia cambia.
- **ADR**: `arch adr` inventaría los ADR corporativos, los de govkit y los del repo, más los Potential ADR (curados y detectados). Nunca crea un ADR.
- **ArchiMate**: `arch dp [repo]` lista los Data Products modelados y compara el diseño aprobado con lo implementado, sin concluir desviaciones sin evidencia.
- **Utilidades**:
  - `arch buscar` (BM25 por sección con traza);
  - `arch trazabilidad` (cada fuente citada por reglas y KB existe);
  - `arch secretos` (SECRET DETECTED, solo archivo, ruta y tipo).
- **MCP**: `arch_status`, `arch_context`, `arch_summary`, `arch_search`, `arch_sync`, `arch_changes`, `arch_conflicts`, `arch_facts`, `arch_adrs`, `arch_dp`, `arch_relations`.
- **Asistente** (`govkit "…"` / `-p`):
  - usa esta capa;
  - responde con Contexto/Evidencia/Esperada/Observada/Diferencias/Impacto/Confianza;
  - etiqueta cada afirmación y dice "NO DETERMINADO" cuando no hay evidencia.
- `govkit doctor` muestra el estado de cada fuente.

### Agregado — estándar platform-core (ADR-009, ruleset 2026.10.0)
- **Estándar por repo** (`auto`, `platform-core` o `lineamientos`), con detección por marcadores, `--estandar` en lint/gate/init, `standard:` en la config o `GOVKIT_STANDARD`.
- **26 reglas GOV-PCX-*** que leen el estándar de global-data-platform-core como dato. Cubren:
  - ficha `metadata/data_product.yaml`;
  - carpetas medallion (sin `contracts/input`);
  - forma ODCS v3.1.0 y extensión xCencosud;
  - linaje por capa y bidireccional;
  - `processing` deprecado;
  - physical/catalog e ingestion_origin;
  - copia del estándar, CI y catalog-export;
  - equivalentes ODCS de GOV 06/08/15 (descripciones, compatibilidad, breaking changes, calidad);
  - nombre de repo.
- `--cenco-dc` (opt-in) ejecuta además el validador oficial desde el clon local.
- `govkit init --estandar platform-core` crea el baseline con la ficha. `govkit fix` crea la ficha y las carpetas del baseline.

### Cambiado
- 22 reglas del lineamiento "Estructura de Repositorio" (contratos input/output, ficha `spec.*`, DoR/DoD, `fact_`,
  workflows y carpetas propias, `quality/expectations`) declaran `standards: [lineamientos]`: no aplican a repos
  platform-core. En repos sin marcadores platform-core el comportamiento no cambia.
- Reportes (consola y JSON) muestran el estándar aplicado.
- `govkit init --type` acepta `mdh`, `sm` y `none` (tipos observados en el diseño ArchiMate aprobado).

### Corregido
- 13 reglas (GOV-AIM-*, GOV-DOC-005) y KB_15/KB_16 citaban `12-ai-ml-data-framework.md`, que no existe; el archivo
  real es `12-ai-ml-dataframework.md`. Detectado por `govkit arch trazabilidad`.

## 1.4.0 — 2026-09-29
### Agregado
- `govkit verificar "lo que escuché"` (alias `existe`): ¿ese criterio existe en el framework? Recuperación
  determinista de criterios KB y reglas GOV-* (BM25 con normalización de plurales y sinónimos frecuentes), veredicto
  EXISTE · EXISTE CON MATICES · NO EXISTE · CONTRADICE vía Claude Code restringido a esa evidencia, fuentes resueltas
  por govkit y alerta si se cita un ID inexistente. `--sin-ia` muestra solo los criterios más cercanos; se guarda
  como nota. Herramienta MCP `criteria_search` para hacer lo mismo desde la sesión interactiva.
- Las preguntas libres (`govkit "…"` / `-p`) ya no evalúan el repo si la pregunta no es sobre él.

## 1.3.0 — 2026-09-29
### Agregado
- `govkit -p "texto"`: solo la respuesta en la terminal (Claude Code no interactivo, sin interfaz ni diálogo de
  confianza), con una línea de progreso y formato legible. `govkit "texto"` sigue abriendo la sesión interactiva.
- «Fuentes para verificar»: cada ID citado (GOV-*, KBnn.Xn) se resuelve de forma determinista a documento § sección y
  cita textual del framework. En `-p` govkit lo agrega solo; en modo interactivo Claude usa la herramienta MCP
  `sources`. Comando `govkit fuentes <IDs>` o `pbpaste | govkit fuentes` para verificar cualquier texto.
- Notas reutilizables en `~/.govkit/notas/` (fuera de cualquier repo): cada respuesta `-p` se guarda sola;
  `--nota N` la usa como contexto, `--sumar N` además le agrega la respuesta nueva; `govkit notas`
  (lista · ver · copiar · exportar · abrir · borrar). En Claude Code: herramientas MCP `notes_*`.

## 1.2.0 — 2026-09-29
### Agregado
- `govkit "texto libre"` (o `pbpaste | govkit`, `govkit -p "…"`): abre Claude Code en la carpeta actual con el
  servidor MCP govkit, permisos previos para las herramientas de solo lectura, el contexto del repo y las reglas de
  privacidad. Una sola palabra desconocida se trata como error (evita lanzar Claude por un typo).
- `govkit privado [--check]`: uso local sin rastro en el remoto. Config y baseline personales en `.git/govkit/`
  (se cargan solos), `.git/info/exclude` para archivos de govkit y guardias locales pre-commit / commit-msg / pre-push
  que bloquean contenido, mensajes, ramas o commits con menciones a govkit (hooks previos encadenados).
- Instalador: si `lakehousev2` es un repo git, el kit queda ignorado localmente; alias `gkp`.

### Cambiado
- Las plantillas y el ejemplo de referencia ya no mencionan la herramienta: lo que `init`/`fix` escriben en un repo
  es solo el estándar corporativo. El `pr.yml` de plantilla usa únicamente el workflow corporativo reutilizable.
- `govkit fix` nunca crea `.github/workflows/*` ni `CODEOWNERS` (disparan CI o revisores en el GitHub corporativo):
  quedan como acción manual.
- `govkit baseline` escribe por defecto en `.git/govkit/baseline.json`; `govkit hooks install` encadena hooks existentes.
- El servidor MCP instruye al agente a no mencionar govkit en archivos, commits, ramas ni PRs.

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
