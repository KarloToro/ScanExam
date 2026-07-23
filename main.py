# main.py
"""
ScanExam (v8) — Servidor FastAPI Stateless en Memoria

Cadena de procesamiento integrada por ficha:
  1. Decodificación de Bytes -> Arreglo NumPy OpenCV BGR (en RAM).
  2. Visión por Computadora (P2 - core_vision): Detección de marcadores, auto-rotación,
     corrección de perspectiva (warp a 2100x1480 px) y control de calidad (M1-M4).
  3. Extracción de Crops en RAM y Clasificación por CNN (P1 - core_classifier.classify_bubble).
  4. Reconstrucción de Identidad del Estudiante (P3 - identity).
  5. Motor Determinista de Calificación (P3 - scoring_engine).
  6. Reducción a Nivel de Lote: Detección de códigos duplicados.
  7. Generación de Reporte Excel de dos pestañas en RAM (openpyxl) y descarga directa.
"""
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración del PATH para resolución de módulos locales (app/)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import io
import json
from typing import List, Dict, Any

import cv2
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

# Importaciones del dominio ScanExam
try:
    from app.template_loader import load_template, TemplateContract
    from app.core_vision import process_ficha, extraer_recorte
    from app.core_classifier import classify_bubble
    from app.identity import identify_student, find_duplicate_codes
    from app.scoring_engine import (
        group_answer_predictions,
        interpret_question,
        score_answers,
    )
except ImportError:
    from template_loader import load_template, TemplateContract
    from core_vision import process_ficha, extraer_recorte
    from core_classifier import classify_bubble
    from identity import identify_student, find_duplicate_codes
    from scoring_engine import (
        group_answer_predictions,
        interpret_question,
        score_answers,
    )

# ---------------------------------------------------------------------------
# Inicialización de la Aplicación y Recursos Globales
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ScanExam AI",
    description=" Corrección automática de exámenes con IA",
    version="8.0.0"
)

templates = Jinja2Templates(directory="templates")

# Plantilla cargada globalmente al arrancar la app
template_contract: TemplateContract = None


@app.on_event("startup")
def startup_event():
    """Carga la plantilla oficial en memoria al arrancar la aplicación."""
    global template_contract
    template_contract = load_template("ficha_optica_a5_horizontal_v1")
    print("ScanExam AI listo: Plantilla cargada.")


# ---------------------------------------------------------------------------
# Adaptadores de Formato de Datos (Tuplas y Detección Flexible de CSV)
# ---------------------------------------------------------------------------

# Tuplas de encabezados aceptados
_CODE_HEADERS = ("codigo", "código", "code", "student_code", "codigo_estudiante", "matricula", "matrícula")
_NAME_HEADERS = ("nombre", "nombres", "name", "student_name", "apellidos_y_nombres", "nombre_completo", "estudiante", "alumno")
_EMAIL_HEADERS = ("correo", "email", "mail", "e-mail", "correo_electronico")

_QUESTION_HEADERS = ("pregunta", "numero", "nro", "n", "question", "id", "question_id", "número_pregunta", "num")
_CORRECT_HEADERS = ("clave", "clave_correcta", "respuesta", "correcta", "respuesta_correcta", "correct", "correct_answer", "answer", "key")
_POINTS_HEADERS = ("puntaje", "puntos", "points", "score", "valor", "peso")


