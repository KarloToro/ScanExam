# app/identity.py
"""
Reconstrucción e identificación del estudiante (P3).

A partir de las predicciones de las burbujas de identificación (id_cNN_vM),
reconstruye el código de estudiante de 8 dígitos y decide si la ficha queda
`OK` (identificada) u `OBSERVED` (revisión docente), según el Anexo D del flujo.

Diseño:
- Cada columna del código es, estructuralmente, "una pregunta de 10 opciones"
  (v0..v9), así que se REUTILIZA `scoring_engine.interpret_question` por columna
  (misma lógica de marcas y regla de oro GHOST, ya testeada). Sin duplicar reglas.
- Reconstrucción estricta y confianza del código: ver ADR-0008.

Funciones puras + un adaptador de I/O (`load_students_csv`). La detección de
códigos duplicados en el lote es responsabilidad del reduce de `core_pipeline`;
aquí se aporta el helper `find_duplicate_codes`.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from app.config import MIN_STUDENT_CODE_CONFIDENCE
from app.scoring_engine import SINGLE_MARK, interpret_question

_IDENTITY_CROP_RE = re.compile(r"id_c(\d+)_v(\d+)$")

# issue_codes (subconjunto de config.ISSUE_CODES relevante a identidad)
MISSING_STUDENT_CODE = "MISSING_STUDENT_CODE"
LOW_STUDENT_CODE_CONFIDENCE = "LOW_STUDENT_CODE_CONFIDENCE"
STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"
DUPLICATED_STUDENT_CODE = "DUPLICATED_STUDENT_CODE"

_DEFAULT_READING_ORDER = "c08_to_c01"

# Encabezados aceptados en Estudiantes.csv (detección flexible).
_CODE_HEADERS = ("codigo", "código", "code", "student_code", "codigo_estudiante")
_NAME_HEADERS = ("nombre", "nombres", "name", "student_name", "apellidos_y_nombres", "nombre_completo")
_EMAIL_HEADERS = ("correo", "email", "mail", "e-mail", "correo_electronico")


def reading_order_columns(order: str = _DEFAULT_READING_ORDER, columns: int = 8) -> list[int]:
    """Convierte 'c08_to_c01' en [8, 7, ..., 1]. Descendente por defecto."""
    found = re.findall(r"c0*(\d+)", order)
    if len(found) >= 2:
        start, end = int(found[0]), int(found[1])
        step = 1 if end >= start else -1
        return list(range(start, end + step, step))
    return list(range(columns, 0, -1))


def group_identity_predictions(
    bubble_predictions: list[dict[str, Any]],
) -> dict[int, dict[str, dict[str, Any]]]:
    """
    Agrupa las predicciones de burbujas de IDENTIFICACIÓN por columna:
      [{"crop_id": "ficha_001_id_c08_v3", "predicted_class": "MARKED", ...}]
      -> {8: {"3": {"predicted_class": "MARKED", "confidence": ...}}, ...}
    Ignora las burbujas de respuestas (q_XX_Y).
    """
    grouped: dict[int, dict[str, dict[str, Any]]] = {}
    for prediction in bubble_predictions:
        match = _IDENTITY_CROP_RE.search(prediction.get("crop_id", ""))
        if not match:
            continue
        column = int(match.group(1))
        value = str(int(match.group(2)))  # normaliza "0".."9"
        grouped.setdefault(column, {})[value] = {
            "predicted_class": prediction.get("predicted_class"),
            "confidence": prediction.get("confidence"),
        }
    return grouped


def reconstruct_student_code(
    grouped: dict[int, dict[str, dict[str, Any]]],
    column_order: list[int] | None = None,
) -> dict[str, Any]:
    """
    Reconstruye el código a partir de las columnas agrupadas.

    Estricto (ADR-0008): requiere exactamente una marca (SINGLE_MARK) en TODAS
    las columnas. La confianza del código es el mínimo de las confianzas por
    columna (eslabón más débil).

    Devuelve: {value, confidence, columns, complete}
    """
    if column_order is None:
        column_order = reading_order_columns()

    columns_info: list[dict[str, Any]] = []
    digits: list[str] = []
    confidences: list[float] = []
    complete = True

    for column in column_order:
        option_predictions = grouped.get(column, {})
        interpreted = interpret_question(column, option_predictions)
        is_single = interpreted["mark_status"] == SINGLE_MARK
        digit = interpreted["accepted_answer"] if is_single else None

        columns_info.append({
            "column": column,
            "digit": digit,
            "mark_status": interpreted["mark_status"],
            "confidence": interpreted["confidence"],
        })

        if digit is None:
            complete = False
        else:
            digits.append(digit)
            if interpreted["confidence"] is not None:
                confidences.append(interpreted["confidence"])

    if not complete:
        return {"value": None, "confidence": None, "columns": columns_info, "complete": False}

    confidence = min(confidences) if confidences else None
    return {"value": "".join(digits), "confidence": confidence, "columns": columns_info, "complete": True}


def _observed(code: str | None, confidence: float | None, rec: dict[str, Any],
              issue_code: str, message: str) -> dict[str, Any]:
    return {
        "identified": False,
        "student_code": {"value": code, "confidence": confidence},
        "student_name": None,
        "email": None,
        "status": "OBSERVED",
        "issue_code": issue_code,
        "processing_message": message,
        "id_columns": rec["columns"],
    }


def identify_student(
    id_predictions: list[dict[str, Any]],
    students_by_code: dict[str, dict[str, Any]],
    column_order: list[int] | None = None,
) -> dict[str, Any]:
    """
    Decisión completa de identidad para una ficha (Anexo D).

    Precedencia: no-reconstruible -> baja-confianza -> no-encontrado.
    (El caso duplicado se resuelve a nivel de lote en core_pipeline.)
    """
    grouped = group_identity_predictions(id_predictions)
    rec = reconstruct_student_code(grouped, column_order)
    code = rec["value"]
    confidence = rec["confidence"]

    if not rec["complete"]:
        return _observed(None, None, rec, MISSING_STUDENT_CODE,
                         "No se pudo reconstruir el código completo del estudiante.")

    if confidence is not None and confidence < MIN_STUDENT_CODE_CONFIDENCE:
        return _observed(code, confidence, rec, LOW_STUDENT_CODE_CONFIDENCE,
                         "La confianza del código del estudiante es demasiado baja.")

    student = students_by_code.get(code)
    if student is None:
        return _observed(code, confidence, rec, STUDENT_NOT_FOUND,
                         f"El código {code} no está en la lista de estudiantes matriculados.")

    return {
        "identified": True,
        "student_code": {"value": code, "confidence": confidence},
        "student_name": student.get("name"),
        "email": student.get("email"),
        "status": "OK",
        "issue_code": None,
        "processing_message": "Estudiante identificado correctamente.",
        "id_columns": rec["columns"],
    }


def find_duplicate_codes(codes: list[str | None]) -> set[str]:
    """Devuelve los códigos que aparecen en más de una ficha del lote."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for code in codes:
        if code is None:
            continue
        if code in seen:
            duplicates.add(code)
        seen.add(code)
    return duplicates


