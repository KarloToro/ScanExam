# 05_crear_template_config.py

import json
from pathlib import Path


def encontrar_raiz_proyecto() -> Path:
    """
    Busca la raíz del proyecto subiendo carpetas hasta encontrar
    archivos característicos del repo.
    """
    actual = Path(__file__).resolve()

    for parent in actual.parents:
        if (parent / "pyproject.toml").exists():
            return parent

    raise RuntimeError(
        "No se pudo encontrar la raíz del proyecto. "
        "Verifica que README.md y requirements.txt existan en la raíz."
    )


PROJECT_ROOT = encontrar_raiz_proyecto()

TEMPLATE_DIR = PROJECT_ROOT / "data" / "plantilla" / "ficha_optica_a5_horizontal_v1"
OUTPUT_FILE = TEMPLATE_DIR / "template_config.json"

CANONICAL_WIDTH = 2100
CANONICAL_HEIGHT = 1480

TEMPLATE_PDF = "FICHA_OPTICA_V1.pdf"
TEMPLATE_IMAGE = "plantilla_referencia.png"

config = {
    "schema_version": "1.0.0",
    "template_id": "ficha_optica_a5_horizontal_v1",
    "template_name": "Ficha Óptica A5 Horizontal v1",

    "canonical_size": {
        "width_px": CANONICAL_WIDTH,
        "height_px": CANONICAL_HEIGHT
    },

    "canonical_view": {
        "orientation": "landscape",
        "orientation_es": "horizontal",
        "reference_file": TEMPLATE_IMAGE,
        "semantic_layout": {
            "top": "encabezado de la ficha",
            "left": "bloque de identificación del estudiante",
            "right": "bloque de respuestas",
            "orientation_marker_position": "top_right"
        },
        "pipeline_contract": (
            "P2 debe transformar toda captura real a la imagen canónica definida "
            "en canonical_size antes de que P3 use los centros de burbujas."
        )
    },

    "physical_size": {
        "unit": "mm",
        "width": 210,
        "height": 148,
        "px_per_mm": 10,
        "dpi_reference": 254
    },

    "coordinate_system": {
        "applies_to": "canonical_image_after_perspective_correction",
        "origin": "top_left",
        "coordinate_order": "[x, y]",
        "x_axis": "right",
        "y_axis": "down",
        "unit": "px",
        "note": (
            "Las coordenadas se interpretan únicamente sobre la imagen canónica "
            "A5 horizontal. No aplicar sobre la foto cruda."
        )
    },

    "bubble": {
        "diameter_px": 48,
        "crop_size_px": 64,
        "analysis_inner_radius_px": 16,
        "center_source": (
            "Centro = X + 24, Y + 24 desde la esquina superior izquierda "
            "del círculo 48x48 en Figma."
        )
    },

    "student_id": {
        "columns": 8,
        "values": 10,
        "id_pattern": "id_c{column:02d}_v{value}",
        "reading_order": "c08_to_c01",
        "centers_file": "identificacion_centros.json"
    },

    "answers": {
        "questions": 10,
        "options": ["A", "B", "C", "D", "E"],
        "id_pattern": "q_{question:02d}_{option}",
        "centers_file": "respuestas_centros.json"
    },

    "perspective": {
        "markers_file": "marcadores_centros.json",
        "output_size_px": [CANONICAL_WIDTH, CANONICAL_HEIGHT],
        "method": "homography",
        "note": (
            "Los marcadores se usan para corregir perspectiva y generar "
            "la imagen canónica antes de leer burbujas."
        )
    },

    "reference_files": {
        "template_pdf": TEMPLATE_PDF,
        "template_image": TEMPLATE_IMAGE
    }
}


def validar_archivos_requeridos():
    archivos = [
        TEMPLATE_DIR / TEMPLATE_PDF,
        TEMPLATE_DIR / TEMPLATE_IMAGE,
        TEMPLATE_DIR / "identificacion_centros.json",
        TEMPLATE_DIR / "respuestas_centros.json",
        TEMPLATE_DIR / "marcadores_centros.json",
    ]

    faltantes = [archivo for archivo in archivos if not archivo.exists()]

    if faltantes:
        print("Advertencia: faltan algunos archivos referenciados por el template:")
        for archivo in faltantes:
            print(f"- {archivo}")
        print()
    else:
        print("Todos los archivos referenciados existen.")


def main():
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    validar_archivos_requeridos()

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

    print("template_config.json generado correctamente:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()