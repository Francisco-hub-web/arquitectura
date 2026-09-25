---
id: KB_16
slug: genai_rag
title: GenAI y RAG gobernados (incluye este asistente)
version: 1.0.0
status: vigente
tier: 5
sources: ["12-ai-ml-data-framework.md §18-§19, §22-§23", "10-data-security-framework.md §19", "13-data-observability.md §20"]
applies_to: [ai_ml, genai]
triggers:
  tasks: [rag_genai]
  paths: ["metadata/catalog/ai/rag*.yaml"]
  rules: ["GOV-AIM-008", "GOV-AIM-009"]
  keywords: [genai, rag, llm, embeddings, vector, índice, prompt, corpus, asistente, copilot, alucinación, retrieval, chunk]
depends_on: [KB_00, KB_10]
related: [KB_15, KB_09]
token_budget: 850
deterministic_rules: [GOV-AIM-008, GOV-AIM-009]
---
# KB_16 · GenAI y RAG
> No se expone GenAI sobre contenido corporativo sin controlar fuentes, clasificación, trazabilidad y alcance de uso.

## R · Reglas canónicas
- **KB16.R1 [MUST]** Gobernar: corpus fuente, chunks, embeddings, índices vectoriales, metadata de documentos, reglas de retrieval, prompts base, políticas de filtrado, artefactos técnicos y outputs. (12 §18)
- **KB16.R2 [MUST]** Fuentes de verdad: contenido oficial y versionado, metadata asociada, clasificación y sensibilidad registradas, acceso por rol o dominio; no usar documentos no validados como base única. (12 §19 — punto pendiente de validación en el framework)
- **KB16.R3 [MUST]** Seguridad: clasificar el corpus, redactar contenido sensible antes de indexar, controlar retención de prompts y embeddings, evitar suplantación y fuga vía asistentes. (10 §19, 12 §22)
- **KB16.R4 [MUST]** Observabilidad RAG: salud del corpus, indexación, cobertura y vigencia (alucinaciones), fallas de retrieval, latencia, respuestas vacías o problemáticas. (13 §20)
- **KB16.R5 [MUST]** Output generado o recuperado = parte de un Data Product (owner, consumo, trazabilidad). (12 §17)

## H · Heurísticas de decisión
- **KB16.H1** Cada respuesta debe citar la fuente (ID de chunk/regla); sin cita verificable, la respuesta es no confiable.
- **KB16.H2** Chunk = unidad de decisión autocontenida con metadata (fuente, versión, clasificación), no cortes por tamaño fijo.
- **KB16.H3** Ámbito de este sistema: govkit es un caso RAG corporativo; su corpus (KB_*) es oficial, versionado, clasificado `interno`, sin PII, y sus hallazgos son consultivos y verificados (citas + grounding).

## A · Anti-patrones
- **KB16.A1** RAG como simple indexación sin metadata ni seguridad. · **KB16.A2** Corpus desactualizado sin versión. · **KB16.A3** Prompts con datos personales retenidos sin política.

## V · Preguntas de verificación
1. **KB16.V1** ¿Todas las fuentes del corpus son oficiales, versionadas y clasificadas?
2. **KB16.V2** ¿Existe redacción de contenido sensible antes de generar embeddings?

## D · Ya verificado por el motor determinista
Ficha de fuentes RAG (oficial, versión, clasificación, owner, alcance) y retención de prompts/embeddings.
