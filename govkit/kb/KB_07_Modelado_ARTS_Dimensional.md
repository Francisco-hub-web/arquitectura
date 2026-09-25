---
id: KB_07
slug: modelado_arts_dimensional
title: Modelado de datos — ARTS (ODM/DWM) y modelo dimensional Gold
version: 1.0.0
status: vigente
tier: 3
sources: ["06-data-product-definition.md §14", "02-data-strategy.md §13", "11-semantic-layer-framework.md §13, §16-§17", "lineamientos/estructura-repositorio.md modeling/"]
applies_to: [data_product_maestro]
triggers:
  tasks: [modelar_silver_odm, modelar_gold_dimensional, disenar_contrato]
  paths: ["modeling/**", "docs/dbdiagram/**", "contracts/gold/**", "contracts/silver/**"]
  rules: ["GOV-NAM-005", "GOV-DPD-020", "GOV-ARC-003", "GOV-ARC-007", "GOV-ARC-008", "GOV-ARC-009", "GOV-ARC-010", "GOV-STR-009", "GOV-STR-012"]
  keywords: [arts, odm, dwm, dimensional, hecho, dimensión, grano, granularidad, star schema, dbt, jerarquía, clave, scd, modelo]
depends_on: [KB_00, KB_06]
related: [KB_05, KB_12]
token_budget: 950
deterministic_rules: [GOV-NAM-005, GOV-DPD-020, GOV-ARC-003, GOV-ARC-007, GOV-ARC-008, GOV-STR-012]
---
# KB_07 · Modelado ARTS y dimensional
> ARTS es un acelerador semántico, no una imposición: el modelo responde al lenguaje del dominio.

## R · Reglas canónicas
- **KB07.R1 [MUST]** Declarar cómo se usa ARTS: alineado al estándar, extensión por dominio (atributos/relaciones propias de Cencosud) o modelo propio (documentado y justificado). (06 §14)
- **KB07.R2 [SHOULD]** ARTS ODM / canónico en Silver; ARTS DWM y extensiones en Gold y Data Products analíticos. (02 §13, 11 §13)
- **KB07.R3 [MUST]** Documentar entidades, hechos y dimensiones, claves de negocio, granularidad, relaciones, jerarquías y nivel de abstracción; versionar el modelo en `docs/dbdiagram` (DBML). (06 §14)
- **KB07.R4 [MUST]** Gold dimensional con `dim_*` y `fact_*`; los modelos dbt son la fuente de verdad Silver→Gold; relaciones vía `ref()`/`source()`. (Estructura de Repositorio)
- **KB07.R5 [MUST]** Dimensiones compartidas con ficha: descripción, niveles de jerarquía, clave de negocio, dominio, Data Product fuente, owner; jerarquías gobernadas (niveles, agregación, faltantes, reestructuraciones, owner del cambio). (11 §16-§17)
- **KB07.R6 [MUST]** La semantic layer no destruye la disciplina del modelo base: expone significado sobre un modelo sólido. (11 §13)

## H · Heurísticas de decisión
- **KB07.H1 [PRÁCTICA]** Declarar el grano antes que las columnas; toda medida debe ser coherente con ese grano (sin mezclar línea y ticket en el mismo hecho).
- **KB07.H2 [PRÁCTICA]** Medidas aditivas en hechos (montos, unidades); ratios y promedios se calculan en la semantic layer.
- **KB07.H3 [PRÁCTICA]** Reutilizar dimensiones conformadas del dominio dueño (tiempo, producto, tienda, canal, país) en vez de crear copias locales.
- **KB07.H4 [PRÁCTICA]** Para dimensiones que cambian en el tiempo, preferir historia (tipo 2) cuando el análisis necesita "como era" y documentarlo en el contrato.
- **KB07.H5** Si una entidad no existe en ARTS, extender con prefijo/namespace Cencosud y registrar el término en el glosario.

## A · Anti-patrones
- **KB07.A1** Hechos sin grano declarado. · **KB07.A2** Dimensiones de otro dominio redefinidas localmente.
- **KB07.A3** Lógica de negocio escondida en SQL no documentado. · **KB07.A4** Relaciones físicas hardcodeadas.

## V · Preguntas de verificación
1. **KB07.V1** ¿Cada hecho tiene un grano único y sus medidas son coherentes con él?
2. **KB07.V2** ¿Las dimensiones son conformadas y provienen del dominio dueño?
3. **KB07.V3** ¿La elección alineado/extensión/propio está justificada en un ADR?

## D · Ya verificado por el motor determinista
Nombres dim_/fact_, declaración ARTS, ref()/source(), tests de clave, descripciones de modelos, DBML y proyecto dbt.
