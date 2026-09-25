# ADR-007: Agentes de código vía MCP y auto-remediación determinista

- Estado: propuesto
- Fecha: 2026-09-25

## Contexto
Los equipos ya trabajan con agentes de código (Claude Code, Cursor) además del LLM local. Sin integración, el agente
"recuerda" el framework de memoria (alucina reglas) y el desarrollador corrige a mano lo que el motor ya sabe
remediar. Dos riesgos: (1) que el agente se convierta en una segunda fuente de verdad no verificable; (2) que una
auto-corrección destruya contenido escrito por personas.

## Decisión
1. **`govkit mcp`** expone el sistema como servidor MCP (stdio, sin dependencias). La frontera de confianza no cambia:
   - Herramientas de **verdad** (`lint`, `gate`, `score`, `fix`, `explain_rule`): mismo motor, mismos resultados que CLI y CI.
   - Herramientas de **contexto** (`kb_context`, `semantic_review_plan`): el mismo enrutador de KB que usa Ollama.
   - **`verify_semantic_findings`**: el mismo verificador de ADR-005 se aplica a los hallazgos del agente. El agente
     sustituye al LLM local como redactor, nunca como verificador. Los hallazgos siguen siendo consultivos.
2. **`govkit fix`** solo automatiza lo que no requiere juicio: carpetas estándar, archivos desde plantilla corporativa,
   valores deterministas conocidos, bumps semver y claves ausentes como `<COMPLETAR>`. Invariantes:
   nunca sobrescribe contenido humano; cada edición se verifica re-parseando (clave presente, valor esperado y ninguna
   clave previa perdida) o se revierte; simulación por defecto (`--apply` explícito); renombres y movimientos quedan
   como acción manual (rompen referencias dbt/imports).

## Consecuencias
- El agente trabaja con los mismos hallazgos, línea exacta y remediación que verá el PR: menos iteraciones de CI.
- Los valores de negocio siguen siendo responsabilidad humana: `fix` hace explícito el esqueleto, no lo inventa.
- El servidor MCP no abre red ni puertos (stdio); hereda los permisos del proceso que lo lanza.
