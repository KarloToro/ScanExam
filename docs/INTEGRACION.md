# 🔗 Documentación de Integración — ScanExam AI

Este documento describe **cómo está integrado todo el sistema**: los servicios,
los componentes de software, el flujo de datos de punta a punta, los contratos
entre módulos y cómo levantar y operar la plataforma.

Es la vista de integración (responsabilidad **P3**). Para el detalle interno de
cada módulo, ver `ESTRUCTURA_PROYECTO.md` y los contratos en
`docs/informacion_relevante_entre_modulos/`. Para el *porqué* de cada decisión,
ver los [ADRs](adr/).

---

## 1. Visión general

ScanExam corrige automáticamente fichas ópticas fotografiadas. La integración
conecta el **panel docente (P4)**, el orquestador **n8n**, el **motor del
pipeline (P3)** y el **versionado del modelo (MLflow)** en un flujo orientado a
eventos, contenerizado con **Docker Compose**:

```mermaid
flowchart LR
    Docente([👩‍🏫 Docente]) -->|navegador| Web

    subgraph Docker["Docker Compose (red: scanexam)"]
        Web["panel-web (P4)<br/>Nuxt :3000"]
        PAPI["panel-api (P4)<br/>Go :8080"]
        N8N["n8n<br/>orquestador :5678"]
        API["scanexam-app<br/>API pipeline :8000"]
        Mongo[("mongo :27017")]
        Mail["mailpit :8025"]
        MLflow["mlflow :5000"]
    end

    Web -->|REST| PAPI
    PAPI -->|"POST /webhook/scanexam"| N8N
    N8N -->|"HTTP: build-batch, run-vision,<br/>crops-classify, score"| API
    API -.->|"carga modelo @champion"| Modelo[("models/<br/>bubble_classifier_v1.pt")]
    MLflow -.->|"versiona / exporta"| Modelo
    API -->|resultados.json| N8N
    N8N -->|resultados| PAPI
    PAPI -->|persiste| Mongo
    PAPI -->|notifica notas| Mail
```

**Idea clave de la integración:** el pipeline es un **motor Python** que expone
sus fases por **HTTP**. n8n **orquesta** (llama las fases y enruta por estado); el
**panel P4 consume esa misma API** a través del webhook de n8n. La lógica de
negocio (visión, CNN, reglas) vive en Python, no en n8n
([ADR-0001](adr/0001-motor-de-reglas-en-python.md),
[ADR-0004](adr/0004-cli-por-fases-y-orquestacion-n8n.md)). Gracias a este
contrato desacoplado, el panel de producción (Go + Nuxt) se construyó **encima**
de la integración sin tocar el pipeline.

---

## 2. Servicios (Docker Compose)

Definidos en [`docker-compose.yml`](../docker-compose.yml). Todos comparten la
red por defecto del proyecto (`scanexam`), por lo que se resuelven por nombre de
servicio (p. ej. `http://scanexam-app:8000`).

| Servicio | Imagen | Puerto host | Rol |
| --- | --- | --- | --- |
| `panel-web` | `scanexam-panel-web:latest` (Nuxt) | **3000** | Frontend del panel docente (P4). |
| `panel-api` | `scanexam-panel-api:latest` (Go) | **8080** | API del panel (P4): auth, uploads, dispara n8n, persiste, notifica. |
| `n8n` | `n8nio/n8n:latest` | **5678** | Orquestador del pipeline (P3). |
| `scanexam-app` | `scanexam-app:latest` | **8000** | API HTTP del pipeline (P3). Larga vida. |
| `mongo` | `mongo:7` | **27017** | Persistencia del panel (usuarios/auth, batches, resultados). |
| `mailpit` | `axllent/mailpit` | **8025** (UI), 1025 (SMTP) | Captura de correos de notificación (entorno local). |
| `mlflow` | `scanexam-app:latest` | **5000** | Tracking + Model Registry del clasificador. |
| `trainer` | `scanexam-app:latest` | — | Job de un solo uso: entrena y registra el modelo. |

