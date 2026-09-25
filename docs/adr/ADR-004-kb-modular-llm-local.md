# ADR-004: Base de conocimiento modular con proyección y presupuesto de tokens para LLM local

- Estado: propuesto
- Fecha: 2026-09-25

## Contexto
Los modelos locales 7B–14B tienen ventanas útiles de 8k–32k tokens y su precisión cae con contextos largos y difusos.

## Decisión
22 mini-contextos (tiers 0–7) con plantilla fija: front-matter (fuentes, disparadores, dependencias, presupuesto,
reglas deterministas cubiertas) y secciones R/H/A/E/V/D/G con reglas atómicas citables `KBnn.Xk` y fuerza normativa
explícita (MUST/SHOULD/PRÁCTICA). Un enrutador determinista (kernel + tarea + reglas violadas + archivos + BM25 +
relacionados) aplica cierre de dependencias duras, proyección por modo (review/assist/qa) y degradación a "solo R"
dentro del presupuesto. Recuperación léxica BM25 (sin embeddings) por simplicidad, reproducibilidad y costo cero.

## Consecuencias
- KB total ≈16,4k tokens; un paquete de revisión típico usa 3–6k tokens.
- `govkit kb validate` controla esquema, presupuesto, IDs únicos, ciclos y referencias cruzadas con el catálogo.
- Si en el futuro se requiere búsqueda semántica, se puede sumar embeddings locales como señal adicional del enrutador.
