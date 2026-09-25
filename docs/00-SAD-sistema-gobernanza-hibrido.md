# Sistema de Gobernanza Híbrido de Datos — Documento de Arquitectura de Solución (SAD)

Versión: 1.0
Estado: Propuesta para revisión del Equipo de Arquitectura de Datos Regional
Fecha: 2026-09-25
Alcance: Corporativo (aplicable a todos los repositorios de Data Products y al repositorio `access-analyzer`)
Artefactos de referencia: `govkit/` (implementación), `govkit/rules/catalog.yaml` (reglas), `govkit/kb/` (base de conocimiento),
`docs/01-matriz-reglas.md` (matriz generada), `docs/02-hallazgos-auditoria-documental.md`, `docs/adr/`

---

## 0. Resumen ejecutivo

El Data & AI Discipline Framework de Cencosud (principios, estrategia, definición de Data Product, calidad, metadata,
seguridad, semantic layer, AI/ML, observabilidad, consumo, DataOps, lifecycle, scoring y los lineamientos de IAM,
estructura de repositorio y OpenMetadata) es hoy **documentación pasiva**: se cumple si alguien la lee y la recuerda.

Este documento propone convertirla en un **Sistema de Gobernanza Híbrido** con una tesis central:

> **Determinista primero, semántico después, humano al final.**
> Todo lo que se puede verificar de forma exacta se verifica con código (milisegundos, costo cero, bloqueante).
> Solo la superficie que requiere interpretación llega a un LLM local, con un contexto mínimo y verificable (consultivo).
> Lo organizacional queda como checklist humano explícito.

Resultados medidos sobre la implementación de referencia (`govkit` v1.0.0):

| Indicador | Valor |
|---|---|
| Lineamientos auditados y convertidos en reglas trazables (documento + sección + cita) | **259** |
| Reglas automatizables (Deterministas + Híbridas) | **230 (89%)** — 217 D · 13 H |
| Reglas semánticas (LLM + KB, consultivas) | 19 (7%) |
| Reglas organizacionales (revisión humana) | 10 (4%) |
| Mini-contextos de la Base de Conocimiento | 22 · 368 reglas atómicas citables (`KBnn.Xn`) |
| Tamaño total de la KB | ≈16,4k tokens (media 746 por mini-contexto; máx. 948) |
| Contexto típico enviado al LLM por revisión | mediana ≈5,7k tokens con presupuesto 6k (≈3–6k), cabe en un 7B con `num_ctx=8192` |
| Latencia del motor determinista (repo de referencia, 73 archivos) | ≈0,5 s |
| Pruebas automatizadas del kit | 52 (Python 3.9 → 3.13) |

El corpus documental completo (~19 páginas más lineamientos; del orden de decenas de miles de tokens, estimado) no cabe
en la ventana útil de un modelo local 7B–14B y, aun si cupiera, diluiría la atención del modelo. La modularización
reduce el contexto por revisión a una fracción del corpus y elimina del LLM todo lo que el código ya prueba.

---

## 1. Contexto, drivers y principios de diseño

### 1.1 Drivers (Architecturally Significant Requirements)

| ID | Driver | Objetivo medible |
|---|---|---|
| ASR-1 | **Costo** | 0 tokens de LLM para reglas verificables; LLM local (sin costo por token ni egreso de datos). |
| ASR-2 | **Latencia** | Lint determinista < 5 s por repo en PR (p95); pre-commit < 2 s. Revisión semántica < 90 s por artefacto en 7B local. |
| ASR-3 | **Escalabilidad** | N repos × M países sin reescribir reglas: reglas como datos, packs versionados, ejecución incremental por diff. |
| ASR-4 | **Trazabilidad** | Cada hallazgo apunta a archivo:línea, regla `GOV-*`, documento fuente y sección, y a su mini-contexto KB. |
| ASR-5 | **Confiabilidad del LLM** | Ninguna salida del LLM se publica sin verificación determinista (esquema, cita existente, evidencia textual). |
| ASR-6 | **Adopción brownfield** | Productos existentes se incorporan con *baseline* y *waivers* con ADR y vencimiento, sin bloquear el día 1. |
| ASR-7 | **Soberanía del dato** | El contenido de los repos y de la KB nunca sale de la máquina/red corporativa (Ollama local). |

### 1.2 Principios de diseño

1. **Determinista primero** (ADR-001): el LLM nunca decide lo que un AST, un regex, un esquema o un grafo pueden probar.
2. **Reglas como datos** (ADR-002): el catálogo YAML es la fuente única de verdad; el código solo implementa *tipos* de chequeo.
3. **Severidad sensible al ciclo de vida** (ADR-003): la misma regla es LOW en ideación y BLOCKER en el gate de producción.
4. **Contexto mínimo suficiente** (ADR-004): mini-contextos atómicos, proyección por secciones y presupuesto de tokens.
5. **Hallazgos semánticos consultivos y verificados** (ADR-005): el LLM sugiere; solo el motor determinista bloquea.
6. **El sistema se gobierna a sí mismo**: es un caso GenAI/RAG del propio framework (12 §18-§19) y cumple sus reglas:
   corpus oficial y versionado, clasificación `interno`, sin PII, citas trazables, observabilidad (métricas de descarte).

---

## 2. Vista general de la arquitectura

```
                         ┌────────────────────────────────────────────────────────────────────┐
  FUENTES DE VERDAD      │ Data & AI Discipline Framework: 01, 02, 02.1, 02.2, 06, 08-15, 18, 19 │
  (docs normativos)      │ + lineamientos IAM · Estructura de Repositorio · OpenMetadata (lite/técnica)│
                         └───────────────────────────────┬────────────────────────────────────┘
                                                         │ (1) Auditoría y compilación del conocimiento
                         ┌───────────────────────────────▼────────────────────────────────────┐
  CAPA DE CONOCIMIENTO   │  rules/catalog.yaml (259 reglas D/H/S/O)   kb/KB_00..KB_21 (22 mini-ctx) │
  (versionada en Git)    │  rules/registry/*.yaml (dominios, tags,     kb/_graph.yaml (dependencias,  │
                         │  lifecycle, scoring, cuentas, matriz)       tareas, proyecciones)          │
                         │  schemas/*.json (contratos de E/S)                                          │
                         └──────────────┬───────────────────────────────────────────┬──────────────┘
                                        │                                           │
            (2) CAPA 1 — DETERMINISTA   ▼                     (3) CAPA 2 — SEMÁNTICA ▼
  ┌──────────────────────────────────────────────┐   ┌──────────────────────────────────────────────┐
  │ Motor govkit (Python stdlib + PyYAML)         │   │ Enrutador de KB (BM25 + grafo + presupuesto)  │
  │  Descubrimiento → Parsers → Checks            │   │  → Paquete de contexto (modo review/assist/qa)│
  │  (declarativos + plugins AST/regex/grafo/diff)│──►│  → LLM local (Ollama · Qwen/Llama, T=0, JSON)  │
  │  → Política (etapa, waivers, baseline)        │ S │  → Verificador determinista de la salida       │
  │  → Scoring bridge → Reportes                  │ H │    (esquema · citas · grounding · tope sev.)   │
  └───────────────┬──────────────────────────────┘ a └───────────────┬──────────────────────────────┘
                  │ BLOQUEANTE                     n                 │ CONSULTIVO
                  │                                d                 │
  (4) PUNTOS DE   ▼                                o                 ▼
  CONTROL   pre-commit · PR (SARIF + resumen) · gate de lifecycle · sync catálogo · auditoría periódica
                  │                                ff                │
                  ▼                                                  ▼
  SALIDAS   JSON (contrato) · SARIF 2.1.0 · Markdown PR · pre-score por pilar · review JSON · OpenMetadata
```

