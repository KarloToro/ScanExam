## Propósito

Este documento define el contrato de entrada y salida del clasificador de burbujas de ScanExam.

El clasificador tiene una responsabilidad limitada: recibir un crop de una burbuja y predecir si esa burbuja está marcada, vacía o dudosa.

La CNN no decide respuestas finales, identificación de estudiantes ni calificación. Esas decisiones pertenecen al módulo de integración e interpretación.

## Responsables

|Elemento|Responsable|
|---|---|
|Entrenamiento del clasificador|P1|
|Definición de clases|P1|
|Generación de crops|P3|
|Llamada al clasificador|P3|
|Interpretación de varias burbujas como respuesta|P3 según reglas de P1|
|Calificación final|P3|

## Entrada esperada

El clasificador recibe un crop individual correspondiente a una burbuja.

El crop debe provenir de una ficha previamente canonizada.

Flujo esperado:

```text
ficha original
→ ficha canonizada
→ crop de burbuja
→ clasificador CNN
→ predicción de burbuja
```

El crop puede corresponder a:

- una burbuja de respuestas;
    
- una burbuja de identificación.
    

## Requisitos del crop

Cada crop debe cumplir:

```text
- provenir de una imagen canonizada;
- estar centrado en una burbuja;
- tener tamaño definido por template_config.json;
- contener una sola burbuja principal;
```

El preprocesamiento interno necesario para la CNN, como redimensionamiento, normalización o conversión a escala de grises, pertenece al clasificador.

## Identificador del crop

Cada crop debe tener un identificador único.

La regla que se sigue para su construcción es:

crop_id = ficha_id + "\_" + bubble_id_base

Ejemplos
1. Para respuesta:

``` text
	ficha_id = ficha_001
	bubble_id_base = q_01_A
	crop_id = ficha_001_q_01_A
```

2. Para identificación:

``` text
	ficha_id = ficha_001
	bubble_id_base = id_c08_v0
	crop_id = ficha_001_id_c08_v0
```

El `crop_id` permite que P3 relacione la predicción del modelo con la pregunta, alternativa o campo de identificación correspondiente.

## Clases de salida

El clasificador predice una de las siguientes clases:

```text
EMPTY
MARKED
GHOST
```

## `EMPTY`

Indica que la burbuja se interpreta como vacía.

Uso esperado:

```text
La burbuja no fue marcada por el estudiante.
```

## `MARKED`

Indica que la burbuja se interpreta como marcada.

Uso esperado:

```text
La burbuja fue seleccionada por el estudiante.
```

## `GHOST`

Indica una marca dudosa, ruido visual o evidencia insuficiente para considerarla una marca fuerte.

Ejemplos posibles:

```text
- marca muy tenue;
- borrón;
- sombra;
- trazo parcial;
- suciedad;
- interferencia visual.
```

`GHOST` no equivale a `MARKED` y necesita pasar por las reglas de interpretación para entenderse según el contexto de la pregunta a la que pertenece. De esta manera se garantiza que el sistema es coherente en su método de calificación e interpretación.

## Salida esperada por crop

El clasificador devuelve esta estructura:

```json
{
  "crop_id": "ficha_001_q_01_A",
  "predicted_class": "MARKED",
  "confidence": 0.94
}
```
## Campos de salida

### `crop_id`

Identificador del crop evaluado.

Debe coincidir con el identificador definido en la sección [Identificador del crop](#identificador-del-crop).

### `predicted_class`

Clase predicha por el clasificador.

Valores permitidos:

```text
EMPTY
MARKED
GHOST
```

### `confidence`

Valor numérico entre `0` y `1` que representa la confianza del modelo en la clase predicha.

Ejemplo:

```text
0.94 = alta confianza
0.51 = baja confianza relativa
```

La confianza no decide por sí sola la respuesta final. Debe ser interpretada junto con las reglas de respuesta.

## Salida esperada por ficha

P3 debe agrupar las predicciones de todos los crops de una ficha en el archivo `bubble_predictions.json`.

Ejemplo:

```json
{
  "file": "ficha_001.png",
  "template_id": "ficha_optica_a5_horizontal_v1",
  "predictions": [
    {
      "crop_id": "ficha_001_q_01_A",
      "predicted_class": "MARKED",
      "confidence": 0.94
    },
    {
      "crop_id": "ficha_001_q_01_B",
      "predicted_class": "EMPTY",
      "confidence": 0.91
    }
  ]
}
```

## Qué no decide el clasificador

El clasificador no decide:

```text
- si la pregunta está correcta;
- si una pregunta tiene doble marca;
- si una pregunta queda en blanco;
- el processing_status de la ficha
- si el estudiante existe en el CSV;
- si la nota es publicable;
- el puntaje final del examen.
```

Estas decisiones ocurren después, en el módulo de interpretación e integración.

## Relación con P3

P3 debe:

```text
1. Generar los crops desde la ficha canonizada.
2. Llamar al clasificador para cada crop.
3. Recibir predicted_class y confidence.
4. Agrupar las predicciones.
5. Aplicar las reglas de interpretación.
6. Reconstruir respuestas e identificación.
```

## Regla de estabilidad

Este contrato debe mantenerse estable durante la integración.

Si se cambia el nombre de una clase, el formato de salida o el significado de `confidence`, P3 debe ser informado antes de adaptar código.

