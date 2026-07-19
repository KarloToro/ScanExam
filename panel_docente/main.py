# panel_docente/main.py
"""
Panel docente (P4) — STUB DE INTEGRACIÓN.

Este archivo NO es el panel final: es un esqueleto mínimo, hecho por P3, que
**cierra el ciclo de punta a punta** para que la integración quede demostrable y
para que la responsable de P4 tenga un punto de partida claro de dónde enchufar
su trabajo.

Qué hace hoy (lo mínimo para cerrar el flujo):
  1. Muestra un formulario para subir el ZIP del lote.
  2. Aplica una **validación temprana (fail-fast)** de la estructura del ZIP.
  3. Extrae el lote y dispara el pipeline llamando al **webhook de n8n**.
  4. Muestra el resumen de `resultados.json` y permite descargarlo.

Qué le toca a P4 (marcado con `TODO(P4)` a lo largo del archivo):
  - Validación completa de CSV (encabezados, puntajes vacíos, duplicados…),
    según docs/especificacion_flujo/00_procesamiento_lote_zip.md.
  - Pantalla de progreso / estados en vivo.
  - Descarga de resultados.xlsx y reporte_observaciones_y_errores.xlsx.
  - Sitio de consulta e imágenes anotadas, estilos/UX y autenticación.

Arquitectura: este panel NO calcula nada. Habla con el pipeline por HTTP (la
misma API que orquesta n8n), respetando la separación de responsabilidades.
"""

from __future__ import annotations

import json
import os
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, send_file, url_for

app = Flask(__name__)

# --- Configuración (por entorno para funcionar dentro de Docker) ----------
WORKSPACE = Path(os.environ.get("SCANEXAM_WORKSPACE", "/workspace"))
UPLOADS_DIR = WORKSPACE / os.environ.get("SCANEXAM_UPLOADS_DIR", "uploads")
BATCHES_ROOT = WORKSPACE / "batches"
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/scanexam")

SUPPORTED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}


