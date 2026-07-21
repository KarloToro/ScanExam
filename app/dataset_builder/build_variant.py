# app/dataset_builder/build_variant.py
"""
Construye una VARIANTE del dataset de burbujas a partir de un subconjunto de
fichas maestras, en una carpeta de salida propia.

Reutiliza el auto-etiquetado de `crear_dataset.py` (P1) sin modificarlo: sirve
para el demo de MLflow, donde se comparan entrenamientos con distintos conjuntos
de fichas (f1–f6, f1–f9, f1–f12) y se justifica la elección del champion.

Uso (dentro del contenedor scanexam-app):
    python app/dataset_builder/build_variant.py --output data/_exp/f1_f6 \
        fotos_crudas_dataset/f1_especial.jpeg fotos_crudas_dataset/f2_especial.jpeg ...
"""

import argparse
import sys
from pathlib import Path

import cv2

SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent
sys.path.append(str(APP_DIR))

from template_loader import load_template
from core_vision import process_ficha, extraer_recorte
from dataset_builder.crear_dataset import (
    obtener_etiqueta_respuesta,
    obtener_etiqueta_identificacion,
)


def build(photos, output_dir) -> int:
    template = load_template()
    crop_size = template.crop_size_px
    output_dir = Path(output_dir)
    for clase in ("EMPTY", "MARKED", "GHOST"):
        (output_dir / clase).mkdir(parents=True, exist_ok=True)

    total = 0
    for image_path in photos:
        image_path = Path(image_path)
        # Mismas banderas que crear_dataset.py (derivadas del nombre).
        es_recontra = image_path.stem.endswith("_recontra_especial")
        es_especial = image_path.stem.endswith("_especial") and not es_recontra

        resultado = process_ficha(image_path)
        if resultado.status != "OK":
            print(f"  SKIP {image_path.name}: {resultado.message}")
            continue
        canonica = resultado.canonical_image

        for bid, center in template.answers_centers.items():
            crop = extraer_recorte(canonica, center, crop_size)
            et = obtener_etiqueta_respuesta(bid, es_especial, es_recontra)
            cv2.imwrite(str(output_dir / et / f"{image_path.stem}_{bid}.png"), crop)
            total += 1
        for bid, center in template.student_id_centers.items():
            crop = extraer_recorte(canonica, center, crop_size)
            et = obtener_etiqueta_identificacion(bid, es_especial, es_recontra)
            cv2.imwrite(str(output_dir / et / f"{image_path.stem}_{bid}.png"), crop)
            total += 1
        print(f"  OK {image_path.name} ({'recontra_especial' if es_recontra else 'especial' if es_especial else 'normal'})")

    print(f"Dataset variante en {output_dir} ({total} crops)")
    return total


def main():
    parser = argparse.ArgumentParser(description="Construye una variante del dataset de burbujas.")
    parser.add_argument("--output", required=True, help="Carpeta de salida de la variante.")
    parser.add_argument("photos", nargs="+", help="Rutas de las fichas maestras a incluir.")
    args = parser.parse_args()
    build(args.photos, args.output)


if __name__ == "__main__":
    main()
