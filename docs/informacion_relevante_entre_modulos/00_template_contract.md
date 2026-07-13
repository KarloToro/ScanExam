## Propósito

Este documento define el contrato de plantilla usado por ScanExam para ubicar marcadores, identificación y respuestas dentro de una ficha óptica canonizada.

La plantilla es la referencia geométrica que conecta el trabajo de:

- **P1**: definición de plantilla, coordenadas y clasificador de burbujas.
    
- **P2**: canonización de la ficha a un tamaño y orientación estándar.
    
- **P3**: generación de crops, reconstrucción de respuestas e integración del pipeline.
    

## Template ID

```text
ficha_optica_a5_horizontal_v1
```

Este identificador representa la versión oficial de la plantilla usada en el proyecto.

## Tamaño canónico

Toda ficha procesada correctamente por P2 debe convertirse al siguiente tamaño:

```text
2100 x 1480 px
```

Donde:

```text
ancho = 2100 px
alto = 1480 px
```

## Orientación canónica

La ficha canonizada debe quedar en orientación:

```text
horizontal / landscape
```

Además, el marcador distintivo debe quedar ubicado en:

```text
top_right
```

Si P2 no puede garantizar esta orientación, la ficha no debe continuar al proceso de crops.

## Sistema de coordenadas

Las coordenadas de la plantilla usan el siguiente sistema:

```text
origen: esquina superior izquierda
eje X: crece hacia la derecha
eje Y: crece hacia abajo
unidad: píxeles
```

Ejemplo:

```json
[1276, 550]
```

significa:

```text
x = 1276 px
y = 550 px
```

## Regla crítica

Las coordenadas de la plantilla solo son válidas después de la canonización.

No deben aplicarse directamente sobre la foto original tomada por el docente.

Flujo correcto:

```text
foto original
→ canonización por P2
→ ficha canonizada 2100 x 1480 px
→ aplicación de coordenadas de plantilla
→ generación de crops por P3
```

## Archivos oficiales de plantilla

La plantilla se compone de los siguientes archivos:

```text
template_config.json
respuestas_centros.json
identificacion_centros.json
marcadores_centros.json
```

## `template_config.json`

Archivo principal de configuración de la plantilla.

Debe contener la información general necesaria para interpretar la ficha, como:

- `template_id`
    
- tamaño canónico
    
- orientación esperada
    
- tamaño de crop
    
- rutas o referencias a los archivos de centros
    

Este archivo funciona como punto de entrada para que P3 sepa qué configuración usar.

## `respuestas_centros.json`

Contiene las coordenadas centrales de las burbujas de respuestas.

Estas coordenadas son consumidas por P3 para generar los crops de respuestas.

Ejemplo conceptual:

```json
{
  "q01_A": [1276, 550],
  "q01_B": [1320, 550],
  "q01_C": [1364, 550],
  "q01_D": [1408, 550],
  "q01_E": [1452, 550]
}
```

## `identificacion_centros.json`

Contiene las coordenadas centrales de las burbujas usadas para reconstruir el código del estudiante u otros campos de identificación.

Estas coordenadas son consumidas por P3 después de recibir la ficha canonizada de P2.

## `marcadores_centros.json`

Contiene las coordenadas esperadas de los marcadores de referencia dentro de la plantilla canónica.

Sirve como referencia para validar que la ficha final quedó correctamente alineada.

P2 puede usar estos puntos como referencia para verificar la canonización, pero la detección inicial de marcadores ocurre sobre la imagen original.

## Evidencia visual

La plantilla debe contar con una evidencia visual de validación:

```text
validacion_centros_v1.png
```

Esta imagen debe mostrar que los centros definidos en los archivos JSON caen correctamente sobre la ficha canonizada (\*).

(\*) Nota: El 08/07/2026 ya fue verificada la correctitud de los centros definidos a la plantilla que corresponde a 
`data\plantilla\ficha_optica_a5_horizontal_v1\FICHA_OPTICA_V1.pdf`

## Responsabilidades

| Elemento                                    | Responsable |
| ------------------------------------------- | ----------- |
| Definir plantilla oficial                   | P1          |
| Mantener archivos JSON de centros           | P1          |
| Canonizar ficha al tamaño esperado          | P2          |
| Usar coordenadas para generar crops         | P3          |
| Validar visualmente centros sobre plantilla | P1          |
| Consumir crops para clasificador            | P1/P3       |

## Qué no define este contrato

Este documento no define:

- el flujo completo de carga ZIP;
    
- la estructura interna del `BATCH`;

Estos temas se documentan en contratos separados.

## Regla de cambios

La plantilla debe considerarse estable durante la integración.

Cualquier cambio en tamaño canónico, coordenadas, nombres de archivos o estructura de `template_config.json` debe tener una justificación técnica clara y coordinarse entre P1, P2 y P3 antes de adoptarse.