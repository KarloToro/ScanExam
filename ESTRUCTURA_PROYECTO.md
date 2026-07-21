# 🗺️ Guía de Arquitectura y Carpetas - ScanExam AI

> **⚠️ Documento de planificación (parcialmente histórico).** La estructura de
> carpetas de abajo refleja el plan inicial del equipo. El **panel docente (P4)**
> ya **no** es `panel_docente/` (stub Flask, superado); el panel real es
> **`scan-exam-panel/`** (backend Go + frontend Nuxt + MongoDB + mailpit). Para el
> estado **actual y completo** de componentes ver
> [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) e
> [`docs/INTEGRACION.md`](docs/INTEGRACION.md).

Se simplifico al maximo la estructura de carpetas del proyecto para que no sean un obstaculo adicional en el desarrollo del proyecto. Con una deadline de 12 días tenemos que correr.

En fin, el objetivo principal es que **cada miembro del equipo trabaje en su propia carpeta/archivo** sin pisarse los unos a los otros en Git, y que todo se integre de forma sencilla utilizando Docker y n8n.

## 📁 Estructura del Repositorio

```text
scanexam-ai/
├── README.md                    # Descripción general para el profesor
├── ESTRUCTURA_PROYECTO.md       # ESTE DOCUMENTO (Guía interna)
├── docker-compose.yml           # Levanta n8n y nuestro entorno Ubuntu
├── requirements.txt             # Librerías de Python (OpenCV, Flask, PyTorch, etc.)
│
├── app/                         # 🧠 MOTOR DE IA Y PROCESAMIENTO (P1, P2, P3)
│   │                            # (Scripts ejecutables por consola para n8n)
│   ├── core_vision.py           # Agente 2: Recortes y normalización con OpenCV
│   ├── core_pipeline.py         # Agente 1 y 4: Validaciones iniciales y reportes finales
│   ├── core_classifier.py       # Agente 3: Predicción de CNN y cálculo de notas
│   └── config.py                # Variables globales y rutas
│
├── panel_docente/               # 💻 INTERFAZ WEB DOCENTE (P4)
│   │                            # (Servidor Flask/FastAPI aislado de la IA)
│   ├── main.py                  # Lógica del servidor web (rutas, subida de ZIP)
│   ├── templates/               # Vistas HTML
│   └── static/                  # Archivos CSS / JavaScript
│
├── n8n_workflows/               # ⚙️ ORQUESTACIÓN
│   └── scanexam_flujo_principal.json # Flujo exportado para evaluación
│
├── notebooks/                   # 📊 ENTRENAMIENTO DE MODELOS (P1)
│   └── clasificador_burbujas.ipynb # Notebook donde se entrenó la CNN
│
├── data/                        # 📂 ARCHIVOS DE PRUEBA Y CONTRATOS
│   ├── plantilla/               # PDF oficial de la ficha óptica
│   ├── lotes_prueba/            # ZIPs de prueba (Ok, Observed, Error)
│   └── contratos_ejemplo/       # Estudiantes.csv y Respuestas.csv
│
└── docs/                        # 📄 DOCUMENTACIÓN Y EVIDENCIAS (P5)
    └── evidencia_capturas/      # Screenshots y videos del funcionamiento