Flujo de compilación del conocimiento (paso 1):

```
Documento ─► Lineamiento atómico ─► Clasificación (árbol §3.1) ─┬─► D/H: regla en catalog.yaml (+ check)
                                                                ├─► S:   regla en catalog.yaml (+ semantic_question) ─┐
                                                                ├─► O:   regla en catalog.yaml (checklist humano)       │
                                                                └─► Conocimiento interpretativo ─► KB_nn (R/H/A/E/V/D) ◄┘
```

---

## 3. Pilar 1 — Clasificación y taxonomía de reglas

### 3.1 Método de auditoría (árbol de decisión aplicado a cada lineamiento)

```
¿El lineamiento se expresa sobre un artefacto versionado (repo, IaC, config, ficha, SQL, código)?
 ├─ NO ─► ¿Depende de personas, comités o procesos? ─► O · Organizacional (checklist humano / runtime)
 └─ SÍ ─► ¿El criterio es cerrado? (presencia, enum, patrón, umbral, relación entre artefactos, diff)
           ├─ SÍ ─► D · Determinista  (AST · regex · schema · path · graph · diff · policy · count · threshold)
           └─ NO ─► ¿Se puede verificar determinísticamente al menos su PRESENCIA o FORMA?
                     ├─ SÍ ─► H · Híbrida  = parte D (bloqueante) + pregunta semántica (consultiva)
                     └─ NO ─► S · Semántica (LLM + KB) — nunca bloqueante
```

**Patrón de descomposición D+S.** La mayoría de los lineamientos "blandos" tiene un componente duro. Ejemplo:
*"descripción útil"* (09 §22) → **D**: existe, no es relleno (`TODO`, `<COMPLETAR>`), ≥60 caracteres → **S**: "¿permite a un
consumidor entender en <1 minuto qué es, qué decisión habilita y qué no incluye?". El LLM solo recibe la pregunta si la
parte D pasó (no tiene sentido juzgar la calidad de un texto inexistente).

### 3.2 Matriz de dos ejes (resumen; detalle completo en `docs/01-matriz-reglas.md`)

| Dominio de gobierno | D | H | S | O | Total | % automatizable |
|---|---:|---:|---:|---:|---:|---:|
| Estructura de repositorio | 12 | 1 | 0 | 0 | 13 | 100% |
| Nomenclatura | 14 | 0 | 0 | 0 | 14 | 100% |
| Definición de Data Product | 27 | 1 | 0 | 0 | 28 | 100% |
| Data Contracts | 13 | 1 | 1 | 0 | 15 | 93% |
| Metadata y catálogo | 15 | 1 | 1 | 1 | 18 | 89% |
| Calidad de datos | 13 | 2 | 1 | 1 | 17 | 88% |
| Seguridad y privacidad | 12 | 2 | 2 | 2 | 18 | 78% |
| IAM | 14 | 1 | 0 | 0 | 15 | 100% |
| DataOps y CI/CD | 12 | 0 | 0 | 1 | 13 | 92% |
| Arquitectura y modelado | 8 | 1 | 5 | 0 | 14 | 64% |
| Semantic layer y métricas | 7 | 1 | 1 | 1 | 10 | 80% |
| Consumo y explotación | 11 | 1 | 2 | 0 | 14 | 86% |
| AI / ML / GenAI | 10 | 0 | 2 | 0 | 12 | 83% |
| Observabilidad | 7 | 0 | 1 | 0 | 8 | 88% |
| Ciclo de vida | 5 | 0 | 1 | 1 | 7 | 71% |
| Scoring | 5 | 0 | 0 | 0 | 5 | 100% |
| Negocio y casos de uso | 7 | 1 | 2 | 2 | 12 | 67% |
| OpenMetadata (pack `omd`) | 14 | 0 | 0 | 1 | 15 | 93% |
| Documentación del framework (pack `docs`) | 5 | 0 | 0 | 0 | 5 | 100% |
| Portafolio cross-repo (pack `portfolio`) | 6 | 0 | 0 | 0 | 6 | 100% |
| **Total** | **217** | **13** | **19** | **10** | **259** | **89%** |

Lectura: los dominios con más contenido interpretativo son **Arquitectura/Modelado** (grano, conformidad dimensional,
uso de ARTS, límites de dominio) y **Negocio** (valor medible, coherencia capacidad→dominio). Allí se concentra el LLM.

### 3.3 Reglas deterministas representativas (sintácticas, estructurales, nomenclatura, tipado, metadatos)

| Tipo | Ejemplos (ID · regla · técnica · fuente) |
|---|---|
| Sintácticas | `GOV-STR-013` YAML/JSON parsean (parser) · `GOV-STR-010` ASL válido: StartAt/Next existen (schema+grafo) |
| Estructurales | `GOV-STR-001/002` estructura fija de carpetas · `GOV-CTR-010` cada modelo Gold tiene contrato (grafo) · `GOV-OPS-007` Silver→Gold solo en dbt |
| Nomenclatura | `GOV-NAM-001` `{domain}-{subdomain}-{type}-dp-{country}` · `GOV-NAM-003` `job_{zone}_{env}_{domain}_{name}_{gran}.py` · `GOV-NAM-009/010` `cencosud-role-{repo}` / `cencosud-policy-{repo}-{data|infra}` |
| Tipado / esquema | `GOV-DPD-002` ficha vs `data_product.schema.json` · `GOV-CTR-003` contrato vs `contract.schema.json` · `GOV-QLT-003/004` enums de dimensión, severidad y acción |
| Metadatos | `GOV-SEC-001` clasificación explícita (BLOCKER) · `GOV-MET-009` linaje ordenado fuente→capas→consumidor · `GOV-MET-008` tags de taxonomía controlada |
| Seguridad por código | `GOV-SEC-006` secretos (regex + AST de kwargs) · `GOV-SEC-008` PII real en muestras (RUT con dígito verificador, CPF, Luhn) |
| Políticas IAM | `GOV-IAM-002` ≤ 6144 caracteres · `GOV-IAM-003` Read/Write separados · `GOV-IAM-004` wildcard de escritura solo en recursos exclusivos · `GOV-IAM-005` KMS explícito |
| Diff / evolución | `GOV-CTR-007` breaking change sin MAJOR (diff contra `--base`) · `GOV-LCY-002` transición de estado permitida |
| Grafo / cross-repo | `GOV-SML-003` no redefinir métricas corporativas · `GOV-PRT-002` DP retirado aún consumido · `GOV-PRT-005` una métrica, una definición en el portafolio |
| Compuestas (gates) | `GOV-DPD-027` Definition of Ready · `GOV-DPD-028` Definition of Done · `GOV-CNS-008` certificación de consumo (8 validaciones) · `GOV-MET-015` catalogable |

