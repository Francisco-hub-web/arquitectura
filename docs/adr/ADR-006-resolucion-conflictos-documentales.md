# ADR-006: Resolución de conflictos documentales que impiden validación exacta

- Estado: propuesto — requiere decisión del Equipo de Arquitectura de Datos Regional
- Fecha: 2026-09-25

## Contexto
La auditoría (docs/02-hallazgos-auditoria-documental.md) detectó contradicciones: estrategia de ramas (H-01),
estructura de repositorio (H-02), referencias renumeradas (H-03), tipos vs códigos de repo (H-04), dimensiones de
calidad (H-05) y estados de lifecycle (H-06).

## Decisión (propuesta)
1. Ramas: trunk-based (`main` + ramas cortas `feat|fix|hotfix|chore/<dominio>/<desc>`) y promoción por pipeline con
   GitHub Environments (dev → staging → prod con aprobación), manteniendo el mapeo a cuentas AWS DATA TEST/PROD.
   Transitorio: `policies.branching: env-branches` hasta migrar.
2. Estructura: estándar fijo + `CHANGELOG.md` + `infra/iam/`; metadata-as-code en `metadata/catalog/`.
3. Referencias: renumerar en un PR único; `govkit docs-lint` en el CI del repo de arquitectura.
4. Tipos: tabla oficial tipo (06) ↔ código de repo.
5. Calidad: 8 dimensiones (08 §9) como canon; 01 §4 y 06 §16 las referencian.
6. Lifecycle: 12 estados (18 §9) como canon con mapeo a catálogo (18 §27).

## Consecuencias
- Hasta la decisión, govkit aplica la interpretación documentada en cada hallazgo y las reglas afectadas son configurables.
- Una vez decidido, se actualiza el catálogo (nueva `ruleset_version`) y la KB (KB_18, KB_08, KB_19).
