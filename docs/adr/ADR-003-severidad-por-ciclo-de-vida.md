# ADR-003: Severidad sensible al ciclo de vida y gates de promoción

- Estado: propuesto
- Fecha: 2026-09-25

## Contexto
Exigir desde la ideación los controles de producción desincentiva la adopción; no exigirlos en el gate permite
productos inmaduros en producción (18 §16, 19 §27).

## Decisión
Cada regla declara severidad base y un mapa por grupo de etapa (`ideacion`, `diseno`, `desarrollo`, `gate`,
`operacion`, `salida`), incluyendo `OFF`. `govkit gate --to <estado>` evalúa con las severidades del estado destino.
DoR, DoD, certificación de consumo y "catalogable" son reglas compuestas sobre otras reglas. Un repo solo puede
endurecer severidades; relajar exige waiver con ADR, owner y vencimiento. El pre-score se calcula siempre contra el
estándar de `productivo` para medir madurez absoluta.

## Consecuencias
- Un esqueleto recién creado (`govkit init`) no tiene BLOCKER en `en_definicion` pero queda BLOQUEADO hacia producción.
- La transición de estados se valida por diff (`GOV-LCY-002`), evitando saltos de gate.
