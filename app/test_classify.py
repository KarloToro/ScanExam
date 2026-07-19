# app/test_classify.py
"""
Prueba de integración de classify.py: verifica que el adaptador enruta
correctamente los crops a la CNN de P1 y devuelve el contrato esperado.

Requiere el modelo entrenado (models/bubble_classifier_v1.pt); si no existe,
la prueba se omite. Usa recortes reales del dataset como entrada y espera que
la clase predicha coincida con la carpeta de origen (mismo criterio que la
verificación 6/6 del paso 0).
"""

import shutil
from pathlib import Path

import pytest

from app.classify import classify_crops_from_manifest

_MODEL = Path("models/bubble_classifier_v1.pt")
pytestmark = pytest.mark.skipif(not _MODEL.exists(), reason="modelo no entrenado (models/bubble_classifier_v1.pt)")


def _sample(cls: str, n: int):
    return sorted(Path(f"data/dataset_burbujas/{cls}").glob("*.png"))[:n]


def test_classify_returns_contract_and_predicts_source_classes(tmp_path):
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()

    entries = []
    expected = {}
    for cls in ["MARKED", "EMPTY", "GHOST"]:
        for i, src in enumerate(_sample(cls, 2)):
            filename = f"{cls.lower()}_{i}.png"
            shutil.copy(src, crops_dir / filename)
            crop_id = f"{cls}_{i}"
            entries.append({"crop_id": crop_id, "file": filename})
            expected[crop_id] = cls

    predictions = classify_crops_from_manifest({"crops": entries}, crops_dir)

    assert len(predictions) == 6
    for pred in predictions:
        assert {"crop_id", "predicted_class", "confidence"} <= set(pred)
        assert 0.0 <= pred["confidence"] <= 1.0
        assert pred["predicted_class"] == expected[pred["crop_id"]]
