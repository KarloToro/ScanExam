# app/api.py
"""
API HTTP de scanexam-app (P3).

Expone las fases del pipeline como endpoints REST para que el orquestador n8n
(y, más adelante, el panel docente P4) las invoquen por HTTP en vez de ejecutar
comandos (ADR-0004, revisado: de Execute Command a HTTP para desacoplar n8n del
runtime de Python y reutilizar la misma API desde P4).

La lógica NO vive aquí: cada endpoint delega en core_pipeline. Este módulo es
solo la capa de transporte (HTTP <-> funciones del pipeline).

Endpoints:
    GET  /health                     -> liveness
    POST /pipeline/build-batch       {source, batch_id}   -> crea el BATCH
    POST /pipeline/run-vision        {batch_id}           -> P2: vision_manifest
    POST /pipeline/crops-classify    {batch_id}           -> crops + CNN
    POST /pipeline/score             {batch_id}           -> resultados.json
    POST /pipeline/run-all           {source, batch_id}   -> las 4 fases (demo)

Ejecuta:
    python -m app.api            (host 0.0.0.0, puerto 8000)
"""

from __future__ import annotations

import json
import traceback

from flask import Flask, jsonify, request

from app import core_pipeline

app = Flask(__name__)

DEFAULT_BATCHES_ROOT = core_pipeline.DEFAULT_BATCHES_ROOT


# ---------------------------------------------------------------------------
# Documentación OpenAPI + Swagger UI (sin dependencias extra: Swagger UI se
# carga por CDN desde el navegador). Disponible en /docs.
# ---------------------------------------------------------------------------

def _batch_body(*, with_source: bool) -> dict:
    props = {"batch_id": {"type": "string", "example": "BATCH-001"}}
    required = ["batch_id"]
    if with_source:
        props["source"] = {"type": "string", "example": "data/lotes_prueba/real",
                           "description": "ZIP ya extraído con Fichas/, Estudiantes/, Respuestas/."}
        required = ["source", "batch_id"]
    props["batches_root"] = {"type": "string", "default": "batches"}
    return {"required": True, "content": {"application/json": {"schema": {
        "type": "object", "required": required, "properties": props}}}}


_OK_RESPONSE = {"200": {"description": "OK",
                "content": {"application/json": {"schema": {"type": "object"}}}}}

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "ScanExam AI — Pipeline API (P3)",
        "version": "1.0.0",
        "description": "Fases del pipeline de corrección expuestas por HTTP. "
                       "Las consume n8n (orquestación) y el panel docente P4.",
    },
    "servers": [{"url": "http://localhost:8000"}],
    "tags": [{"name": "pipeline", "description": "Fases del procesamiento de lotes"},
             {"name": "sistema"}],
    "paths": {
        "/health": {"get": {"tags": ["sistema"], "summary": "Liveness",
                            "responses": _OK_RESPONSE}},
        "/pipeline/build-batch": {"post": {"tags": ["pipeline"],
            "summary": "Crea la estructura del BATCH desde un ZIP extraído",
            "requestBody": _batch_body(with_source=True), "responses": _OK_RESPONSE}},
        "/pipeline/run-vision": {"post": {"tags": ["pipeline"],
            "summary": "Fase P2: canoniza fichas y genera vision_manifest.json",
            "requestBody": _batch_body(with_source=False), "responses": _OK_RESPONSE}},
        "/pipeline/crops-classify": {"post": {"tags": ["pipeline"],
            "summary": "Fase P3: recorta burbujas y clasifica con la CNN",
            "requestBody": _batch_body(with_source=False), "responses": _OK_RESPONSE}},
        "/pipeline/score": {"post": {"tags": ["pipeline"],
            "summary": "Fase P3: identidad + reglas + calificación -> resultados.json",
            "requestBody": _batch_body(with_source=False), "responses": _OK_RESPONSE}},
        "/pipeline/run-all": {"post": {"tags": ["pipeline"],
            "summary": "Corre las 4 fases en secuencia (conveniencia para demo)",
            "requestBody": _batch_body(with_source=True), "responses": _OK_RESPONSE}},
    },
}

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ScanExam API — Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({
      url: '/openapi.json',
      dom_id: '#swagger-ui',
      deepLinking: true,
    });
  </script>
