# ADR-0002: Paralelismo del procesamiento en Python (no en n8n)

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

El diagrama del flujo (`docs/especificacion_flujo/00_procesamiento_lote_zip.md`)
dibuja "Procesar fichas del lote" como un bucle secuencial. Sin embargo, el
procesamiento por ficha (canonizar → crops → clasificar → reglas) es **independiente
entre fichas**: es un problema *embarrassingly parallel*. La única parte que necesita
visión global del lote es la consolidación (detección de códigos de estudiante
duplicados y `resultados.json` global).

Se evaluó dónde ubicar el paralelismo: en n8n o en Python.

## Decisión

El paralelismo vive en **Python**, siguiendo un modelo **map → reduce**:

- **map (paralelo, por ficha):** visión/crops (CPU-bound) con
  `concurrent.futures.ProcessPoolExecutor`.
- **CNN:** inferencia por lotes (*batched*) en un solo `forward` sobre un tensor
  `[N, 1, 64, 64]` (más eficiente que multiproceso). *Para v1 se usa inferencia
  por-ficha con `classify_crops` (~130 crops/ficha, trivial en CPU); el batching
  se difiere como optimización para no modificar el archivo de P1.*
- **reduce (secuencial, una vez):** duplicados + `resultados.json`.

n8n orquesta a nivel de **fase del lote**, nunca ficha por ficha.

## Consecuencias

**Positivas**
- Escala con núcleos de CPU y aprovecha vectorización en la CNN.
- Mantiene a n8n simple y estable como orquestador.

**Negativas / trade-offs**
- El nodo `Loop`/sub-workflows de n8n queda descartado para paralelismo (es
  secuencial y frágil); la orquestación de n8n opera a granularidad de fase.

## Alternativas consideradas

- **Paralelismo en n8n (por ficha):** el nodo `Loop Over Items` es secuencial y el
  paralelismo real exige sub-workflows con alto overhead y difícil depuración.
  Descartada.
- **Secuencial simple:** aceptable para lotes pequeños, pero no aprovecha el hardware
  ni el batching de la CNN. Descartada como diseño objetivo (sirve solo de fallback).
