# Reglas de interpretación y calificación de respuestas

## Propósito

Este documento define cómo ScanExam convierte las predicciones individuales de burbujas en respuestas interpretadas, respuestas aceptadas y puntajes por pregunta.

La CNN clasifica burbujas individuales.  
El motor de integración agrupa esas predicciones por pregunta, interpreta la marca visual, decide si existe una respuesta aceptable y calcula el puntaje cuando la ficha está en estado `OK`.

Este documento no define el entrenamiento de la CNN ni la detección de la ficha completa. Solo define cómo deben interpretarse las predicciones ya generadas para cada burbuja.

---

## Decisión de diseño

Para esta versión, ScanExam adopta un enfoque determinista y directo de interpretación/calificación.

No se implementa un motor de reglas dinámico ni una capa adicional de estados intermedios innecesarios.

La razón es que el alcance actual del sistema es cerrado:

```text
- una plantilla oficial;
- 10 preguntas;
- alternativas A, B, C, D y E;
- tipos de examen A y B;
- reglas de calificación estáticas.
```

Por tanto, la prioridad es mantener reglas claras, implementables y fáciles de integrar por P3.

La interpretación de respuestas debe ser simple:

```text
predicciones de burbujas
→ interpretación visual por pregunta
→ accepted_answer
→ comparación con clave
→ puntaje
```

---

## Relación con el clasificador

El clasificador recibe crops individuales y devuelve predicciones por burbuja.

Ejemplo:

```json
{
  "crop_id": "ficha_001_q01_A",
  "predicted_class": "MARKED",
  "confidence": 0.94
}
```

Valores posibles de `predicted_class`:

```text
EMPTY
MARKED
GHOST
```

El clasificador no calcula puntaje, no decide si una pregunta es correcta y no determina el estado final de la ficha.

El clasificador solo responde:

```text
Esta burbuja está vacía, marcada o tiene una marca residual/dudosa.
```

---

## Definición de clases visuales

### `EMPTY`

La burbuja está visualmente vacía.

Interpretación:

```text
No hay evidencia suficiente de que el estudiante haya marcado esa alternativa.
```

Ejemplo:

```text
La burbuja se ve blanca o prácticamente limpia.
```

---

### `MARKED`

La burbuja está marcada de forma fuerte y clara.

Interpretación:

```text
El estudiante seleccionó esa alternativa.
```

En términos visuales, corresponde a una marca oscura, intensa y consistente con el lápiz 2B exigido por el sistema.

Ejemplo:

```text
La burbuja se ve claramente rellenada o marcada con suficiente intensidad.
```

---

### `GHOST`

La burbuja contiene una marca residual, tenue o grisácea.

Interpretación:

```text
La burbuja no está completamente vacía, pero tampoco alcanza el nivel de una marca fuerte.
```

En términos prácticos, `GHOST` representa un borrón, una marca parcialmente borrada o una señal visual residual. Puede corresponder a una alternativa que el estudiante marcó antes y luego corrigió.

Visualmente:

```text
EMPTY  = burbuja blanca o limpia
GHOST  = burbuja gris, tenue o con borrón residual
MARKED = burbuja negra, fuerte e intensa
```

`GHOST` no equivale a `MARKED`.

Regla conceptual:

```text
GHOST no compite contra MARKED.
GHOST solo domina cuando no existe ningún MARKED en la pregunta.
```

Esto permite que el estudiante pueda corregir marcas sin que un borrón residual genere un falso positivo de MARKED lo que causaria la anulación de esa pregunta debido a una DOUBLE_MARK. De hecho ese es el motivo principal de la introducción de GHOST, el permitir al sisterma ser más realista respecto al proceso normal de desarrollo de un examen y que no se cierre a solo se marca cuando existe un confianza completa en lo que se marca, caso que daria si solo exisiteran MARKED y EMPTY. 

---

## Relación con estados de ficha

Una ficha puede terminar con uno de estos estados generales:

```text
OK
OBSERVED
ERROR
```

La calificación solo se aplica cuando:

```text
processing_status = OK
```

Si la ficha queda como `OBSERVED` o `ERROR`, no se genera una nota automática publicable.

```text
OBSERVED → score = null, publishable = false
ERROR    → score = null, publishable = false
```

Las preguntas en blanco, con doble marca o con solo borrones no convierten por sí mismas una ficha en `OBSERVED` ni en `ERROR`.

Solo afectan el puntaje de la pregunta correspondiente.

---

## Campos usados por pregunta

Para cada pregunta, ScanExam debe producir los siguientes campos durante la interpretación:

```text
question_id
detected_answer
accepted_answer
mark_status
confidence
```

Luego, durante la calificación, se agregan:

```text
correct_answer
question_status
points
earned_points
```

---

## `detected_answer`