def _match_header(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    """Busca en los encabezados del CSV la columna que coincida con la lista de candidatos."""
    normalized = {
        name.strip().lower().replace(" ", "_").replace("á", "a").replace("ó", "o"): name
        for name in fieldnames
    }
    for candidate in candidates:
        cand_norm = candidate.strip().lower().replace(" ", "_").replace("á", "a").replace("ó", "o")
        if cand_norm in normalized:
            return normalized[cand_norm]
    return None


def parse_students_data(raw_json_str: str) -> Dict[str, Dict[str, Any]]:
    """
    Convierte el JSON enviado desde el cliente (PapaParse) en el diccionario
    de matriculados esperado por identity.py: {codigo: {name, email}}.
    """
    students_raw = json.loads(raw_json_str)
    if not students_raw:
        return {}

    fieldnames = list(students_raw[0].keys())
    code_key = _match_header(fieldnames, _CODE_HEADERS)
    name_key = _match_header(fieldnames, _NAME_HEADERS)
    email_key = _match_header(fieldnames, _EMAIL_HEADERS)

    if not code_key:
        raise ValueError(f"CSV de estudiantes sin columna de código reconocible. Encabezados recibidos: {fieldnames}")

    students_dict = {}
    for row in students_raw:
        code = str(row.get(code_key, "")).strip()
        if not code:
            continue

        name = str(row.get(name_key, "")).strip() if name_key else "Desconocido"
        email = str(row.get(email_key, "")).strip() if email_key else ""

        students_dict[code] = {
            "name": name or "Desconocido",
            "email": email
        }

    return students_dict


def parse_answers_data(raw_json_str: str) -> Dict[int, Dict[str, Any]]:
    """
    Convierte el JSON enviado desde el cliente en la clave de respuestas
    esperada por scoring_engine.py: {question_id: {"correct_answer": "A", "points": 2.0}}.
    """
    respuestas_raw = json.loads(raw_json_str)
    if not respuestas_raw:
        return {}

    fieldnames = list(respuestas_raw[0].keys())
    q_key = _match_header(fieldnames, _QUESTION_HEADERS)
    c_key = _match_header(fieldnames, _CORRECT_HEADERS)
    p_key = _match_header(fieldnames, _POINTS_HEADERS)

    if not (q_key and c_key):
        raise ValueError(f"CSV de respuestas sin columnas de pregunta o clave reconocibles. Encabezados recibidos: {fieldnames}")

    answer_key = {}
    for row in respuestas_raw:
        raw_q = row.get(q_key)
        if raw_q is None:
            continue
        try:
            q_num = int(raw_q)
        except (ValueError, TypeError):
            continue

        raw_c = row.get(c_key)
        if not raw_c:
            continue
        key = str(raw_c).strip().upper()

        pts = 1.0
        if p_key and row.get(p_key) is not None:
            try:
                pts = float(row.get(p_key))
            except (ValueError, TypeError):
                pts = 1.0

        answer_key[q_num] = {
            "correct_answer": key,
            "points": pts
        }

    return answer_key

# ---------------------------------------------------------------------------
# Endpoints HTTP
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Sirve la interfaz del panel docente."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def process_exam(
    images: List[UploadFile] = File(...),
    alumnos_data: str = Form(...),
    respuestas_data: str = Form(...)
):
    """
    Endpoint principal de calificación. Recibe las imágenes de los exámenes
    y los datos estructurados en multipart/form-data, procesa en RAM y
    devuelve un Excel (.xlsx) con los resultados.
    """
    if not images or len(images) == 0:
        raise HTTPException(status_code=400, detail="No se enviaron imágenes de exámenes.")

    try:
        students_dict = parse_students_data(alumnos_data)
        answer_key = parse_answers_data(respuestas_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parseando datos de entrada: {str(e)}")

    if not answer_key:
        raise HTTPException(status_code=400, detail="La clave de respuestas no contiene preguntas válidas.")

    registros = []

    # -----------------------------------------------------------------------
    # Procesamiento Ficha por Ficha en Memoria (Map Step)
    # -----------------------------------------------------------------------
    for image_file in images:
        filename = image_file.filename or "ficha_sin_nombre.png"
        file_bytes = await image_file.read()

        if not file_bytes:
            registros.append({
                "filename": filename,
                "status": "ERROR",
                "issue_code": "CORRUPT_FILE",
                "student_code": "N/A",
                "student_name": "N/A",
                "score": None,
                "max_score": None,
                "percentage": None,
                "message": "El archivo de imagen está vacío."
            })
            continue

        # Decodificar imagen directamente en RAM
        img_np = np.frombuffer(file_bytes, np.uint8)
        img_bgr = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

        if img_bgr is None or img_bgr.size == 0:
            registros.append({
                "filename": filename,
                "status": "ERROR",
                "issue_code": "CORRUPT_FILE",
                "student_code": "N/A",
                "student_name": "N/A",
                "score": None,
                "max_score": None,
                "percentage": None,
                "message": "No se pudo decodificar la imagen (formato no soportado o corrupto)."
            })
            continue

        # 1. Capa de Visión (P2): Detección de marcadores y corrección de perspectiva
        vision_res = process_ficha(img_bgr, original_filename=filename)

        if vision_res.status == "ERROR":
            registros.append({
                "filename": filename,
                "status": "ERROR",
                "issue_code": vision_res.issue_code or "VISION_ERROR",
                "student_code": "N/A",
                "student_name": "N/A",
                "score": None,
                "max_score": None,
                "percentage": None,
                "message": vision_res.message
            })
            continue

        canonical_img = vision_res.canonical_image
        predictions = []

        # 2. Extracción de Crops en RAM e Inferencia con el modelo oficial (P1)
        # 2a. Crops de respuestas
        for key, center in template_contract.answers_centers.items():
            crop = extraer_recorte(canonical_img, center, template_contract.crop_size_px)
            pred = classify_bubble(crop)
            predictions.append({
                "crop_id": f"{filename}_{key}",
                "predicted_class": pred["predicted_class"],
                "confidence": pred["confidence"]
            })

        # 2b. Crops de identificación
        for key, center in template_contract.student_id_centers.items():
            crop = extraer_recorte(canonical_img, center, template_contract.crop_size_px)
            pred = classify_bubble(crop)
            predictions.append({
                "crop_id": f"{filename}_{key}",
                "predicted_class": pred["predicted_class"],
                "confidence": pred["confidence"]
            })

        # 3. Capa de Identidad (P3): Reconstrucción y validación contra matriculados
        identidad = identify_student(predictions, students_dict)

        if not identidad["identified"]:
            registros.append({
                "filename": filename,
                "status": "OBSERVED",
                "issue_code": identidad["issue_code"],
                "student_code": identidad["student_code"]["value"] or "N/A",
                "student_name": "Revisión requerida",
                "score": None,
                "max_score": None,
                "percentage": None,
                "message": identidad["processing_message"]
            })
            continue

        # 4. Capa de Calificación (P3): Evaluación de reglas por pregunta
        grouped_answers = group_answer_predictions(predictions)
        interpreted_questions = []

        for q_id in sorted(answer_key.keys()):
            opts = grouped_answers.get(q_id, {})
            interpreted = interpret_question(q_id, opts)
            interpreted_questions.append(interpreted)

        score_res = score_answers(interpreted_questions, answer_key)

        # Registro Examen Exitoso (OK)
        registros.append({
            "filename": filename,
            "status": "OK",
            "issue_code": None,
            "student_code": identidad["student_code"]["value"],
            "student_name": identidad["student_name"],
            "score": score_res["score"],
            "max_score": score_res["max_score"],
            "percentage": score_res["percentage"],
            "message": "Ficha procesada correctamente."
        })

    # -----------------------------------------------------------------------
    # Consolidación Global del Lote (Reduce Step: Detección de Duplicados)
    # -----------------------------------------------------------------------
    ok_codes = [r["student_code"] for r in registros if r["status"] == "OK"]
    duplicates = find_duplicate_codes(ok_codes)

    if duplicates:
        for reg in registros:
            if reg["status"] == "OK" and reg["student_code"] in duplicates:
                reg["status"] = "OBSERVED"
                reg["issue_code"] = "DUPLICATED_STUDENT_CODE"
                reg["score"] = None
                reg["max_score"] = None
                reg["percentage"] = None
                reg["message"] = f"El código {reg['student_code']} aparece en más de una ficha del lote."

    # -----------------------------------------------------------------------
    # Generación de Reporte Excel Multi-Pestaña en RAM
    # -----------------------------------------------------------------------
    ok_rows = [
        {
            "Código Estudiante": r["student_code"],
            "Nombre del Estudiante": r["student_name"],
            "Nota Final": r["score"],
            "Puntaje Máximo": r["max_score"],
            "Porcentaje (%)": r["percentage"],
            "Archivo Imagen": r["filename"]
        }
        for r in registros if r["status"] == "OK"
    ]

    obs_rows = [
        {
            "Archivo Imagen": r["filename"],
            "Estado": r["status"],
            "Código Detectado": r["student_code"],
            "Nombre / Referencia": r["student_name"],
            "Código de Incidencia": r["issue_code"] or "NINGUNA",
            "Detalle / Observación": r["message"]
        }
        for r in registros if r["status"] in ("OBSERVED", "ERROR")
    ]

    df_ok = pd.DataFrame(ok_rows if ok_rows else [{
        "Código Estudiante": "-",
        "Nombre del Estudiante": "Sin fichas calificadas OK",
        "Nota Final": 0,
        "Puntaje Máximo": 0,
        "Porcentaje (%)": 0,
        "Archivo Imagen": "-"
    }])

    df_obs = pd.DataFrame(obs_rows if obs_rows else [{
        "Archivo Imagen": "-",
        "Estado": "NINGUNO",
        "Código Detectado": "-",
        "Nombre / Referencia": "-",
        "Código de Incidencia": "-",
        "Detalle / Observación": "Sin observaciones ni errores en este lote"
    }])

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_ok.to_excel(writer, index=False, sheet_name='Calificaciones')
        df_obs.to_excel(writer, index=False, sheet_name='Observaciones_y_Errores')

    excel_buffer.seek(0)

    headers = {
        'Content-Disposition': 'attachment; filename="resultados_scanexam.xlsx"'
    }

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )