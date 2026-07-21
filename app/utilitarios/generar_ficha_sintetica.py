# app/utilitarios/generar_ficha_sintetica.py
"""
Genera una ficha sintética "bien llenada" sobre la plantilla canónica oficial.

Sirve para validar el camino OK del pipeline de forma determinista, sin depender
de la calidad de una foto real (que es terreno de P2). Como parte de la plantilla
`plantilla_referencia.png` (2100x1480, con los 4 marcadores nítidos), la imagen
pasa por TODO el pipeline —incluida la visión de P2— y produce un OK con nota.

Marca las burbujas usando las MISMAS coordenadas (template_loader) y el MISMO
orden de columnas (identity.reading_order_columns) que usa la reconstrucción,
por lo que el código resultante coincide exactamente con el solicitado.

Uso:
    python -m app.utilitarios.generar_ficha_sintetica \
        --code 22200100 --answers A,B,C,A,E,A,B,C,D,A \
        --output data/lotes_prueba/sintetico/Fichas/ficha_sintetica.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from app import config
from app.identity import reading_order_columns
from app.template_loader import load_template


def _mark(img, center, radius: int) -> None:
    # Círculo oscuro y sólido => clase MARKED para la CNN.
    cv2.circle(img, (int(center[0]), int(center[1])), radius, (45, 45, 45), -1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una ficha sintética llena.")
    parser.add_argument("--code", default="22200100", help="Código de estudiante (8 dígitos).")
    parser.add_argument("--answers", default="A,B,C,A,E,A,B,C,D,A",
                        help="Respuestas por pregunta 1..10, separadas por coma.")
    parser.add_argument("--output", required=True, help="Ruta de salida (.png).")
    parser.add_argument("--paper-tone", type=float, default=0.90,
                        help="Factor de brillo (blanco puro=1.0). <1 simula papel "
                             "real para pasar el control de brillo M2 de P2.")
    args = parser.parse_args()

    template = load_template()
    base_path = template.template_image_path
    img = cv2.imread(str(base_path))
    if img is None:
        raise SystemExit(f"No se pudo leer la plantilla de referencia: {base_path}")

    radius = max(8, template.bubble_diameter_px // 2 - 4)

    # --- Código de estudiante: 1 marca por columna, en el orden de lectura ---
    columns = reading_order_columns()
    if len(args.code) != len(columns):
        raise SystemExit(f"El código debe tener {len(columns)} dígitos: {args.code!r}")
    for digit, column in zip(args.code, columns):
        key = f"id_c{column:02d}_v{int(digit)}"
        center = template.student_id_centers.get(key)
        if center is None:
            raise SystemExit(f"No existe el centro de identificación {key}")
        _mark(img, center, radius)

    # --- Respuestas: 1 marca por pregunta ---
    answers = [a.strip().upper() for a in args.answers.split(",") if a.strip()]
    for q, option in enumerate(answers, start=1):
        if option not in config.OPTIONS:
            raise SystemExit(f"Opción inválida en la pregunta {q}: {option!r}")
        key = f"q_{q:02d}_{option}"
        center = template.answers_centers.get(key)
        if center is None:
            raise SystemExit(f"No existe el centro de respuesta {key}")
        _mark(img, center, radius)

    # Tono de papel: el blanco puro (255) supera el umbral de brillo M2 de P2.
    # Un factor <1 simula el gris ligero del papel/iluminación real.
    img = np.clip(img.astype(np.float32) * args.paper_tone, 0, 255).astype(np.uint8)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    print(f"Ficha sintética generada: {out}")
    print(f"  código={args.code}  respuestas={answers}")


if __name__ == "__main__":
    main()
