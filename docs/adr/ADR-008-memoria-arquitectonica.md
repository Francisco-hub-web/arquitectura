# ADR-008: Memoria arquitectónica local, incremental y trazable (`govkit arch`)

- Estado: propuesto
- Fecha: 2026-09-30

## Contexto
El conocimiento arquitectónico corporativo vive en cuatro repositorios que evolucionan por separado:
- **global-data-governance**: el *qué*, el marco normativo.
- **global-data-platform-core**: el *cómo*, en forma ejecutable (estándar de contratos, baseline de Data Products y validadores).
- **global-data-archimate-models**: el diseño aprobado de la plataforma y de cada Data Product.
- **global-metadata-catalog**: el destino del catálogo.

Hasta 1.4, govkit solo destilaba a mano los documentos de governance. No conocía los otros tres repos ni el
commit de lo que citaba, y no detectaba cambios. Tampoco distinguía una norma de una implementación ni de una
propuesta en curso.

Restricciones:
- **Privacidad**: los repos corporativos no se tocan desde la nube. govkit es una herramienta local del usuario.
- **Seguridad**: los working trees muestran restos de la remediación del ataque a la cadena de suministro "Miasma" (`.github/setup.js`).
- **No inventar arquitectura.**

## Decisión
1. **Subsistema `govkit arch`** que complementa la KB y el catálogo existentes. No se crea un árbol paralelo
   `architecture-knowledge/`. Cada equivalente vive así:
   - fuentes → `rules/registry/arch_sources.yaml`;
   - mapa de contexto curado → `arch_context_map.yaml`;
   - hechos → `arch_facts.yaml`;
   - contradicciones y Potential ADR → `arch_conflicts.yaml`, con espejo humano H-18..H-32 en `docs/02`;
   - estado generado (índices por `repo@commit`, changelogs, resúmenes) → solo en `~/.govkit/arch`, nunca en un repo.
2. **Lectura Git de solo lectura**:
   - hay una lista blanca de subcomandos;
   - `fetch` actualiza solo las refs remotas y el contenido se lee de `origin/<rama>` con `ls-tree`/`cat-file`;
   - nunca se hace `pull`, `checkout`, `reset` ni `stash`, los hooks se desactivan y no se ejecuta código del repo analizado;
   - con un working tree sucio, govkit informa y no actúa.
   - Como alternativa sin git, se aceptan los snapshots `.txt` del usuario, que se comparan por sha256.
3. **Etiquetas obligatorias**. Cada archivo y cada sección llevan:
   - un estado normativo (`REQUIRED`, `APPROVED`, `RECOMMENDED`, `IMPLEMENTED`, `DEPRECATED`, `UNKNOWN`), asignado por reglas deterministas;
   - una etiqueta epistemológica (`DOC`, `COD`, `INF`, `PROP`, `DESC`, `CONF`).

   Las reglas de asignación son estas:
   - lo que está en `main` de ArchiMate es `APPROVED`;
   - un documento en borrador es `UNKNOWN`;
   - un CI deshabilitado no cuenta como enforcement;
   - las ramas `proposal/`, `dp/`, etc. son señales, no norma.
4. **Detección incremental de cambios**:
   - diff por contenido y semántico (secciones Markdown, claves y enums de YAML/JSON, elementos, vistas y relaciones ArchiMate);
   - clasificación NEW/UPDATED/DEPRECATED/CONFLICTING/UNKNOWN;
   - impacto de NONE a CRITICAL, siempre con el porqué;
   - alertas ARCHITECTURAL CHANGE DETECTED agrupadas por unidad arquitectónica;
   - changelog ARCHITECTURAL KNOWLEDGE UPDATE;
   - lista de análisis posiblemente obsoletos (reglas, KB y notas cuya fuente cambió).
5. **Hechos verificables**. Las contradicciones se sostienen sobre hechos que se re-evalúan en cada sincronización.
   Si un hecho deja de cumplirse, el conflicto pasa a REVISAR. govkit nunca decide cuál fuente gana.
6. **Integración con el mecanismo existente**:
   - CLI `govkit arch …`;
   - herramientas MCP `arch_*`;
   - reglas del asistente: formato del §18, etiquetas y "NO DETERMINADO";
   - `govkit doctor`;
   - validador de trazabilidad de reglas y KB (`govkit arch trazabilidad`).

## Consecuencias
- Toda afirmación arquitectónica tiene traza `repo@commit:ruta §sección`. Lo que falta se declara NO DETERMINADO.
- **Hallazgos inmediatos**:
  - 13 reglas y 2 mini-contextos citaban un documento inexistente (`12-ai-ml-data-framework.md`); ya está corregido;
  - hay 69 referencias rotas en los repos corporativos;
  - hay una divergencia entre las dos copias de la referencia ARTS (C-15).
- El contenido corporativo no sale de la máquina del usuario. En el repo solo quedan metadatos curados: rutas, patrones y relaciones.
- **Costo**: mantener los registros curados (contexto, hechos, conflictos). La deriva queda acotada porque los
  hechos se verifican solos y avisan cuando cambian.
