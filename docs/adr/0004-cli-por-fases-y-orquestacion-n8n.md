# ADR-0004: CLI por fases de P3 y orquestación por n8n

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

P3 debe exponerse a n8n para que este orqueste el pipeline. Había que definir la
**granularidad** del CLI (un comando end-to-end vs. comandos por fase) y **quién
invoca a P2** (`core_vision.py`). Esto determina cuánta orquestación es visible en
n8n y qué tan acoplados quedan los módulos.

## Decisión

1. **CLI por fases:** `core_pipeline.py` expone comandos por fase. n8n los invoca en
   secuencia, lee los manifiestos intermedios y hace el enrutamiento condicional.
2. **n8n invoca a P2 por separado:** n8n ejecuta `core_vision.py` (P2) como su propio
   nodo `Execute Command`, y luego las fases de P3. P3 **no** invoca a P2 internamente.

Flujo resultante:

```
n8n Webhook (batch_id)
 1. Execute: python app/core_vision.py --batch BATCH-001            [P2]
      -> work/normalized/ + vision_manifest.json
 2. Execute: python -m app.core_pipeline crops-classify --batch ... [P3]
      -> work/crops/ + crop_manifest.json + bubble_predictions.json
 3. Switch por ficha (vision_manifest.status): OK -> sigue | ERROR -> observaciones
 4. Execute: python -m app.core_pipeline score --batch BATCH-001    [P3]
      -> recognition_output.json + resultados.json
```

## Consecuencias

**Positivas**
- Orquestación visible en n8n (fiel al espíritu del contrato 04) y buena para la
  defensa.
- Respeta la separación de responsabilidades P2/P3.
- Fases depurables y reejecutables de forma independiente.

**Negativas / trade-offs**
- Más superficie de CLI y más manifiestos intermedios que mantener y validar.
- n8n debe conocer el orden de fases y las rutas de artefactos.

## Alternativas consideradas

- **Comando end-to-end único:** más simple, pero n8n "se ve" solo como disparador y
  se pierde visibilidad de la orquestación. Descartada.
- **P3 invoca a P2 internamente:** menos nodos en n8n, pero acopla P2 dentro de P3 y
  contradice el contrato de responsabilidades. Descartada.
