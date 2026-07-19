# panel_docente/test_panel.py
"""
Pruebas del stub del panel (P4): validación fail-fast y vista raíz.
No dispara el pipeline (eso se prueba end-to-end aparte).
"""

import pytest

from panel_docente import main as panel


def _make_source(tmp_path, *, fichas=("f1.jpg",), estudiantes=1, respuestas=1):
    root = tmp_path / "lote"
    (root / "Fichas").mkdir(parents=True)
    (root / "Estudiantes").mkdir(parents=True)
    (root / "Respuestas").mkdir(parents=True)
    for name in fichas:
        (root / "Fichas" / name).write_bytes(b"x")
    for i in range(estudiantes):
        (root / "Estudiantes" / f"e{i}.csv").write_text("Codigo\n1\n")
    for i in range(respuestas):
        (root / "Respuestas" / f"r{i}.csv").write_text("pregunta,clave,puntaje\n1,A,2\n")
    return root


def test_valid_structure_passes(tmp_path):
    source = _make_source(tmp_path)
    panel.validate_source_structure(source)  # no lanza


def test_missing_images_rejected(tmp_path):
    source = _make_source(tmp_path, fichas=())
    with pytest.raises(panel.ValidationError, match="im.genes"):
        panel.validate_source_structure(source)


def test_two_csv_in_estudiantes_rejected(tmp_path):
    source = _make_source(tmp_path, estudiantes=2)
    with pytest.raises(panel.ValidationError, match="Estudiantes"):
        panel.validate_source_structure(source)


def test_find_batch_root_handles_nesting(tmp_path):
    outer = tmp_path / "extraido"
    inner = _make_source(outer)  # crea extraido/lote/Fichas...
    assert panel.find_batch_root(outer) == inner


def test_index_page_renders():
    client = panel.app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Panel Docente" in resp.data