El pipeline (`scanexam-app`), MLflow y el `trainer` comparten una sola imagen
(construida desde [`docker/app.Dockerfile`](../docker/app.Dockerfile)); el panel
tiene sus propias imágenes (Go y Nuxt, bajo `scan-exam-panel/`). El repo se monta
como volumen (`./:/workspace`) en `scanexam-app`, `n8n` y `panel-api`, de modo que
los tres ven el **mismo** `uploads/`, `batches/`, `models/` y código — clave para
que el lote que escribe el panel sea legible por el pipeline (ver §5).

---

## 3. Componentes de software

### 3.1 Motor del pipeline (P3 — lo que integra)

| Archivo | Responsabilidad |
| --- | --- |
| `app/core_pipeline.py` | Orquestador por fases (map→reduce) + CLI. |
| `app/crops.py` | Recorte de burbujas por coordenadas de plantilla (64px). |
| `app/classify.py` | Adaptador que corre la CNN (P1) sobre los crops. |
| `app/identity.py` | Reconstrucción del código de estudiante + búsqueda en CSV. |
| `app/scoring_engine.py` | Motor de reglas determinista (fuente de verdad). |
| `app/api.py` | Capa HTTP (Flask) que expone las fases; incluye `/docs`. |

### 3.2 Módulos que se consumen (no se modifican)

| Archivo | Dueño | Se usa para |
| --- | --- | --- |
| `app/core_vision.py` | **P2** | Canonización/warp + `vision_manifest.json`. Se invoca vía la fase `run-vision`. |
| `app/core_classifier.py` | **P1** | CNN `classify_bubble` / `classify_crops`. |
| `app/template_loader.py` | **P1** | Carga de la plantilla y sus coordenadas. |
| `app/train_classifier.py` | P3 (glue) | Entrena el modelo de P1 de forma reproducible + MLflow. |

### 3.3 Orquestación y panel (P4)

| Archivo / carpeta | Rol |
| --- | --- |
| `n8n_workflows/scanexam_flujo_principal.json` | Workflow de n8n (webhook → fases → routing). |
| `scan-exam-panel/backend/` (Go) | **Panel docente P4 (producción):** API con auth JWT, subida de exámenes, disparo del pipeline (cliente n8n), persistencia MongoDB y notificación por email. Arquitectura hexagonal. |
| `scan-exam-panel/frontend/` (Nuxt/Vue) | **Panel docente P4 (producción):** UI del docente (login, carga, edición de CSV) y página pública de consulta de notas. |
| `panel_docente/main.py` | Stub Flask que **probó el contrato de P4** durante la integración. **Superado** por `scan-exam-panel/`; se conserva como referencia mínima del contrato. |

---

## 4. Flujo de datos end-to-end

```mermaid
sequenceDiagram
    participant D as Docente
    participant W as panel-web (Nuxt)
    participant P as panel-api (Go)
    participant N as n8n
    participant A as scanexam-app (API)
    participant FS as uploads/ + batches/
    participant DB as MongoDB
    participant M as mailpit

    D->>W: Carga examen (fichas + CSV) / login
    W->>P: REST (multipart)
    P->>P: Validación fail-fast
    P->>FS: Escribe uploads/BATCH-XXX/ (Fichas, Estudiantes, Respuestas)
    P->>N: POST /webhook/scanexam { batch_id, source }
    N->>A: POST /pipeline/build-batch { source, batch_id }
    A->>FS: batches/BATCH-XXX/ (input, config, work, output)
    N->>A: POST /pipeline/run-vision { batch_id }
    A->>FS: work/normalized/*.png + vision_manifest.json  (P2)
    N->>A: POST /pipeline/crops-classify { batch_id }
    A->>FS: work/crops/ + bubble_predictions.json  (P1+CNN)
    N->>A: POST /pipeline/score { batch_id }
    A->>FS: recognition_output.json + output/resultados.json
    A-->>N: resultados (+ resumen por estado)
    N->>N: Switch por ficha: OK / OBSERVED / ERROR
    N-->>P: resultados.json
    P->>DB: Persiste batch + resultados (con clave de acceso)
    P->>M: Notifica notas por email
    P-->>W: OK (batch_id)
    D->>W: Consulta su nota con clave de acceso
```