def _match_header(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {name.strip().lower().replace(" ", "_"): name for name in fieldnames}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def load_students_csv(path: str | Path) -> dict[str, dict[str, Any]]:
    """
    Adaptador de I/O: carga Estudiantes.csv a {code: {name, email}}.
    Detecta las columnas por encabezado de forma flexible (código/nombre/correo).
    """
    path = Path(path)
    students: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        code_key = _match_header(fieldnames, _CODE_HEADERS)
        if code_key is None:
            raise ValueError(
                f"Estudiantes.csv sin columna de código reconocible. "
                f"Encabezados: {fieldnames}"
            )
        name_key = _match_header(fieldnames, _NAME_HEADERS)
        email_key = _match_header(fieldnames, _EMAIL_HEADERS)

        for row in reader:
            code = str(row[code_key]).strip()
            if not code:
                continue
            students[code] = {
                "name": row[name_key].strip() if name_key else None,
                "email": row[email_key].strip() if email_key else None,
            }
    return students


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Identifica un estudiante desde bubble_predictions + Estudiantes.csv (debug)."
    )
    parser.add_argument("--predictions", required=True, help="JSON con [{crop_id, predicted_class, confidence}].")
    parser.add_argument("--students", required=True, help="Ruta a Estudiantes.csv.")
    args = parser.parse_args()

    predictions = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    students = load_students_csv(args.students)
    result = identify_student(predictions, students)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
