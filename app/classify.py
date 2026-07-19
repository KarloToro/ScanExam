# app/classify.py
"""
Clasificación de crops (P3) — adaptador sobre el clasificador de P1.

Toma los recortes generados por `crops.py` (los PNG en `work/crops/` descritos
en el fragmento de manifiesto) y ejecuta la CNN a través de
`core_classifier.classify_crops` (la función de contrato que dejó lista P1).

No reimplementa inferencia ni reglas: solo enruta cada crop a la CNN y devuelve
las predicciones puras `[{crop_id, predicted_class, confidence}]`, que consume
luego el `scoring_engine` (respuestas) y `identity` (identificación).

Es la parte "map" por ficha; el orquestador (`core_pipeline.py`) lo paraleliza y
consolida `bubble_predictions.json`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.core_classifier import classify_crops


def classify_crops_from_manifest(
    crop_manifest_fragment: dict[str, Any],
    crops_dir: str | Path,
) -> list[dict[str, Any]]:
    """
    Clasifica todos los crops de una ficha descritos en su fragmento de
    manifiesto.

    - `crop_manifest_fragment`: dict devuelto por `crops.crop_ficha`
      (contiene la lista `crops` con `crop_id` y `file`).
    - `crops_dir`: carpeta donde están los PNG (work/crops/).

    Devuelve: [{crop_id, predicted_class, confidence}, ...]
    """
    crops_dir = Path(crops_dir)
    crops = [
        {"crop_id": entry["crop_id"], "path": str(crops_dir / entry["file"])}
        for entry in crop_manifest_fragment["crops"]
    ]
    return classify_crops(crops)


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Clasifica los crops de una ficha a partir de su manifiesto (debug)."
    )
    parser.add_argument("--manifest", required=True, help="JSON del fragmento de manifiesto de la ficha.")
    parser.add_argument("--crops-dir", required=True, help="Carpeta con los PNG de crops.")
    args = parser.parse_args()

    fragment = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    predictions = classify_crops_from_manifest(fragment, args.crops_dir)
    print(json.dumps(predictions, indent=2, ensure_ascii=False))
    print(f"\n{len(predictions)} predicciones")


if __name__ == "__main__":
    _main()