**Regla de oro de estados** (aplicada en `score`): una ficha es `OK` solo si es
visualmente procesable **y** el estudiante se identifica; si no,
`OBSERVED`/`ERROR` sin nota publicable. La calificación es determinista
(mismas predicciones → mismo resultado).

---

## 5. Contrato de estructura del BATCH

El panel escribe el lote subido en `uploads/<BATCH_ID>/` (con las carpetas
`Fichas/ Estudiantes/ Respuestas/`) y pasa `source = "uploads/<BATCH_ID>"` al
webhook. Como `panel-api`, `n8n` y `scanexam-app` montan el **mismo**
`./:/workspace`, el pipeline lee esa carpeta y genera `batches/<BATCH_ID>/`
según [`01_batch_contract.md`](informacion_relevante_entre_modulos/01_batch_contract.md):

```text
batches/BATCH-XXX/
├── input/                      # fichas originales (P3 build-batch)
├── config/                     # estudiantes_matriculados.csv, claves.csv
├── work/
│   ├── normalized/*.png        # canónicas 2100x1480 (P2 run-vision)
│   ├── vision_manifest.json    # estado visual por ficha (P2)
│   ├── crops/*.png             # 130 recortes por ficha (P3 crops)
│   ├── crop_manifest.json      # (P3)
│   ├── bubble_predictions.json # clases EMPTY/MARKED/GHOST (P1 CNN)
│   └── recognition_output.json # interpretación por pregunta (P3)
├── output/
│   └── resultados.json         # salida final consolidada (P3 score)
└── batch_manifest.json
```

Artefactos JSON intermedios = **contratos** entre fases. Cada fase lee los de la
anterior y escribe el suyo, lo que las hace depurables y reejecutables por
separado.

---

## 6. La API HTTP del pipeline

Servida por `scanexam-app` ([`app/api.py`](../app/api.py)). Documentación
interactiva (Swagger UI) en **http://localhost:8000/docs**; spec en `/openapi.json`.

| Método | Ruta | Cuerpo | Efecto |
| --- | --- | --- | --- |
| `GET` | `/health` | — | Liveness. |
| `POST` | `/pipeline/build-batch` | `{ source, batch_id }` | Crea la estructura del BATCH. |
| `POST` | `/pipeline/run-vision` | `{ batch_id }` | P2: canoniza → `vision_manifest.json`. |
| `POST` | `/pipeline/crops-classify` | `{ batch_id }` | Recorta + CNN → `bubble_predictions.json`. |
| `POST` | `/pipeline/score` | `{ batch_id }` | Reglas + calificación → `resultados.json`. |
| `POST` | `/pipeline/run-all` | `{ source, batch_id }` | Las 4 fases en secuencia (demo). |

La API es **solo transporte**: cada endpoint delega en `core_pipeline`. No
contiene lógica de negocio.

---

## 7. El workflow de n8n

Archivo: [`n8n_workflows/scanexam_flujo_principal.json`](../n8n_workflows/scanexam_flujo_principal.json)
(id `scanexamMain0001`, webhook `POST /webhook/scanexam`).

```text
[Webhook] → [build-batch] → [run-vision] → [crops-classify] → [score] ┬→ [Responder resultados]
                                                                       └→ [Separar fichas] → [Switch por estado]
                                                                                              ├ OK       → Publicar
                                                                                              ├ OBSERVED → Revisión docente
                                                                                              └ ERROR    → Incidencia técnica
```

- Los 4 nodos de fase son **HTTP Request** contra `http://scanexam-app:8000`.
- El nodo **Switch** enruta cada ficha por `processing_status`: es la
  **decisión inteligente del orquestador** (n8n decide el camino; Python decide
  el contenido).
