# ADR-0008: Reconstrucción del código de estudiante e identificación

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

El Anexo D del flujo define *cuándo* una ficha queda `OBSERVED` por identidad
(código no reconstruible, baja confianza, no encontrado, duplicado), pero **no
define cómo** reconstruir el código de 8 dígitos a partir de las burbujas de
identificación (8 columnas × 10 valores, orden de lectura `c08_to_c01`), ni cómo
calcular su confianza. El scoring necesita reglas deterministas.

## Decisión

1. **Reutilizar el motor de reglas por columna.** Cada columna se interpreta con
   `scoring_engine.interpret_question` (opciones = v0..v9), obteniendo su
   `mark_status`, dígito aceptado y confianza con la misma lógica y regla de oro
   GHOST ya adoptadas (ADR-0007). No se duplican reglas.

2. **Reconstrucción estricta.** Se exige `SINGLE_MARK` en **las 8 columnas**. Si
   alguna queda `BLANK`, `DOUBLE_MARK` o `UNCERTAIN`, el código **no** se
   reconstruye → `OBSERVED` con `MISSING_STUDENT_CODE`.
   *Razón:* los códigos son de 8 dígitos (p. ej. `20240001`); una identidad
   incompleta o ambigua debe ir a revisión docente, que es el propósito de
   `OBSERVED`. Es la opción segura y determinista.

3. **Confianza del código = mínimo** de las confianzas por columna (eslabón más
   débil). Si es menor que `MIN_STUDENT_CODE_CONFIDENCE` (0.75) → `OBSERVED` con
   `LOW_STUDENT_CODE_CONFIDENCE`.

4. **Orden de lectura** `c08 -> c01` tomado de la plantilla (`reading_order`). El
   código se preserva como **string** (mantiene ceros a la izquierda).

5. **Precedencia de estados:** no-reconstruible → baja-confianza → no-encontrado.
   Si el código no es confiable, no se busca en `Estudiantes.csv`. El caso
   **duplicado** requiere visión global del lote y se resuelve en el *reduce* de
   `core_pipeline` (`DUPLICATED_STUDENT_CODE`), no por ficha.

## Consecuencias

**Positivas**
- Reglas simples, deterministas y testeadas (10 casos en `test_identity.py`).
- Máxima reutilización del motor de reglas; una sola fuente de verdad de marcas.

**Negativas / notas**
- Consecuencia de los umbrales actuales: como el clasificador fuerza `GHOST`
  cuando la confianza de un `MARKED` es < 0.80 (`MIN_CLASSIFICATION_CONFIDENCE`),
  una marca de baja confianza se vuelve `GHOST` y la columna deja de ser
  `SINGLE_MARK` → domina `MISSING_STUDENT_CODE` sobre
  `LOW_STUDENT_CODE_CONFIDENCE`. El chequeo de baja confianza queda como defensa
  por si esos umbrales cambian.
- Es una interpretación nuestra de un punto abierto del Anexo D; se comunica al
  equipo. Si en el futuro se admiten códigos de longitud variable, esta ADR debe
  revisarse.

## Alternativas consideradas

- **Reconstrucción tolerante** (saltar columnas en blanco y armar códigos de
  longitud variable): ambigua (un blanco intermedio vs. final) y propensa a
  falsos positivos de identidad. Descartada por seguridad.
