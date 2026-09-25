# ADR-002: Reglas como código — catálogo declarativo + plugins

- Estado: propuesto
- Fecha: 2026-09-25

## Contexto
Las reglas cambian con más frecuencia que el motor y deben ser auditables por Arquitectura y Gobierno sin leer Python.

## Decisión
`rules/catalog.yaml` es la fuente única de verdad: cada regla declara naturaleza, severidad, escalamiento por etapa,
técnica, puntos de control, fuente (documento + sección + cita), mini-contextos KB, remediación y un `check`.
Tipos declarativos (`exists`, `field`, `each`, `count`, `filename`, `regex_scan`, `composite`) cubren presencia, enums,
patrones, umbrales y relaciones; los plugins (registro por nombre) cubren AST, grafo, diff y políticas IAM.
Los registros corporativos (dominios, tags, lifecycle, scoring, cuentas, matriz de consumo) viven en `rules/registry/`.

## Consecuencias
- Agregar una regla de presencia/forma no requiere código; toda regla nueva exige un test que la dispare.
- La matriz de reglas (`docs/01-matriz-reglas.md`) se genera desde el catálogo: la documentación no deriva.
- Los repos fijan la versión del ruleset (`ruleset_version`, `ruleset_digest` en cada reporte).
