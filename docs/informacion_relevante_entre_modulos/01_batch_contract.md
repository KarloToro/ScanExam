# Contrato de estructura interna de BATCH

## Propósito

Este documento define la estructura interna que debe usar ScanExam para procesar un lote de fichas. Un `BATCH` representa una subida completa realizada por el docente, no una ficha individual.

Si el docente sube un ZIP con 30 fichas, el sistema crea un solo `BATCH` con 30 imágenes dentro.

```text
1 ZIP válido = 1 BATCH
30 fichas dentro del ZIP = 30 archivos dentro del mismo BATCH
```

## Regla de estabilidad

La estructura definida en este documento funciona como contrato entre módulos.
P2, P3 y P4 deben asumir estos nombres de carpetas y archivos para integrarse correctamente.

Se pueden proponer cambios, pero solo deben aceptarse si existe un motivo técnico sólido. Cualquier cambio aceptado debe comunicarse al equipo, porque puede requerir ajustes en varios módulos.

## Estructura definida

```text
BATCH-001/
├── input/
│   ├── ficha_001.jpg
│   ├── ficha_002.jpg
│   ├── ...
│   └── ficha_030.jpg
├── config/
│   ├── estudiantes_matriculados.csv
│   └── claves_parcial_2026_01.csv
├── work/
│   ├── normalized/
│   │   ├── ficha_001.png
│   │   ├── ficha_002.png
│   │   ├── ...
│   │   └── ficha_030.png
│   ├── vision_manifest.json
│   └── crops/
│       ├── ficha_001_q_01_A.png
│       ├── ficha_001_q_01_B.png
│       ├── ...
│       └── ...
└── output/
    ├── resultados.json
    ├── resultados.xlsx
    ├── reporte_observaciones_y_errores.xlsx
    └── imagenes_anotadas/
```

## Significado de cada carpeta

### `input/`

Contiene las fichas originales tal como fueron subidas por el docente.
Estas imágenes no deben sobrescribirse.

Formatos aceptados:

```text
.jpg
.jpeg
.png
```

### `config/`

Contiene los archivos CSV del lote.

```text
estudiantes_matriculados.csv
claves_parcial_2026_01.csv
```

En la carga inicial, los archivos dentro de `Estudiantes/` y `Respuestas/` pueden tener cualquier nombre. Sin embargo, una vez aceptado el lote, el sistema puede normalizarlos internamente a nombres estables dentro de `config/`.

### `work/`

Contiene archivos intermedios del procesamiento.
No representa la salida final para el docente.

### `work/normalized/`

Contiene las fichas canonizadas por P2.

Cada ficha válida visualmente debe generar una imagen PNG canónica:

```text
work/normalized/ficha_001.png
```

Estas imágenes deben cumplir:

```text
orientación landscape
marcador distintivo en top_right
tamaño 2100 x 1480 px
```

### `work/vision_manifest.json`

Archivo generado por P2 con el resultado visual de cada ficha.

Debe indicar, como mínimo:

```json
{
  "file": "ficha_001.jpg",
  "status": "OK",
  "canonical_path": "work/normalized/ficha_001.png",
  "issue_code": null,
  "quality_metrics": null
}
```

Si la ficha falla por `LOW_CONFIDENCE`, puede incluir métricas de calidad:

```json
{
  "file": "ficha_014.jpg",
  "status": "ERROR",
  "canonical_path": null,
  "issue_code": "LOW_CONFIDENCE",
  "quality_metrics": {
    "blur_score": 32.8,
    "brightness": 41.2,
    "black_ratio": 0.18
  }
}
```

### `work/crops/`

Contiene los recortes generados por P3 a partir de las fichas canonizadas y de las coordenadas definidas en la plantilla.

Ejemplo:

```text
ficha_001_q_01_A.png
ficha_001_q_01_B.png
```

P2 no está obligado a crear esta carpeta.
P3 es responsable de generar los crops y construir el manifiesto correspondiente.

### `output/`

Contiene la salida final del lote.

Archivos esperados:

```text
resultados.json
resultados.xlsx
reporte_observaciones_y_errores.xlsx
imagenes_anotadas/
```

Estos artefactos son consumidos por la plataforma docente y pueden formar parte del ZIP final descargable.

## Responsabilidades por módulo

| Elemento                                  | Responsable              |
| ----------------------------------------- | ------------------------ |
| Validar ZIP y CSV                         | P4                       |
| Crear contexto general del BATCH          | P3 / core_pipeline       |
| Guardar fichas originales en `input/`     | P3 / core_pipeline       |
| Guardar CSV en `config/`                  | P3 / core_pipeline       |
| Generar `work/normalized/`                | P2                       |
| Generar `work/vision_manifest.json`       | P2                       |
| Generar `work/crops/`                     | P3                       |
| Ejecutar clasificador de burbujas         | P3 usando contrato de P1 |
| Generar resultados y reportes             | P3                       |
| Mostrar y permitir descarga de resultados | P4                       |

## Uso de `output_root` en P2

P2 no debe depender directamente del nombre `BATCH-001`.

La función principal de P2 debe recibir una carpeta base de salida, por ejemplo:

```text
batches/BATCH-001/work/
```

A esa carpeta se le llamará `output_root`.

Dentro de `output_root`, P2 debe crear o actualizar:

```text
normalized/
vision_manifest.json
```

Ejemplo:

```text
output_root = batches/BATCH-001/work/
```

Resultado esperado:

```text
batches/BATCH-001/work/normalized/ficha_001.png
batches/BATCH-001/work/vision_manifest.json
```

Durante desarrollo, P2 puede usar otra ruta:

```text
data/lotes_prueba/p2_test/work/
```

La lógica debe ser la misma. Solo cambia la carpeta base recibida.

## Regla final

El contrato de carpetas debe mantenerse estable para evitar adaptaciones manuales entre módulos.
Cualquier cambio debe tener una justificación técnica clara y coordinarse con todo el equipo antes de modificar código.
