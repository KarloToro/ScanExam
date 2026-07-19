# app/crops.py
"""
Extracción de recortes (P3) desde la ficha canónica usando la plantilla.

Responsabilidad (batch_contract): recorrer todos los centros de
`respuestas_centros.json` e `identificacion_centros.json`, generar los crops de
64x64 en `work/crops/` y construir el `crop_manifest.json`.

Alineación train/inferencia: se REUTILIZA `core_vision.extraer_recorte` — la
misma función con la que P1 construyó el dataset
(`app/dataset_builder/crear_dataset.py`). Así los recortes de inferencia son
idénticos, por construcción, a los de entrenamiento (mismo tamaño, mismo
centrado, mismo manejo de bordes). No se reimplementa el recorte.

Este módulo es la parte "map" (por ficha) del pipeline; el orquestador
(`core_pipeline.py`) lo paraleliza por ficha y consolida el manifiesto del lote.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import cv2

from app.core_vision import extraer_recorte
from app.template_loader import TemplateContract, load_template

# Formatos de las claves de centros en la plantilla.
_ANSWER_KEY_RE = re.compile(r"^q_(\d+)_([A-Z])$")
_IDENTITY_KEY_RE = re.compile(r"^id_c(\d+)_v(\d+)$")


def _describe_answer(key: str) -> dict[str, Any] | None:
    match = _ANSWER_KEY_RE.match(key)
    if not match:
        return None
    return {"kind": "answer", "question": int(match.group(1)), "option": match.group(2)}


def _describe_identity(key: str) -> dict[str, Any] | None:
    match = _IDENTITY_KEY_RE.match(key)
    if not match:
        return None
    return {"kind": "identity", "column": int(match.group(1)), "value": int(match.group(2))}


def crop_ficha(
    canonical_path: str | Path,
    crops_dir: str | Path,
    template: TemplateContract,
) -> dict[str, Any]:
    """
    Genera todos los recortes de una ficha canónica y devuelve su fragmento de
    manifiesto.

    - `canonical_path`: PNG canónico producido por P2 (work/normalized/ficha_XXX.png).
    - `crops_dir`: carpeta donde se escriben los PNG (work/crops/).
    - `template`: contrato de plantilla ya cargado (template_loader.load_template()).

    Devuelve:
        {
          "ficha": "ficha_001.png",
          "canonical_path": "...",
          "crop_size_px": 64,
          "crops": [
            {"crop_id": "ficha_001_q_01_A", "file": "ficha_001_q_01_A.png",
             "kind": "answer", "question": 1, "option": "A"},
            {"crop_id": "ficha_001_id_c08_v3", "file": "ficha_001_id_c08_v3.png",
             "kind": "identity", "column": 8, "value": 3},
            ...
          ]
        }
    """
    canonical_path = Path(canonical_path)
    crops_dir = Path(crops_dir)
    crops_dir.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(canonical_path))
    if image is None:
        raise ValueError(f"No se pudo leer la ficha canónica: {canonical_path}")

    height, width = image.shape[:2]
    if (width, height) != (template.canonical_width, template.canonical_height):
        # Las coordenadas de la plantilla solo aplican sobre la imagen canónica.
        raise ValueError(
            f"Tamaño canónico inválido para {canonical_path.name}: "
            f"{width}x{height}, se esperaba "
            f"{template.canonical_width}x{template.canonical_height}."
        )

    ficha_stem = canonical_path.stem  # p. ej. "ficha_001"
    crop_size = template.crop_size_px

    # Respuestas primero, luego identificación. Se preserva el orden estable de
    # las claves de la plantilla para que el manifiesto sea determinista.
    all_centers: list[tuple[str, list[int], dict[str, Any]]] = []
    for key, center in template.answers_centers.items():
        meta = _describe_answer(key)
        if meta:
            all_centers.append((key, center, meta))
    for key, center in template.student_id_centers.items():
        meta = _describe_identity(key)
        if meta:
            all_centers.append((key, center, meta))

    crops: list[dict[str, Any]] = []
    for key, center, meta in all_centers:
        crop = extraer_recorte(image, center, crop_size)  # reutiliza la función de P1
        crop_id = f"{ficha_stem}_{key}"
        filename = f"{crop_id}.png"
        cv2.imwrite(str(crops_dir / filename), crop)
        crops.append({"crop_id": crop_id, "file": filename, **meta})

    return {
        "ficha": canonical_path.name,
        "canonical_path": str(canonical_path),
        "crop_size_px": crop_size,
        "crops": crops,
    }


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera los crops de una ficha canónica (debug de una sola ficha)."
    )
    parser.add_argument("--canonical", required=True, help="Ruta al PNG canónico.")
    parser.add_argument("--out", required=True, help="Carpeta de salida de crops.")
    args = parser.parse_args()

    template = load_template()
    manifest = crop_ficha(args.canonical, args.out, template)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n{len(manifest['crops'])} crops escritos en {args.out}")


if __name__ == "__main__":
    _main()
