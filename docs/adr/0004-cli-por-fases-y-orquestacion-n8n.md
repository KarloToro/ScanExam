# ADR-0004: CLI por fases de P3 y orquestación por n8n

**Estado:** Aceptada
**Fecha:** 2026-07-19
**Actualizada:** 2026-07-19 (modelo de invocación: Execute Command → HTTP; y P2
se invoca mediante una fase `run-vision` de P3 que delega en `process_batch`).

## Contexto

P3 debe exponerse a n8n para que este orqueste el pipeline. Había que definir la
**granularidad** del CLI (un comando end-to-end vs. comandos por fase), **cómo**
invoca n8n cada fase, y **quién** invoca a P2 (`core_vision.py`). Esto determina
cuánta orquestación es visible en n8n y qué tan acoplados quedan los módulos.

## Decisión

1. **CLI/fases por etapa:** `core_pipeline.py` expone las fases por separado
   (`build-batch`, `run-vision`, `crops-classify`, `score`), tanto como CLI como
   por HTTP. n8n las invoca en secuencia y hace el enrutamiento condicional.

2. **n8n invoca por HTTP, no por Execute Command:** `scanexam-app` corre una API
   Flask (`app/api.py`) que expone cada fase como endpoint. n8n usa nodos
   **HTTP Request** contra `http://scanexam-app:8000`. El contenedor de n8n es
   Node.js y no puede correr el Python del pipeline; HTTP desacopla n8n del
   runtime y permite que el panel P4 reutilice la **misma** API.

3. **P2 se invoca vía una fase `run-vision` de P3:** `core_vision.py` (P2) solo
   expone un CLI de depuración de una sola foto, no un entrypoint por lote. En
   lugar de modificar el archivo de P2, P3 añade la fase `run-vision`, que reúne
   `input/` y **delega en la función oficial de P2** (`process_batch`). Es glue
   de integración: P2 queda intacto y su lógica de visión sigue siendo suya.

Flujo resultante:

```
POST /webhook/scanexam  { batch_id, source }
 1. HTTP POST /pipeline/build-batch     -> BATCH-XXX/ (input, config, work, output)
 2. HTTP POST /pipeline/run-vision      [P3 -> P2.process_batch]
      -> work/normalized/ + vision_manifest.json
 3. HTTP POST /pipeline/crops-classify  [P3 + CNN]
      -> work/crops/ + crop_manifest.json + bubble_predictions.json
 4. HTTP POST /pipeline/score           [P3]
      -> recognition_output.json + resultados.json
 5. (siguiente iteración) Switch por ficha OK/OBSERVED/ERROR
 6. Respond to Webhook -> resultados.json
```

## Consecuencias

**Positivas**
- Orquestación visible en n8n (fiel al espíritu del contrato 04) y buena para la
  defensa; el enrutamiento por estado es la decisión "inteligente" del orquestador.
- HTTP desacopla n8n del runtime Python y **la misma API sirve a P4**.
- Imagen oficial de n8n sin modificar (no requiere docker-CLI ni el socket).
- Fases depurables y reejecutables de forma independiente.

**Negativas / trade-offs**
- `scanexam-app` debe estar levantado como servicio de larga vida.
- Más superficie (API + manifiestos intermedios) que mantener y validar.
- La fase `run-vision` introduce un acoplamiento controlado P3→P2 (glue), aceptado
  porque P2 no ofrece entrypoint por lote y no queremos tocar su archivo.

## Alternativas consideradas

- **Execute Command → `docker exec scanexam-app ...`:** fiel al texto del contrato
  04, pero exige imagen de n8n con docker-CLI y montar el socket de Docker (acopla
  n8n a Docker, con implicaciones de seguridad). Descartada frente a HTTP.
- **Comando end-to-end único:** más simple, pero n8n "se ve" solo como disparador y
  se pierde visibilidad de la orquestación. Descartada.
- **Modificar `core_vision.py` para un CLI `--batch`:** invadiría el archivo de P2.
  Se prefirió la fase `run-vision` de P3 como glue, dejando a P2 intacto.
