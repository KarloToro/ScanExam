# ADR-0007: Cálculo del `confidence` por pregunta

**Estado:** Propuesta
**Fecha:** 2026-07-19

## Contexto

El contrato `docs/informacion_relevante_entre_modulos/03_response_interpretation_rules.md`
incluye un campo `confidence` por pregunta (con valores de ejemplo 0.94, 0.88, 0.62 y
`null`) pero **no define cómo derivarlo** a partir de las confianzas por burbuja que
entrega la CNN. El scoring necesita una regla determinista y única (regla 15).

## Decisión (propuesta, pendiente de confirmación)

Agregar las confianzas por burbuja según el `mark_status`:

| `mark_status` | `confidence` de la pregunta |
| ------------- | --------------------------- |
| `SINGLE_MARK` | confianza de la única burbuja `MARKED` |
| `DOUBLE_MARK` | **mínimo** de las confianzas de las `MARKED` |
| `UNCERTAIN`   | **máximo** de las confianzas de las `GHOST` |
| `BLANK`       | `null` |

Razonamiento:
- `SINGLE_MARK`: el número relevante es la marca aceptada.
- `DOUBLE_MARK`: el `min` es conservador (refleja la peor de las marcas en conflicto).
- `UNCERTAIN`: el `max` refleja qué tan cerca estuvo un borrón de ser una marca.
- `BLANK`: no hay marcas, por lo que no hay confianza que reportar.

Los valores encajan con los ejemplos del documento de reglas.

## Consecuencias

**Positivas**
- Regla determinista y simple de implementar y testear.
- Coherente con los ejemplos existentes del contrato.

**Negativas / trade-offs**
- Es una interpretación nuestra de un punto que el contrato dejó abierto; debe
  confirmarse con el equipo antes de pasar el ADR a **Aceptada**.

## Alternativas consideradas

- **Promedio de confianzas en `DOUBLE_MARK`/`UNCERTAIN`:** suaviza pero diluye el caso
  peor/mejor; menos interpretable. Pendiente de discusión.
