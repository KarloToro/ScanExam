> **⚠️ Especificación base (histórica).** Este documento fija los **conceptos,
> reglas y estados** del sistema y sigue vigente en eso. Algunos aspectos de
> **implementación evolucionaron** respecto a lo aquí descrito: la entrada por el
> panel es **multipart, no ZIP**; la persistencia es **MongoDB** (no SQLite); y el
> panel es **Go + Nuxt** (no Flask). Para el estado actual ver
> [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) e
> [`docs/INTEGRACION.md`](docs/INTEGRACION.md).

## 1. Descripción general

ScanExam AI es un sistema inteligente de arquitectura distribuida local, orientada a eventos, para la corrección automática de hojas de respuestas ópticas a partir de fotografías. Está diseñado para docentes que necesitan evaluar exámenes en papel de manera rápida, trazable y confiable, combinando la eficiencia de un sistema digital con la transparencia de una evaluación tradicional en papel.

El sistema no busca reemplazar completamente la revisión docente. Su objetivo es automatizar la corrección de las fichas confiables y separar los casos que requieren intervención humana, de manera que el docente pase de corregir todo el lote a revisar únicamente casos puntuales.

Para funcionar, ScanExam AI requiere:
- ejecución local en la computadora o red local del docente;
- una plantilla oficial imprimible `FICHA_OPTICA_V1`;
- archivos Excel docentes que generan `Estudiantes.csv` y `Respuestas.csv`;
- un lote comprimido en ZIP con fichas fotografiadas y configuración académica;
- n8n como orquestador del flujo;
- un motor local de procesamiento visual y calificación.

La plataforma se ejecuta sobre una máquina virtual Ubuntu local. En ella se levantan contenedores mediante Docker Compose: `n8n` para orquestación y `scanexam-app` para la plataforma docente, procesamiento visual, CNN, calificación, persistencia SQLite y generación de reportes.

---

## 2. Regla central del sistema

ScanExam califica automáticamente una ficha únicamente cuando se cumplen dos condiciones:
1. la imagen corresponde a una ficha óptica válida, procesable y dentro de tolerancias visuales;
2. el estudiante fue identificado correctamente a partir del código marcado en la ficha.

Bajo este criterio, cuando una ficha tiene `processing_status = OK`, el sistema no deja preguntas pendientes de calificar por incertidumbre. Siempre genera una nota para el examen completo aplicando reglas deterministas por pregunta.

