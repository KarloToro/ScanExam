# app/test_api.py
"""
Pruebas de la capa HTTP (app.api).

La API es solo transporte: se verifica el contrato HTTP (rutas, validación de
campos, forma de la respuesta) monkeypatcheando core_pipeline, sin correr el
pipeline real ni depender del modelo.
"""

import pytest

from app import api as api_module


@pytest.fixture
def client():
    api_module.app.config.update(TESTING=True)
    return api_module.app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_build_batch_delegates(client, monkeypatch, tmp_path):
    calls = {}

    def fake_build_batch(source, batch_id, batches_root):
        calls["args"] = (source, batch_id, batches_root)
        bdir = tmp_path / batch_id
        bdir.mkdir()
        (bdir / "batch_manifest.json").write_text('{"batch_id": "X", "input_count": 3}')
        return bdir

    monkeypatch.setattr(api_module.core_pipeline, "build_batch", fake_build_batch)

    resp = client.post("/pipeline/build-batch",
                       json={"source": "data/lotes_prueba/demo", "batch_id": "BATCH-1"})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["ok"] is True
    assert body["manifest"]["input_count"] == 3
    assert calls["args"] == ("data/lotes_prueba/demo", "BATCH-1", "batches")


def test_missing_required_field_returns_400(client):
    resp = client.post("/pipeline/build-batch", json={"batch_id": "BATCH-1"})  # falta source
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_openapi_spec_lists_pipeline_paths(client):
    body = client.get("/openapi.json").get_json()
    assert body["openapi"].startswith("3.")
    for path in ("/pipeline/build-batch", "/pipeline/run-vision",
                 "/pipeline/crops-classify", "/pipeline/score"):
        assert path in body["paths"]


def test_docs_serves_swagger_ui(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert b"swagger-ui" in resp.data


def test_score_summary_by_status(client, monkeypatch):
    def fake_run_score(batch_id, batches_root):
        return {"batch_id": batch_id, "results": [
            {"processing_status": "OK"}, {"processing_status": "OK"},
            {"processing_status": "OBSERVED"},
        ]}

    monkeypatch.setattr(api_module.core_pipeline, "run_score", fake_run_score)

    resp = client.post("/pipeline/score", json={"batch_id": "BATCH-1"})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["summary"] == {"OK": 2, "OBSERVED": 1}
