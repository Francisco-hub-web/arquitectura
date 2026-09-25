# ADR-005: Hallazgos semánticos consultivos con verificación determinista

- Estado: propuesto
- Fecha: 2026-09-25

## Contexto
Un LLM puede alucinar reglas, citar evidencia inexistente o sobredimensionar la severidad. Bloquear un pipeline con
esa señal erosiona la confianza (13 §28: alertas irrelevantes) y contradice 12 §18-§19.

## Decisión
La salida del LLM se restringe por JSON Schema y se verifica antes de publicarse: (1) esquema; (2) el `kb_rule_id`
debe existir en las reglas efectivamente visibles en el paquete (no basta con que exista en la KB); (3) la
`evidence_quote` debe estar en el artefacto (exacta o ≥80% de términos); (4) la severidad se acota por la fuerza
normativa de la regla citada; (5) confianza < 0,5 ⇒ `insuficiente_informacion`. Los hallazgos son siempre consultivos.

## Consecuencias
- Métricas de descarte (citas inválidas, sin grounding, errores de esquema) sirven para observar la calidad del modelo.
- El bloqueo sigue siendo 100% determinista y reproducible.