- `Responder resultados` devuelve el `resultados.json` completo al llamador
  (el panel lo parsea y persiste).

**Importar/actualizar el workflow** (tras editar el JSON):

```bash
docker exec scanexam-n8n n8n import:workflow --input=/workspace/n8n_workflows/scanexam_flujo_principal.json
docker exec scanexam-n8n n8n publish:workflow --id=scanexamMain0001
docker restart scanexam-n8n   # necesario para registrar el webhook
```

---

## 8. El panel docente (P4)

El panel de producción vive en **`scan-exam-panel/`** y consume la integración
por HTTP (nunca calcula notas: solo dispara el pipeline y presenta/persiste sus
resultados).

- **`panel-web` (Nuxt/Vue)** — http://localhost:3000. UI del docente: login
  (JWT), carga del examen (fichas + edición inline de estudiantes/respuestas) y
  **página pública de consulta** (`/consulta/[id]`) donde el estudiante ve su
  nota con una clave de acceso.
- **`panel-api` (Go, arquitectura hexagonal)** — http://localhost:8080. Recibe
  la subida, **valida (fail-fast)**, escribe el lote en `uploads/`, dispara el
  pipeline vía el **webhook de n8n**, **persiste** batches y resultados en
  **MongoDB** y **notifica** las notas por email (mailpit) con la clave de acceso.

**Integración con nuestro contrato** (verificada): `panel-api` envía
`{batch_id, source}` al webhook y parsea la respuesta
`{ok, batch_id, summary, resultados:{results:[…]}}` campo por campo — exactamente
el contrato de la API del pipeline.

> **Nota histórica:** durante la integración, P3 dejó un stub Flask
> (`panel_docente/main.py`, :5001) para *probar el contrato de extremo a extremo*.
> Ese stub cumplió su rol y quedó **superado** por `scan-exam-panel/`; se conserva
> en el repo como referencia mínima del contrato.

---

## 9. Versionado del modelo (MLflow)

El clasificador de P1 se entrena de forma reproducible con
[`app/train_classifier.py`](../app/train_classifier.py) (semilla fija) y se
registra en MLflow como `bubble_classifier` con alias **`@champion`**
([ADR-0003](adr/0003-versionado-del-modelo-con-mlflow.md)). El `.pt` se exporta a
`models/bubble_classifier_v1.pt`, que es lo que la CNN carga en runtime — por eso
**MLflow no necesita estar encendido para operar** (solo para entrenar/auditar).
MLflow UI en **http://localhost:5000**.

```bash
docker compose up --build mlflow trainer   # entrena y registra @champion
```

---

## 10. Cómo levantar todo

Requisitos: Docker + Docker Compose. En este entorno el daemon se arranca con
`sudo systemctl start docker` y el build usa el builder legacy
([ADR-0006](adr/0006-contenerizacion-y-entorno.md)).

```bash
# 1. Construir imágenes (una vez)
DOCKER_BUILDKIT=0 docker compose build

# 2. (Si aún no hay modelo) entrenar y versionar
docker compose up --build mlflow trainer

# 3. Levantar la plataforma completa
docker compose up -d scanexam-app n8n mongo mailpit panel-api panel-web

# 4. Importar/activar el workflow de n8n (ver §7)
```

Servicios: **panel http://localhost:3000** · panel-api http://localhost:8080 ·
API pipeline http://localhost:8000/docs · n8n http://localhost:5678 ·
mailpit http://localhost:8025 · MLflow http://localhost:5000.

---

## 11. Cómo correr un lote (varias formas)

**A) Desde el panel (flujo del docente):** entrar a http://localhost:3000, iniciar
sesión y subir el examen.

**B) Disparando el webhook de n8n directamente:**

```bash
curl -X POST http://localhost:5678/webhook/scanexam \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"BATCH-001","source":"data/lotes_prueba/real"}'
```

**C) Contra la API, sin n8n (útil para depurar):**

```bash
curl -X POST http://localhost:8000/pipeline/run-all \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"BATCH-001","source":"data/lotes_prueba/real"}'
```

