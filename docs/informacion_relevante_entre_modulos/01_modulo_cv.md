# 01 — Módulo de Visión por Computadora (P2)

Responsable: **P2**
Archivo: `app/core_vision.py`
Configuración asociada: `app/config.py` (sección "P2")

## 1. Qué hace este módulo

Transforma una foto cruda de una ficha óptica en una **imagen canónica**
(2100×1480px, landscape) lista para que P3 lea las burbujas usando
directamente los centros de `respuestas_centros.json` /
`identificacion_centros.json`, sin ninguna transformación adicional.

Corresponde al paso **"Canonizar ficha"** del diagrama de flujo general
(`docs/especificacion_flujo/00_procesamiento_lote_zip.md`).

## 2. Contratos públicos: `process_ficha()` y `process_batch()`

`process_ficha()` procesa **una** foto. `process_batch()` procesa una
lista de fotos y además escribe `vision_manifest.json` del lote
completo. `core_pipeline.py` normalmente solo necesita
`process_batch()`.

```python
from core_vision import process_batch

resultados = process_batch(
    paths=["input/ficha_001.jpg", "input/ficha_002.jpg", ...],
    output_root="batches/BATCH-001/work",  # P2 no conoce BATCH-001/, solo escribe dentro de esta carpeta
)
```

Esto genera:

```text
batches/BATCH-001/work/
├── normalized/
│   ├── ficha_001.png
│   └── ficha_002.png
└── vision_manifest.json
```

Si se necesita procesar una ficha a la vez (por ejemplo, para
reintentar una sola sin rehacer el lote completo):

```python
from core_vision import process_ficha

resultado = process_ficha(ruta_o_imagen, output_root="batches/BATCH-001/work")

if resultado.status == "ERROR":
    # mover la foto original a rechazadas/, registrar issue_code
    ...
else:
    # resultado.canonical_path ya quedó escrito en disco (PNG).
    ...
```

`output_root` es opcional en `process_ficha()`: si no se pasa, no se
escribe nada a disco (`canonical_path = None`) y solo se devuelve
`canonical_image` en memoria — útil para pruebas o depuración rápida.

**`FichaProcessingResult`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `status` | `"OK"` \| `"ERROR"` | `"OK"` = canonizada y validada. `"ERROR"` = no se pudo procesar. |
| `issue_code` | `str \| None` | Código de `config.ISSUE_CODES` (ver tabla de la sección 4). `None` si `status == "OK"`. |
| `message` | `str` | Descripción legible del resultado o del error. |
| `canonical_image` | `np.ndarray \| None` | Imagen canónica BGR 2100×1480 en memoria. |
| `canonical_path` | `Path \| None` | Ruta del PNG en disco, si se pasó `output_root`. |
| `debug` | `dict \| None` | Detalle interno (fase, métricas M1-M4, rotación aplicada). No es parte estricta del contrato. |
| `manifest_entry` | `dict \| None` | Entrada lista para `vision_manifest.json` (ver sección 3.1). |

Internamente cachea la plantilla cargada (no relee los JSON en cada
ficha de un mismo lote).

### Auto-rotación de orientación 

`process_ficha()`/`process_batch()` ya no rechazan una ficha solo por
estar rotada 90°/180°/270°: `detect_and_autorotate()` prueba las 4
orientaciones y usa la que resuelve el marcador especial en
`top_right` de forma inequívoca. Solo se devuelve
`INVALID_ORIENTATION` si ninguna rotación resuelve el problema, o si
más de una rotación "parece" válida (ambiguo — no debería ocurrir con
el diseño actual de un único marcador especial, pero queda cubierto).

La condición de salida sigue siendo siempre: **landscape, marcador
especial en `top_right`, 2100×1480px** — la auto-rotación solo decide
cuántos grados girar antes del warp para llegar a esa condición.

### Helper de recorte 

```python
from core_vision import extraer_recorte

crop = extraer_recorte(canonical_image, center=[1276, 550], crop_size=64)
```

Recibe la imagen canonizada, un centro `[x, y]` (tal como vienen en
`respuestas_centros.json` / `identificacion_centros.json`) y un
tamaño de recorte, y devuelve el crop cuadrado. Si el centro está
cerca del borde, el recorte se desplaza para mantener el tamaño
exacto en vez de devolver un recorte más chico.

**Recorrer todos los centros, generar todos los crops y construir
`crop_manifest.json` es responsabilidad de P3** — este helper solo
resuelve el recorte individual.

## 3. Las 3 fases internas + normalización PNG

Si se necesita más control que `process_ficha()` (por ejemplo, para
depuración), cada fase también es una función pública independiente:

1. **`detect_and_autorotate(image)`** → envuelve `detect_reference_markers()`
   con auto-corrección de orientación. Retorna
   `(imagen_final, resultado, grados_rotados)`.

2. **`detect_reference_markers(image)`** → detecta los 4 marcadores
   cuadrados de referencia en la foto cruda (sin auto-rotar) y
   resuelve orientación. No asume tamaño absoluto de marcador (filtra
   por forma + % de área de la imagen), y usa ordenamiento geométrico
   relativo entre candidatos (no posición fija en el encuadre), por lo
   que es robusto a fotos no recortadas, inclinadas, o con una segunda
   ficha parcialmente visible.

3. **`correct_perspective(image, detected_points, marker_centers, canonical_width, canonical_height)`**
   → calcula la homografía (marcadores detectados → posiciones
   oficiales de `marcadores_centros.json`) y genera la imagen canónica.

4. **`validate_canonical_quality(canonical_image, marker_centers)`**
   → aplica las 4 métricas del Anexo C sobre la imagen ya canonizada.

**Normalización a PNG:** la entrada sigue aceptando
`.jpg/.jpeg/.png` indistintamente, pero la salida canonizada siempre
se guarda como `.png` (sin compresión con pérdida adicional), vía
`cv2.imwrite` con extensión `.png` — se maneja automáticamente dentro
de `process_ficha()` cuando se pasa `output_root`, tomando el nombre
base del archivo original (`ficha_001.jpg → ficha_001.png`).

Utilidades de depuración visual (no forman parte del contrato de
producción — ver sección 7): `draw_detection_debug()`,
`draw_canonical_debug()`, `draw_marker_roi_debug()`.

## 3.1. `vision_manifest.json`

`process_batch()` escribe este archivo en `{output_root}/vision_manifest.json`
con una entrada por ficha procesada:

```json
[
  {
    "file": "ficha_001.jpg",
    "status": "OK",
    "canonical_path": "work/normalized/ficha_001.png",
    "issue_code": null,
    "quality_metrics": null
  },
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
]
```

`quality_metrics` solo viene poblado cuando `issue_code == "LOW_CONFIDENCE"`;
en cualquier otro caso (`OK`, o `ERROR` por otro motivo) va `null`.

> **Importante — dos catálogos de código distintos, a propósito:**
> el `issue_code` de `vision_manifest.json` usa el vocabulario técnico
> de Anexo A tal cual (`MARKERS_NOT_FOUND`, `INVALID_ORIENTATION`,
> `WARP_FAILED`, `LOW_CONFIDENCE`, `CORRUPT_FILE`), porque así lo pidió
> el equipo explícitamente para este archivo. Esto es **distinto** del
> `issue_code` que trae `FichaProcessingResult.issue_code` a nivel de
> código Python, que usa `config.ISSUE_CODES` (`MISSING_REFERENCE_MARKERS`,
> `EXTREME_PERSPECTIVE`, `TEMPLATE_MISMATCH`, `CORRUPT_FILE` — la
> decisión ya confirmada de no crear códigos nuevos). Si en algún
> momento esto genera confusión entre equipos, avisar para unificar.

## 4. Errores técnicos e `issue_code`

Todos los errores de las 3 fases se traducen al mismo desenlace de
pipeline: la ficha no pudo canonizarse → `status = "ERROR"`,
`canonical_image = None`, no se genera score/publishable (igual que
cualquier ficha en `ERROR` según el diagrama de flujo general).

| Error técnico (Anexo A) | Fase | `issue_code` usado |
|---|---|---|
| `MARKERS_NOT_FOUND` | Marcadores | `MISSING_REFERENCE_MARKERS` |
| `INVALID_ORIENTATION` | Marcadores | `EXTREME_PERSPECTIVE` |
| `WARP_FAILED` | Warp | `TEMPLATE_MISMATCH` |
| `LOW_CONFIDENCE` | Calidad (M1-M4) | `CORRUPT_FILE` |
| Archivo ilegible / vacío | (previo a fase 1) | `CORRUPT_FILE` |

> **Nota para el equipo:** `ISSUE_CODES` en `config.py` no tiene un
> código dedicado para `INVALID_ORIENTATION`, `WARP_FAILED` ni
> `LOW_CONFIDENCE`. Se decidió en conjunto con el equipo (P1/P3)
> reutilizar los códigos de la tabla de arriba en vez de crear 3
> códigos nuevos. Si en el futuro se necesita distinguir estos casos
> en reportes, el detalle específico sigue disponible en `message` y
> en `debug`.

## 5. Métricas de calidad (Anexo C) y umbrales calibrados