Si la ficha es visualmente procesable, pero el estudiante no puede ser identificado con suficiente confianza, la ficha queda como `OBSERVED`, con:
```text
score = null
publishable = false
````

En ese escenario, la ficha se deriva a revisión docente puntual.

Para las fichas `OK`, el sistema aplica las siguientes reglas por pregunta:

- si `accepted_answer` coincide con `correct_answer`, se asignan los puntos correspondientes;
    
- si `accepted_answer` existe pero difiere de `correct_answer`, se asignan 0 puntos;
    
- si la pregunta está en blanco, `accepted_answer = null` y se asignan 0 puntos;
    
- si hay doble marca, `detected_answer` contiene dos o más opciones detectadas, `accepted_answer = null` y se asignan 0 puntos;
    
- si la marca es dudosa (solo borrones o residuales detectados como `GHOST`), `accepted_answer = null` y se asignan 0 puntos.
    

## 3. Principio de validación temprana

ScanExam aplica el principio de **fallar rápido**.

Esto significa que los errores que pueden detectarse antes del procesamiento visual se rechazan en la recepción. El sistema no inicia el procesamiento de imágenes si el lote, los formatos o los CSV docentes no cumplen las reglas mínimas.

Consecuencia principal:

```
ZIP inválido o CSV inválido
→ se rechaza el lote
→ no se genera resultados.json
→ no se procesa ninguna ficha
```

En cambio:

```
ZIP válido y CSV válidos, pero una ficha individual falla
→ se genera resultados.json
→ esa ficha queda como ERROR u OBSERVED
```

## 4. Consideraciones del sistema

1. La configuración académica del examen se realiza mediante archivos CSV generados desde plantillas Excel oficiales.
    
2. El archivo `Estudiantes.csv` contiene los códigos, nombres y correos de los estudiantes matriculados.
    
3. El archivo `Respuestas.csv` contiene el número de pregunta, clave correcta y puntaje.
    
4. El código de estudiante se identifica mediante burbujas circulares en la ficha.
    
5. La ficha óptica incluye cuatro marcadores de referencia impresos que permiten detectar orientación, corregir perspectiva y canonizar la imagen.
    
6. El sistema acepta imágenes en formato `jpg`, `jpeg` y `png`.
    
7. Durante la normalización, todas las fichas se convierten a `png` para evitar pérdidas en recortes y auditoría visual.
    
8. Las imágenes originales se conservan intactas en `input/`.
    
9. Para esta versión, solo se soporta una plantilla: `FICHA_OPTICA_V1`.
    
10. La ficha tiene 10 preguntas y soporta alternativas `A`, `B`, `C`, `D` y `E`.
    
11. El código de estudiante puede ser de hasta 8 dígitos.
    
12. **Cada lote se procesará con una única clave de respuestas.** No se soportan variantes de examen A/B dentro de una misma ficha.
    
13. El sistema genera archivos `resultados.json`, `resultados.xlsx`, `reporte_observaciones_y_errores.xlsx`, imágenes anotadas y sitio de consulta.
    
14. En los casos `OBSERVED` y `ERROR`, el sistema siempre registra el motivo mediante `processing_message` y códigos de incidencia (`issue_code`).
    

## 5. Estados del sistema

### 5.1 Estados de procesamiento por ficha

```
processing_status:
- OK
- OBSERVED
- ERROR
```

### OK

La ficha fue procesada, el estudiante identificado, se generó nota y el resultado puede publicarse.

### OBSERVED

La ficha es procesable visualmente, pero el estudiante no fue identificado de forma confiable. Pasa a revisión docente manual.

### ERROR

La ficha no pudo procesarse de forma confiable por un problema técnico (falla al leer archivo), visual (M1-M4 fallidos) o geométrico (perspectiva extrema).

## 6. Arquitectura de despliegue local

```
PC del docente / Windows
└── Navegador web
    ├── Panel de Administración Docente (P4)
    │   └── http://IP_VM_UBUNTU:5000
    └── Panel n8n (P3)
        └── http://IP_VM_UBUNTU:5678

Servidor Ubuntu local / VM VirtualBox
└── Docker Compose
    ├── contenedor: n8n (Ejecuta los workflows / agentes)
    ├── contenedor: scanexam-app (Flask, OpenCV, PyTorch, SQLite)
    └── volúmenes persistentes (batches/, models/, output/, sitio/, scanexam.db)