</body>
</html>"""


@app.get("/openapi.json")
def openapi_spec():
    return jsonify(OPENAPI_SPEC)


@app.get("/docs")
def docs():
    return _SWAGGER_HTML


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _require(data: dict, *keys: str) -> None:
    missing = [k for k in keys if not data.get(k)]
    if missing:
        raise ValueError(f"Faltan campos requeridos: {', '.join(missing)}")


@app.errorhandler(ValueError)
def _handle_value_error(exc: ValueError):
    return jsonify({"ok": False, "error": str(exc)}), 400


@app.errorhandler(Exception)
def _handle_error(exc: Exception):
    return jsonify({"ok": False, "error": str(exc),
                    "trace": traceback.format_exc()}), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/pipeline/build-batch")
def build_batch_endpoint():
    data = _body()
    _require(data, "source", "batch_id")
    batches_root = data.get("batches_root", DEFAULT_BATCHES_ROOT)
    bdir = core_pipeline.build_batch(data["source"], data["batch_id"], batches_root)
    manifest = json.loads((bdir / "batch_manifest.json").read_text(encoding="utf-8"))
    return jsonify({"ok": True, "batch_id": data["batch_id"],
                    "batch_dir": str(bdir), "manifest": manifest})


@app.post("/pipeline/run-vision")
def run_vision_endpoint():
    data = _body()
    _require(data, "batch_id")
    batches_root = data.get("batches_root", DEFAULT_BATCHES_ROOT)
    manifest_path = core_pipeline.run_vision(data["batch_id"], batches_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ok = sum(1 for e in manifest if e.get("status") == "OK")
    return jsonify({"ok": True, "batch_id": data["batch_id"],
                    "fichas": len(manifest), "ok_fichas": ok,
                    "vision_manifest": manifest})


@app.post("/pipeline/crops-classify")
def crops_classify_endpoint():
    data = _body()
    _require(data, "batch_id")
    batches_root = data.get("batches_root", DEFAULT_BATCHES_ROOT)
    result = core_pipeline.run_crops_classify(data["batch_id"], batches_root)
    return jsonify({"ok": True, "batch_id": data["batch_id"],
                    "classified_fichas": len(result["fichas"])})


@app.post("/pipeline/score")
def score_endpoint():
    data = _body()
    _require(data, "batch_id")
    batches_root = data.get("batches_root", DEFAULT_BATCHES_ROOT)
    resultados = core_pipeline.run_score(data["batch_id"], batches_root)
    # Resumen por estado para que n8n enrute (OK/OBSERVED/ERROR).
    summary: dict[str, int] = {}
    for r in resultados["results"]:
        summary[r["processing_status"]] = summary.get(r["processing_status"], 0) + 1
    return jsonify({"ok": True, "batch_id": data["batch_id"],
                    "summary": summary, "resultados": resultados})


@app.post("/pipeline/run-all")
def run_all_endpoint():
    """Conveniencia para demo: corre las 4 fases en secuencia."""
    data = _body()
    _require(data, "source", "batch_id")
    batches_root = data.get("batches_root", DEFAULT_BATCHES_ROOT)
    batch_id = data["batch_id"]
    core_pipeline.build_batch(data["source"], batch_id, batches_root)
    core_pipeline.run_vision(batch_id, batches_root)
    core_pipeline.run_crops_classify(batch_id, batches_root)
    resultados = core_pipeline.run_score(batch_id, batches_root)
    return jsonify({"ok": True, "batch_id": batch_id, "resultados": resultados})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