### 3.4 Reglas semánticas (lógica de negocio, modelado conceptual, patrones)

| ID | Pregunta que resuelve el LLM (consultiva) | KB |
|---|---|---|
| `GOV-ARC-009` | ¿Cada hecho declara un grano único y sus medidas son coherentes con él? ¿Dimensiones conformadas? | KB_07 |
| `GOV-ARC-012` | ¿El producto redefine entidades de otro dominio en vez de consumirlas por contrato? | KB_03, KB_01 |
| `GOV-CTR-014` | ¿Algún campo cambió de significado manteniendo nombre y tipo? (breaking semántico) | KB_05 |
| `GOV-CNS-013` | ¿El patrón y la plataforma son fit-for-purpose según audiencia, interacción, volumen y acción? | KB_13 |
| `GOV-QLT-015` | ¿Umbrales y severidades son coherentes con el uso (ejecutivo, operacional, AI)? | KB_08 |
| `GOV-SEC-016` | ¿Alguna vista permite reidentificar personas combinando cuasi-identificadores? | KB_10 |
| `GOV-AIM-011` | ¿Alguna feature usa información posterior al momento de predicción (leakage)? | KB_15 |
| `GOV-BIZ-009` | ¿La hipótesis de valor es específica (línea base, meta, horizonte) y medible? | KB_02 |

Las 10 reglas **O** (sponsorship, priorización por valor, certificación de usuarios self-service, revisión periódica de
accesos, incidentes, recursos manuales en producción, aprobación de Seguridad en access-analyzer…) quedan explícitas en
el catálogo para que el scoring y los comités las traten como checklist humano y no se pierdan.

### 3.5 Modelo de severidad y escalamiento por ciclo de vida

Severidades del motor alineadas al Data Quality Framework (08 §13): `crítica→BLOCKER · alta→HIGH · media→MEDIUM · baja→LOW`
(+ INFO). Cada regla declara una severidad base y, opcionalmente, un mapa por **grupo de etapa** (18 §9):

| Grupo | Estados | Intención |
|---|---|---|
| `ideacion` | identificado · en definición · candidato · priorizado | guiar sin bloquear (mayoría LOW/MEDIUM u OFF) |
| `diseno` | en diseño | preparar la Definition of Ready |
| `desarrollo` | en desarrollo | DoR bloqueante; controles técnicos crecientes |
| `gate` | listo para producción | DoD, PIA, SLA, runbook, calidad, observabilidad → BLOCKER |
| `operacion` | productivo · en evolución | igual que gate + reglas periódicas (staleness, inactividad, scoring vigente) |
| `salida` | en consolidación · en retiro · retirado | foco en retiro gobernado |

Ejemplo real (`GOV-DPD-013` SLA): `ideacion: LOW · diseno: MEDIUM · desarrollo: HIGH · gate: BLOCKER · operacion: BLOCKER`.
`govkit gate --to listo_para_produccion` evalúa el repo con las severidades del estado destino (pre-flight de promoción).

Reglas de política adicionales: un repo puede **endurecer** severidades en `.govkit.yaml` pero nunca relajarlas; toda
excepción es un **waiver** con `rule`, `reason`, `owner`, `adr` existente y `expires` (vencido ⇒ `GOV-OPS-009`).

---

## 4. Pilar 2 — Motor de Validación Determinista (Architecture Guardrails)

### 4.1 Arquitectura de componentes

```
┌──────────────────────────────────── govkit (CLI) ─────────────────────────────────────┐
│ lint · gate · score · rules · explain · init · omd-lint · docs-lint · portfolio ·     │
│ baseline · hooks · review · ask · kb · doctor · selftest                               │
└──────────────┬────────────────────────────────────────────────────────────────────────┘
               ▼
┌─ Descubrimiento y Config ─┐   ┌─ Parsers (Analizador Sintáctico) ──────────────────────┐
│ RepoContext: índice de    │   │ yamlloc: YAML/JSON → datos + mapa ruta→(línea,col)     │
│ archivos, globs lógicos   │──►│ ast (Python) · léxico SQL/dbt · CODEOWNERS · ASL        │
│ (artifacts), .govkit.yaml │   │ minischema: JSON Schema subset (sin dependencias)       │
│ git (base, diff, branch)  │   └───────────────────────────┬────────────────────────────┘
│ estado → grupo de etapa   │                               ▼
└───────────────────────────┘   ┌─ Motor de reglas ───────────────────────────────────────┐
                                │ Catálogo → selección (pack, profile, --rules)            │
                                │ ├─ Checks declarativos: exists · field · each · count ·  │
                                │ │   filename · regex_scan  (+ condiciones `when`)        │
                                │ ├─ Plugins (registro por nombre):                         │
                                │ │   Validador de Nomenclatura · Inspector de Esquemas ·   │
                                │ │   Evaluador de Metadatos · Analizador IAM · SQL/dbt ·   │
                                │ │   AST PySpark · Contratos (grafo + diff) · Consumo ·    │
                                │ │   Observabilidad · AI/ML · OMD · Docs · Portafolio      │
                                │ ├─ Compuestas (DoR, DoD, certificación) en orden topológico│
                                │ └─ Post (consumen el resultado: mínimos de scoring)       │
                                └───────────────────────────┬─────────────────────────────┘
                                                            ▼
┌─ Motor de política ────────────────────┐   ┌─ Scoring bridge ─────────────────────────┐
│ severidad = f(regla, etapa, override↑) │──►│ pre-score por pilar (19 §24) evaluado     │
│ waivers (ADR+vencimiento) · baseline   │   │ contra `productivo` · tope por BLOCKER    │
│ fingerprint estable · veredicto        │   │ · divergencia con score declarado         │
└────────────────────┬───────────────────┘   └───────────────┬──────────────────────────┘
                     ▼                                       ▼
            ┌─ Reporters ─────────────────────────────────────────────────────────┐
            │ JSON (contrato) · SARIF 2.1.0 · Markdown (PR/Step Summary) · consola  │
            │ + semantic_handoff (preguntas S/H + KB sugeridas para la Capa 2)      │
            └──────────────────────────────────────────────────────────────────────┘
```

