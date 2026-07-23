# validar_centros.py

import json, time
from pathlib import Path

import cv2


TEMPLATE_ID = "ficha_optica_a5_horizontal_v1"

DRAW_CROP_BOX = True
DRAW_LABELS = False

# Colores en formato BGR porque OpenCV usa BGR, no RGB
COLOR_RESPUESTAS = (0, 180, 0)          # verde
COLOR_IDENTIFICACION = (255, 120, 0)    # azul claro/naranja visual
COLOR_MARCADORES = (0, 0, 255)          # rojo
COLOR_CROP = (180, 180, 180)            # gris
COLOR_TEXT = (237, 40, 237)             # morado


def encontrar_raiz_proyecto() -> Path:
    actual = Path(__file__).resolve()

    for parent in actual.parents:
        if (parent / "pyproject.toml").exists():
            return parent

    raise RuntimeError(
        "No se pudo encontrar la raíz del proyecto. "
        "Verifica que README.md y requirements.txt existan en la raíz."
    )


def cargar_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def resolver_ruta(template_dir: Path, relative_path: str) -> Path:
    return template_dir / relative_path


def validar_tamano_imagen(image, expected_width: int, expected_height: int):
    height, width = image.shape[:2]

    if width != expected_width or height != expected_height:
        raise ValueError(
            "La imagen de referencia no coincide con canonical_size.\n"
            f"Esperado: {expected_width}x{expected_height}px\n"
            f"Encontrado: {width}x{height}px\n"
            "Exporta plantilla_referencia.png desde Figma con el tamaño exacto."
        )


def extraer_marcadores(markers_data: dict) -> dict:
    """
    Soporta dos formatos:

    Formato recomendado:
    {
        "marker_size_px": 100,
        "coordinate_type": "center",
        "markers": {
            "top_left": [180, 180],
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


def punto_en_imagen(center, width: int, height: int) -> bool:
    x, y = center
    return 0 <= x < width and 0 <= y < height


def dibujar_centro(
    image,
    bubble_id: str,
    center,
    color,
    crop_size: int | None = None,
    draw_crop_box: bool = False,
    draw_label: bool = False,
):
    cx, cy = int(round(center[0])), int(round(center[1]))

    # Punto central
    cv2.circle(image, (cx, cy), 5, color, thickness=-1)

    # Círculo guía alrededor del centro
    cv2.circle(image, (cx, cy), 12, color, thickness=2)

    # Caja de recorte esperada
    if draw_crop_box and crop_size is not None:
        half = crop_size // 2

        x1 = cx - half
        y1 = cy - half
        x2 = x1 + crop_size
        y2 = y1 + crop_size

        cv2.rectangle(image, (x1, y1), (x2, y2), COLOR_CROP, thickness=1)

    # Etiqueta opcional
    if draw_label:
        cv2.putText(
            image,
            bubble_id,
            (cx + 8, cy - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            COLOR_TEXT,
            1,
            cv2.LINE_AA,
        )


def validar_y_dibujar_grupo(
    image,
    centers: dict,
    group_name: str,
    color,
    crop_size: int | None,
    draw_crop_box: bool,
    draw_labels: bool,
) -> list[str]:
    height, width = image.shape[:2]
    errores = []

    for item_id, center in centers.items():
        if not isinstance(center, list) or len(center) != 2:
            errores.append(f"{group_name}: {item_id} no tiene formato [x, y].")
            continue

        if not punto_en_imagen(center, width, height):
            errores.append(
                f"{group_name}: {item_id} está fuera de imagen: {center}"
            )
            continue

        dibujar_centro(
            image=image,
            bubble_id=item_id,
            center=center,
            color=color,
            crop_size=crop_size,
            draw_crop_box=draw_crop_box,
            draw_label=draw_labels,
        )

    return errores


def main():
    inicio = time.perf_counter()
    project_root = encontrar_raiz_proyecto()

    template_dir = (
        project_root
        / "data"
        / "plantilla"
        / TEMPLATE_ID
    )

    template_config_path = template_dir / "template_config.json"
    config = cargar_json(template_config_path)

    canonical_width = config["canonical_size"]["width_px"]
    canonical_height = config["canonical_size"]["height_px"]

    reference_image_name = config["reference_files"]["template_image"]
    reference_image_path = resolver_ruta(template_dir, reference_image_name)

    answers_path = resolver_ruta(
        template_dir,
        config["answers"]["centers_file"]
    )

    student_id_path = resolver_ruta(
        template_dir,
        config["student_id"]["centers_file"]
    )

    markers_path = resolver_ruta(
        template_dir,
        config["perspective"]["markers_file"]
    )

    output_dir = project_root / "docs" / "evidencia_capturas"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "validacion_centros_v1.png"

    image = cv2.imread(str(reference_image_path))

    if image is None:
        raise FileNotFoundError(
            f"No se pudo cargar la imagen de referencia: {reference_image_path}"
        )

    validar_tamano_imagen(
        image=image,
        expected_width=canonical_width,
        expected_height=canonical_height,
    )

    answers_centers = cargar_json(answers_path)
    student_id_centers = cargar_json(student_id_path)
    markers_data = cargar_json(markers_path)
    markers_centers = extraer_marcadores(markers_data)

    crop_size = config["bubble"]["crop_size_px"]

    errores = []

    errores += validar_y_dibujar_grupo(
        image=image,
        centers=answers_centers,
        group_name="respuestas",
        color=COLOR_RESPUESTAS,
        crop_size=crop_size,
        draw_crop_box=DRAW_CROP_BOX,
        draw_labels=DRAW_LABELS,
    )

    errores += validar_y_dibujar_grupo(
        image=image,
        centers=student_id_centers,
        group_name="identificacion",
        color=COLOR_IDENTIFICACION,
        crop_size=crop_size,
        draw_crop_box=DRAW_CROP_BOX,
        draw_labels=DRAW_LABELS,
    )

    errores += validar_y_dibujar_grupo(
        image=image,
        centers=markers_centers,
        group_name="marcadores",
        color=COLOR_MARCADORES,
        crop_size=None,
        draw_crop_box=False,
        draw_labels=True,
    )

    cv2.imwrite(str(output_path), image)

    print("Validación visual generada correctamente:")
    print(output_path)
    print()

    print("Resumen:")
    print(f"- Respuestas: {len(answers_centers)} centros")
    print(f"- Identificación: {len(student_id_centers)} centros")
    print(f"- Marcadores: {len(markers_centers)} centros")
    print(f"- Crop size usado: {crop_size}px")
    print()

    if errores:
        print("Advertencias encontradas:")
        for error in errores:
            print(f"- {error}")
    else:
        print("No se encontraron errores de formato ni puntos fuera de imagen.")
    fin = time.perf_counter()
    tiempo_total = fin - inicio
    print(f"Tiempo de ejecución: {tiempo_total:.4f} segundos")

if __name__ == "__main__":
    main()