Representa la respuesta detectada visualmente como marca válida o como conjunto de marcas fuertes.

Puede ser:

```text
"A"
"B"
"C"
"D"
"E"
["B", "C"]
null
```

Reglas:

```text
Si hay una sola marca fuerte:
detected_answer = opción MARKED

Si hay dos o más marcas fuertes:
detected_answer = lista de opciones MARKED

Si no hay MARKED y solo hay GHOST/EMPTY:
detected_answer = null

Si todo está EMPTY:
detected_answer = null
```

Importante:

```text
GHOST no se registra como detected_answer.
```

La razón es que `detected_answer` representa una respuesta visualmente válida o un conjunto de marcas fuertes.  
Un `GHOST` es un borrón residual, no una respuesta válida.

---

## `accepted_answer`

Representa la respuesta que el sistema acepta para calificación.

Puede ser:

```text
"A"
"B"
"C"
"D"
"E"
null
```

Regla central:

```text
Solo existe accepted_answer cuando hay una única alternativa MARKED.
```

Si la pregunta está en blanco, tiene doble marca o solo contiene borrones `GHOST`, entonces:

```text
accepted_answer = null
```

---

## `mark_status`

Describe el estado visual de la marca en la pregunta.

Valores permitidos:

```text
SINGLE_MARK
BLANK
DOUBLE_MARK
UNCERTAIN
```

### `SINGLE_MARK`

Existe exactamente una alternativa `MARKED`.

La pregunta tiene una respuesta aceptable.

```text
MARKED = 1
→ mark_status = SINGLE_MARK
→ accepted_answer = opción MARKED
```

Los `GHOST`, si existen, no invalidan la respuesta.

---

### `BLANK`

No existe ninguna alternativa `MARKED` ni `GHOST`.

La pregunta está vacía.

```text
MARKED = 0
GHOST = 0
→ mark_status = BLANK
→ accepted_answer = null
```

---

### `DOUBLE_MARK`

Existen dos o más alternativas `MARKED`.

La pregunta tiene más de una marca fuerte.

```text
MARKED >= 2
→ mark_status = DOUBLE_MARK
→ accepted_answer = null
```

Los `GHOST`, si existen, se ignoran para determinar la doble marca.  
La doble marca depende únicamente de la cantidad de alternativas `MARKED`.

---

### `UNCERTAIN`

No existe ninguna alternativa `MARKED`, pero sí existe una o más alternativas `GHOST`.

La pregunta no está vacía del todo, pero tampoco tiene una marca válida.

```text
MARKED = 0
GHOST >= 1
→ mark_status = UNCERTAIN
→ accepted_answer = null
```

Interpretación:

```text
No se detectó una marca válida. Solo se detectaron uno o más borrones o marcas residuales.
```

---

## `question_status`

Describe el resultado académico de la pregunta después de comparar contra la clave.

Valores permitidos:

```text
CORRECT
INCORRECT
BLANK
DOUBLE_MARK
UNCERTAIN
```

`question_status` se calcula después de conocer:

```text
accepted_answer
correct_answer
mark_status
points
```

---

## Regla principal de interpretación visual

Para cada pregunta, P3 agrupa las predicciones de sus alternativas y cuenta:

```text
MARKED = número de alternativas clasificadas como MARKED
GHOST = número de alternativas clasificadas como GHOST
```

La regla se aplica en este orden:

```text
1. Si MARKED >= 2 → DOUBLE_MARK
2. Si MARKED = 1  → SINGLE_MARK
3. Si MARKED = 0 y GHOST >= 1 → UNCERTAIN
4. Si MARKED = 0 y GHOST = 0 → BLANK
```

Este orden es importante porque `MARKED` tiene prioridad sobre `GHOST`.

---

## Regla de oro para `GHOST`

La regla de oro es:

```text
MARKED manda.
GHOST advierte.
Solo GHOST no responde.
Dos o más MARKED invalidan.
```

Formalmente:

```text
MARKED = 1 y GHOST >= 1
→ se acepta la alternativa MARKED
→ los GHOST se ignoran para la calificación

MARKED = 0 y GHOST >= 1
→ no existe marca válida
→ mark_status = UNCERTAIN
→ accepted_answer = null
```

Esta decisión permite que el estudiante pueda corregir una marca sin que cualquier borrón residual anule automáticamente su respuesta.

---

## Caso 1: una única marca fuerte

Condición:

```text
MARKED = 1
```

Decisión:

```text
mark_status = SINGLE_MARK
detected_answer = opción MARKED
accepted_answer = opción MARKED
```

Los `GHOST`, si existen, se ignoran para la calificación.

Ejemplo con borrón residual:

```text
A = EMPTY
B = MARKED
C = GHOST
D = EMPTY
E = EMPTY
```

Salida:

