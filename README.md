# Arquitectura de Datos — Sistema de Gobernanza Híbrido

Convierte el **Data & AI Discipline Framework** (principios, estrategia, Data Products, calidad, metadata, seguridad,
semantic layer, AI/ML, observabilidad, consumo, DataOps, lifecycle, scoring y lineamientos IAM / repositorio /
OpenMetadata) en un sistema ejecutable de dos capas:

1. **Validación determinista** (`govkit lint`): 230 reglas verificables con AST, regex, esquemas, grafo y diff — bloqueantes, en < 1 s.
2. **Base de conocimiento modular** (`govkit/kb`): 22 mini-contextos para un **LLM local** (Ollama) que revisa solo la
   superficie semántica, con citas verificadas — consultivo.

| Documento | Contenido |
|---|---|
| [`docs/00-SAD-sistema-gobernanza-hibrido.md`](docs/00-SAD-sistema-gobernanza-hibrido.md) | Documento de Arquitectura de Solución (diagramas, taxonomía, motor, KB, interfaces, roadmap) |
| [`docs/01-matriz-reglas.md`](docs/01-matriz-reglas.md) | Matriz de las 259 reglas (generada desde el catálogo) |
| [`docs/02-hallazgos-auditoria-documental.md`](docs/02-hallazgos-auditoria-documental.md) | 17 inconsistencias del framework que impiden validar de forma exacta + resolución propuesta |
| [`docs/adr/`](docs/adr/) | ADR-001 … ADR-007 |
| [`govkit/`](govkit/) | Implementación: motor, catálogo, KB, esquemas, plantillas, ejemplo de referencia, tests |
| [`govkit/CHANGELOG.md`](govkit/CHANGELOG.md) | Historial de versiones del kit |

## Instalación (macOS / Linux, en `lakehousev2`)

```bash
cd ~/Downloads && tar xzf govkit-v1.1.tar.gz && cd govkit && ./install.sh && source ~/.zshrc
```

El instalador detecta `~/lakehousev2` (o `LAKEHOUSE_DIR=/ruta ./install.sh`), instala en
`lakehousev2/governance/govkit`, agrega `govkit` al PATH en `~/.zshrc` y ejecuta el autodiagnóstico.
Solo requiere `python3 ≥ 3.9` (PyYAML va incluido). Ollama es opcional: `./install.sh --pull-model`.
Si el CLI `claude` está instalado, registra además el servidor MCP `govkit` en Claude Code (`--no-mcp` para omitirlo).

## Uso rápido

```bash
govkit init --domain sales --subdomain transactions --type anl --country cl --owner tu.email@cencosud.com
cd sales-transactions-anl-dp-cl && govkit lint             # qué falta según la etapa actual
govkit gate --to listo_para_produccion                    # pre-flight de promoción
govkit score                                              # pre-score por pilar (19-scoring-model)
govkit fix                                                # plan de auto-remediación segura (--apply para escribir)
govkit lint --format html -o reporte.html                 # reporte autocontenido para compartir
govkit explain GOV-IAM-004                                # fuente, severidad, remediación, KB
govkit kb route --task exponer_consumo                    # qué conocimiento cargar para una tarea
govkit review --base origin/main                          # revisión semántica local (Ollama)
govkit ask "¿cuándo un cambio de contrato es breaking?"
govkit omd-lint <repo-access-analyzer>                    # roles cross-account OpenMetadata
govkit docs-lint <carpeta-del-framework>                  # consistencia de la documentación
govkit portfolio <carpeta-con-N-repos>                    # auditoría cross-repo
```

### Con Claude Code (MCP)

Dentro de `claude`, el agente usa las herramientas de govkit (`lint`, `fix`, `gate`, `kb_context`,
`verify_semantic_findings`, …) y los prompts `/mcp__govkit__revision_gobernanza`, `/mcp__govkit__nuevo_data_product`
y `/mcp__govkit__consulta_framework`. Otros clientes MCP: `govkit mcp --print-config`.

## Construir el tarball

```bash
./scripts/build-kit.sh          # → dist/govkit-v<MAJOR.MINOR>.tar.gz (incluye docs/ y MANIFEST)
```
