# app/template_loader.py

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemplateContract:
    """
    Contrato cargado de una plantilla ScanExam.

    Este objeto concentra:
    - configuración general de la plantilla
    - centros de respuestas
    - centros de identificación
    - centros de marcadores
    - rutas absolutas a archivos de referencia
    """

    template_id: str
    template_dir: Path

    config: dict[str, Any]
    answers_centers: dict[str, list[int]]
    student_id_centers: dict[str, list[int]]
    marker_centers: dict[str, list[int]]

    template_pdf_path: Path | None
    template_image_path: Path | None

    canonical_width: int
    canonical_height: int
    bubble_diameter_px: int
    crop_size_px: int
    analysis_inner_radius_px: int


def find_project_root() -> Path:
    """
    Busca la raíz del proyecto subiendo carpetas hasta encontrar
    README.md y requirements.txt.
    """
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "README.md").exists() and (parent / "requirements.txt").exists():
            return parent

    raise RuntimeError(
        "No se pudo encontrar la raíz del proyecto. "
        "Verifica que README.md y requirements.txt existan en la raíz."
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo requerido: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def resolve_template_file(template_dir: Path, relative_path: str) -> Path:
    """
    Resuelve rutas relativas tomando como base la carpeta de la plantilla.
    """
    return template_dir / relative_path


def normalize_marker_centers(markers_data: dict[str, Any]) -> dict[str, list[int]]:
    """
    Soporta dos formatos para marcadores.

    Formato recomendado:
    {
        "marker_size_px": 100,
        "coordinate_type": "center",
        "markers": {
            "top_left": [180, 180],
            "top_right": [1920, 180],
            ...
        },
        "orientation_marker": "top_right"
    }

    Formato simple:
    {
        "top_left": [180, 180],
        "top_right": [1920, 180],
        ...
    }
    """
    if "markers" in markers_data:
        return markers_data["markers"]

    return {
        key: value
        for key, value in markers_data.items()
        if isinstance(value, list) and len(value) == 2
    }


def validate_center_dict(name: str, centers: dict[str, Any]) -> None:
    """
    Valida que todos los centros tengan formato [x, y].
    """
    for item_id, center in centers.items():
        if not isinstance(center, list) or len(center) != 2:
            raise ValueError(
                f"{name}: '{item_id}' debe tener formato [x, y]. Valor recibido: {center}"
            )

        x, y = center

        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(
                f"{name}: '{item_id}' debe usar coordenadas enteras. Valor recibido: {center}"
            )


def load_template(
    template_id: str = "ficha_optica_a5_horizontal_v1",
    project_root: Path | None = None,
) -> TemplateContract:
    """
    Carga la plantilla oficial de ScanExam.

    Uso esperado:
        template = load_template("ficha_optica_a5_horizontal_v1")

    Devuelve:
        - config
        - answers_centers
        - student_id_centers
        - marker_centers
        - rutas absolutas a PDF/PNG
        - parámetros útiles de tamaño y burbuja
    """
    if project_root is None:
        project_root = find_project_root()

    template_dir = project_root / "data" / "plantilla" / template_id
    config_path = template_dir / "template_config.json"

    config = load_json(config_path)

    if config["template_id"] != template_id:
        raise ValueError(
            f"El template_id solicitado es '{template_id}', "
            f"pero el config declara '{config['template_id']}'."
        )

    answers_path = resolve_template_file(
        template_dir,
        config["answers"]["centers_file"]
    )

    student_id_path = resolve_template_file(
        template_dir,
        config["student_id"]["centers_file"]
    )

    markers_path = resolve_template_file(
        template_dir,
        config["perspective"]["markers_file"]
    )

    answers_centers = load_json(answers_path)
    student_id_centers = load_json(student_id_path)
    markers_data = load_json(markers_path)
    marker_centers = normalize_marker_centers(markers_data)

    validate_center_dict("answers_centers", answers_centers)
    validate_center_dict("student_id_centers", student_id_centers)
    validate_center_dict("marker_centers", marker_centers)

    reference_files = config.get("reference_files", {})

    template_pdf_path = None
    if "template_pdf" in reference_files:
        template_pdf_path = resolve_template_file(
            template_dir,
            reference_files["template_pdf"]
        )

    template_image_path = None
    if "template_image" in reference_files:
        template_image_path = resolve_template_file(
            template_dir,
            reference_files["template_image"]
        )

    canonical_width = config["canonical_size"]["width_px"]
    canonical_height = config["canonical_size"]["height_px"]

    bubble_diameter_px = config["bubble"]["diameter_px"]
    crop_size_px = config["bubble"]["crop_size_px"]
    analysis_inner_radius_px = config["bubble"]["analysis_inner_radius_px"]

    return TemplateContract(
        template_id=template_id,
        template_dir=template_dir,
        config=config,
        answers_centers=answers_centers,
        student_id_centers=student_id_centers,
        marker_centers=marker_centers,
        template_pdf_path=template_pdf_path,
        template_image_path=template_image_path,
        canonical_width=canonical_width,
        canonical_height=canonical_height,
        bubble_diameter_px=bubble_diameter_px,
        crop_size_px=crop_size_px,
        analysis_inner_radius_px=analysis_inner_radius_px,
    )


if __name__ == "__main__":
    template = load_template()

    print("Plantilla cargada correctamente:")
    print(f"- Template ID: {template.template_id}")
    print(f"- Carpeta: {template.template_dir}")
    print(f"- Tamaño canónico: {template.canonical_width}x{template.canonical_height}")
    print(f"- Respuestas: {len(template.answers_centers)} centros")
    print(f"- Identificación: {len(template.student_id_centers)} centros")
    print(f"- Marcadores: {len(template.marker_centers)} centros")
    print(f"- Crop size: {template.crop_size_px}px")