# govkit — Kit de Gobernanza Híbrida de Datos

Motor determinista (reglas como código) + base de conocimiento modular para LLM local, sobre el
Data & AI Discipline Framework de Cencosud. Arquitectura: `docs/00-SAD-sistema-gobernanza-hibrido.md`.

## Contenido

| Carpeta | Qué es |
|---|---|
| `bin/govkit` | Lanzador (bash 3.2 compatible) |
| `lib/govkit/` | Motor: `engine`, `declarative`, `plugins/*` (IAM, contratos, SQL/dbt, AST, seguridad, OMD…), `kb/*` (almacén, BM25, enrutador), `llm/*` (Ollama, revisor), `report/*` (JSON, SARIF, MD, consola), `scoring`, `scaffold`, `cli` |
| `rules/catalog.yaml` | 259 reglas trazadas a documento + sección + cita |
| `rules/registry/` | Dominios, tags, lifecycle, scoring, cuentas AWS/OMD, matriz de consumo, métricas corporativas, capacidades |
| `schemas/` | Contratos JSON: ficha de Data Product, Data Contract, calidad, reporte, salida del LLM, front-matter KB, config |
| `kb/` | 22 mini-contextos `KB_00 … KB_21` + `_graph.yaml` (dependencias, tareas, proyecciones) |
| `templates/` | Esqueleto de repo de Data Product (`govkit init`) y workflow reusable de CI |
| `examples/sales-transactions-anl-dp-cl/` | Data Product de referencia completo (PASS en gate a producción) |
| `tests/` | 52 pruebas (motor, packs, reportes, KB, revisor LLM con Ollama simulado) |
| `vendor/yaml` | PyYAML 6.0.1 puro Python (MIT) para instalación sin pip |

## Comandos

```
govkit lint [path] [--base REF] [--stage S] [--profile pre-commit|pr|gate|catalog|periodic] [--format console|json|sarif|md]
govkit gate [path] --to <estado>            govkit score [path]            govkit baseline [path]
govkit init --domain D --subdomain S --type anl|txd --country cl [--owner email]
govkit rules [--format md|json] [--nature DH]   govkit explain GOV-XXX-NNN
govkit omd-lint DIR | docs-lint DIR | portfolio DIR
govkit kb list|show|route|pack|graph|validate [--task T] [-q "consulta"] [--files a,b] [--rules GOV-*] [--budget N] [--mode review|assist|qa]
govkit review [path] [--base REF] [--dry-run] [--model qwen2.5:7b-instruct]
govkit ask "pregunta" [--no-llm]            govkit doctor            govkit hooks install [path]            govkit selftest
```

Variables: `GOVKIT_MODEL` (default `qwen2.5:7b-instruct`), `GOVKIT_CTX` (default 8192), `OLLAMA_HOST`, `GOVKIT_PYTHON`, `NO_COLOR`.

## Configuración por repositorio (`.govkit.yaml`)

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
