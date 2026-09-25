---
id: KB_15
slug: ai_ml_features
title: AI/ML sobre Data Products — features, training, inferencia
version: 1.0.0
status: vigente
tier: 5
sources: ["01-data-principles.md §10", "12-ai-ml-data-framework.md §3-§17, §20-§24, §28", "14 §9.12, §11.6", "08 §10.5, §19"]
applies_to: [ai_ml]
triggers:
  tasks: [feature_ml, entrenar_modelo]
  paths: ["metadata/catalog/ai/**"]
  rules: ["GOV-AIM-001", "GOV-AIM-002", "GOV-AIM-003", "GOV-AIM-004", "GOV-AIM-005", "GOV-AIM-006", "GOV-AIM-007", "GOV-AIM-010", "GOV-AIM-011", "GOV-AIM-012", "GOV-QLT-017", "GOV-DPD-010", "GOV-DPD-023"]
  keywords: [ai, ml, modelo, feature, feature store, entrenamiento, training, inferencia, leakage, drift, mlops, forecast, propensión, recomendador]
depends_on: [KB_00, KB_08]
related: [KB_16, KB_17]
token_budget: 1000
deterministic_rules: [GOV-AIM-001, GOV-AIM-002, GOV-AIM-003, GOV-AIM-004, GOV-AIM-005, GOV-AIM-006, GOV-AIM-007, GOV-AIM-010]
---
# KB_15 · AI/ML sobre Data Products
> La AI corporativa se construye sobre Data Products gobernados, no sobre datasets o notebooks aislados.

## R · Reglas canónicas
- **KB15.R1 [MUST]** Principios: no usar datos sin ownership, no entrenar sin trazabilidad, no exponer modelos sin entender sus inputs, no usar features sin definición, no promover sin observabilidad. (12 §9)
- **KB15.R2 [MUST]** Feature = activo: nombre, definición, lógica, ventana temporal, granularidad, owner, Data Product fuente, frecuencia, calidad esperada, sensibilidad, contexto. Feature reutilizada ⇒ gobernada, no cálculo local. (12 §12)
- **KB15.R3 [MUST]** Training dataset reproducible y versionado: fuentes, features, target, ventana, población, filtros, exclusiones, versión, calidad mínima. (12 §14)
- **KB15.R4 [MUST]** Evaluación: validación, test, partición temporal o lógica, métricas y controles de leakage. (12 §15)
- **KB15.R5 [MUST]** Consistencia training/inferencia (mismas definiciones y versiones de features, batch/online); si no, no se promueve. (12 §16)
- **KB15.R6 [MUST]** Outputs de modelos (score, ranking, forecast, segmento, respuesta RAG) se gobiernan como Data Products: owner, metadata, consumo, observabilidad, acceso. (12 §17)
- **KB15.R7 [MUST]** Observabilidad AI: calidad de features, freshness, drift de datos y modelo, latencia, uso del output, trazas de agentes. (12 §23)
- **KB15.R8 [MUST]** Serving para ML con versionado exacto y time travel (Delta, Feature Store). (14 §11.6)

## H · Heurísticas de decisión
- **KB15.H1** Point-in-time: toda feature debe calcularse con información disponible antes del momento de predicción.
- **KB15.H2** Si el modelo compensa carencias del Data Product base, primero mejorar el producto (12 §28).
- **KB15.H3** Las métricas de negocio usadas como features deben venir de la semántica oficial (12 §25).

## A · Anti-patrones
- **KB15.A1** Datasets de entrenamiento fuera del ecosistema. · **KB15.A2** Features sin versión. · **KB15.A3** AI como demo sin proceso real.

## V · Preguntas de verificación
1. **KB15.V1** ¿Alguna feature cruza la fecha de corte del target (leakage)?
2. **KB15.V2** ¿Los datos personales usados tienen base de consentimiento y minimización?
3. **KB15.V3** ¿El output del modelo tiene consumidor y decisión asociada?

## D · Ya verificado por el motor determinista
Fichas de features y training sets, evaluación declarada, consistencia training/inferencia por nombre y versión, fuentes declaradas, monitores de drift, PII con consentimiento, outputs de modelo como DP.
