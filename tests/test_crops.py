# app/test_crops.py
"""
Pruebas de crops.py. Usan la plantilla oficial real y una ficha canónica
sintética (imagen blanca del tamaño canónico) para verificar que:
- se generan todos los crops de respuestas + identificación,
- cada crop tiene exactamente crop_size x crop_size,
- el manifiesto describe correctamente pregunta/opción y columna/valor,
- se rechaza una imagen que no respeta el tamaño canónico.
"""

import cv2
import numpy as np
import pytest

from app.crops import crop_ficha
from app.template_loader import load_template


@pytest.fixture(scope="module")
def template():
    return load_template()


def _canonical_blank(path, template):
    """Crea una ficha canónica blanca del tamaño esperado."""
    image = np.full((template.canonical_height, template.canonical_width, 3), 255, np.uint8)
    cv2.imwrite(str(path), image)
    return path


def test_crops_count_matches_template(tmp_path, template):
    canonical = _canonical_blank(tmp_path / "ficha_001.png", template)
    manifest = crop_ficha(canonical, tmp_path / "crops", template)

    expected = len(template.answers_centers) + len(template.student_id_centers)
    assert len(manifest["crops"]) == expected
    assert manifest["ficha"] == "ficha_001.png"
    assert manifest["crop_size_px"] == template.crop_size_px


def test_every_crop_is_written_and_correct_size(tmp_path, template):
    canonical = _canonical_blank(tmp_path / "ficha_001.png", template)
    crops_dir = tmp_path / "crops"
    manifest = crop_ficha(canonical, crops_dir, template)

    size = template.crop_size_px
    for entry in manifest["crops"]:
        crop_path = crops_dir / entry["file"]
        assert crop_path.exists()
        crop = cv2.imread(str(crop_path))
        assert crop.shape[:2] == (size, size)


def test_answer_and_identity_metadata(tmp_path, template):
    canonical = _canonical_blank(tmp_path / "ficha_001.png", template)
    manifest = crop_ficha(canonical, tmp_path / "crops", template)

    by_id = {c["crop_id"]: c for c in manifest["crops"]}

    answer = by_id["ficha_001_q_01_A"]
    assert answer["kind"] == "answer"
    assert answer["question"] == 1
    assert answer["option"] == "A"

    identity = by_id["ficha_001_id_c08_v3"]
    assert identity["kind"] == "identity"
    assert identity["column"] == 8
    assert identity["value"] == 3


def test_rejects_non_canonical_size(tmp_path, template):
    wrong = tmp_path / "ficha_bad.png"
    cv2.imwrite(str(wrong), np.full((100, 100, 3), 255, np.uint8))
    with pytest.raises(ValueError):
        crop_ficha(wrong, tmp_path / "crops", template)
