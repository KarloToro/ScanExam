# app/run_pruebas.py
"""
Corre las 3 fases de P2 (marcadores -> warp -> calidad) sobre todas las
fotos en pruebas/ y guarda el debug visual de cada una organizado en
su propia carpeta dentro de debug/, en vez de sobrescribir archivos
fijos en cada corrida.

Uso (desde app/):
    python run_pruebas.py

Estructura esperada:
    app/
      pruebas/
        prueba1.jpg
        prueba2.jpeg
        prueba3.png
        ...
      debug/
        prueba1/
          01_marcadores.png
          02_canonical.png
          03_canonical_marcadores.png
          04_marker_rois.png
        prueba2/
          ...
"""

import csv
import re
from pathlib import Path

import cv2

import config
import template_loader
from core_vision import (
    correct_perspective,
    detect_and_autorotate,
    draw_canonical_debug,
    draw_detection_debug,
    draw_marker_roi_debug,
    validate_canonical_quality,
)

BASE_DIR = Path(__file__).resolve().parent
PRUEBAS_DIR = BASE_DIR / "pruebas"
DEBUG_DIR = BASE_DIR / "debug"

VALID_EXTENSIONS = {ext.lower() for ext in config.SUPPORTED_INPUT_FORMATS}


def _extract_number(path: Path) -> int:
    """Permite ordenar prueba2 antes que prueba10 (orden natural, no alfabético)."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def _find_pruebas() -> list[Path]:
    if not PRUEBAS_DIR.exists():
        raise FileNotFoundError(f"No existe la carpeta de pruebas: {PRUEBAS_DIR}")

    archivos = [
        path for path in PRUEBAS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS
    ]

    return sorted(archivos, key=_extract_number)


def procesar_prueba(path: Path, template) -> dict:
    """
    Corre las 3 fases sobre una foto y guarda su debug en
    debug/<nombre_prueba>/. Retorna un resumen en dict para la tabla final.
    """
    output_dir = DEBUG_DIR / path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    resumen = {
        "prueba": path.stem,
        "marcadores": None,
        "rotacion_grados": 0,
        "warp": None,
        "calidad": None,
        "detalle": "",
    }

    raw_image = cv2.imread(str(path))

    if raw_image is None:
        resumen["marcadores"] = "ERROR_LECTURA"
        resumen["detalle"] = f"No se pudo leer el archivo: {path.name}"
        return resumen

    # --- Fase 1: marcadores (con auto-rotación) ---
    imagen_final, deteccion, grados_rotados = detect_and_autorotate(raw_image)
    resumen["marcadores"] = deteccion.status
    resumen["rotacion_grados"] = grados_rotados

    debug_marcadores = draw_detection_debug(imagen_final, deteccion)
    cv2.imwrite(str(output_dir / "01_marcadores.png"), debug_marcadores)

    if deteccion.status != "OK":
        resumen["detalle"] = deteccion.message
        return resumen

    # --- Fase 2: warp ---
    warp = correct_perspective(
        image=imagen_final,
        detected_points=deteccion.ordered_points,
        marker_centers=template.marker_centers,
        canonical_width=template.canonical_width,
        canonical_height=template.canonical_height,
    )
    resumen["warp"] = warp.status

    if warp.status != "OK":
        resumen["detalle"] = warp.message
        return resumen

    cv2.imwrite(str(output_dir / "02_canonical.png"), warp.canonical_image)

    debug_canonico = draw_canonical_debug(warp.canonical_image, template.marker_centers)
    cv2.imwrite(str(output_dir / "03_canonical_marcadores.png"), debug_canonico)

    # --- Fase 3: calidad ---
    calidad = validate_canonical_quality(
        canonical_image=warp.canonical_image,
        marker_centers=template.marker_centers,
    )
    resumen["calidad"] = calidad.status

    if calidad.status != "OK":
        resumen["detalle"] = calidad.message

    debug_rois = draw_marker_roi_debug(warp.canonical_image, template.marker_centers)
    cv2.imwrite(str(output_dir / "04_marker_rois.png"), debug_rois)

    return resumen


def imprimir_resumen(resultados: list[dict]) -> None:
    encabezado = f"{'prueba':<12}{'marcadores':<20}{'rot°':<6}{'warp':<15}{'calidad':<15}detalle"
    print(encabezado)
    print("-" * len(encabezado))

    for r in resultados:
        print(
            f"{r['prueba']:<12}"
            f"{str(r['marcadores']):<20}"
            f"{str(r['rotacion_grados']):<6}"
            f"{str(r['warp']):<15}"
            f"{str(r['calidad']):<15}"
            f"{r['detalle']}"
        )


def guardar_resumen_csv(resultados: list[dict]) -> None:
    csv_path = DEBUG_DIR / "resumen.csv"
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["prueba", "marcadores", "rotacion_grados", "warp", "calidad", "detalle"],
        )
        writer.writeheader()
        writer.writerows(resultados)

    print(f"\nResumen guardado en: {csv_path}")


def main() -> None:
    pruebas = _find_pruebas()

    if not pruebas:
        print(f"No se encontraron imágenes válidas en {PRUEBAS_DIR}")
        return

    template = template_loader.load_template()

    resultados = [procesar_prueba(path, template) for path in pruebas]

    print()
    imprimir_resumen(resultados)
    guardar_resumen_csv(resultados)


if __name__ == "__main__":
    main()