```json
{
  "question_id": 1,
  "detected_answer": "B",
  "accepted_answer": "B",
  "mark_status": "SINGLE_MARK",
  "confidence": 0.94
}
```

Interpretación:

```text
El estudiante marcó B de forma clara. El rastro en C se considera un borrón o corrección previa, pero no compite contra la marca fuerte.
```

---

## Caso 2: ninguna marca

Condición:

```text
MARKED = 0
GHOST = 0
```

Decisión:

```text
mark_status = BLANK
detected_answer = null
accepted_answer = null
```

Ejemplo:

```text
A = EMPTY
B = EMPTY
C = EMPTY
D = EMPTY
E = EMPTY
```

Salida:

```json
{
  "question_id": 2,
  "detected_answer": null,
  "accepted_answer": null,
  "mark_status": "BLANK",
  "confidence": null
}
```

Interpretación:

```text
El estudiante no marcó ninguna alternativa.
```

---

## Caso 3: doble marca

Condición:

```text
MARKED >= 2
```

Decisión:

```text
mark_status = DOUBLE_MARK
detected_answer = lista de opciones MARKED
accepted_answer = null
```

Los `GHOST`, si existen, se ignoran para determinar la doble marca.  
La doble marca depende únicamente de la cantidad de alternativas `MARKED`.

Ejemplo:

```text
A = EMPTY
B = MARKED
C = MARKED
D = EMPTY
E = GHOST
```

Salida:

```json
{
  "question_id": 3,
  "detected_answer": ["B", "C"],
  "accepted_answer": null,
  "mark_status": "DOUBLE_MARK",
  "confidence": 0.88
}
```

Interpretación:

```text
El estudiante marcó dos alternativas de forma fuerte. La pregunta no tiene una respuesta aceptada.
```

---

## Caso 4: solo borrones o marcas residuales

Condición:

```text
MARKED = 0
GHOST >= 1
```

Decisión:

```text
mark_status = UNCERTAIN
detected_answer = null
accepted_answer = null
```

Ejemplo:

```text
A = EMPTY
B = GHOST
C = EMPTY
D = EMPTY
E = EMPTY
```

Salida:

```json
{
  "question_id": 4,
  "detected_answer": null,
  "accepted_answer": null,
  "mark_status": "UNCERTAIN",
  "confidence": 0.62
}
```

Interpretación:

```text
No se detectó una marca válida. Solo se detectaron uno o más borrones o marcas residuales.
```

Mensaje sugerido para UI docente:

```text
No se detectó una marca válida, solo uno o más borrones. Por eso no se asignó puntaje a la pregunta. Apelar al docente si cree que se trata de un error.
```

---

## Reglas de calificación

La calificación se aplica únicamente si la ficha tiene:

```text
processing_status = OK
```

Para cada pregunta, se compara `accepted_answer` contra `correct_answer`.

---

### Pregunta correcta

Condición:

```text
accepted_answer = correct_answer
```

Decisión:

```text
question_status = CORRECT
earned_points = points
```

Ejemplo:

```json
{
  "question_id": 1,
  "detected_answer": "B",
  "accepted_answer": "B",
  "correct_answer": "B",
  "question_status": "CORRECT",
  "points": 2,
  "earned_points": 2,
  "confidence": 0.94
}
```

---

### Pregunta incorrecta

Condición:

```text
accepted_answer != null
accepted_answer != correct_answer
```

Decisión:

```text
question_status = INCORRECT
earned_points = 0
```

Ejemplo:

```json
{
  "question_id": 2,
  "detected_answer": "C",
  "accepted_answer": "C",
  "correct_answer": "A",
  "question_status": "INCORRECT",
  "points": 2,
  "earned_points": 0,
  "confidence": 0.91
}
```

---

### Pregunta en blanco

Condición:

```text
mark_status = BLANK
```

Decisión:

```text
question_status = BLANK
earned_points = 0
```

Ejemplo:

```json
{
  "question_id": 3,
  "detected_answer": null,
  "accepted_answer": null,
  "correct_answer": "D",
  "question_status": "BLANK",
  "points": 2,
  "earned_points": 0,
  "confidence": null
}
```

---

### Pregunta con doble marca

Condición:

```text
mark_status = DOUBLE_MARK
```

Decisión:

```text
question_status = DOUBLE_MARK
earned_points = 0
```

Ejemplo:

```json
{
  "question_id": 4,
  "detected_answer": ["B", "C"],
  "accepted_answer": null,
  "correct_answer": "B",
  "question_status": "DOUBLE_MARK",
  "points": 2,
  "earned_points": 0,
  "confidence": 0.88
}
```

---

### Pregunta dudosa por borrón

Condición:

```text
mark_status = UNCERTAIN
```

Decisión:

