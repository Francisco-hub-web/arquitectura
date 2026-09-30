# govkit — Kit de Gobernanza Híbrida de Datos

Motor determinista (reglas como código) + base de conocimiento modular para LLM local, sobre el
Data & AI Discipline Framework de Cencosud. Arquitectura: `docs/00-SAD-sistema-gobernanza-hibrido.md`.

## Contenido

| Carpeta | Qué es |
|---|---|
| `bin/govkit` | Lanzador (bash 3.2 compatible) |
| `lib/govkit/` | Motor: `engine`, `declarative`, `plugins/*` (IAM, contratos, SQL/dbt, AST, seguridad, OMD, platform-core…), `kb/*` (almacén, BM25, enrutador), `llm/*` (Ollama, revisor), `report/*` (JSON, SARIF, MD, HTML, consola), `fixer` (auto-remediación), `mcpserver` (MCP stdio), `standards`, `scoring`, `scaffold`, `cli` |
| `lib/govkit/arch/` | Memoria arquitectónica (ADR-008): git solo lectura, snapshots, índice, grafo, contexto por ruta, mini-resúmenes, hechos, contradicciones, ADR, cambios y alertas, ArchiMate |
| `rules/catalog.yaml` | 285 reglas trazadas a documento + sección + cita (26 del estándar platform-core) |
| `rules/registry/` | Dominios, tags, lifecycle, scoring, cuentas AWS/OMD, matriz de consumo, métricas corporativas, capacidades · `arch_*` (fuentes, mapa de contexto, hechos, contradicciones) · `platform_core` (fallback del estándar) |
| `schemas/` | Contratos JSON: ficha de Data Product, Data Contract, calidad, reporte, salida del LLM, front-matter KB, config |
| `kb/` | 22 mini-contextos `KB_00 … KB_21` + `_graph.yaml` (dependencias, tareas, proyecciones) |
| `templates/` | Esqueleto de repo de Data Product (`govkit init`) y workflow reusable de CI |
| `examples/sales-transactions-anl-dp-cl/` | Data Product de referencia completo (PASS en gate a producción) |
| `tests/` | 97 pruebas (motor, packs, reportes, KB, revisor LLM con Ollama simulado, fix, MCP, HTML, modo privado, lanzador, arch con repos git sintéticos, estándar platform-core) |
| `vendor/yaml` | PyYAML 6.0.1 puro Python (MIT) para instalación sin pip |

## Comandos

```
govkit lint [path] [--base REF] [--stage S] [--profile pre-commit|pr|gate|catalog|periodic] [--format console|json|sarif|md|html]
govkit fix [path] [--apply] [--stage S] [--no-placeholders] [--domain D --subdomain S --type anl|txd --country C --owner E] [-v]      govkit mcp [--print-config]
govkit gate [path] --to <estado>            govkit score [path]            govkit baseline [path]
govkit init --domain D --subdomain S --type anl|txd --country cl [--owner email]
govkit rules [--format md|json] [--nature DH]   govkit explain GOV-XXX-NNN
govkit omd-lint DIR | docs-lint DIR | portfolio DIR
govkit kb list|show|route|pack|graph|validate [--task T] [-q "consulta"] [--files a,b] [--rules GOV-*] [--budget N] [--mode review|assist|qa]
govkit review [path] [--base REF] [--dry-run] [--model qwen2.5:7b-instruct]
govkit ask "pregunta" [--no-llm]            govkit doctor            govkit hooks install [path]            govkit selftest
govkit "texto libre"  ·  pbpaste | govkit                             → Claude Code interactivo con govkit (MCP)
govkit -p "pregunta" [--nota N | --sumar N] [--no-guardar]          → solo la respuesta + fuentes, guardada como nota
govkit notas [ver|copiar|exportar|abrir|borrar] [N]  ·  govkit fuentes <IDs> (o pbpaste | govkit fuentes)
govkit verificar "lo que escuché en la reunión" [--sin-ia]        → ¿existe ese criterio? veredicto + fuentes
govkit privado [path] [--check]                                     → uso local sin rastro en el remoto
govkit lint … --estandar auto|platform-core|lineamientos [--cenco-dc]  → estándar del repo (ADR-009)
govkit init … --estandar platform-core --type mdh|sm|txd|anl|none   → baseline platform-core + ficha
govkit arch estado | sync [--sin-fetch] | ingest --snapshot F… | contexto RUTA | resumen RUTA|--todos
            conflictos [C-xx] | hechos | adr [--potenciales] | relaciones [--rotas] | buscar "…" | dp [REPO]
            trazabilidad | secretos | cambios [N] | config FUENTE RUTA
```

