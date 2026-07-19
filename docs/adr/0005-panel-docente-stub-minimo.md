# ADR-0005: Panel docente (P4) como stub mínimo

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

El panel docente, la validación temprana del ZIP y la generación de reportes/salidas
corresponden a P4, que **es responsabilidad de otra integrante del equipo**. Nuestro
alcance es la integración completa (P3 + n8n + contenerización). Sin embargo, para que
la integración quede demostrable de punta a punta, hace falta un punto de entrada que
cierre el ciclo.

## Decisión

Entregar un **stub mínimo de Flask** (`panel_docente/main.py`) que cierra el ciclo:

```
subir ZIP -> validación fail-fast de estructura -> POST al webhook de n8n -> descargar resultados
```

El stub deja **TODOs explícitos** donde la compañera construye la UI real, la
validación completa de CSV y los reportes (`resultados.xlsx`,
`reporte_observaciones_y_errores.xlsx`, imágenes anotadas, sitio de consulta).

No construimos el panel completo ni los reportes.

## Consecuencias

**Positivas**
- Integración demostrable end-to-end sin invadir el trabajo de P4.
- La compañera parte de un esqueleto funcional y de un contrato claro
  (`resultados.json`) en lugar de una hoja en blanco.

**Negativas / trade-offs**
- El stub no valida CSV a fondo ni genera reportes; son responsabilidad de P4.

## Alternativas consideradas

- **Solo contrato + README, sin código:** menos útil como punto de partida y no cierra
  el ciclo para la demo. Descartada.
- **Stub más completo con reportes básicos:** invade territorio de P4 y consume tiempo
  nuestro fuera de alcance. Descartada.