Módulos solicitados y su materialización:

| Módulo | Responsabilidad | Implementación |
|---|---|---|
| **Analizador Sintáctico** | Parsear todo artefacto y ubicar cada nodo en línea/columna | `yamlloc.py` (compose de PyYAML → índice de rutas), `ast` de Python, léxico SQL sin comentarios preservando líneas, `GOV-STR-013` |
| **Validador de Nomenclatura** | Repos, jobs, lambdas, modelos, contratos, ramas, commits, IAM, buckets, databases | `plugins/naming.py`, `plugins/iam.py`, checks `filename` |
| **Inspector de Esquemas** | Ficha, contratos, calidad, ASL, reportes; compatibilidad de contratos por diff | `minischema.py` + `schemas/*.json`, `plugins/contracts.py` |
| **Evaluador de Metadatos** | Metadata mínima, glosario, tags, linaje, OMD-ready, dominios, emails, frescura | checks `field/each/count` + `plugins/metadata.py` |
| Analizador de Políticas IAM (extra) | Aislamiento por producto, wildcards, KMS, tags, trust | `plugins/iam.py` |
| Resolver de grafo (extra) | Contrato↔modelo, regla de calidad↔campo, métrica↔glosario, DP↔DP | plugins `contracts`, `quality`, `semantic`, `portfolio` |
| Motor de política (extra) | Etapa, waivers, baseline, veredicto | `engine.py` |

### 4.2 Contrato de entrada

| Entrada | Descripción |
|---|---|
| Ruta del repo | Raíz del Data Product (o del repo `access-analyzer`, docs del framework, o carpeta de portafolio) |
| `.govkit.yaml` | `repo_name`, `policies` (branching, dominios de email, patrones CODEOWNERS, servicios de trust, carpetas extra), `artifacts` (override de globs), `rules.severity` (solo endurecer), `waivers` |
| Artefactos lógicos | `data_product`, `contracts_*`, `quality_rules`, `monitors`, `dbt_yml`, `iam_*`, `asl`, `scorecard`, `features`, `training_sets`, `rag`… (globs en el catálogo) |
| Opciones | `--stage`, `--base` (diff git), `--changed-only`, `--profile` (pre-commit, pr, gate, catalog, periodic, runtime), `--rules` (globs), `--fail-on`, `--baseline`, `--pack` |

La **ficha canónica** (`metadata/catalog/data_product.yaml`, esquema `schemas/data_product.schema.json`) materializa los
20 bloques de 06 como metadata as code (15 §18) y es el origen de la sincronización hacia OpenMetadata.

### 4.3 Contrato de salida (reporte JSON — `schemas/report.schema.json`)

```json
{
  "schema_version": "1.0",
  "tool": {"name": "govkit", "version": "1.0.0", "ruleset_version": "2026.09.1", "ruleset_digest": "3f9a…"},
  "run": {"id": "a81c…", "started_at": "2026-09-25T12:00:00+00:00", "duration_ms": 512, "mode": "diff",
          "base_ref": "origin/main", "packs": ["dp"], "profile": "pr"},
  "target": {"repo": "sales-transactions-anl-dp-cl", "data_product_id": "DP-SAL-TRANSACTIONS-CL-001",
             "lifecycle_state": "listo_para_produccion", "stage_group": "gate", "type": "analytical"},
  "summary": {"verdict": "FAIL", "fail_on": "BLOCKER",
              "counts": {"BLOCKER": 1, "HIGH": 2, "MEDIUM": 0, "LOW": 1, "INFO": 0},
              "rules": {"pass": 168, "fail": 4, "not_applicable": 30, "semantic": 19, "organizational": 9}},
  "violations": [{
    "rule_id": "GOV-SEC-003", "title": "PII ⇒ clasificación sensible y masking", "nature": "D",
    "category": "seguridad", "pillar": "security_privacy",
    "severity": "BLOCKER", "base_severity": "BLOCKER",
    "message": "Contiene PII sin `masking_required: true`",
    "location": {"file": "metadata/catalog/data_product.yaml", "line": 71, "column": 5,
                 "json_path": "spec.classification.masking_required"},
    "remediation": {"summary": "Con pii: true → level: sensible_pii y masking_required: true.", "autofixable": true,
                    "fix": {"type": "set", "path": "spec.classification.masking_required", "value": true}},
    "references": {"source": {"doc": "10-data-security-framework.md", "section": "§11, §15",
                              "quote": "Si el uso no requiere el dato sensible en forma completa…"},
                   "kb": ["KB_10"]},
    "fingerprint": "9c1e7a44d0b2f311"
  }],
  "waivers_applied": [],
  "scoring": {"global": 3.4, "classification": "Data Product gestionado", "pillars": {"…": "…"}},
  "semantic_handoff": {"kb_suggested": ["KB_05", "KB_07"], "questions": [{"rule_id": "GOV-ARC-009", "question": "…"}]}
}
```

Formatos adicionales: **SARIF 2.1.0** (anotaciones en el PR con línea exacta y `partialFingerprints`), **Markdown**
(comentario de PR / `$GITHUB_STEP_SUMMARY`), consola. Códigos de salida: `0` PASS/WARN · `1` FAIL · `2` uso/config · `3` interno.

### 4.4 Pseudológica del motor

```
lint(repo, opciones):
  ctx      ← descubrir(repo)                         # índice de archivos, config, git, estado → grupo de etapa
  reglas   ← catálogo ∩ packs ∩ profile ∩ --rules − disable
  para r en reglas:
     si r.naturaleza ∈ {S}:  handoff ← handoff + (r.pregunta, r.kb)            ; continuar
     si r.naturaleza ∈ {O}:  registrar "organizacional"                        ; continuar
     sev ← severidad(r, grupo_etapa, override_repo_solo_si_más_estricto)
     si sev = OFF o ¬cuando(r) o ¬existe(r.requiere_artefacto):  registrar skip/n.a. ; continuar
     hallazgos ← r.check es declarativo ? interpretar(r.check) : plugin[r.check.nombre](ctx)
     si modo diff y r.scope = file:  hallazgos ← hallazgos ∩ archivos_cambiados
     para h en hallazgos:
        v ← violación(r, h, sev, ubicación=h.línea:columna, fingerprint)
        v.waiver ← waiver_vigente(v) ; v.baseline ← v.fingerprint ∈ baseline
  evaluar reglas post (scoring) ; evaluar compuestas en orden topológico (DoR → DoD → certificación)
  handoff ← handoff + preguntas H cuya parte D pasó
  veredicto ← FAIL si ∃ v contable con sev ≥ fail_on ; WARN si ∃ HIGH/MEDIUM ; si no PASS
  emitir(JSON | SARIF | MD | consola) ; exit(veredicto)
```

