# app/test_identity.py
"""
Pruebas de identity.py: reconstrucción del código, estados OBSERVED (Anexo D),
orden de lectura c08->c01, duplicados y carga flexible de Estudiantes.csv.
"""

import pytest

from app.identity import (
    identify_student,
    reconstruct_student_code,
    group_identity_predictions,
    find_duplicate_codes,
    load_students_csv,
    reading_order_columns,
)


def _preds_for_code(code, marked_conf=0.95, column_order=None):
    """Construye predicciones de identificación para un código dado.
    code[i] corresponde a la columna column_order[i] (orden de lectura)."""
    order = column_order or reading_order_columns()
    preds = []
    for digit, column in zip(code, order):
        for value in range(10):
            is_digit = str(value) == digit
            preds.append({
                "crop_id": f"ficha_001_id_c{column:02d}_v{value}",
                "predicted_class": "MARKED" if is_digit else "EMPTY",
                "confidence": marked_conf if is_digit else 0.99,
            })
    return preds


def test_reconstructs_and_identifies_student():
    preds = _preds_for_code("20240001")
    students = {"20240001": {"name": "Pedro Sota", "email": "pedro@example.com"}}
    result = identify_student(preds, students)
    assert result["identified"] is True
    assert result["status"] == "OK"
    assert result["student_code"]["value"] == "20240001"
    assert result["student_name"] == "Pedro Sota"
    assert result["email"] == "pedro@example.com"
    assert result["issue_code"] is None


def test_reading_order_round_trips():
    # Dígitos distintos por columna: solo cuadra si el orden c08->c01 se aplica bien.
    grouped = group_identity_predictions(_preds_for_code("12345678"))
    rec = reconstruct_student_code(grouped)
    assert rec["value"] == "12345678"
    assert rec["complete"] is True


def test_preserves_leading_zeros():
    rec = reconstruct_student_code(group_identity_predictions(_preds_for_code("00000042")))
    assert rec["value"] == "00000042"


def test_blank_column_is_observed_missing():
    preds = _preds_for_code("20240001")
    # Borra las marcas de la columna 5 (queda toda EMPTY).
    preds = [p for p in preds if not (p["crop_id"].split("_id_")[1].startswith("c05")
                                      and p["predicted_class"] == "MARKED")]
    result = identify_student(preds, {"20240001": {"name": "X", "email": "y"}})
    assert result["identified"] is False
    assert result["status"] == "OBSERVED"
    assert result["issue_code"] == "MISSING_STUDENT_CODE"
    assert result["student_code"]["value"] is None


def test_double_mark_column_is_observed_missing():
    preds = _preds_for_code("20240001")
    # Añade una segunda marca fuerte en la columna 3.
    for p in preds:
        if p["crop_id"].endswith("id_c03_v7"):
            p["predicted_class"] = "MARKED"
    result = identify_student(preds, {"20240001": {"name": "X", "email": "y"}})
    assert result["issue_code"] == "MISSING_STUDENT_CODE"


def test_golden_rule_single_mark_with_ghost_still_reconstructs():
    preds = _preds_for_code("20240001")
    # Añade un borrón GHOST en una columna que ya tiene su MARKED: no debe invalidar.
    for p in preds:
        if p["crop_id"].endswith("id_c04_v9"):
            p["predicted_class"] = "GHOST"
            p["confidence"] = 0.6
    result = identify_student(preds, {"20240001": {"name": "X", "email": "y"}})
    assert result["identified"] is True


def test_student_not_found_is_observed():
    preds = _preds_for_code("20240001")
    result = identify_student(preds, {})  # nadie matriculado
    assert result["identified"] is False
    assert result["issue_code"] == "STUDENT_NOT_FOUND"
    assert result["student_code"]["value"] == "20240001"  # el código sí se muestra


def test_group_identity_ignores_answer_crops():
    preds = [
        {"crop_id": "ficha_001_id_c08_v3", "predicted_class": "MARKED", "confidence": 0.9},
        {"crop_id": "ficha_001_q_01_A", "predicted_class": "MARKED", "confidence": 0.9},
    ]
    grouped = group_identity_predictions(preds)
    assert set(grouped.keys()) == {8}
    assert "3" in grouped[8]


def test_find_duplicate_codes():
    assert find_duplicate_codes(["A", "B", "A", None, "C", "B"]) == {"A", "B"}


def test_load_students_csv_flexible_headers(tmp_path):
    csv_path = tmp_path / "estudiantes.csv"
    csv_path.write_text(
        "Codigo,Nombre,Correo\n20240001,Pedro Sota,pedro@example.com\n",
        encoding="utf-8",
    )
    students = load_students_csv(csv_path)
    assert students["20240001"]["name"] == "Pedro Sota"
    assert students["20240001"]["email"] == "pedro@example.com"
