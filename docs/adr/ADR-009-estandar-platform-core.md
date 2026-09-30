# ADR-009: Perfil de estándar por repositorio — platform-core (ODCS v3.1.0 + xCencosud) vs lineamientos

- Estado: propuesto. Supersede parcialmente la decisión 2 de ADR-006 (ubicación de la ficha) para repos platform-core.
- Fecha: 2026-09-30

## Contexto
global-data-platform-core publica un estándar **ejecutable** de Data Contracts y del baseline de Data Products:
- ODCS v3.1.0 con la extensión `customProperties.xCencosud`, perfil 1.2.0;
- carpetas medallion;
- ficha en `metadata/data_product.yaml`;
- validadores que corre el CI de cada Data Product (`validate-contracts.yaml`).

Ese estándar contradice reglas de govkit derivadas del lineamiento "Estructura de Repositorio", que no está versionado en los repos corporativos:
- `contracts/input|output`;
- la ficha en `metadata/catalog/`;
- los hechos Gold `fact_*`.

Detalle en C-01, C-02, C-13 y C-14 (`govkit arch conflictos`).

## Decisión
1. **Estándar por repositorio**: `standard: auto | platform-core | lineamientos`. Se configura en la config personal o compartida, con la variable `GOVKIT_STANDARD` o con `--estandar`.
   - En modo `auto` se elige **platform-core** si el repo tiene alguno de estos marcadores:
     - una copia del estándar (`contracts/_schema/`);
     - la ficha en `metadata/data_product.yaml`, sin `metadata/catalog/`;
     - contratos ODCS v3.
   - Si no, se usa **lineamientos**: la base instalada no cambia de comportamiento.
2. Las reglas declaran `standards: [...]`.
   - Se restringen a `lineamientos` 22 reglas cuyo artefacto o esquema difiere del estándar platform-core:
     - contratos de interfaz;
     - ficha `spec.*`;
     - DoR/DoD sobre esa ficha;
     - naming `fact_`;
     - workflows y carpetas del lineamiento;
     - `quality/expectations`.
   - Las reglas cuyo artefacto es el mismo en ambos estándares siguen aplicando a los dos (README, CHANGELOG, runbook, observabilidad, IAM, etc.).
3. **Reglas GOV-PCX-001..026 (estándar platform-core)**. **Leen el estándar como dato** y no lo duplican. El orden de lectura es:
   1. la copia del propio repo;
   2. el clon local de platform-core;
   3. el índice de `govkit arch`;
   4. un fallback destilado (`rules/registry/platform_core.yaml`, verificado contra `c07803a`).

   La semántica replica el validador corporativo `cenco_dc` (Tier 1 y metadata) sin copiar su código.

   Los requisitos de GOV 06/08/15 que aplican a cualquier contrato se expresan sobre ODCS:
   - descripción;
   - compatibilidad;
   - breaking change con MAJOR;
   - reglas de calidad.
4. `--cenco-dc` (opt-in) ejecuta además el validador oficial desde el clon local. Nunca es automático, porque ejecutar código corporativo es decisión del usuario.
5. **`govkit init --estandar platform-core`** genera la estructura del baseline, la ficha y los README/CHANGELOG/runbook con `<COMPLETAR>`.
   - No genera workflows ni CODEOWNERS: se copian desde el baseline oficial.
   - `govkit fix` crea la ficha y las carpetas faltantes.

## Consecuencias
- En un repo platform-core, govkit exige lo mismo que el CI oficial y agrega lo que ese CI no cubre (GOV 06/08/15, seguridad, ciclo de vida, trazabilidad), con fuente verificable.
- El naming de repos acepta los tipos observados en el diseño ArchiMate aprobado (`mdh`, `sm`, sin tipo), pero su significado sigue NO DETERMINADO (C-04).
- Cuando el Equipo de Arquitectura de Datos Regional decida C-01, C-02 y C-13 (Potential ADR PA-01, PA-02, PA-05), este ADR se acepta o se ajusta, y el ruleset sube de versión.