Anti-inflación del scoring: una regla sin artefacto evaluable es *no aplica* (no "aprobada"); el pre-score se calcula
siempre contra el estándar de `productivo` y un BLOCKER abierto limita el pilar a 2.0 (08 §24).

### 4.5 Escalabilidad

| Mecanismo | Cómo escala |
|---|---|
| Reglas como datos | Nuevas reglas de presencia/enum/patrón/umbral/relación se agregan en YAML sin código; los plugins son tipos reutilizables. |
| Packs versionados | `dp`, `omd`, `docs`, `portfolio`; el catálogo vive en la organización global (`cencosud-data-global`) y cada repo país fija la versión (`ruleset_version`, `ruleset_digest` en el reporte) — alineado a 15 §10-§12. |
| Incremental | `--base` + `--changed-only` limita hallazgos de archivo al diff del PR; reglas de repo siempre corren (son baratas). |
| Perfiles por punto de control | `pre-commit` (< 2 s: sintaxis, secretos, nombres, esquemas), `pr`, `gate`, `catalog`, `periodic`. |
| Cross-repo | `govkit portfolio <dir>` audita N repos (métricas duplicadas, retirados consumidos, referencias colgantes, solapamientos). |
| Sin dependencias pesadas | Python ≥3.9 + PyYAML (vendorizado, puro Python): corre igual en laptop macOS, runner de CI o contenedor. |
| Adopción brownfield | `govkit baseline` congela hallazgos existentes por fingerprint; se exige solo lo nuevo. |
| Resiliencia | Un plugin que falla emite INFO y no aborta la corrida. |

### 4.6 Puntos de control

| Punto | Comando | Bloquea | Reglas típicas |
|---|---|---|---|
| Pre-commit | `govkit hooks install` → `lint --profile pre-commit` | BLOCKER | sintaxis, secretos, nomenclatura, esquemas, PII en muestras |
| Pull Request | reusable workflow `govkit-governance.yml` → SARIF + resumen | ≥ `fail_on` | todo el pack `dp` en modo diff |
| Gate de lifecycle | `govkit gate --to <estado>` | BLOCKER del estado destino | DoR/DoD, PIA, SLA, runbook, observabilidad, scoring mínimo |
| Catálogo | sync metadata-as-code → OpenMetadata | BLOCKER | ficha, clasificación, dominio, linaje, mapeo OMD |
| Periódico | `govkit portfolio` / `lint --profile periodic` | reporte | staleness, inactividad, scoring vigente, waivers vencidos |

---

## 5. Pilar 3 — Ontología y Base de Conocimiento modular para LLM local

### 5.1 Ontología del dominio de gobierno

```
Capacidad ─1..n─► Dominio ─1..n─► Subdominio ─1..n─► Caso de uso ─n..m─► DATA PRODUCT ◄─ owner/steward/tech (Roles)
                                                                           │ rol: maestro | consumo (patrón 1..12)
                     ┌──────────────┬──────────────┬───────────────┬──────┴───────┬──────────────┬─────────────┐
                  Contrato       Dataset/Capa    Regla calidad    Métrica/Dim     Feature/Modelo   Monitor
                 (in/out, semver) (brz/slv/gld/  (dim, umbral,    (semantic,      (training,       (5 pilares,
                                  smt/serving)    severidad)       glosario)       inferencia, RAG)  severidad)
                     │              │                               │
                 Linaje ◄──────────┘            Clasificación/Acceso (PII, RLS, IAM 1 rol + 2 policies)
Estado de lifecycle (12) ─► Gate ─► Scoring (11 pilares) ─► Certificación / Retiro
```

Esta ontología organiza (a) la taxonomía de la KB, (b) las rutas del esquema de la ficha y (c) las relaciones que
verifican los plugins de grafo. Es la misma estructura que se proyecta a OpenMetadata (dominio, data product, assets,
glosario, tags, linaje).

### 5.2 Taxonomía de Mini-Contextos (medida real)

| Tier | ID | Mini-contexto | Fuentes principales | Tokens | Reglas KB |
|---|---|---|---|---:|---:|
| 0 | KB_00 | Núcleo — principios no negociables (kernel, siempre cargado) | 01, 02 | 948 | 24 |
| 1 | KB_01 | Alineamiento capacidad → dominio → Data Product | 02, 02.1 | 847 | 20 |
| 1 | KB_02 | Casos de uso | 02.2 | 649 | 17 |
| 1 | KB_03 | Dominios y ownership multi-rol | 01 §7, 06 §10 | 587 | 15 |
| 2 | KB_04 | Definición del Data Product (ficha, DoR, DoD, niveles) | 06 | 906 | 19 |
| 2 | KB_05 | Data Contracts, versionado y breaking changes | 06 §11, 15 §17-§20 | 786 | 16 |
| 3 | KB_06 | Lakehouse Medallion, serving y desacople | 02, 08 §10, 14 §11 | 718 | 19 |
| 3 | KB_07 | Modelado ARTS y dimensional Gold | 06 §14, 11 §13-§17 | 747 | 18 |
| 3 | KB_12 | Semantic layer, métricas y dimensiones | 11, 14 §12 | 767 | 18 |
| 4 | KB_08 | Calidad de datos | 08 | 860 | 19 |
| 4 | KB_09 | Metadata, glosario, tags y linaje | 09, 15 §18 | 790 | 16 |
| 4 | KB_10 | Seguridad, privacidad y compliance | 10 | 876 | 20 |
| 4 | KB_11 | IAM por Data Product | Lineamiento IAM | 732 | 16 |
| 4 | KB_17 | Observabilidad | 13 | 560 | 15 |
| 5 | KB_13 | Consumo — 12 patrones y selección | 14 §7-§15 | 791 | 15 |
| 5 | KB_14 | Serving, plataformas y certificación de consumo | 14 §10-§22 | 687 | 13 |
| 5 | KB_15 | AI/ML — features, training, inferencia | 12 | 707 | 17 |
| 5 | KB_16 | GenAI y RAG gobernados | 12 §18-§19, 10 §19 | 612 | 13 |
| 6 | KB_18 | DataOps, CI/CD y repositorio | 15, Estructura de Repositorio | 795 | 16 |
| 6 | KB_19 | Ciclo de vida | 18 | 666 | 15 |
| 6 | KB_20 | Scoring de madurez | 19 (draft) | 608 | 13 |
| 7 | KB_21 | OpenMetadata con cross-account role | Lineamientos OMD | 766 | 14 |
| | | **Total** | | **16.405** | **368** |

Criterio de corte ("chunking"): **un mini-contexto = una frontera de decisión** (lo que un desarrollador necesita para
una tarea), no un corte por tamaño. Presupuesto 500–1.000 tokens (validado: `govkit kb validate` falla si se excede +15%).

