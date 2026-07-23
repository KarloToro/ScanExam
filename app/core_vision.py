# app/core_vision.py
"""
Procesamiento visual de la ficha completa.

Este módulo se construye por fases:

    Fase 1: detección de los 4 marcadores de referencia sobre la foto cruda 
            y resolución de orientación.
    Fase 2: corrección de perspectiva y transformación a la imagen canónica (homografía).
    Fase 3: validación de calidad visual (Anexo C: M1-M4) sobre la imagen ya canonizada.

Errores técnicos que puede producir este módulo:
    MARKERS_NOT_FOUND     -> no se detectaron los 4 marcadores.
    INVALID_ORIENTATION   -> se detectaron 4 marcadores, pero el marcador especial no cae en top_right.
    WARP_FAILED           -> los marcadores se detectaron bien, pero la transformación falló.
    LOW_CONFIDENCE        -> la ficha se canonizó, pero no superó los controles mínimos de calidad (M1-M4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

# Adaptación para importaciones compatibles con el monolito FastAPI desde raíz y ejecuciones locales
try:
    from app import config
    from app import template_loader
except ImportError:
    import config
    import template_loader


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class MarkerCandidate:
    """Un contorno cuadrado candidato a marcador de referencia."""

    contour: np.ndarray
    center: tuple[float, float]
    area: float
    bbox: tuple[int, int, int, int]  # x, y, w, h
    has_inner_hole: bool


@dataclass
class MarkerDetectionResult:
    """
    Resultado de la detección de marcadores sobre una foto cruda.
    """

    status: str
    issue_code: str | None
    message: str
    ordered_points: dict[str, tuple[float, float]] | None = None
    candidates: list[MarkerCandidate] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fase 1: detección de marcadores
# ---------------------------------------------------------------------------

def detect_reference_markers(
    image: np.ndarray,
    orientation_marker: str = config.ORIENTATION_MARKER_POSITION,
) -> MarkerDetectionResult:
    """
    Detecta los 4 marcadores cuadrados de referencia sobre la foto cruda
    y determina si la orientación coincide con la esperada.
    """
    if image is None or image.size == 0:
        return MarkerDetectionResult(
            status="MARKERS_NOT_FOUND",
            issue_code=config.MARKER_ISSUE_CODES["NOT_FOUND"],
            message="La imagen recibida está vacía o no pudo cargarse.",
        )

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    candidates = _find_square_candidates(gray, width, height)
    quad_candidates = _select_best_quad(candidates)

    if quad_candidates is None:
        return MarkerDetectionResult(
            status="MARKERS_NOT_FOUND",
            issue_code=config.MARKER_ISSUE_CODES["NOT_FOUND"],
            message=(
                "No se encontraron 4 candidatos cuadrados consistentes entre sí "
                f"(candidatos totales detectados: {len(candidates)})."
            ),
            candidates=candidates,
        )

    corner_map = _order_candidates_by_geometry(quad_candidates)

    holed_corners = [
        name for name, candidate in corner_map.items()
        if candidate.has_inner_hole
    ]

    if len(holed_corners) != 1:
        return MarkerDetectionResult(
            status="MARKERS_NOT_FOUND",
            issue_code=config.MARKER_ISSUE_CODES["NOT_FOUND"],
            message=(
                "No se pudo identificar de forma inequívoca el marcador de "
                f"orientación (candidatos con hueco interior: {len(holed_corners)}, "
                "se esperaba exactamente 1)."
            ),
            candidates=candidates,
        )

    detected_orientation = holed_corners[0]

    ordered_points = {
        name: candidate.center
        for name, candidate in corner_map.items()
    }

    if detected_orientation != orientation_marker:
        return MarkerDetectionResult(
            status="INVALID_ORIENTATION",
            issue_code=config.MARKER_ISSUE_CODES["INVALID_ORIENTATION"],
            message=(
                f"El marcador de orientación se ubicó en '{detected_orientation}', "
                f"pero se esperaba en '{orientation_marker}'. "
                "La ficha probablemente fue fotografiada rotada."
            ),
            ordered_points=ordered_points,
            candidates=candidates,
        )

    return MarkerDetectionResult(
        status="OK",
        issue_code=None,
        message="Los 4 marcadores fueron detectados y la orientación es correcta.",
        ordered_points=ordered_points,
        candidates=candidates,
    )


def detect_and_autorotate(
    image: np.ndarray,
) -> tuple[np.ndarray, MarkerDetectionResult, int]:
    """
    Envuelve detect_reference_markers() con auto-corrección de orientación.
    """
    original_result = detect_reference_markers(image)

    if original_result.status == "OK":
        return image, original_result, 0

    rotation_flags = {
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }

    resolved: list[tuple[int, np.ndarray, MarkerDetectionResult]] = []

    for degrees, flag in rotation_flags.items():
        rotated_image = cv2.rotate(image, flag)
        rotated_result = detect_reference_markers(rotated_image)

        if rotated_result.status == "OK":
            resolved.append((degrees, rotated_image, rotated_result))

    if len(resolved) == 1:
        degrees, rotated_image, rotated_result = resolved[0]
        return rotated_image, rotated_result, degrees

    if len(resolved) == 0:
        return image, original_result, 0

    ambiguous_result = MarkerDetectionResult(
        status="INVALID_ORIENTATION",
        issue_code=config.MARKER_ISSUE_CODES["INVALID_ORIENTATION"],
        message=(
            f"Se encontraron {len(resolved)} rotaciones distintas que "
            "resuelven la orientación de forma aparentemente válida; "
            "no se puede autocorregir con confianza."
        ),
    )
    return image, ambiguous_result, 0


def _find_square_candidates(
    gray: np.ndarray,
    width: int,
    height: int,
) -> list[MarkerCandidate]:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    if hierarchy is None:
        return []

    hierarchy = hierarchy[0]
    image_area = float(width * height)

    min_area = image_area * config.MARKER_MIN_AREA_RATIO
    max_area = image_area * config.MARKER_MAX_AREA_RATIO

    candidates: list[MarkerCandidate] = []

    for index, contour in enumerate(contours):
        area = cv2.contourArea(contour)

        if area < min_area or area > max_area:
            continue

        perimeter = cv2.arcLength(contour, True)
        epsilon = config.MARKER_POLY_APPROX_EPSILON_RATIO * perimeter
        approx = cv2.approxPolyDP(contour, epsilon, True)

        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue

        x, y, w, h = cv2.boundingRect(approx)

        if h == 0:
            continue

        aspect_ratio = w / h
        tol = config.MARKER_ASPECT_RATIO_TOLERANCE

        if not (1 - tol <= aspect_ratio <= 1 + tol):
            continue

        center = (x + w / 2.0, y + h / 2.0)
        has_hole = _has_inner_hole(index, hierarchy, contours, min_area)

        candidates.append(
            MarkerCandidate(
                contour=approx,
                center=center,
                area=area,
                bbox=(x, y, w, h),
                has_inner_hole=has_hole,
            )
        )

    return candidates


def _has_inner_hole(
    contour_index: int,
    hierarchy: np.ndarray,
    contours: list[np.ndarray],
    min_child_area: float,
) -> bool:
    first_child = hierarchy[contour_index][2]

    child_index = first_child
    while child_index != -1:
        child_area = cv2.contourArea(contours[child_index])

        if child_area >= min_child_area * 0.15:
            return True

        child_index = hierarchy[child_index][0]

    return False


def _hull_area(centers: list[tuple[float, float]]) -> float:
    points = np.array(centers, dtype=np.float32)
    hull = cv2.convexHull(points)
    return cv2.contourArea(hull)


def _select_best_quad(
    candidates: list[MarkerCandidate],
) -> list[MarkerCandidate] | None:
    if len(candidates) < 4:
        return None

    if len(candidates) == 4:
        return candidates

    best_group: tuple[MarkerCandidate, ...] | None = None
    best_area = -1.0

    for group in combinations(candidates, 4):
        area = _hull_area([c.center for c in group])

        if area > best_area:
            best_area = area
            best_group = group

    return list(best_group) if best_group is not None else None


def _order_candidates_by_geometry(
    candidates: list[MarkerCandidate],
) -> dict[str, MarkerCandidate]:
    centers = np.array([c.center for c in candidates], dtype=np.float32)
    sums = centers.sum(axis=1)
    diffs = centers[:, 0] - centers[:, 1]

    return {
        "top_left": candidates[int(np.argmin(sums))],
        "bottom_right": candidates[int(np.argmax(sums))],
        "top_right": candidates[int(np.argmax(diffs))],
        "bottom_left": candidates[int(np.argmin(diffs))],
    }


# ---------------------------------------------------------------------------
# Fase 2: corrección de perspectiva (warp a imagen canónica)
# ---------------------------------------------------------------------------

@dataclass
class WarpResult:
    status: str
    issue_code: str | None
    message: str
    canonical_image: np.ndarray | None = None
    homography: np.ndarray | None = None


def correct_perspective(
    image: np.ndarray,
    detected_points: dict[str, tuple[float, float]],
    marker_centers: dict[str, list[int]],
    canonical_width: int,
    canonical_height: int,
) -> WarpResult:
    missing_keys = [
        key for key in config.WARP_POINT_ORDER
        if key not in detected_points or key not in marker_centers
    ]

    if missing_keys:
        return WarpResult(
            status="WARP_FAILED",
            issue_code=config.WARP_FAILED_ISSUE_CODE,
            message=(
                "Faltan puntos de referencia para calcular la homografía: "
                f"{', '.join(missing_keys)}."
            ),
        )

    src_points = np.array(
        [detected_points[key] for key in config.WARP_POINT_ORDER],
        dtype=np.float32,
    )

    dst_points = np.array(
        [marker_centers[key] for key in config.WARP_POINT_ORDER],
        dtype=np.float32,
    )

    src_area = cv2.contourArea(src_points)

    if src_area <= 0:
        return WarpResult(
            status="WARP_FAILED",
            issue_code=config.WARP_FAILED_ISSUE_CODE,
            message=(
                "Los 4 puntos de origen no forman un cuadrilátero válido "
                "(área nula o puntos colineales)."
            ),
        )

    try:
        homography = cv2.getPerspectiveTransform(src_points, dst_points)
    except cv2.error as error:
        return WarpResult(
            status="WARP_FAILED",
            issue_code=config.WARP_FAILED_ISSUE_CODE,
            message=f"No se pudo calcular la homografía: {error}",
        )

    canonical_image = cv2.warpPerspective(
        image,
        homography,
        (canonical_width, canonical_height),
    )

    mean_intensity = float(
        cv2.cvtColor(canonical_image, cv2.COLOR_BGR2GRAY).mean()
    )

    if mean_intensity < config.WARP_MIN_MEAN_GRAY_INTENSITY:
        return WarpResult(
            status="WARP_FAILED",
            issue_code=config.WARP_FAILED_ISSUE_CODE,
            message=(
                "La imagen canónica resultante es casi completamente "
                f"negra (intensidad promedio: {mean_intensity:.1f}). "
                "La homografía probablemente es incorrecta."
            ),
            homography=homography,
        )

    return WarpResult(
        status="OK",
        issue_code=None,
        message="Perspectiva corregida correctamente.",
        canonical_image=canonical_image,
        homography=homography,
    )


def extraer_recorte(
    canonical_image: np.ndarray,
    center: list[int] | tuple[float, float],
    crop_size: int,
) -> np.ndarray:
    """
    Extrae un recorte cuadrado alrededor de un centro geométrico directamente en RAM.
    """
    cx, cy = center
    half = crop_size // 2
    height, width = canonical_image.shape[:2]

    x1 = int(round(cx)) - half
    y1 = int(round(cy)) - half

    x1 = max(0, min(x1, width - crop_size))
    y1 = max(0, min(y1, height - crop_size))

    x2 = x1 + crop_size
    y2 = y1 + crop_size

    return canonical_image[y1:y2, x1:x2].copy()


# ---------------------------------------------------------------------------
# Fase 3: validación de calidad visual (Anexo C: M1-M4)
# ---------------------------------------------------------------------------

@dataclass
class QualityMetrics:
    sharpness: float
    sharpness_passed: bool

    brightness: float
    brightness_passed: bool

    dark_area_ratio: float
    dark_area_passed: bool

    marker_offsets_px: dict[str, float | None]
    markers_passed: bool


@dataclass
class QualityValidationResult:
    status: str
    issue_code: str | None
    message: str
    metrics: QualityMetrics


def validate_canonical_quality(
    canonical_image: np.ndarray,
    marker_centers: dict[str, list[int]],
    marker_size_px: int = 100,
) -> QualityValidationResult:
    gray = cv2.cvtColor(canonical_image, cv2.COLOR_BGR2GRAY)

    # M1: nitidez
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharpness_passed = sharpness >= config.QUALITY_MIN_SHARPNESS

    # M2: brillo
    brightness = float(gray.mean())
    brightness_passed = (
        config.QUALITY_MIN_BRIGHTNESS <= brightness <= config.QUALITY_MAX_BRIGHTNESS
    )

    # M3: zonas negras
    dark_mask = gray < config.QUALITY_DARK_PIXEL_THRESHOLD
    dark_area_ratio = float(dark_mask.sum()) / dark_mask.size
    dark_area_passed = dark_area_ratio <= config.QUALITY_MAX_DARK_AREA_RATIO

    # M4: marcadores
    marker_offsets: dict[str, float | None] = {}
    markers_passed = True

    for name, expected_center in marker_centers.items():
        offset = _measure_marker_offset(
            gray, expected_center, marker_size_px
        )
        marker_offsets[name] = offset

        if offset is None or offset > config.QUALITY_MARKER_POSITION_TOLERANCE_PX:
            markers_passed = False

    metrics = QualityMetrics(
        sharpness=sharpness,
        sharpness_passed=sharpness_passed,
        brightness=brightness,
        brightness_passed=brightness_passed,
        dark_area_ratio=dark_area_ratio,
        dark_area_passed=dark_area_passed,
        marker_offsets_px=marker_offsets,
        markers_passed=markers_passed,
    )

    failed_checks = []

    if not sharpness_passed:
        failed_checks.append(f"M1 nitidez ({sharpness:.1f} < {config.QUALITY_MIN_SHARPNESS})")

    if not brightness_passed:
        failed_checks.append(f"M2 brillo ({brightness:.1f})")

    if not dark_area_passed:
        failed_checks.append(
            f"M3 zonas negras ({dark_area_ratio * 100:.1f}% > "
            f"{config.QUALITY_MAX_DARK_AREA_RATIO * 100:.1f}%)"
        )

    if not markers_passed:
        failed_checks.append(f"M4 posición de marcadores ({marker_offsets})")

    if failed_checks:
        return QualityValidationResult(
            status="LOW_CONFIDENCE",
            issue_code=config.QUALITY_LOW_CONFIDENCE_ISSUE_CODE,
            message=(
                "La ficha canonizada no superó los controles mínimos de "
                f"calidad: {'; '.join(failed_checks)}."
            ),
            metrics=metrics,
        )

    return QualityValidationResult(
        status="OK",
        issue_code=None,
        message="La ficha canonizada superó las 4 métricas de calidad.",
        metrics=metrics,
    )


def _measure_marker_offset(
    gray: np.ndarray,
    expected_center: list[int],
    marker_size_px: int,
) -> float | None:
    half = marker_size_px // 2 + config.QUALITY_MARKER_ROI_MARGIN
    cx, cy = expected_center

    height, width = gray.shape[:2]

    x1 = max(0, int(cx - half))
    y1 = max(0, int(cy - half))
    x2 = min(width, int(cx + half))
    y2 = min(height, int(cy + half))

    roi = gray[y1:y2, x1:x2]

    if roi.size == 0:
        return None

    dark_mask = roi < config.QUALITY_DARK_PIXEL_THRESHOLD
    dark_ratio = float(dark_mask.sum()) / dark_mask.size

    if dark_ratio < config.QUALITY_MIN_MARKER_DARK_RATIO:
        return None

    ys, xs = np.nonzero(dark_mask)
    centroid_x = x1 + float(xs.mean())
    centroid_y = y1 + float(ys.mean())

    offset = float(np.hypot(centroid_x - cx, centroid_y - cy))
    return offset


# ---------------------------------------------------------------------------
# Contrato público de P2: process_ficha()
# ---------------------------------------------------------------------------

@dataclass
class FichaProcessingResult:
    status: str
    issue_code: str | None
    message: str
    canonical_image: np.ndarray | None = None
    canonical_path: Path | None = None
    debug: dict | None = None
    manifest_entry: dict | None = None


@lru_cache(maxsize=4)
def _get_cached_template(template_id: str):
    return template_loader.load_template(template_id=template_id)


def _build_manifest_entry(
    filename: str | None,
    status: str,
    canonical_path_for_manifest: str | None,
    technical_code: str | None,
    quality_metrics: dict | None,
) -> dict:
    return {
        "file": filename,
        "status": status,
        "canonical_path": canonical_path_for_manifest,
        "issue_code": technical_code,
        "quality_metrics": quality_metrics,
    }


def process_ficha(
    image: np.ndarray | str | Path,
    template_id: str = config.TEMPLATE_ID,
    output_root: str | Path | None = None,
    original_filename: str | None = None,
) -> FichaProcessingResult:
    """
    Punto de entrada único de P2. Recibe una foto cruda (ruta o np.ndarray BGR)
    y devuelve la imagen canónica lista en RAM.
    """
    template = _get_cached_template(template_id)
    filename = original_filename

    if isinstance(image, (str, Path)):
        image_path = Path(image)
        filename = filename or image_path.name
        raw_image = cv2.imread(str(image_path))

        if raw_image is None:
            return FichaProcessingResult(
                status="ERROR",
                issue_code="CORRUPT_FILE",
                message=f"No se pudo leer el archivo de imagen: {image}",
                manifest_entry=_build_manifest_entry(
                    filename, "ERROR", None, "CORRUPT_FILE", None
                ),
            )
    else:
        raw_image = image

    if raw_image is None or raw_image.size == 0:
        return FichaProcessingResult(
            status="ERROR",
            issue_code="CORRUPT_FILE",
            message="La imagen recibida está vacía o corrupta.",
            manifest_entry=_build_manifest_entry(
                filename, "ERROR", None, "CORRUPT_FILE", None
            ),
        )

    # --- Fase 1: marcadores ---
    imagen_final, deteccion, grados_rotados = detect_and_autorotate(raw_image)

    if deteccion.status != "OK":
        return FichaProcessingResult(
            status="ERROR",
            issue_code=deteccion.issue_code,
            message=deteccion.message,
            debug={"fase": "marcadores", "detalle": deteccion.message},
            manifest_entry=_build_manifest_entry(
                filename, "ERROR", None, deteccion.status, None
            ),
        )

    # --- Fase 2: warp ---
    warp = correct_perspective(
        image=imagen_final,
        detected_points=deteccion.ordered_points,
        marker_centers=template.marker_centers,
        canonical_width=template.canonical_width,
        canonical_height=template.canonical_height,
    )

    if warp.status != "OK":
        return FichaProcessingResult(
            status="ERROR",
            issue_code=warp.issue_code,
            message=warp.message,
            debug={"fase": "warp", "detalle": warp.message},
            manifest_entry=_build_manifest_entry(
                filename, "ERROR", None, "WARP_FAILED", None
            ),
        )

    # --- Fase 3: calidad ---
    calidad = validate_canonical_quality(
        canonical_image=warp.canonical_image,
        marker_centers=template.marker_centers,
    )

    if calidad.status != "OK":
        quality_metrics_manifest = {
            "blur_score": calidad.metrics.sharpness,
            "brightness": calidad.metrics.brightness,
            "black_ratio": calidad.metrics.dark_area_ratio,
        }
        return FichaProcessingResult(
            status="ERROR",
            issue_code=calidad.issue_code,
            message=calidad.message,
            debug={
                "fase": "calidad",
                "detalle": calidad.message,
                "m1_nitidez": calidad.metrics.sharpness,
                "m2_brillo": calidad.metrics.brightness,
                "m3_zonas_negras": calidad.metrics.dark_area_ratio,
                "m4_offsets_px": calidad.metrics.marker_offsets_px,
            },
            manifest_entry=_build_manifest_entry(
                filename, "ERROR", None, "LOW_CONFIDENCE", quality_metrics_manifest
            ),
        )

    debug_info = {
        "rotacion_aplicada_grados": grados_rotados,
        "m1_nitidez": calidad.metrics.sharpness,
        "m2_brillo": calidad.metrics.brightness,
        "m3_zonas_negras": calidad.metrics.dark_area_ratio,
        "m4_offsets_px": calidad.metrics.marker_offsets_px,
    }

    canonical_path = None
    canonical_path_for_manifest = None

    if output_root is not None:
        canonical_path, canonical_path_for_manifest = _guardar_canonica_png(
            warp.canonical_image, output_root, filename
        )

    return FichaProcessingResult(
        status="OK",
        issue_code=None,
        message="Ficha canonizada y validada correctamente.",
        canonical_image=warp.canonical_image,
        canonical_path=canonical_path,
        debug=debug_info,
        manifest_entry=_build_manifest_entry(
            filename, "OK", canonical_path_for_manifest, None, None
        ),
    )


def _guardar_canonica_png(
    canonical_image: np.ndarray,
    output_root: str | Path,
    filename: str | None,
) -> tuple[Path, str]:
    output_root = Path(output_root)
    normalized_dir = output_root / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(filename).stem if filename else "ficha"
    png_path = normalized_dir / f"{stem}.png"

    cv2.imwrite(str(png_path), canonical_image)

    path_for_manifest = str(
        Path(output_root.name) / "normalized" / f"{stem}.png"
    ).replace("\\", "/")

    return png_path, path_for_manifest


def process_batch(
    paths: list[str | Path],
    output_root: str | Path,
    template_id: str = config.TEMPLATE_ID,
) -> list[FichaProcessingResult]:
    output_root = Path(output_root)
    resultados = []

    for path in paths:
        resultado = process_ficha(path, template_id=template_id, output_root=output_root)
        resultados.append(resultado)

    manifest = [r.manifest_entry for r in resultados]

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "vision_manifest.json"

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    return resultados