# app/test_core_pipeline.py
"""
Pruebas del orquestador (core_pipeline).

- build_batch: estructura del BATCH desde un ZIP extraído.
- run_score: end-to-end del scoring/identidad con predicciones fabricadas
  (sin modelo): OK, OBSERVED (no encontrado) y ERROR (visión).
- run_crops_classify: integración real con el modelo (se omite si falta).
"""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core_pipeline import build_batch, run_score, run_crops_classify
from app.identity import reading_order_columns

_MODEL = Path("models/bubble_classifier_v1.pt")


# --------------------------- helpers de predicciones ---------------------------

def _identity_preds(code, stem="ficha_001", conf=0.95):
    order = reading_order_columns()
    preds = []
    for digit, column in zip(code, order):
        for value in range(10):
            marked = str(value) == digit
            preds.append({
                "crop_id": f"{stem}_id_c{column:02d}_v{value}",
                "predicted_class": "MARKED" if marked else "EMPTY",
                "confidence": conf if marked else 0.99,
            })
    return preds


def _answer_preds(question, marked_option, stem="ficha_001", conf=0.95):
    preds = []
    for option in ["A", "B", "C", "D", "E"]:
        marked = option == marked_option
        preds.append({
            "crop_id": f"{stem}_q_{question:02d}_{option}",
            "predicted_class": "MARKED" if marked else "EMPTY",
            "confidence": conf if marked else 0.99,
        })
    return preds


def _make_batch(tmp_path, vision_manifest, bubble_predictions, students_csv, claves_csv):
    bdir = tmp_path / "BATCH-001"
    (bdir / "work").mkdir(parents=True)
    (bdir / "config").mkdir(parents=True)
    (bdir / "output").mkdir(parents=True)
    (bdir / "work" / "vision_manifest.json").write_text(json.dumps(vision_manifest), encoding="utf-8")
    (bdir / "work" / "bubble_predictions.json").write_text(json.dumps(bubble_predictions), encoding="utf-8")
    (bdir / "config" / "estudiantes_matriculados.csv").write_text(students_csv, encoding="utf-8")
    (bdir / "config" / "claves.csv").write_text(claves_csv, encoding="utf-8")
    return bdir


_OK_VISION = [{"file": "ficha_001.jpg", "status": "OK",
               "canonical_path": "work/normalized/ficha_001.png",
               "issue_code": None, "quality_metrics": None}]
_CLAVES = "pregunta,clave,puntaje\n1,B,2\n2,A,2\n"


def _predictions_for(code):
    preds = _identity_preds(code) + _answer_preds(1, "B") + _answer_preds(2, "C")
    return {"batch_id": "BATCH-001", "fichas": [
        {"file": "ficha_001.png", "stem": "ficha_001", "predictions": preds}]}


# --------------------------------- build_batch ---------------------------------

def test_build_batch_creates_structure(tmp_path):
    source = tmp_path / "extraido"
    (source / "Fichas").mkdir(parents=True)
    (source / "Estudiantes").mkdir(parents=True)
    (source / "Respuestas").mkdir(parents=True)
    cv2.imwrite(str(source / "Fichas" / "f1.jpg"), np.full((10, 10, 3), 255, np.uint8))
    (source / "Estudiantes" / "e.csv").write_text("Codigo,Nombre\n20240001,X\n", encoding="utf-8")
    (source / "Respuestas" / "r.csv").write_text(_CLAVES, encoding="utf-8")

    bdir = build_batch(source, "BATCH-001", batches_root=tmp_path / "batches")

    assert (bdir / "input" / "f1.jpg").exists()
    assert (bdir / "config" / "estudiantes_matriculados.csv").exists()
    assert (bdir / "config" / "claves.csv").exists()
    manifest = json.loads((bdir / "batch_manifest.json").read_text())
    assert manifest["input_count"] == 1


# --------------------------------- run_score -----------------------------------

def test_score_ok_ficha(tmp_path):
    students = "Codigo,Nombre,Correo\n20240001,Pedro Sota,pedro@example.com\n"
    _make_batch(tmp_path, _OK_VISION, _predictions_for("20240001"), students, _CLAVES)

    resultados = run_score("BATCH-001", batches_root=tmp_path)
    result = resultados["results"][0]

    assert result["processing_status"] == "OK"
    assert result["publishable"] is True
    assert result["student_name"] == "Pedro Sota"
    assert result["score"] == 2       # q1=B correcta (2), q2=C incorrecta (0)
    assert result["max_score"] == 4
    assert result["percentage"] == 50.0
    # resultados.json se escribió en output/
    assert (tmp_path / "BATCH-001" / "output" / "resultados.json").exists()


def test_score_observed_when_student_not_found(tmp_path):
    students = "Codigo,Nombre,Correo\n99999999,Otro,o@e.com\n"  # 20240001 no está
    _make_batch(tmp_path, _OK_VISION, _predictions_for("20240001"), students, _CLAVES)

    result = run_score("BATCH-001", batches_root=tmp_path)["results"][0]
    assert result["processing_status"] == "OBSERVED"
    assert result["issue_code"] == "STUDENT_NOT_FOUND"
    assert result["score"] is None


def test_score_error_ficha_from_vision(tmp_path):
    vision = [{"file": "ficha_009.jpg", "status": "ERROR", "canonical_path": None,
               "issue_code": "MARKERS_NOT_FOUND", "quality_metrics": None}]
    empty_preds = {"batch_id": "BATCH-001", "fichas": []}
    students = "Codigo,Nombre\n20240001,X\n"
    _make_batch(tmp_path, vision, empty_preds, students, _CLAVES)

    result = run_score("BATCH-001", batches_root=tmp_path)["results"][0]
    assert result["processing_status"] == "ERROR"
    assert result["issue_code"] == "MARKERS_NOT_FOUND"
    assert result["publishable"] is False


# ------------------------- run_crops_classify (con modelo) ---------------------

@pytest.mark.skipif(not _MODEL.exists(), reason="modelo no entrenado")
def test_crops_classify_produces_predictions(tmp_path, monkeypatch):
    # Ejecuta desde /workspace para que classify encuentre models/.
    monkeypatch.chdir("/workspace")
    template_size = (1480, 2100, 3)  # alto, ancho, canales (canónico)

    bdir = tmp_path / "BATCH-001"
    normalized = bdir / "work" / "normalized"
    normalized.mkdir(parents=True)
    cv2.imwrite(str(normalized / "ficha_001.png"), np.full(template_size, 255, np.uint8))
    (bdir / "work" / "vision_manifest.json").write_text(json.dumps(_OK_VISION), encoding="utf-8")

    result = run_crops_classify("BATCH-001", batches_root=tmp_path)

    assert len(result["fichas"]) == 1
    predictions = result["fichas"][0]["predictions"]
    assert len(predictions) == 130  # 50 respuestas (10x5) + 80 identificación (8x10)
    assert (bdir / "work" / "bubble_predictions.json").exists()
    assert (bdir / "work" / "crop_manifest.json").exists()