```

## 7. Módulos y Agentes del Sistema

Para respetar la arquitectura técnica, se definen como **"Módulos"** a las piezas de software directas (frontend, scripts de visión) y como **"Agente"** al componente orquestador operado mediante n8n.

### 7.1 Módulo Frontend: Recepción y Validación Temprana (P4)

**Objetivo:** Recibir el ZIP del examen, validar su estructura física y la integridad de los datos académicos para evitar que lotes corruptos entren al flujo pesado.

**Entrada:** `E_Parcial_Seccion_A.zip` subido por el docente. **Salida:** Un lote interno (BATCH) estructurado, o el rechazo inmediato al usuario.

**Qué hace:**

- Descomprime el ZIP y verifica las carpetas `Fichas/`, `Estudiantes/`, `Respuestas/`.
    
- Valida formatos de imágenes y la consistencia interna de los CSV.
    

**Reglas de rechazo (Detalle):** Para consultar el detalle exacto de las reglas que provocan el rechazo del ZIP (ej. puntajes vacíos, extensiones inválidas), referirse al documento: `docs/especificacion_flujo/00_procesamiento_lote_zip.md` (Secciones _Requisitos previos_ y _Criterios de lectura_).

**Justificación:** Este módulo existe para aplicar el principio de "fallar rápido". Al purgar los errores administrativos en el frontend, se protege al Agente n8n de procesar lotes mal formados, quitándole carga inútil al orquestador.

### 7.2 Módulo de Visión Computacional: Calidad y Normalización (P2)

**Objetivo:** Transformar la foto cruda de una ficha en una imagen canónica estandarizada geométrica y visualmente (2100×1480px, apaisada).

**Entrada:** Imágenes en bruto ubicadas en `input/`. **Salida:** `work/normalized/ficha.png` y un `vision_manifest.json`.

**Flujo Interno:**

```
foto cruda
↓
detección de 4 marcadores (con auto-rotación si aplica)
↓
corrección de perspectiva (warp)
↓
validación de calidad (Métricas M1, M2, M3, M4)
↓
imagen canónica en PNG
```

**Ejemplo de Salida (`vision_manifest.json`):**

JSON

```
{
  "file": "ficha_001.jpg",
  "status": "OK",
  "canonical_path": "work/normalized/ficha_001.png",
  "issue_code": null,
  "quality_metrics": null
}
```

**Justificación:** Este módulo aísla el complejo problema geométrico y fotográfico. Entrega un "lienzo" perfecto y estandarizado, permitiendo que la fase de IA opere sobre un entorno controlado sin preocuparse por rotaciones o perspectivas extremas.

### 7.3 Agente Orquestador (n8n): Integración, Crops y Motor Académico (P3)

**Objetivo:** Orquestar el flujo asíncrono, extraer recortes, llamar a la IA para clasificar burbujas, aplicar las reglas académicas y calcular la calificación final.

**Entrada:** `vision_manifest.json` y las imágenes en `work/normalized/`. **Salida:** `crop_manifest.json`, `bubble_predictions.json`, `recognition_output.json`, y `resultados.json`.

**Flujo Interno:**

```
imagen canónica (PNG)
↓
extracción de recortes por coordenadas (crops)
↓
clasificación CNN por burbuja (EMPTY, MARKED, GHOST)
↓
reconstrucción de identidad e interpretación de reglas por pregunta
↓
calificación (contraste con Respuestas.csv)
↓
resultados consolidados
```

**Ejemplo de Salidas:** _`bubble_predictions.json` (Clasificación pura):_

JSON

```
{
  "crop_id": "ficha_001_q_01_A",
  "predicted_class": "MARKED",
  "confidence": 0.94
}
```

_`recognition_output.json` (Regla interpretada):_

JSON

```
{
  "question_id": 1,
  "detected_answer": "A",
  "accepted_answer": "A",
  "mark_status": "SINGLE_MARK"
}
```

**Justificación:** Este Agente existe (dentro de n8n) para escalar y paralelizar las tareas pesadas. Al actuar como el cerebro integrador, combina la salida determinista de P2 con la IA de P1, ejecutando las lógicas de negocio sin bloquear la interfaz web.

### 7.4 Módulo Frontend: Transparencia y Publicación (P4)

**Objetivo:** Permitir al docente auditar el lote y a los estudiantes consultar sus notas mediante una interfaz web. **Entrada:** `resultados.json` consolidado. **Salida:** Interfaz web, `resultados.xlsx`, `reporte_observaciones_y_errores.xlsx` e imágenes anotadas. **Justificación:** Cierra el ciclo de usuario entregando reportes legibles e interactivos, separando el motor backend de la experiencia de usuario.

## 8. Contrato de Plantilla Canónica

La referencia geométrica se basa en cuatro archivos fundamentales ubicados en `data/plantilla/ficha_optica_a5_horizontal_v1/`. Todas las coordenadas operan estrictamente en la imagen de `2100 x 1480 px`.

1. **`template_config.json`**: Directrices maestras de la plantilla (tamaño, tamaño de crop de 64px, etc).
    
2. **`respuestas_centros.json`**: Coordenadas exactas para recortes de opciones. _(Ejemplo de formato: `"q_01_A": [1276, 550]`)_.
    
3. **`identificacion_centros.json`**: Coordenadas de las burbujas de la matrícula.
    
4. **`marcadores_centros.json`**: Coordenadas de los cuadrados perimetrales para el warp de P2.
    

## 9. Estructura de `resultados.json`

(Muestra enfocada en la estructura sin variantes A/B):

JSON

```
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
    }
  ]
}
```

## 10. Reporte de Observaciones

El archivo `reporte_observaciones_y_errores.xlsx` consolida las fichas con estados `OBSERVED` o `ERROR`. Códigos de incidencia probables:

```
LOW_STUDENT_CODE_CONFIDENCE
STUDENT_NOT_FOUND
DUPLICATED_STUDENT_CODE
MISSING_STUDENT_CODE
UNCERTAIN_MARK
DOUBLE_MARK
MISSING_REFERENCE_MARKERS
EXTREME_PERSPECTIVE
TEMPLATE_MISMATCH
CORRUPT_FILE
```

## 11. Parámetros Globales (config.py)

Python

```
TEMPLATE_ID = "ficha_optica_a5_horizontal_v1"
OPTIONS = ["A", "B", "C", "D", "E"]
SUPPORTED_INPUT_FORMATS = [".jpg", ".jpeg", ".png"]
NORMALIZED_IMAGE_FORMAT = "png"
STUDENT_CODE_DIGITS = 8
MIN_CLASSIFICATION_CONFIDENCE = 0.80
MIN_STUDENT_CODE_CONFIDENCE = 0.75
QUALITY_STATUS = ["OK", "ERROR"]
PROCESSING_STATUS = ["OK", "OBSERVED", "ERROR"]
MARK_STATUS = ["SINGLE_MARK", "BLANK", "DOUBLE_MARK", "UNCERTAIN"]
QUESTION_STATUS = ["CORRECT", "INCORRECT", "BLANK", "DOUBLE_MARK", "UNCERTAIN"]
BUBBLE_CLASSES = ["EMPTY", "MARKED", "GHOST"]
# (Configuración P2 y de umbrales M1-M4 definida en el módulo correspondiente)
```

## 12. Distribución de responsabilidades

### P1 — Clasificador de burbujas, plantilla oficial y contratos base

**Responsabilidad principal:** Diseñar la plantilla oficial del sistema, definir los contratos entre módulos y construir el clasificador CNN encargado de identificar el estado de cada burbuja. **Entregables:**

- Plantilla oficial imprimible `FICHA_OPTICA_V1`.
    
- Diseño de burbujas, marcadores y regiones de la ficha.
    
- Definición del tamaño de ficha canónica.
    
- `template_layout.json` (y sus derivados de centros).
    
- Definición de contratos CSV de Respuestas y Estudiantes.
    
- Reglas de validación académica de `Respuestas.csv`.
    
- Dataset de burbujas y recortes perfectos.
    
- CNN para clasificación de burbujas (`EMPTY`, `MARKED`, `GHOST`) con función real `classify_bubble(crop)`.
    
- Especificación de reglas de interpretación por pregunta y calificación. **Límites de responsabilidad:** No implementa la detección de marcadores, panel docente ni n8n. Define las reglas del sistema calificador, pero la implementación la orquesta P3.
    

### P2 — Procesamiento visual de la ficha completa

**Responsabilidad principal:** Procesar la imagen completa de la ficha: detectar marcadores, validar calidad visual, corregir orientación/perspectiva y generar una versión canonizada lista para recorte. **Entregables:**

- Carga, apertura y normalización inicial a PNG.
    
- Detección de los cuatro marcadores de referencia.
    
- Validación de calidad visual y perspectiva.
    
- Corrección de orientación y perspectiva (Warp).
    
- Generación de imágenes normalizadas en `work/normalized/` junto al `vision_manifest.json`.
    
- Evidencia visual del proceso. **Límites de responsabilidad:** No entrena la CNN, no realiza los _crops_ individuales, no calcula notas y no genera informes finales. Entrega el insumo canónico.
    

### P3 — Integración del pipeline, automatización y motor de decisión académica

**Responsabilidad principal:** Implementar la integración del pipeline: validación de estructura `BATCH`, ejecución de módulos en n8n, generación de archivos intermedios, motor de reconocimiento, scoring y orquestación. **Entregables:**

- Generación de estructura `BATCH` y `batch_manifest.json`.
    
- Endpoints usados por n8n y Workflows en n8n (Agentes).
    
- Script CLI para correr el pipeline y Docker Compose.
    
- Utilitario de recorte por coordenadas sobre ficha canonizada (generación de `work/crops/` y `crop_manifest.json`).
    
- Ejecución del clasificador sobre los crops (`bubble_predictions.json`).
    
- Implementación de `scoring_engine.py` (aplicación de reglas y estados `OK/OBSERVED/ERROR`).
    
- Generación de `recognition_output.json`, `resultados.json` y base de reporte de observaciones. **Límites de responsabilidad:** No diseña la ficha oficial, no entrena la CNN y no resuelve el complejo geométrico de OpenCV, sino que lo consume. No construye la UI docente final.
    

### P4 — Panel docente, interfaz, visualización y publicación

**Responsabilidad principal:** Construir el panel docente, la validación temprana de lotes, la visualización de estados, descarga de resultados, y sitio local de consulta. **Entregables:**

- Panel docente (Módulo Frontend) en Flask/backend preferido.
    
- Validador temprano de ZIP, `Estudiantes.csv` y `Respuestas.csv` (Rechazo temprano).
    
- Pantalla de progreso y visores de estados.
    
- Descarga de `resultados.json`, `resultados.xlsx` y `reporte_observaciones_y_errores.xlsx`.
    
- Sitio estático local para consulta y render de imágenes anotadas. **Límites de responsabilidad:** No calcula notas, no interpreta burbujas, no entrena redes neuronales ni lidia con lógicas de visión artificial puras.
    

### P5 — Documentación, evidencia, pruebas y exposición

**Responsabilidad principal:** Construir el informe final, diagramas, pruebas documentadas, manuales, diapositivas, guion de exposición y evidencia de respaldo para la defensa técnica. **Entregables:**

- Informe PDF final, diseño conceptual y diagramas de arquitectura/flujo.
    
- Tablas de métricas y casos de prueba.
    
- Capturas funcionales del sistema (n8n, Docker, UI, resultados).
    
- Manuales, guion de demo y diapositivas de exposición.
    
- Preparación de los lotes de prueba (perfecto, observado, error visual, rechazado). **Límites de responsabilidad:** No programa el sistema principal, no inventa métricas, necesita la colaboración del equipo para obtener la evidencia y se centra en asegurar la excelencia de la defensa formal del proyecto.
    

## 13. Flujo Final

1. Docente prepara Estudiantes y Respuestas en CSV.
    
2. Docente toma fotos y arma ZIP.
    
3. **P4 (Módulo Frontend)** valida ZIP y CSV en la recepción. Rechaza inmediatamente si es inválido.
    
4. Se crea el `BATCH` interno.
    
5. **P2 (Módulo de Visión)** normaliza fotos y entrega un PNG canónico y `vision_manifest.json`.
    
6. **P3 (Agente n8n)** orquesta la extracción de crops desde las coordenadas y los envía a la CNN.
    
7. **P3** procesa las calificaciones ignorando borrones `GHOST` frente a marcas `MARKED`.
    
8. Si no hay identidad segura del alumno, la nota queda en estado `OBSERVED`.
    
9. **P4 (Módulo Frontend)** presenta la plataforma web final y emite Excel/JSON a disposición para descargar o publicar.