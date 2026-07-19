# ADR-0001: Motor de reglas y scoring en Python (no en n8n)

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

Existe una tensión entre dos contratos del proyecto:

- `docs/informacion_relevante_entre_modulos/04_n8n_orchestration_contract.md` plantea
  que n8n sea el "motor de reglas inteligentes" y que la interpretación de burbujas
  y el scoring se ejecuten en nodos `Code` (JavaScript) dentro de n8n.
- `docs/informacion_relevante_entre_modulos/01_batch_contract.md` y las reglas de
  interpretación indican que P3 (Python) genera `resultados.json` y aplica el scoring.

El scoring es el activo crítico del sistema: **determina la nota de un estudiante**.
La regla 15 del contrato de interpretación exige determinismo (mismo input → mismo
output). Además existe un requisito académico de "incorporar al menos un mecanismo
de decisión inteligente en el orquestador".

## Decisión

**La lógica de negocio (interpretación + scoring) vive en Python**, en un módulo
`app/scoring_engine.py` que es la **única fuente de verdad**, con pruebas unitarias
(`pytest`). n8n **no** contiene lógica de calificación.

El requisito de "orquestador inteligente" se cumple de forma honesta mediante el
**enrutamiento condicional por estado de ficha** en n8n (`Switch`/`IF` sobre
`OK`/`OBSERVED`/`ERROR`): Python decide *el contenido*, n8n decide *el camino*.

## Consecuencias

**Positivas**
- Testeable: cada regla se cubre con `pytest` (imposible en un nodo `Code` de n8n).
- Reproducible y auditable: determinista y versionado línea a línea en Git.
- Separación de responsabilidades: el orquestador coordina; no es dueño del dominio.

**Negativas / trade-offs**
- Contradice la letra del contrato 04 (se documenta explícitamente aquí).
- n8n "se ve" menos como motor de reglas en la demo; se compensa mostrando el
  enrutamiento condicional como decisión inteligente real del orquestador.

## Alternativas consideradas

- **Todo en nodos n8n (JS):** más fiel al contrato 04, pero frágil, no testeable
  unitariamente y con la lógica crítica enterrada en un JSON exportado. Descartada.
- **Híbrido literal** (Python solo predice; n8n interpreta y califica): concentra el
  riesgo en JavaScript no testeado. Descartada.
