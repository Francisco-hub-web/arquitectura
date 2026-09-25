# ADR-001: Arquitectura híbrida "determinista primero, semántico después, humano al final"

- Estado: propuesto
- Fecha: 2026-09-25
- Decisores: Arquitectura de Datos Regional

## Contexto
El Data & AI Discipline Framework es documentación pasiva. Evaluarlo completo con un LLM es caro, lento, no reproducible
y no cabe en la ventana de un modelo local; evaluarlo solo con reglas deja fuera el modelado conceptual y la lógica de negocio.

## Decisión
Dos capas: (1) motor determinista (AST, regex, esquemas, grafo, diff) para todo criterio cerrado — bloqueante;
(2) revisor semántico con LLM local y KB modular solo para la superficie interpretativa — consultivo. Las reglas
organizacionales quedan explícitas como checklist humano. Las reglas híbridas se descomponen en parte D + pregunta S.

## Consecuencias
- 89% de los lineamientos se verifican con costo cero y en < 1 s; el LLM recibe solo preguntas que el código no puede responder.
- El LLM nunca repite hallazgos deterministas (sección D de cada mini-contexto + lista de hallazgos en el prompt).
- Requiere mantener el catálogo y la KB sincronizados con los documentos (ver ADR-002, ADR-004).