Calibrados empíricamente con fotos reales tomadas con celular, a
distintas distancias y ángulos (ver `app/pruebas/` + `app/run_pruebas.py`
para el set usado en calibración):

| Métrica | Qué mide | Umbral actual (`config.py`) |
|---|---|---|
| M1 — Nitidez | Varianza del Laplaciano | `QUALITY_MIN_SHARPNESS = 75.0` |
| M2 — Brillo | Promedio de intensidad de gris | `QUALITY_MIN_BRIGHTNESS = 60` / `QUALITY_MAX_BRIGHTNESS = 220` |
| M3 — Zonas negras | % de píxeles muy oscuros en toda la imagen | `QUALITY_DARK_PIXEL_THRESHOLD = 60`, `QUALITY_MAX_DARK_AREA_RATIO = 0.15` |
| M4 — Posición de marcadores | Densidad oscura + offset en la ROI de cada marcador | `QUALITY_MARKER_ROI_MARGIN = 20`, `QUALITY_MIN_MARKER_DARK_RATIO = 0.25`, `QUALITY_MARKER_POSITION_TOLERANCE_PX = 15` |

**Nota de diseño sobre M4:** el offset en píxeles casi siempre da un
valor muy pequeño (<2px) cuando el marcador SÍ se encuentra, porque el
warp se calcula usando esos mismos 4 puntos como correspondencia
exacta con `marcadores_centros.json` — matemáticamente no puede haber
un offset grande ahí. El valor que realmente aporta señal es si el
marcador se encuentra o no (`None` = no se encontró suficiente
densidad oscura en esa esquina, típicamente por sombra parcial o blur
localizado en esa zona específica de la foto).

`QUALITY_DARK_PIXEL_THRESHOLD` se subió de 50 a 60 tras observar que
fotos con iluminación despareja (una esquina en sombra suave) medían
valores de gris entre 53-58 en marcadores perfectamente legibles —
no era un problema real de captura, sino un umbral demasiado estricto.

## 6. Pendiente de calibración futura

- `QUALITY_MAX_BRIGHTNESS = 220` está calibrado contra fotos reales de
  celular (que rondan 135-165), no contra la plantilla digital pura
  (que da ~246, por ser fondo blanco sin exposición de cámara). Si en
  producción aparecen fotos muy sobreexpuestas (flash directo, papel
  brillante), revisar este umbral primero.
- `MARKER_MIN_AREA_RATIO` / `MARKER_MAX_AREA_RATIO` (detección de
  marcadores en foto cruda) están calibrados con fotos tomadas a
  distancias "normales" de celular. Fotos extremadamente cercanas o
  lejanas podrían necesitar ajuste.
- Validación de consistencia de área entre los 4 marcadores
  finalistas (queda como mejora pendiente, no bloqueante): protegería
  contra el caso límite de que falte un marcador real y un candidato
  falso (p. ej. una casilla de "Código de estudiante") ocupe su lugar
  por casualidad geométrica.

## 7. Evidencia visual / debug 

Las salidas obligatorias del contrato de producción son únicamente:

```text
work/normalized/
work/vision_manifest.json
```

Las funciones de depuración visual (`draw_detection_debug()`,
`draw_canonical_debug()`, `draw_marker_roi_debug()`) **no se llaman
desde `process_ficha()`/`process_batch()`** — solo se usan en
herramientas internas de desarrollo/calibración (`run_pruebas.py`, el
`__main__` de `core_vision.py`). La evidencia visible para el docente
(`imagenes_anotadas/`, `fichas_con_error/`, `fichas_con_observaciones/`,
`reporte_observaciones_y_errores.xlsx`) la integra P3/P4 con los
resultados del pipeline completo, no P2.

## 8. Pruebas automatizadas

`app/test_core_vision.py` (pytest). Corre:

```bash
python -m pytest test_core_vision.py -v
```

Incluye casos sintéticos (no dependen de fotos externas, siempre
corren) y casos "dorados" con fotos reales en `app/pruebas/` (se
saltan automáticamente si esas fotos no están presentes en la máquina,
ya que no forman parte del repo). Cubre las 3 fases, auto-rotación,
salida a disco (PNG + manifest) y `extraer_recorte()`.

`app/run_pruebas.py` corre las 3 fases sobre todas las fotos en
`app/pruebas/` y guarda el debug visual de cada una en
`app/debug/<nombre_prueba>/`, más una tabla resumen y un
`debug/resumen.csv` — útil para recalibrar umbrales con nuevas fotos
sin tener que revisar imagen por imagen. Esta es una herramienta de
desarrollo, no parte del contrato de producción (ver sección 7).