**D) Por CLI dentro del contenedor (fase por fase):**

```bash
docker exec scanexam-app python -m app.core_pipeline build-batch --source data/lotes_prueba/real --batch-id BATCH-001
docker exec scanexam-app python -m app.core_pipeline run-vision     --batch BATCH-001
docker exec scanexam-app python -m app.core_pipeline crops-classify --batch BATCH-001
docker exec scanexam-app python -m app.core_pipeline score          --batch BATCH-001
```

Los resultados quedan en `batches/BATCH-001/output/resultados.json`. Para validar
el camino `OK` sin depender de una foto real, se puede generar una ficha bien
llenada con `app/utilitarios/generar_ficha_sintetica.py`.

---

## 12. Pruebas

Los tests del pipeline corren dentro de la imagen (trae torch/cv2/flask):

```bash
docker run --rm -v "$(pwd)":/workspace -w /workspace \
  -e PYTHONPATH=/workspace:/workspace/app scanexam-app:latest \
  python -m pytest app/ panel_docente/ -q
```

Cobertura de integración (P3): `test_core_pipeline` (fases + end-to-end de
scoring), `test_api` (contrato HTTP + `/docs`), además de los tests por módulo
(crops, classify, identity, scoring, vision). El panel de producción
(`scan-exam-panel/backend`, Go) trae sus propios tests (`go test ./...`).

---

## 13. Decisiones de arquitectura (ADRs)

| ADR | Decisión |
| --- | --- |
| [0001](adr/0001-motor-de-reglas-en-python.md) | Motor de reglas en Python, no en n8n. |
| [0002](adr/0002-paralelismo-en-python.md) | Paralelismo en Python (ProcessPool + CNN). |
| [0003](adr/0003-versionado-del-modelo-con-mlflow.md) | Versionado del modelo con MLflow `@champion`. |
| [0004](adr/0004-cli-por-fases-y-orquestacion-n8n.md) | CLI por fases + n8n orquesta por **HTTP**. |
| [0005](adr/0005-panel-docente-stub-minimo.md) | Panel docente como stub mínimo (contrato). |
| [0006](adr/0006-contenerizacion-y-entorno.md) | Contenerización y entorno. |
| [0007](adr/0007-confidence-por-pregunta.md) | Cálculo del `confidence` por pregunta. |
| [0008](adr/0008-reconstruccion-codigo-estudiante.md) | Reconstrucción del código de estudiante. |

---

## 14. Estado

**Integrado y verificado end-to-end:** panel (Nuxt/Go) → n8n → API → pipeline
(P2+P1+P3) → `resultados.json` → persistencia MongoDB + notificación por email +
consulta con clave de acceso. El panel de producción se conecta al webhook de n8n
respetando el contrato al 100% (payload `{batch_id, source}` y respuesta de
`score`). Modelo versionado en MLflow (`@champion`) y servido desde el `.pt`.

**Los 4 estados por ficha** quedaron validados: `OK` (con nota), `OBSERVED`
(estudiante no identificado), `ERROR` (visión) y **rechazo fail-fast** (ZIP
inválido, antes de procesar).

---

## 15. Notas de entorno / troubleshooting

- **Daemon Docker:** `sudo systemctl start docker` (no arranca solo).
- **buildx ausente:** usar `DOCKER_BUILDKIT=0 docker compose build`.
- **`PYTHONPATH=/workspace:/workspace/app`**: necesario porque `core_classifier.py`
  hace `import config`; se inyecta por entorno, sin tocar el archivo de P1.
- **MLflow y pandas:** MLflow exige `pandas<3`; la imagen usa pandas 2.x + mlflow 3.14.
- **Webhook n8n no responde:** reiniciar el contenedor tras `publish:workflow`.
- **Volumen compartido:** `panel-api`, `n8n` y `scanexam-app` deben montar el
  mismo `./:/workspace`; si no, el pipeline no encuentra el `source` que escribe
  el panel.
