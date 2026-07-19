# app/scoring_engine.py
"""
Motor de reglas de interpretación y calificación (P3) — fuente de verdad.

Funciones puras y deterministas, SIN entrada/salida a disco: reciben datos ya
estructurados y devuelven datos. El parseo de archivos (bubble_predictions.json,
Respuestas.csv) vive en adaptadores finos, no en el núcleo. Esto hace al motor
100% testeable (ver app/test_scoring_engine.py).

Referencias:
- ADR-0001 (motor de reglas en Python).
- ADR-0007 (política de `confidence` por pregunta).
- docs/informacion_relevante_entre_modulos/03_response_interpretation_rules.md
"""

from __future__ import annotations

import re
from typing import Any

# --- Clases visuales que entrega la CNN ---
MARKED = "MARKED"
GHOST = "GHOST"
EMPTY = "EMPTY"

# --- Estados de marca (mark_status) ---
SINGLE_MARK = "SINGLE_MARK"
BLANK = "BLANK"
DOUBLE_MARK = "DOUBLE_MARK"
UNCERTAIN = "UNCERTAIN"

# --- Estados académicos (question_status) ---
CORRECT = "CORRECT"
INCORRECT = "INCORRECT"
# BLANK, DOUBLE_MARK y UNCERTAIN se reutilizan como question_status.

# crop_id de respuestas: "...q_01_A" -> pregunta 1, opción A.
_ANSWER_CROP_RE = re.compile(r"q_(\d+)_([A-Z])$")


def _round_conf(value: float | None) -> float | None:
    return round(float(value), 4) if value is not None else None


def interpret_question(
    question_id: int,
    option_predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Interpreta una pregunta a partir de las predicciones de sus alternativas.

    option_predictions: {"A": {"predicted_class": "MARKED", "confidence": 0.94}, ...}
    Una alternativa ausente se trata como EMPTY (robustez).

    Devuelve: {question_id, detected_answer, accepted_answer, mark_status, confidence}

    Orden de reglas (03_response_interpretation_rules.md, "Regla principal"):
      1. MARKED >= 2 -> DOUBLE_MARK
      2. MARKED == 1 -> SINGLE_MARK
      3. MARKED == 0 y GHOST >= 1 -> UNCERTAIN
      4. resto -> BLANK
    GHOST nunca se registra como detected_answer (regla 9).
    """
    marked: list[tuple[str, float | None]] = []
    ghost: list[tuple[str, float | None]] = []

    for option in sorted(option_predictions):
        prediction = option_predictions[option] or {}
        predicted_class = prediction.get("predicted_class", EMPTY)
        confidence = prediction.get("confidence")
        if predicted_class == MARKED:
            marked.append((option, confidence))
        elif predicted_class == GHOST:
            ghost.append((option, confidence))

    if len(marked) >= 2:
        mark_status = DOUBLE_MARK
        detected_answer: Any = [option for option, _ in marked]
        accepted_answer = None
        confs = [c for _, c in marked if c is not None]
        confidence = min(confs) if confs else None  # ADR-0007: min de las MARKED
    elif len(marked) == 1:
        mark_status = SINGLE_MARK
        option, conf = marked[0]
        detected_answer = option
        accepted_answer = option  # única MARKED se acepta aunque haya GHOST (regla de oro)
        confidence = conf
    elif len(ghost) >= 1:
        mark_status = UNCERTAIN
        detected_answer = None
        accepted_answer = None
        confs = [c for _, c in ghost if c is not None]
        confidence = max(confs) if confs else None  # ADR-0007: max de las GHOST
    else:
        mark_status = BLANK
        detected_answer = None
        accepted_answer = None
        confidence = None

    return {
        "question_id": question_id,
        "detected_answer": detected_answer,
        "accepted_answer": accepted_answer,
        "mark_status": mark_status,
        "confidence": _round_conf(confidence),
    }


def grade_question(
    interpreted: dict[str, Any],
    correct_answer: str,
    points: float,
) -> dict[str, Any]:
    """
    Califica una pregunta ya interpretada contra la clave del docente.

    Añade: correct_answer, question_status, points, earned_points.
    Solo SINGLE_MARK puede ganar puntos; BLANK/DOUBLE_MARK/UNCERTAIN dan 0.
    """
    mark_status = interpreted["mark_status"]
    accepted_answer = interpreted["accepted_answer"]

    if mark_status == SINGLE_MARK:
        if accepted_answer == correct_answer:
            question_status, earned_points = CORRECT, points
        else:
            question_status, earned_points = INCORRECT, 0
    elif mark_status == DOUBLE_MARK:
        question_status, earned_points = DOUBLE_MARK, 0
    elif mark_status == UNCERTAIN:
        question_status, earned_points = UNCERTAIN, 0
    else:  # BLANK
        question_status, earned_points = BLANK, 0

    return {
        "question_id": interpreted["question_id"],
        "detected_answer": interpreted["detected_answer"],
        "accepted_answer": accepted_answer,
        "correct_answer": correct_answer,
        "question_status": question_status,
        "points": points,
        "earned_points": earned_points,
        "confidence": interpreted["confidence"],
    }


def score_answers(
    interpreted_questions: list[dict[str, Any]],
    answer_key: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """
    Agrega las preguntas interpretadas en el bloque de notas de la ficha.

    answer_key: {question_id: {"correct_answer": "B", "points": 2}}.
    Devuelve: {answers, score, max_score, percentage}.
    Aplica solo a fichas con processing_status == OK (lo decide core_pipeline).
    """
    answers: list[dict[str, Any]] = []
    score: float = 0
    max_score: float = 0

    for question in interpreted_questions:
        key = answer_key[question["question_id"]]
        graded = grade_question(question, key["correct_answer"], key["points"])
        answers.append(graded)
        score += graded["earned_points"]
        max_score += graded["points"]

    percentage = round(100.0 * score / max_score, 2) if max_score else 0.0
    return {
        "answers": answers,
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
    }


def group_answer_predictions(
    bubble_predictions: list[dict[str, Any]],
) -> dict[int, dict[str, dict[str, Any]]]:
    """
    Adaptador (única parte que conoce el formato de crop_id).

    Agrupa las predicciones de burbujas de RESPUESTAS por pregunta:
      [{"crop_id": "ficha_001_q_01_A", "predicted_class": "MARKED", "confidence": 0.9}, ...]
      -> {1: {"A": {"predicted_class": "MARKED", "confidence": 0.9}, ...}, ...}

    Ignora las burbujas de identificación (id_cNN_vM), que maneja identity.py.
    """
    grouped: dict[int, dict[str, dict[str, Any]]] = {}
    for prediction in bubble_predictions:
        match = _ANSWER_CROP_RE.search(prediction.get("crop_id", ""))
        if not match:
            continue
        question_id = int(match.group(1))
        option = match.group(2)
        grouped.setdefault(question_id, {})[option] = {
            "predicted_class": prediction.get("predicted_class"),
            "confidence": prediction.get("confidence"),
        }
    return grouped