### 5.3 Plantilla estándar del Mini-Contexto (esquema `schemas/kb_chunk.schema.json`)

```markdown
---
id: KB_nn                        # estable; las reglas se citan como KBnn.Xk
slug: nombre_corto
title: Título
version: 1.0.0                   # semver del fragmento
status: vigente | borrador       # borrador = fuente en Draft (p.ej. 19-scoring-model)
tier: 0..7                       # capa ontológica
sources: ["NN-doc.md §x"]        # trazabilidad a la fuente oficial
applies_to: [data_product_maestro, consumo, ai_ml, ...]
triggers:                        # señales de enrutamiento
  tasks: [...]                   # tareas del desarrollador
  paths: ["contracts/**"]        # archivos tocados
  rules: ["GOV-CTR-*"]           # reglas deterministas violadas
  keywords: [...]                # refuerzo BM25
depends_on: [KB_00]              # dependencia DURA (cierre transitivo, se carga antes)
related: [KB_04]                 # dependencia BLANDA (solo si sobra presupuesto)
token_budget: 900
deterministic_rules: [GOV-...]   # lo que el motor YA verifica
---
# KB_nn · Título
> Propósito en una frase (la "regla final" del documento fuente).

## R · Reglas canónicas          → **KBnn.R1 [MUST|SHOULD|MAY|MUST NOT]** enunciado atómico. (fuente §)
## H · Heurísticas de decisión   → **KBnn.H1** SI … ENTONCES …   ([PRÁCTICA] = no normativo)
## A · Anti-patrones (señales)   → **KBnn.A1** patrón · señal observable
## E · Ejemplo mínimo            → ✔ / ✘
## V · Preguntas de verificación → **KBnn.V1** pregunta cerrada para el revisor
## D · Ya verificado por el motor determinista → qué NO debe reevaluar el LLM
## G · Glosario local            (opcional)
```

Por qué maximiza el *recall* en modelos 7B–14B minimizando la ventana:

1. **Reglas primero, atómicas y con ID**: el modelo "ve" enunciados cortos y los cita; la cita es verificable.
2. **Fuerza normativa explícita** (`MUST/SHOULD/PRÁCTICA`): el verificador acota la severidad según la etiqueta.
3. **Autocontenido**: cada fragmento repite lo mínimo necesario (sin "como vimos antes"); no hay referencias implícitas.
4. **Sección D (deduplicación con el motor)**: elimina trabajo redundante y contradicciones con hallazgos deterministas.
5. **Proyección por modo**: `review` = R+A+V+D (−18% tokens vs completo), `assist` = R+H+E+A, `qa` = todo; si no cabe,
   degradación a **solo R** (−43%).
6. **Preguntas V cerradas**: convierten "evalúa la calidad" en verificaciones puntuales, con mejor precisión en modelos pequeños.
7. **Idioma y terminología del framework** (español + términos de la fuente): el BM25 y el modelo comparten vocabulario.

### 5.4 Mapa de dependencias entre temas

```
                         KB_00 Núcleo (kernel: siempre cargado · todo mini-contexto depende de él)
                                                     │
 T1 Negocio       KB_01 Alineamiento ·· KB_02 Casos de uso ·· KB_03 Dominios y ownership
 T2 Producto      KB_04 Definición del DP ◄─────────── KB_19 Lifecycle (T6) ·· KB_20 Scoring (T6)
                  KB_05 Contratos ·· KB_18 DataOps (T6)
 T3 Arquitectura  KB_06 Capas ◄── KB_07 Modelado           KB_09 Metadata ◄── KB_12 Semantic layer
 T4 Gobierno      KB_08 Calidad ◄── KB_15 AI/ML (T5)       KB_10 Seguridad ◄── KB_16 GenAI/RAG (T5)
                  KB_11 IAM ·· KB_10                        KB_17 Observabilidad ·· KB_08
 T5 Consumo       KB_13 Patrones de consumo ◄── KB_14 Serving y certificación
 T7 Plataforma    KB_21 OpenMetadata ·· KB_09 ·· KB_11

 ◄── dependencia DURA (la base se carga antes, cierre transitivo)   ·· relacionada BLANDA (solo si sobra presupuesto)
 Detalle completo generado: `govkit kb graph`
```

Enrutamiento por tarea del desarrollador (`kb/_graph.yaml`, 26 tareas; extracto):

| Tarea | Núcleo (siempre) | Complementarios (si hay presupuesto) |
|---|---|---|
| Crear un Data Product | KB_04 · KB_01 · KB_03 | KB_05 · KB_09 · KB_10 · KB_19 · KB_18 |
| Formular caso de uso | KB_02 · KB_01 | KB_04 · KB_13 |
| Diseñar / cambiar contrato | KB_05 | KB_07 · KB_10 / KB_18 · KB_17 |
| Modelar Silver (ARTS ODM) | KB_07 · KB_06 | KB_08 · KB_05 |
| Modelar Gold dimensional | KB_07 · KB_06 | KB_12 · KB_08 · KB_05 |
| Definir métrica semántica | KB_12 (+KB_09 por dependencia) | KB_07 |
| Reglas de calidad | KB_08 | KB_17 · KB_06 |
| Clasificar seguridad / PII | KB_10 | KB_11 · KB_12 |
| IAM | KB_11 | KB_10 |
| Exponer consumo (BI/API/export/reverse ETL) | KB_13 · KB_14 | KB_12 · KB_10 |
| Features / entrenamiento | KB_15 (+KB_08) | KB_10 · KB_17 |
| GenAI / RAG | KB_16 (+KB_10) | KB_15 · KB_09 |
| Observabilidad | KB_17 | KB_08 · KB_18 |
| Repo / CI/CD / hotfix | KB_18 | KB_11 · KB_06 / KB_17 · KB_05 |
| Promover a producción | KB_19 · KB_04 | KB_20 · KB_08 · KB_10 · KB_17 |
| Retirar / consolidar | KB_19 | KB_14 · KB_03 |
| Catalogar / conectar OpenMetadata | KB_09 · KB_21 / KB_21 | KB_03 / KB_11 |

Además del mapa por tarea, el enrutador usa tres señales automáticas: **archivos tocados** (`triggers.paths`), **reglas
violadas por el motor** (`triggers.rules`, p.ej. `GOV-IAM-004` ⇒ KB_11) y **consulta libre** (BM25 léxico, sin embeddings).

### 5.5 Algoritmo de enrutamiento y empaquetado

```
route(tarea?, consulta?, archivos[], reglas_violadas[], presupuesto, modo):
  candidatos ← {KB_00: 100}
  + tarea.core: 90 · reglas violadas: 85 · archivos: 80 · BM25(consulta): ≤70 · tarea.plus: 60
  + related de candidatos con prioridad ≥ 60 (excepto kernel): 40
  orden ← prioridad desc, tier asc, id
  para c en orden:
     grupo ← cierre_dependencias_duras(c) − ya_elegidos           # bases primero
     costo ← Σ tokens(g, proyección[modo])
     si usado + costo ≤ presupuesto:  elegir(grupo, proyección)
     si no, si usado + Σ tokens(g, [R]) ≤ presupuesto: elegir(grupo, [R]) (degradado)
     si no: descartar(c)
  devolver paquete (orden topológico) + manifiesto explicable (motivo de cada fragmento)
```