# ---------------------------------------------------------------------------
# Validación temprana (fail-fast) — responsabilidad de P4
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Estructura de lote inválida: se rechaza antes de procesar."""


def find_batch_root(extracted: Path) -> Path:
    """Ubica la carpeta que contiene Fichas/ (permite un nivel de anidamiento)."""
    if (extracted / "Fichas").is_dir():
        return extracted
    for child in sorted(extracted.iterdir()):
        if child.is_dir() and (child / "Fichas").is_dir():
            return child
    raise ValidationError("El ZIP no contiene una carpeta 'Fichas/'.")


def _single_csv(directory: Path, label: str) -> None:
    if not directory.is_dir():
        raise ValidationError(f"Falta la carpeta '{label}/' en el ZIP.")
    csvs = [p for p in directory.iterdir() if p.suffix.lower() == ".csv"]
    if len(csvs) != 1:
        raise ValidationError(
            f"'{label}/' debe contener exactamente un CSV (hay {len(csvs)}).")


def validate_source_structure(source: Path) -> None:
    """
    Reglas mínimas de aceptación (fail-fast). Rechaza el lote si no cumple.

    TODO(P4): ampliar con validación de contenido de los CSV
    (encabezados requeridos, puntajes no vacíos, códigos duplicados, etc.),
    ver docs/especificacion_flujo/00_procesamiento_lote_zip.md.
    """
    fichas = source / "Fichas"
    images = [p for p in fichas.iterdir()
              if p.suffix.lower() in SUPPORTED_IMAGE_EXT] if fichas.is_dir() else []
    if not images:
        raise ValidationError(
            "'Fichas/' no tiene imágenes válidas (.jpg, .jpeg, .png).")
    _single_csv(source / "Estudiantes", "Estudiantes")
    _single_csv(source / "Respuestas", "Respuestas")


# ---------------------------------------------------------------------------
# Disparo del pipeline vía webhook de n8n
# ---------------------------------------------------------------------------

def trigger_pipeline(batch_id: str, source_rel: str) -> dict:
    payload = json.dumps({"batch_id": batch_id, "source": source_rel}).encode("utf-8")
    req = urllib.request.Request(
        N8N_WEBHOOK_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------

# TODO(P4): reemplazar esta plantilla inline por templates/ + static/ (CSS/JS)
# y una UX real. Se deja inline para que el stub sea un solo archivo legible.
_PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel Docente — ScanExam (stub P4)</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
 .stub{background:#fff3cd;border:1px solid #ffe08a;padding:.6rem .9rem;border-radius:8px;font-size:.9rem}
 .err{background:#f8d7da;border:1px solid #f1aeb5;padding:.6rem .9rem;border-radius:8px}
 table{border-collapse:collapse;width:100%;margin-top:1rem}
 th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;font-size:.9rem}
 .OK{color:#0a7d28;font-weight:600}.OBSERVED{color:#b26a00;font-weight:600}.ERROR{color:#c02626;font-weight:600}
 button{padding:.5rem 1rem;border:0;background:#2b6cb0;color:#fff;border-radius:6px;cursor:pointer}
</style></head><body>
<h1>📄 Panel Docente — ScanExam</h1>
<p class="stub">⚠️ <b>Stub de integración (P4).</b> Sube un ZIP con
<code>Fichas/</code>, <code>Estudiantes/</code> y <code>Respuestas/</code>.
La UI final, reportes y sitio de consulta los construye P4.</p>

{% if error %}<p class="err">❌ {{ error }}</p>{% endif %}

<form method="post" action="{{ url_for('upload') }}" enctype="multipart/form-data">
  <p><input type="file" name="zip" accept=".zip" required></p>
  <p><button type="submit">Subir y procesar</button></p>
</form>

{% if resultados %}
  <h2>Resultados — {{ batch_id }}</h2>
  <p><a href="{{ url_for('download', batch_id=batch_id) }}">⬇️ Descargar resultados.json</a></p>
  <table><tr><th>Ficha</th><th>Estado</th><th>Estudiante</th><th>Nota</th><th>Incidencia</th></tr>
  {% for r in resultados %}
    <tr><td>{{ r.file }}</td>
        <td class="{{ r.processing_status }}">{{ r.processing_status }}</td>
        <td>{{ r.student_name or '—' }}</td>
        <td>{% if r.score is not none %}{{ r.score }}/{{ r.max_score }}{% else %}—{% endif %}</td>
        <td>{{ r.issue_code or '' }}</td></tr>
  {% endfor %}
  </table>
{% endif %}
</body></html>"""


@app.get("/")
def index():
    return render_template_string(_PAGE, error=None, resultados=None, batch_id=None)


@app.post("/upload")
def upload():
    file = request.files.get("zip")
    if not file or not file.filename.lower().endswith(".zip"):
        return render_template_string(_PAGE, error="Debes subir un archivo .zip.",
                                      resultados=None, batch_id=None), 400

    batch_id = "BATCH-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = UPLOADS_DIR / batch_id
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / "lote.zip"
    file.save(zip_path)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
        source = find_batch_root(dest)
        validate_source_structure(source)  # fail-fast
    except (ValidationError, zipfile.BadZipFile) as exc:
        return render_template_string(_PAGE, error=str(exc),
                                      resultados=None, batch_id=None), 400

    source_rel = source.relative_to(WORKSPACE).as_posix()
    try:
        response = trigger_pipeline(batch_id, source_rel)
    except Exception as exc:  # noqa: BLE001
        return render_template_string(
            _PAGE, error=f"El pipeline falló: {exc}", resultados=None, batch_id=None), 502

    resultados = (response.get("resultados") or {}).get("results", [])
    return render_template_string(_PAGE, error=None, resultados=resultados, batch_id=batch_id)


@app.get("/resultados/<batch_id>")
def download(batch_id: str):
    # TODO(P4): además de resultados.json, ofrecer resultados.xlsx y el
    # reporte_observaciones_y_errores.xlsx cuando P4 los genere.
    path = BATCHES_ROOT / batch_id / "output" / "resultados.json"
    if not path.exists():
        return redirect(url_for("index"))
    return send_file(path, as_attachment=True, download_name=f"{batch_id}_resultados.json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