```text
question_status = UNCERTAIN
earned_points = 0
```

Ejemplo:

```json
{
  "question_id": 5,
  "detected_answer": null,
  "accepted_answer": null,
  "correct_answer": "D",
  "question_status": "UNCERTAIN",
  "points": 2,
  "earned_points": 0,
  "confidence": 0.62
}
```

---

## `recognition_output.json`

`recognition_output.json` representa la salida interpretada de la ficha antes de consolidar el resultado final publicable.

No debe ser un reporte final de nota.  
Su propósito es registrar qué detectó y qué aceptó el sistema.

Ejemplo:

```json
{
  "file": "ficha_001.png",
  "quality_status": "OK",
  "student_code": {
    "value": "20240001",
    "confidence": 0.97
  },
  "exam_type": {
    "value": "A",
    "confidence": 0.99
  },
  "questions": [
    {
      "question_id": 1,
      "detected_answer": "B",
      "accepted_answer": "B",
      "mark_status": "SINGLE_MARK",
      "confidence": 0.94
    },
    {
      "question_id": 2,
      "detected_answer": ["C", "D"],
      "accepted_answer": null,
      "mark_status": "DOUBLE_MARK",
      "confidence": 0.86
    },
    {
      "question_id": 3,
      "detected_answer": null,
      "accepted_answer": null,
      "mark_status": "BLANK",
      "confidence": null
    },
    {
      "question_id": 4,
      "detected_answer": null,
      "accepted_answer": null,
      "mark_status": "UNCERTAIN",
      "confidence": 0.62
    }
  ]
}
```

---

## `resultados.json`

`resultados.json` representa la salida final del lote.

Aquí sí se incluye:

```text
processing_status
publishable
student_name
email
correct_answer
question_status
points
earned_points
score
max_score
percentage
processing_message
```

Ejemplo de pregunta dentro de `resultados.json`:

```json
{
  "question_id": 1,
  "detected_answer": "B",
  "accepted_answer": "B",
  "correct_answer": "B",
  "question_status": "CORRECT",
  "points": 2,
  "earned_points": 2,
  "confidence": 0.94
}
```

Ejemplo completo simplificado:

```json
{
  "file": "ficha_001.png",
  "processing_status": "OK",
  "quality_status": "OK",
  "publishable": true,
  "student_code": {
    "value": "20240001",
    "confidence": 0.97
  },
  "student_name": "Pedro Sota",
  "email": "pedro.sota@gmail.com",
  "exam_type": "A",
  "score": 2,
  "max_score": 4,
  "percentage": 50,
  "issue_code": null,
  "processing_message": "Ficha procesada correctamente.",
  "answers": [
    {
      "question_id": 1,
      "detected_answer": "B",
      "accepted_answer": "B",
      "correct_answer": "B",
      "question_status": "CORRECT",
      "points": 2,
      "earned_points": 2,
      "confidence": 0.94
    },
    {
      "question_id": 2,
      "detected_answer": null,
      "accepted_answer": null,
      "correct_answer": "D",
      "question_status": "UNCERTAIN",
      "points": 2,
      "earned_points": 0,
      "confidence": 0.62
    }
  ]
}
```

---

## Regla de publicación

Solo se publican resultados cuando:

```text
processing_status = OK
publishable = true
```

Las fichas `OBSERVED` y `ERROR` no se publican automáticamente.

---

## Reglas finales

1. El clasificador solo clasifica burbujas.
2. La interpretación agrupa burbujas por pregunta y define `detected_answer`, `accepted_answer` y `mark_status`.
3. La calificación solo se aplica si `processing_status = OK`.
4. Una única alternativa `MARKED` siempre se acepta como respuesta, incluso si existen alternativas `GHOST`.
5. Dos o más alternativas `MARKED` generan `DOUBLE_MARK`.
6. Si no existe ninguna alternativa `MARKED`, pero sí una o más `GHOST`, la pregunta queda como `UNCERTAIN`.
7. Si todas las alternativas son `EMPTY`, la pregunta queda como `BLANK`.
8. `GHOST` no compite contra `MARKED`; solo indica borrón o marca residual.
9. `GHOST` no se registra como `detected_answer`.
10. Si `accepted_answer` coincide con `correct_answer`, la pregunta obtiene sus puntos.
11. Si `accepted_answer` es incorrecta, nula, doble o dudosa, la pregunta obtiene 0 puntos.
12. `BLANK`, `DOUBLE_MARK` y `UNCERTAIN` no convierten la ficha en `OBSERVED` ni en `ERROR`.
13. `OBSERVED` queda reservado para problemas de identificación del estudiante.
14. `ERROR` queda reservado para problemas técnicos, visuales o de plantilla.
15. Para el mismo conjunto de predicciones, el sistema debe producir siempre el mismo resultado.