Es **determinista** (mismo input ⇒ mismo paquete, probado) y **explicable** (`govkit kb route` muestra por qué se cargó
cada fragmento y qué se descartó por presupuesto).

### 5.6 Protocolo de revisión semántica (Capa 2)

```
1. Motor determinista sobre el repo → violaciones + handoff (preguntas S/H)
2. Superficie semántica = ficha, contratos, modelos Gold/Silver, métricas, calidad, monitores, AI, publicación, README
   (con --base: solo archivos cambiados)
3. Por artefacto: presupuesto = num_ctx − 1.400 (respuesta) − 450 (sistema) − artefacto(≤35%) − hallazgos D
   paquete = route(tarea inferida por ruta, archivos=[artefacto], reglas=violaciones del archivo, modo=review)
4. Prompt: CONTEXTO NORMATIVO · HALLAZGOS DETERMINISTAS (no repetir) · PREGUNTAS PRIORITARIAS · ARTEFACTO
5. Ollama /api/chat · temperature 0 · seed 42 · format = JSON Schema (structured outputs) · <think> eliminado
6. Verificación determinista de la salida:
     esquema válido                         ✗ → descartar (schema_errors)
     kb_rule_id ∈ reglas VISIBLES en el paquete  ✗ → descartar (invalid_citation)
     evidence_quote ⊂ artefacto (exacto | ≥80% términos) ✗ → descartar (ungrounded)
     severidad ≤ tope(fuerza normativa): MUST→HIGH · SHOULD→MEDIUM · PRÁCTICA/MAY→LOW · heurística→MEDIUM
     confianza < 0,5 ⇒ "insuficiente_informacion"
7. Publicar como CONSULTIVO (nunca BLOCKER) con métricas de descarte (observabilidad del propio LLM, 13 §20)
```

Contrato de salida del LLM: `schemas/semantic_review.schema.json`
(`kb_rule_id`, `verdict`, `severity_suggested`, `confidence`, `artifact`, `evidence_quote`, `rationale`, `remediation`).

### 5.7 Selección de modelo local y parámetros

| Hardware (RAM unificada / VRAM) | Modelo sugerido (Ollama) | `num_ctx` | Uso |
|---|---|---|---|
| 16 GB (MacBook M1/M2/M3) | `qwen2.5:7b-instruct` (default) · alternativa `llama3.1:8b` | 8.192 | review por artefacto, ask |
| 32 GB | `qwen2.5:14b-instruct` (o equivalente Qwen3 14B sin modo *thinking*) | 16.384 | review con más KB por artefacto |
| ≥ 64 GB / GPU | `qwen2.5:32b-instruct` | 32.768 | revisión de lotes / portafolio |

Parámetros: `temperature=0`, `seed=42`, `format=<JSON Schema>`; variables `GOVKIT_MODEL`, `GOVKIT_CTX`, `OLLAMA_HOST`.
El sistema funciona **sin LLM**: `review --dry-run` y `ask --no-llm` entregan el paquete de contexto para usar con
cualquier modelo aprobado.

---

## 6. Integración híbrida end-to-end

```
Desarrollador          pre-commit              PR (CI)                        Revisión semántica        Gate / Catálogo
     │  git commit ─────► lint --profile ──► ⛔ secretos / sintaxis / nombres
     │                    pre-commit        (bloquea local)
     │  git push ─────────────────────────► govkit-governance.yml
     │                                        lint --base origin/main ─► SARIF (anotaciones) + resumen PR
     │                                        FAIL si ≥ fail_on  ─────────────────────────────────┐
     │  govkit review --base origin/main (local, Ollama) ◄── handoff (preguntas S/H + KB) ──────────┤
     │     └─► hallazgos consultivos verificados (citas + grounding) → el dev decide / Arquitectura valida
     │  govkit gate --to listo_para_produccion ──────────────────────────────────────────────────► ✅/⛔
     │                                                     merge → deploy → sync metadata → OpenMetadata
     │                                                     periódico: govkit portfolio (cross-repo)
```

---

## 7. Especificación de interfaces

### 7.1 CLI

| Comando | Propósito | Salida |
|---|---|---|
| `govkit lint [path] [--base REF] [--stage S] [--profile P] [--format console\|json\|sarif\|md]` | Motor determinista | reporte + exit code |
| `govkit gate [path] --to <estado>` | Pre-flight de promoción con severidades del estado destino | APROBADO / BLOQUEADO |
| `govkit score [path]` | Pre-score por pilar (19) evaluado contra `productivo` | tabla / JSON |
| `govkit init --domain --subdomain --type --country [--owner]` | Repo estándar (estructura, ficha, contratos, IAM data+infra, CI) | repo listo para `lint` |
| `govkit rules [--format md]` · `govkit explain GOV-XXX-NNN` | Catálogo y trazabilidad de una regla | texto / Markdown |
| `govkit omd-lint <dir>` · `docs-lint <dir>` · `portfolio <dir>` | Packs `omd`, `docs`, `portfolio` | reporte |
| `govkit baseline [path]` · `govkit hooks install [path]` | Adopción brownfield · hook pre-commit | archivo / hook |
| `govkit kb list\|show\|route\|pack\|graph\|validate` | Operar la base de conocimiento | texto / JSON |
| `govkit review [path] [--base] [--dry-run] [--model]` | Revisión semántica consultiva (Ollama) | consola / JSON / MD |
| `govkit ask "pregunta" [--no-llm]` | Q&A sobre el framework con citas | respuesta + fuentes |
| `govkit doctor` · `govkit selftest` | Diagnóstico e integridad del kit | checks / tests |

### 7.2 Esquemas (contratos) versionados

`schemas/data_product.schema.json` (ficha) · `contract.schema.json` (Data Contract, mapeable a ODCS) ·
`quality_rules.schema.json` · `report.schema.json` (salida del motor) · `semantic_review.schema.json` (salida del LLM) ·
`kb_chunk.schema.json` (front-matter KB) · `govkit_config.schema.json` (`.govkit.yaml`).

### 7.3 Integración CI

`govkit/templates/github/govkit-governance.yml`: reusable workflow para `base-workflows` (descarga el kit por versión,
ejecuta `lint --base`, sube SARIF a Code Scanning y publica el resumen). `pre-commit-config.yaml` para equipos que usan
pre-commit.

---

## 8. Gobierno del propio sistema