Variables: `GOVKIT_MODEL` (default `qwen2.5:7b-instruct`), `GOVKIT_CTX` (default 8192), `OLLAMA_HOST`, `GOVKIT_PYTHON`, `NO_COLOR`.

## Memoria arquitectónica (`govkit arch`, ADR-008)

Convierte los repos corporativos en conocimiento trazable y actualizado, sin tocarlos:
- **global-data-governance**: el *qué*.
- **global-data-platform-core**: el *cómo* ejecutable.
- **global-data-archimate-models**: el diseño aprobado.
- **global-metadata-catalog**: el catálogo.

```bash
govkit arch sync                         # clones en ~/global-* → fetch (solo refs remotas) + diff + alertas + changelog
govkit arch ingest --snapshot *.txt      # sin git: snapshots .txt (misma detección incremental, por sha256)
govkit arch contexto contracts/gold/fact/fct_x.yaml   # qué debo mirar si analizo esta ruta (y por qué)
govkit arch contexto global-data-platform-core/framework/data-contracts/specs/schemas
govkit arch conflictos                   # CONFLICT DETECTED C-01..C-15, VIGENTE/REVISAR según hechos re-verificados
govkit arch adr --potenciales            # decisiones de facto sin ADR (nunca se crean automáticamente)
govkit arch dp .                         # diseño ArchiMate aprobado vs implementación del repo
govkit arch relaciones --rotas           # referencias rotas entre documentos corporativos
```

**Garantías:**
- Nunca hace `pull`, `checkout`, `reset` ni `stash`: el análisis lee `origin/<rama>` sin tocar el working tree.
- Desactiva los hooks y no ejecuta código de los repos analizados.
- Los secretos se reportan solo como `SECRET DETECTED` (archivo, ruta y tipo) y los IDs de cuenta se enmascaran.
- El estado generado vive solo en `~/.govkit/arch`.

**Formato de las respuestas:**
- Cada afirmación lleva su traza `repo@commit:ruta §sección`, su estado normativo (REQUIRED, APPROVED, RECOMMENDED, IMPLEMENTED, DEPRECATED, UNKNOWN) y una etiqueta epistemológica.
- Lo que no tiene evidencia se reporta como "NO DETERMINADO".

**Otras rutas locales:** si los clones no están en `~/global-*`, usa `govkit arch config platform-core /ruta`.

## Estándar platform-core (ADR-009)

En repos con la copia del estándar (`contracts/_schema/`), la ficha `metadata/data_product.yaml` o contratos ODCS v3,
govkit aplica el estándar ejecutable de global-data-platform-core (reglas **GOV-PCX-***):
- ODCS v3.1.0 con la extensión `customProperties.xCencosud`;
- carpetas medallion;
- linaje por capa y bidireccional;
- bloques physical/catalog;
- ingestion_origin;
- copia del estándar, CI y catalog-export.

Las reglas leen el estándar como dato (copia del repo › clon local › índice arch › fallback). Las 22 reglas del
lineamiento que contradicen ese estándar no aplican en esos repos. `--cenco-dc` ejecuta además el validador oficial.

## Uso personal y privado

`govkit privado` dentro de un repo deja todo lo de govkit en `.git/` (nunca se sube): config y baseline personales en
`.git/govkit/`, archivos de govkit ignorados en `.git/info/exclude` y guardias locales que bloquean commits o pushes
que mencionen govkit. `govkit privado --check` verifica que no haya rastros. Las plantillas que `init`/`fix` escriben
no mencionan la herramienta, y `fix` no crea workflows de CI ni CODEOWNERS.

## Configuración por repositorio (`.govkit.yaml` compartido o `.git/govkit/config.yaml` personal)

```yaml
version: 1
repo_name: sales-transactions-anl-dp-cl
policies:
  branching: env-branches          # o trunk (ver ADR-006)
rules:
  severity: {GOV-MET-008: HIGH}    # solo endurecer
waivers:
  - {rule: GOV-STR-005, paths: ["notebooks/**"], reason: "...", owner: a@cencosud.com,
     adr: docs/adr/0002-x.md, expires: 2026-12-31}
```
