# app/core_pipeline.py
"""
Orquestador del pipeline de integración (P3).

Expone un CLI por fases que n8n invoca (ADR-0004):

    build-batch    --source <zip_extraido> --batch-id BATCH-001
    crops-classify --batch BATCH-001
    score          --batch BATCH-001

Modelo map -> reduce (ADR-0002): el trabajo por ficha es independiente; solo la
consolidación (códigos duplicados + resultados.json) necesita visión global del
lote. La extracción de crops se paraleliza con ProcessPoolExecutor (cv2 puro,
seguro para fork); la CNN corre en el proceso principal (modelo cargado una vez).

Este módulo NO reimplementa reglas ni visión: orquesta crops.py, classify.py,
identity.py y scoring_engine.py, y consume el vision_manifest.json de P2.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from app import config
from app import core_vision as vision_module
from app import crops as crops_module
from app import identity as identity_module
from app import scoring_engine
from app.classify import classify_crops_from_manifest
from app.template_loader import load_template

DEFAULT_BATCHES_ROOT = "batches"

# Encabezados aceptados en Respuestas.csv (detección flexible).
_QUESTION_HEADERS = ("pregunta", "numero", "nro", "n", "question", "id", "question_id")
_CORRECT_HEADERS = ("clave", "respuesta", "correcta", "respuesta_correcta", "correct", "correct_answer", "answer")
_POINTS_HEADERS = ("puntaje", "puntos", "points", "score", "valor", "peso")


# ---------------------------------------------------------------------------
# Rutas del lote
# ---------------------------------------------------------------------------

def batch_dir(batch_id: str, batches_root: str | Path = DEFAULT_BATCHES_ROOT) -> Path:
    return Path(batches_root) / batch_id


def _work_dir(bdir: Path) -> Path:
    return bdir / "work"


# ---------------------------------------------------------------------------
# Fase build-batch
# ---------------------------------------------------------------------------

def _single_csv(directory: Path) -> Path:
    csvs = sorted(p for p in directory.iterdir() if p.suffix.lower() == ".csv")
    if len(csvs) != 1:
        raise ValueError(f"Se esperaba exactamente un CSV en {directory}, hay {len(csvs)}.")
    return csvs[0]


def build_batch(
    source_dir: str | Path,
    batch_id: str,
    batches_root: str | Path = DEFAULT_BATCHES_ROOT,
) -> Path:
    """
    Crea la estructura interna del BATCH a partir de un ZIP ya extraído
    (Fichas/, Estudiantes/, Respuestas/). La validación fail-fast es de P4;
    aquí se asume una fuente estructuralmente válida.
    """
    source = Path(source_dir)
    bdir = batch_dir(batch_id, batches_root)
    input_dir = bdir / "input"
    config_dir = bdir / "config"
    for directory in (input_dir, config_dir, _work_dir(bdir), bdir / "output"):
        directory.mkdir(parents=True, exist_ok=True)

    fichas_dir = source / "Fichas"
    images = sorted(
        p for p in fichas_dir.iterdir()
        if p.suffix.lower() in config.SUPPORTED_INPUT_FORMATS
    )
    for image in images:
        shutil.copy(image, input_dir / image.name)

    shutil.copy(_single_csv(source / "Estudiantes"), config_dir / "estudiantes_matriculados.csv")
    shutil.copy(_single_csv(source / "Respuestas"), config_dir / "claves.csv")

    manifest = {
        "batch_id": batch_id,
        "created_by": "P3/core_pipeline",
        "input_count": len(images),
        "files": [image.name for image in images],
    }
    (bdir / "batch_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return bdir


# ---------------------------------------------------------------------------
# Fase run-vision (envoltura de integración de P2)
# ---------------------------------------------------------------------------

def run_vision(
    batch_id: str,
    batches_root: str | Path = DEFAULT_BATCHES_ROOT,
    template_id: str = config.TEMPLATE_ID,
) -> Path:
    """
    Fase de visión (P2) por lote. Es glue de integración: reúne las fotos de
    `input/` y delega en `core_vision.process_batch`, que canoniza cada ficha y
    escribe `work/vision_manifest.json` + `work/normalized/*.png`.

    No reimplementa nada de visión (responsabilidad exclusiva de P2); solo le da
    a P2 el contrato por lote que su CLI de depuración no expone. La
    paralelización de esta fase se difiere a una v2 (ver ADR-0002): para lotes
    pequeños el costo secuencial es despreciable y así respetamos el entrypoint
    oficial de P2 (`process_batch`, su Decisión 3.1).
    """
    bdir = batch_dir(batch_id, batches_root)
    input_dir = bdir / "input"
    work = _work_dir(bdir)
    images = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in config.SUPPORTED_INPUT_FORMATS
    )
    vision_module.process_batch(images, output_root=work, template_id=template_id)
    return work / "vision_manifest.json"


# ---------------------------------------------------------------------------
# Fase crops-classify
# ---------------------------------------------------------------------------

def _crop_worker(args: tuple[str, str, str]) -> dict[str, Any]:
    """Worker de ProcessPool: recorta una ficha. Debe ser top-level (picklable)."""
    canonical_path, crops_dir, template_id = args
    template = load_template(template_id)
    return crops_module.crop_ficha(canonical_path, crops_dir, template)


def run_crops_classify(
    batch_id: str,
    batches_root: str | Path = DEFAULT_BATCHES_ROOT,
    template_id: str = config.TEMPLATE_ID,
) -> dict[str, Any]:
    """
    Genera crops (paralelo) y clasifica (CNN, proceso principal) para las fichas
    OK del vision_manifest. Escribe crop_manifest.json y bubble_predictions.json.
    """
    bdir = batch_dir(batch_id, batches_root)
    work = _work_dir(bdir)
    crops_dir = work / "crops"

    vision_manifest = json.loads((work / "vision_manifest.json").read_text(encoding="utf-8"))
    ok_entries = [e for e in vision_manifest if e.get("status") == "OK" and e.get("canonical_path")]

    # MAP: crops en paralelo (una ficha por proceso).
    worker_args = [
        (str(bdir / entry["canonical_path"]), str(crops_dir), template_id)
        for entry in ok_entries
    ]
    if worker_args:
        with ProcessPoolExecutor() as executor:
            fragments = list(executor.map(_crop_worker, worker_args))
    else:
        fragments = []

    # CLASSIFY: en el proceso principal (modelo cargado una vez).
    fichas_predictions = []
    for fragment in fragments:
        predictions = classify_crops_from_manifest(fragment, crops_dir)
        fichas_predictions.append({
            "file": fragment["ficha"],
            "stem": Path(fragment["ficha"]).stem,
            "predictions": predictions,
        })

    crop_manifest: dict[str, Any] = {"batch_id": batch_id, "crop_size_px": None, "fichas": fragments}
    if fragments:
        crop_manifest["crop_size_px"] = fragments[0]["crop_size_px"]
    bubble_predictions = {"batch_id": batch_id, "fichas": fichas_predictions}

    (work / "crop_manifest.json").write_text(
        json.dumps(crop_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (work / "bubble_predictions.json").write_text(
        json.dumps(bubble_predictions, indent=2, ensure_ascii=False), encoding="utf-8")
    return bubble_predictions


# ---------------------------------------------------------------------------
# Fase score
# ---------------------------------------------------------------------------

def _match_header(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {name.strip().lower().replace(" ", "_"): name for name in fieldnames}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _as_number(value: str) -> float | int:
    number = float(value)
    return int(number) if number.is_integer() else number


def load_answer_key(path: str | Path) -> dict[int, dict[str, Any]]:
    """Carga Respuestas.csv a {question_id: {correct_answer, points}} (headers flexibles)."""
    path = Path(path)
    answer_key: dict[int, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        q_key = _match_header(fieldnames, _QUESTION_HEADERS)
        c_key = _match_header(fieldnames, _CORRECT_HEADERS)
        p_key = _match_header(fieldnames, _POINTS_HEADERS)
        if not (q_key and c_key and p_key):
            raise ValueError(f"Respuestas.csv sin columnas reconocibles. Encabezados: {fieldnames}")
        for row in reader:
            question_id = int(str(row[q_key]).strip())
            answer_key[question_id] = {
                "correct_answer": str(row[c_key]).strip().upper(),
                "points": _as_number(str(row[p_key]).strip()),
            }
    return answer_key


def _error_result(entry: dict[str, Any], stem: str) -> dict[str, Any]:
    return {
        "file": f"{stem}.png",
        "processing_status": "ERROR",
        "quality_status": "ERROR",
        "publishable": False,
        "student_code": {"value": None, "confidence": None},
        "student_name": None,
        "email": None,
        "score": None,
        "max_score": None,
        "percentage": None,
        "issue_code": entry.get("issue_code"),
        "processing_message": "La ficha no pudo procesarse visualmente (ver módulo de visión).",
        "answers": [],
    }


def _observed_result(stem: str, identity_result: dict[str, Any],
                     issue_code: str | None = None, message: str | None = None) -> dict[str, Any]:
    return {
        "file": f"{stem}.png",
        "processing_status": "OBSERVED",
        "quality_status": "OK",
        "publishable": False,
        "student_code": identity_result["student_code"],
        "student_name": None,
        "email": None,
        "score": None,
        "max_score": None,
        "percentage": None,
        "issue_code": issue_code or identity_result["issue_code"],
        "processing_message": message or identity_result["processing_message"],
        "answers": [],
    }


def _ok_result(stem: str, identity_result: dict[str, Any], scored: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": f"{stem}.png",
        "processing_status": "OK",
        "quality_status": "OK",
        "publishable": True,
        "student_code": identity_result["student_code"],
        "student_name": identity_result["student_name"],
        "email": identity_result["email"],
        "score": scored["score"],
        "max_score": scored["max_score"],
        "percentage": scored["percentage"],
        "issue_code": None,
        "processing_message": "Ficha procesada correctamente.",
        "answers": scored["answers"],
    }


def run_score(
    batch_id: str,
    batches_root: str | Path = DEFAULT_BATCHES_ROOT,
) -> dict[str, Any]:
    """
    Aplica identidad + reglas + calificación y consolida resultados.json.
    """
    bdir = batch_dir(batch_id, batches_root)
    work = _work_dir(bdir)
    config_dir = bdir / "config"

    vision_manifest = json.loads((work / "vision_manifest.json").read_text(encoding="utf-8"))
    bubble_predictions = json.loads((work / "bubble_predictions.json").read_text(encoding="utf-8"))
    predictions_by_stem = {f["stem"]: f["predictions"] for f in bubble_predictions["fichas"]}

    students = identity_module.load_students_csv(config_dir / "estudiantes_matriculados.csv")
    answer_key = load_answer_key(config_dir / "claves.csv")

    # Primer pase: identidad + interpretación (sin decidir estado final aún).
    interim: list[dict[str, Any]] = []
    identified_codes: list[str] = []
    for entry in vision_manifest:
        canonical = entry.get("canonical_path") or entry.get("file", "")
        stem = Path(canonical).stem
        if entry.get("status") != "OK":
            interim.append({"kind": "ERROR", "stem": stem, "entry": entry})
            continue

        preds = predictions_by_stem.get(stem, [])
        identity_result = identity_module.identify_student(preds, students)
        grouped = scoring_engine.group_answer_predictions(preds)
        interpreted = [scoring_engine.interpret_question(q, grouped[q]) for q in sorted(grouped)]
        interim.append({
            "kind": "PROCESSED", "stem": stem,
            "identity": identity_result, "interpreted": interpreted,
        })
        if identity_result["identified"]:
            identified_codes.append(identity_result["student_code"]["value"])

    # Reduce: códigos duplicados en el lote.
    duplicates = identity_module.find_duplicate_codes(identified_codes)

    # Segundo pase: ensamblar resultados y recognition_output.
    results: list[dict[str, Any]] = []
    recognition: list[dict[str, Any]] = []
    for item in interim:
        stem = item["stem"]
        if item["kind"] == "ERROR":
            results.append(_error_result(item["entry"], stem))
            continue

        identity_result = item["identity"]
        interpreted = item["interpreted"]
        recognition.append({
            "file": f"{stem}.png",
            "quality_status": "OK",
            "student_code": identity_result["student_code"],
            "identity_status": identity_result["status"],
            "issue_code": identity_result["issue_code"],
            "questions": interpreted,
        })

        code = identity_result["student_code"]["value"]
        if not identity_result["identified"]:
            results.append(_observed_result(stem, identity_result))
        elif code in duplicates:
            results.append(_observed_result(
                stem, identity_result,
                issue_code=identity_module.DUPLICATED_STUDENT_CODE,
                message=f"El código {code} aparece duplicado en el lote."))
        else:
            scored = scoring_engine.score_answers(interpreted, answer_key)
            results.append(_ok_result(stem, identity_result, scored))

    (work / "recognition_output.json").write_text(
        json.dumps({"batch_id": batch_id, "fichas": recognition}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    resultados = {"batch_id": batch_id, "generated_by": "P3/core_pipeline", "results": results}
    output_path = bdir / "output" / "resultados.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    return resultados


# ---------------------------------------------------------------------------
# CLI por fases (invocado por n8n)
# ---------------------------------------------------------------------------

def _main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline de integración ScanExam (P3).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build-batch", help="Crea la estructura BATCH desde un ZIP extraído.")
    p_build.add_argument("--source", required=True)
    p_build.add_argument("--batch-id", required=True)
    p_build.add_argument("--batches-root", default=DEFAULT_BATCHES_ROOT)

    p_vision = sub.add_parser("run-vision", help="Corre P2 (visión) sobre input/ del lote -> vision_manifest.json.")
    p_vision.add_argument("--batch", required=True)
    p_vision.add_argument("--batches-root", default=DEFAULT_BATCHES_ROOT)

    p_cc = sub.add_parser("crops-classify", help="Genera crops y clasifica burbujas.")
    p_cc.add_argument("--batch", required=True)
    p_cc.add_argument("--batches-root", default=DEFAULT_BATCHES_ROOT)

    p_score = sub.add_parser("score", help="Identidad + reglas + calificación -> resultados.json.")
    p_score.add_argument("--batch", required=True)
    p_score.add_argument("--batches-root", default=DEFAULT_BATCHES_ROOT)

    args = parser.parse_args()
    if args.command == "build-batch":
        path = build_batch(args.source, args.batch_id, args.batches_root)
        print(f"BATCH creado en {path}")
    elif args.command == "run-vision":
        path = run_vision(args.batch, args.batches_root)
        print(f"vision_manifest generado en {path}")
    elif args.command == "crops-classify":
        result = run_crops_classify(args.batch, args.batches_root)
        print(f"Clasificadas {len(result['fichas'])} fichas.")
    elif args.command == "score":
        result = run_score(args.batch, args.batches_root)
        print(f"resultados.json generado con {len(result['results'])} fichas.")


if __name__ == "__main__":
    _main()