| Aspecto | Decisión |
|---|---|
| Ownership | Equipo de Arquitectura de Datos Regional (catálogo, KB, registros); Gobierno de Datos co-owner de taxonomías y glosario. |
| Cambio de reglas | PR al repo global con: regla nueva/modificada + fuente (doc §) + test que la dispare + actualización de KB si aplica; `govkit kb validate` y `govkit selftest` en CI. |
| Versionado | `ruleset_version` (fecha) + `ruleset_digest` en cada reporte; los repos país fijan versión (15 §10-§12). |
| Trazabilidad | Regla → documento/sección/cita; KB → `sources`; hallazgo → regla → KB. `govkit docs-lint` mantiene la coherencia de la fuente. |
| Excepciones | Solo waivers con ADR, owner y vencimiento; revisión periódica de waivers. |
| KPIs del sistema | % reglas automatizadas (hoy 89%) · tasa de falsos positivos por regla (objetivo < 5%) · tiempo de lint p95 · tokens por revisión · tasa de descarte del verificador LLM (citas inválidas / sin grounding) · adopción (repos con `govkit` en PR). |
| Autocumplimiento GenAI | Corpus oficial y versionado, clasificación `interno`, sin PII, LLM local, hallazgos consultivos con citas verificadas (12 §18-§19, 10 §19). |

---

## 9. Roadmap de implementación

| Ola | Alcance | Criterio de salida |
|---|---|---|
| 0 · Validación (2 semanas) | Revisión de este SAD, del catálogo y de los hallazgos documentales; decidir ADR-006 | Catálogo aprobado por Arquitectura + Gobierno |
| 1 · Piloto (4 semanas) | 2–3 Data Products (Sales, Product, Customer) en CL; `lint` en PR en modo informativo; baseline | FP < 5%, lint < 5 s |
| 2 · Enforcement (4 semanas) | `fail_on: BLOCKER` en PR; `gate` en promoción; pack `omd` en `access-analyzer` | 0 BLOCKER en productivos piloto |
| 3 · Semántica (4 semanas) | `review` local con Qwen 7B/14B; medir tasa de hallazgos útiles y descarte | ≥ 60% hallazgos útiles según Arquitectura |
| 4 · Escala regional | Repos país, `portfolio` periódico, integración de reportes JSON a OpenMetadata/scoring | adopción ≥ 80% repos |

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Falsos positivos en reglas léxicas (SQL, PII por nombre) | Reglas H (parte D + confirmación semántica), severidades moderadas, waivers con ADR, baseline |
| Gaming de reglas de existencia (archivos esqueleto) | Detección de marcas `<COMPLETAR>` en runbook/arquitectura/DBML; parte S de reglas H; `gate` con DoD compuesto |
| Deriva entre documentos y reglas | `docs-lint`, `sources` en KB, `ruleset_digest`, PRs con test obligatorio |
| Alucinación del LLM | Verificador determinista (esquema, citas visibles, grounding, tope de severidad); nunca bloqueante |
| Conflictos normativos no resueltos (p.ej. branching) | Política configurable + ADR-006; el LLM tiene instrucción de reportar conflictos, no resolverlos (KB00.H3) |
| Registros aún en propuesta (códigos de dominio, mapa de capacidades, métricas corporativas) | Marcados `status: propuesta/pendiente`; reglas dependientes en severidad informativa hasta su aprobación |

---

## 11. Hallazgos de auditoría documental (resumen)

La auditoría para construir el catálogo detectó **inconsistencias que impiden validar de forma exacta** si no se
resuelven (detalle y propuesta de resolución en `docs/02-hallazgos-auditoria-documental.md` y `docs/adr/`):

1. **Estrategia de ramas contradictoria**: 15 §15 (trunk-based, "no ramas por ambiente") vs Estructura de Repositorio (`develop`/`staging`/`main` por ambiente).
2. **Estructura de repositorio divergente**: 15 §14 (`infra/`, `config/`, `CHANGELOG.md`, `metadata/*.yaml` planos) vs estándar fijo (`metadata/{catalog,lineage,tags}`, sin `infra/`).
3. **Referencias cruzadas renumeradas**: `14-dataops-cicd.md` vs `15-dataops-cicd.md`; `15-scoring-model.md` vs `19-scoring-model.md`; 14 es consumo.
4. **Tipos de Data Product vs códigos de repo**: 06 define 5 tipos; el nombre de repo usa `txd`/`anl`, y `txd` aparece también como *dominio* en el ejemplo de jobs.
5. **Dimensiones de calidad**: 01 §4 (5), 06 Bloque 10 (6), 08 §9 (8).
6. **Estados de lifecycle**: 06 §7 (7 estados) vs 18 §9 (12) vs catálogo 18 §27 (6, en inglés).
7. **Tag `repo` apunta a GitLab** mientras 15 §8 define GitHub como system of record.
8. **Sin política normada de particionamiento** (solo ejemplos en 14 §11.4) — la KB lo marca como [PRÁCTICA].

---

## Anexo A — Glosario del sistema

| Término | Definición |
|---|---|
| Regla D/H/S/O | Naturaleza de validación: Determinista, Híbrida, Semántica, Organizacional |
| Pack | Conjunto de reglas por tipo de repositorio: `dp`, `omd`, `docs`, `portfolio` |
| Mini-contexto (KB_nn) | Fragmento atómico de conocimiento normativo, citable y con presupuesto de tokens |
| Proyección | Subconjunto de secciones de un mini-contexto enviado según el modo (review/assist/qa) |
| Handoff semántico | Preguntas S/H que el motor determinista entrega al revisor LLM |
| Grounding | Verificación de que la evidencia citada por el LLM existe en el artefacto |
| Waiver | Excepción temporal a una regla, con ADR, owner y vencimiento |
| Baseline | Conjunto de hallazgos preexistentes (fingerprints) que no bloquean durante la adopción |

## Anexo B — Mapa de archivos

```
arquitectura/
├── docs/00-SAD-sistema-gobernanza-hibrido.md   ← este documento
├── docs/01-matriz-reglas.md                     ← generado: govkit rules --format md
├── docs/02-hallazgos-auditoria-documental.md
├── docs/adr/ADR-001 … ADR-006
└── govkit/
    ├── install.sh · uninstall.sh · bin/govkit · VERSION
    ├── rules/catalog.yaml · rules/registry/*.yaml
    ├── schemas/*.schema.json
    ├── kb/KB_00 … KB_21 · kb/_graph.yaml
    ├── lib/govkit/ (engine, declarative, plugins/*, kb/*, llm/*, report/*, scoring, scaffold, cli)
    ├── templates/data-product/ · templates/github/
    ├── examples/sales-transactions-anl-dp-cl/   ← Data Product de referencia (PASS en gate)
    ├── tests/ (52 pruebas + fixtures omd/docs/portfolio)
    └── vendor/yaml (PyYAML puro, MIT)
```
