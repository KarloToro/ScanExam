# app/test_scoring_engine.py
"""
Pruebas del motor de reglas (scoring_engine). Cada caso mapea 1:1 con los
ejemplos de docs/informacion_relevante_entre_modulos/03_response_interpretation_rules.md
y con la política de confidence del ADR-0007.
"""

from app.scoring_engine import (
    interpret_question,
    grade_question,
    score_answers,
    group_answer_predictions,
)


def _opts(**kwargs):
    """Helper: _opts(A="EMPTY", B=("MARKED", 0.94)) -> dict de predicciones.
    Un string es solo la clase; una tupla es (clase, confidence)."""
    out = {}
    for option, value in kwargs.items():
        if isinstance(value, tuple):
            out[option] = {"predicted_class": value[0], "confidence": value[1]}
        else:
            out[option] = {"predicted_class": value, "confidence": None}
    return out


# ---------------------------------------------------------------------------
# Interpretación: los 4 casos del documento
# ---------------------------------------------------------------------------

def test_case1_single_mark_ignores_ghost_golden_rule():
    # A=EMPTY B=MARKED C=GHOST D=EMPTY E=EMPTY  (regla de oro: MARKED manda)
    result = interpret_question(1, _opts(
        A="EMPTY", B=("MARKED", 0.94), C=("GHOST", 0.5), D="EMPTY", E="EMPTY",
    ))
    assert result["mark_status"] == "SINGLE_MARK"
    assert result["detected_answer"] == "B"
    assert result["accepted_answer"] == "B"
    assert result["confidence"] == 0.94  # confidence de la única MARKED


def test_case2_blank():
    result = interpret_question(2, _opts(
        A="EMPTY", B="EMPTY", C="EMPTY", D="EMPTY", E="EMPTY",
    ))
    assert result["mark_status"] == "BLANK"
    assert result["detected_answer"] is None
    assert result["accepted_answer"] is None
    assert result["confidence"] is None


def test_case3_double_mark_confidence_is_min():
    # B=MARKED(0.9) C=MARKED(0.8) E=GHOST -> DOUBLE_MARK, confidence = min(MARKED)
    result = interpret_question(3, _opts(
        A="EMPTY", B=("MARKED", 0.9), C=("MARKED", 0.8), D="EMPTY", E=("GHOST", 0.7),
    ))
    assert result["mark_status"] == "DOUBLE_MARK"
    assert result["detected_answer"] == ["B", "C"]
    assert result["accepted_answer"] is None
    assert result["confidence"] == 0.8  # ADR-0007: min de las MARKED


def test_case4_uncertain_confidence_is_max_ghost():
    # solo GHOST -> UNCERTAIN, confidence = max(GHOST)
    result = interpret_question(4, _opts(
        A="EMPTY", B=("GHOST", 0.62), C=("GHOST", 0.4), D="EMPTY", E="EMPTY",
    ))
    assert result["mark_status"] == "UNCERTAIN"
    assert result["detected_answer"] is None
    assert result["accepted_answer"] is None
    assert result["confidence"] == 0.62  # ADR-0007: max de las GHOST


def test_missing_option_treated_as_empty():
    # Solo se entrega B; el resto ausente se asume EMPTY.
    result = interpret_question(5, {"B": {"predicted_class": "MARKED", "confidence": 0.88}})
    assert result["mark_status"] == "SINGLE_MARK"
    assert result["accepted_answer"] == "B"


def test_ghost_never_in_detected_answer():
    result = interpret_question(6, _opts(A=("GHOST", 0.9), B=("GHOST", 0.8)))
    assert result["detected_answer"] is None
    assert result["mark_status"] == "UNCERTAIN"


# ---------------------------------------------------------------------------
# Calificación contra la clave
# ---------------------------------------------------------------------------

def test_grade_correct():
    interpreted = interpret_question(1, _opts(B=("MARKED", 0.94)))
    graded = grade_question(interpreted, correct_answer="B", points=2)
    assert graded["question_status"] == "CORRECT"
    assert graded["earned_points"] == 2


def test_grade_incorrect():
    interpreted = interpret_question(1, _opts(C=("MARKED", 0.91)))
    graded = grade_question(interpreted, correct_answer="A", points=2)
    assert graded["question_status"] == "INCORRECT"
    assert graded["earned_points"] == 0


def test_grade_blank_gives_zero():
    interpreted = interpret_question(1, _opts(A="EMPTY", B="EMPTY"))
    graded = grade_question(interpreted, correct_answer="D", points=2)
    assert graded["question_status"] == "BLANK"
    assert graded["earned_points"] == 0


def test_grade_double_mark_gives_zero():
    interpreted = interpret_question(1, _opts(B=("MARKED", 0.9), C=("MARKED", 0.9)))
    graded = grade_question(interpreted, correct_answer="B", points=2)
    assert graded["question_status"] == "DOUBLE_MARK"
    assert graded["earned_points"] == 0  # aunque una MARKED sea la correcta, doble marca = 0


def test_grade_uncertain_gives_zero():
    interpreted = interpret_question(1, _opts(B=("GHOST", 0.62)))
    graded = grade_question(interpreted, correct_answer="B", points=2)
    assert graded["question_status"] == "UNCERTAIN"
    assert graded["earned_points"] == 0


# ---------------------------------------------------------------------------
# Agregación de la ficha
# ---------------------------------------------------------------------------

def test_score_answers_aggregation():
    q1 = interpret_question(1, _opts(B=("MARKED", 0.94)))   # correcta
    q2 = interpret_question(2, _opts(C=("MARKED", 0.91)))   # incorrecta
    answer_key = {
        1: {"correct_answer": "B", "points": 2},
        2: {"correct_answer": "A", "points": 2},
    }
    result = score_answers([q1, q2], answer_key)
    assert result["score"] == 2
    assert result["max_score"] == 4
    assert result["percentage"] == 50.0
    assert len(result["answers"]) == 2


# ---------------------------------------------------------------------------
# Determinismo (regla 15) y adaptador de crop_id
# ---------------------------------------------------------------------------

def test_determinism():
    preds = _opts(A="EMPTY", B=("MARKED", 0.9), C=("GHOST", 0.5), D="EMPTY", E="EMPTY")
    assert interpret_question(1, preds) == interpret_question(1, preds)


def test_group_answer_predictions_parses_and_ignores_identity():
    bubble_predictions = [
        {"crop_id": "ficha_001_q_01_A", "predicted_class": "EMPTY", "confidence": 0.9},
        {"crop_id": "ficha_001_q_01_B", "predicted_class": "MARKED", "confidence": 0.95},
        {"crop_id": "ficha_001_id_c08_v3", "predicted_class": "MARKED", "confidence": 0.9},
    ]
    grouped = group_answer_predictions(bubble_predictions)
    assert set(grouped.keys()) == {1}
    assert grouped[1]["B"]["predicted_class"] == "MARKED"
    assert "id_c08_v3" not in str(grouped)  # las de identificación se ignoran
