# app/core_vision.py
"""
P2 — Procesamiento visual de la ficha completa.

Este módulo se construye por fases:

    Fase 1 (implementada): detección de los 4 marcadores de referencia
        sobre la foto cruda y resolución de orientación.
    Fase 2 (implementada): corrección de perspectiva y transformación
        a la imagen canónica (homografía). Se adelantó respecto al
        plan original porque las métricas de calidad de Anexo C
        (M3, M4) requieren la imagen ya canonizada para tener sentido.
    Fase 3 (implementada): validación de calidad visual (Anexo C:
        M1-M4) sobre la imagen ya canonizada.

Errores técnicos que puede producir este módulo (ver Anexo A del
documento de flujo):

    MARKERS_NOT_FOUND     -> no se detectaron los 4 marcadores.
    INVALID_ORIENTATION   -> se detectaron 4 marcadores, pero el
                             marcador especial no cae en la posición
                             de orientación esperada (top_right).
    WARP_FAILED           -> los marcadores se detectaron bien, pero la
                             transformación de perspectiva no pudo
                             calcularse o produjo un resultado inválido.
    LOW_CONFIDENCE        -> la ficha se canonizó, pero no superó los
                             controles mínimos de calidad (M1-M4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

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

    status:
        "OK"                  -> los 4 marcadores fueron ubicados y la
                                  orientación es la esperada.
        "MARKERS_NOT_FOUND"   -> no se pudo ubicar alguno de los 4
                                  marcadores (o hay ambigüedad en cuál
                                  es el marcador de orientación).
        "INVALID_ORIENTATION" -> los 4 marcadores se ubicaron, pero el
                                  marcador especial no está donde debería.

    ordered_points:
        dict con las 4 llaves "top_left", "top_right", "bottom_left",
        "bottom_right" -> (x, y) en la foto cruda. Solo viene poblado
        cuando status == "OK". Este es el insumo directo para la
        homografía de Fase 3.
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

    No asume ningún tamaño absoluto de marcador: filtra por forma
    (cuadrado) y por proporción respecto al área total de la imagen,
    ya que la foto puede tomarse a distintas distancias.

    Parámetros:
        image: imagen BGR cargada con cv2.imread (foto cruda, sin
            canonizar).
        orientation_marker: nombre de la posición que debe tener el
            marcador especial (con hueco interior). Por defecto se
            toma de config.ORIENTATION_MARKER_POSITION, que debe
            coincidir con "orientation_marker" en
            marcadores_centros.json.

    Retorna:
        MarkerDetectionResult
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

    # ¿Cuál de los 4 candidatos elegidos tiene el hueco interior?
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
    Envuelve detect_reference_markers() con auto-corrección de
    orientación (Decisión 1 del equipo, ver 01_modulo_cv.md):

        Si la orientación puede resolverse de forma inequívoca
        rotando 90°, 180° o 270°, se corrige automáticamente.
        Si no se puede resolver con confianza, se devuelve
        INVALID_ORIENTATION (o el error original si nunca se
        encontraron los 4 marcadores).

    Retorna (imagen_final, resultado_deteccion, grados_rotados).
    La imagen_final ya viene rotada si hubo auto-corrección; los
    "ordered_points" de resultado_deteccion son relativos a esa
    imagen_final, no a la imagen original.
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
        # No se pudo resolver en ninguna rotación: se conserva el
        # motivo de falla original (MARKERS_NOT_FOUND o
        # INVALID_ORIENTATION), tal como venía.
        return image, original_result, 0

    # Más de una rotación "resuelve" la orientación: ambiguo, no se
    # autocorrige con confianza (caso extremadamente improbable dado
    # que solo hay 1 marcador especial, pero se cubre por seguridad).
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
    """
    Busca contornos cuadrados oscuros que puedan ser marcadores de
    referencia, en cualquier parte de la imagen.
    """
    # Otsu separa razonablemente bien "hoja blanca" de "marcador negro"
    # en condiciones normales de iluminación.
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    if hierarchy is None:
        return []

    hierarchy = hierarchy[0]  # cv2 envuelve la jerarquía en un array extra
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
    """
    Revisa si el contorno tiene al menos un hijo (hueco interior) con
    área significativa. Esto distingue al marcador de orientación
    (cuadrado negro con cuadrado claro adentro) de los 3 marcadores
    sólidos.

    hierarchy[i] = [next, previous, first_child, parent]
    """
    first_child = hierarchy[contour_index][2]

    child_index = first_child
    while child_index != -1:
        child_area = cv2.contourArea(contours[child_index])

        # El hueco debe ser una fracción razonable del marcador padre,
        # no ruido de compresión/JPEG.
        if child_area >= min_child_area * 0.15:
            return True

        child_index = hierarchy[child_index][0]  # siguiente hermano

    return False


def _hull_area(centers: list[tuple[float, float]]) -> float:
    """Área del cuadrilátero convexo formado por 4 (o más) puntos."""
    points = np.array(centers, dtype=np.float32)
    hull = cv2.convexHull(points)
    return cv2.contourArea(hull)


def _select_best_quad(
    candidates: list[MarkerCandidate],
) -> list[MarkerCandidate] | None:
    """
    De entre todos los candidatos cuadrados detectados, selecciona el
    grupo de 4 que forma el cuadrilátero convexo de mayor área.

    Esto es deliberadamente independiente de la posición del candidato
    dentro del encuadre de la foto (a diferencia de un enfoque por
    zonas fijas), porque en fotos reales la hoja rara vez llena todo
    el encuadre y puede estar rotada o inclinada. También permite
    ignorar ruido o una segunda ficha parcialmente visible, ya que la
    ficha principal en primer plano casi siempre forma el
    cuadrilátero más grande.
    """
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
    """
    Ordena 4 candidatos como top_left/top_right/bottom_left/bottom_right
    usando la heurística estándar de suma/diferencia de coordenadas.
    Es robusta a inclinación y a que la hoja no esté perfectamente
    encuadrada, porque compara los candidatos entre sí en vez de contra
    posiciones fijas del frame completo.
    """
    centers = np.array([c.center for c in candidates], dtype=np.float32)
    sums = centers.sum(axis=1)
    diffs = centers[:, 0] - centers[:, 1]  # x - y

    return {
        "top_left": candidates[int(np.argmin(sums))],
        "bottom_right": candidates[int(np.argmax(sums))],
        "top_right": candidates[int(np.argmax(diffs))],
        "bottom_left": candidates[int(np.argmin(diffs))],
    }


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Fase 2: corrección de perspectiva (warp a imagen canónica)
# ---------------------------------------------------------------------------

@dataclass
class WarpResult:
    """
    Resultado de la corrección de perspectiva sobre una foto cruda ya
    con marcadores detectados (status == "OK" en MarkerDetectionResult).

    status:
        "OK"           -> se generó la imagen canónica correctamente.
        "WARP_FAILED"  -> la homografía no pudo calcularse o el
                          resultado no pasó las validaciones mínimas
                          de sanidad.
    """

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
    """
    Corrige la perspectiva de la foto cruda y la transforma a la imagen
    canónica, usando los 4 marcadores detectados (Fase 1) como origen y
    las coordenadas oficiales de marcadores_centros.json como destino.

    Parámetros:
        image: foto cruda original (BGR).
        detected_points: "ordered_points" de un MarkerDetectionResult
            con status == "OK" (top_left/top_right/bottom_left/bottom_right
            en la foto cruda).
        marker_centers: centros oficiales de marcadores en la imagen
            canónica (viene de TemplateContract.marker_centers, es decir,
            de marcadores_centros.json vía template_loader).
        canonical_width / canonical_height: tamaño de salida esperado
            (TemplateContract.canonical_width / canonical_height).

    Retorna:
        WarpResult
    """
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

    # Un cuadrilátero degenerado (puntos casi colineales, área ~0) no
    # puede producir una homografía válida.
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

    # Validación mínima de sanidad: si el resultado es casi completamente
    # negro, algo salió mal en el mapeo (orden de puntos incorrecto,
    # homografía degenerada, etc.). La validación exhaustiva de zonas
    # negras vive en la métrica M3 (Fase 3).
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
    Helper de apoyo (Decisión 4 del equipo, ver 01_modulo_cv.md): recibe
    la imagen canonizada, un centro [x, y] y un tamaño de recorte, y
    devuelve el crop cuadrado alrededor de ese centro.

    Recorrer todos los centros de respuestas_centros.json /
    identificacion_centros.json, generar todos los crops y construir
    crop_manifest.json es responsabilidad de P3 — esta función solo
    resuelve el recorte individual.

    Si el centro está cerca del borde de la imagen, el recorte se
    desplaza lo necesario para mantener exactamente crop_size x
    crop_size en vez de devolver un recorte más chico.
    """
    cx, cy = center
    half = crop_size // 2
    height, width = canonical_image.shape[:2]

    x1 = int(round(cx)) - half
    y1 = int(round(cy)) - half

    # Si el crop se sale por un borde, se desplaza para conservar el
    # tamaño exacto (en vez de recortar el crop resultante).
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
    """Valores crudos de cada métrica, útiles para depuración/calibración."""

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
    """
    Resultado de aplicar las métricas M1-M4 (Anexo C) sobre la imagen
    ya canonizada.

    status:
        "OK"              -> pasó las 4 métricas.
        "LOW_CONFIDENCE"   -> alguna métrica falló.
    """

    status: str
    issue_code: str | None
    message: str
    metrics: QualityMetrics


def validate_canonical_quality(
    canonical_image: np.ndarray,
    marker_centers: dict[str, list[int]],
    marker_size_px: int = 100,
) -> QualityValidationResult:
    """
    Aplica las métricas M1 (nitidez), M2 (brillo), M3 (zonas negras) y
    M4 (posición de marcadores) sobre la imagen canónica, tal como
    describe el Anexo C.

    Parámetros:
        canonical_image: imagen ya corregida por Fase 2
            (correct_perspective).
        marker_centers: centros oficiales de marcadores._centros.json
            (TemplateContract.marker_centers).
        marker_size_px: tamaño físico del marcador en la plantilla
            (marker_size_px de marcadores_centros.json).

    Retorna:
        QualityValidationResult
    """
    gray = cv2.cvtColor(canonical_image, cv2.COLOR_BGR2GRAY)

    # --- M1: nitidez ---
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharpness_passed = sharpness >= config.QUALITY_MIN_SHARPNESS

    # --- M2: brillo ---
    brightness = float(gray.mean())
    brightness_passed = (
        config.QUALITY_MIN_BRIGHTNESS <= brightness <= config.QUALITY_MAX_BRIGHTNESS
    )

    # --- M3: zonas negras/vacías ---
    dark_mask = gray < config.QUALITY_DARK_PIXEL_THRESHOLD
    dark_area_ratio = float(dark_mask.sum()) / dark_mask.size
    dark_area_passed = dark_area_ratio <= config.QUALITY_MAX_DARK_AREA_RATIO

    # --- M4: verificación de marcadores en posiciones esperadas ---
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
    """
    Recorta una región de interés alrededor del centro esperado de un
    marcador (M4) y mide qué tan lejos está el centroide oscuro real
    respecto al centro oficial. Retorna None si no se encontró
    suficiente presencia oscura en la ROI (el marcador se perdió o
    deformó en el warp).
    """
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
# Esta es la única función que core_pipeline.py (y por extensión P3)
# debería necesitar llamar. Consolida las 3 fases y traduce cualquier
# falla técnica (Anexo A: MARKERS_NOT_FOUND, INVALID_ORIENTATION,
# WARP_FAILED, LOW_CONFIDENCE) al mismo desenlace de pipeline: la ficha
# no pudo canonizarse, así que se marca como ERROR y no se genera
# score/publishable (ver "Canonizar ficha" -> "Ficha canonizada
# correctamente?" en el diagrama de flujo). El detalle de CUÁL de los
# 4 errores ocurrió viaja en issue_code/message para reportes y
# depuración, pero P3 no necesita distinguir entre ellos para decidir
# su propio flujo.

@dataclass
class FichaProcessingResult:
    """
    Resultado consolidado de process_ficha().

    status:
        "OK"    -> la ficha se canonizó y pasó control de calidad.
                   canonical_image queda listo para que P3 lea burbujas
                   usando los centros de respuestas_centros.json /
                   identificacion_centros.json directamente sobre esta
                   imagen (sin transformación adicional).
        "ERROR" -> alguna de las 3 fases falló. canonical_image es
                   None. issue_code indica el motivo específico
                   (ver Anexo A) para reportes/depuración.

    issue_code:
        Código de config.ISSUE_CODES (decisión ya confirmada con el
        equipo: se reutilizan MISSING_REFERENCE_MARKERS,
        EXTREME_PERSPECTIVE, TEMPLATE_MISMATCH y CORRUPT_FILE en vez
        de crear códigos nuevos). Distinto del campo "issue_code" que
        va en vision_manifest.json (ver manifest_entry), que usa el
        vocabulario técnico de Anexo A tal como pidió el equipo
        (MARKERS_NOT_FOUND / INVALID_ORIENTATION / WARP_FAILED /
        LOW_CONFIDENCE) para ese archivo específico.

    canonical_path:
        Ruta donde se guardó el PNG canónico en disco, si se pasó
        output_root. None si no se persistió a disco o si status es
        "ERROR".

    debug:
        Detalle interno por fase (no es parte estricta del contrato,
        pero es útil para logging).

    manifest_entry:
        Dict con el formato exacto que espera vision_manifest.json
        (Decisión 3.1 del equipo). process_batch() usa este campo
        para construir el manifest de un lote completo; también está
        disponible acá por si el llamador quiere armar su propio
        manifest de otra forma.
    """

    status: str
    issue_code: str | None
    message: str
    canonical_image: np.ndarray | None = None
    canonical_path: Path | None = None
    debug: dict | None = None
    manifest_entry: dict | None = None


@lru_cache(maxsize=4)
def _get_cached_template(template_id: str):
    """
    Evita recargar los JSON de plantilla en cada ficha de un mismo
    lote. Un lote completo (Anexo B) puede tener decenas de fichas;
    releer y revalidar los JSON de plantilla en cada una sería
    trabajo repetido innecesario.
    """
    return template_loader.load_template(template_id=template_id)


def _build_manifest_entry(
    filename: str | None,
    status: str,
    canonical_path_for_manifest: str | None,
    technical_code: str | None,
    quality_metrics: dict | None,
) -> dict:
    """
    Arma la entrada de vision_manifest.json (Decisión 3.1 del equipo).
    "issue_code" acá usa el vocabulario técnico de Anexo A
    (MARKERS_NOT_FOUND / INVALID_ORIENTATION / WARP_FAILED /
    LOW_CONFIDENCE), no el config.ISSUE_CODES de FichaProcessingResult
    -- son dos catálogos distintos para dos consumidores distintos.
    """
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
    Punto de entrada único de P2. Recibe una foto cruda (ruta o imagen
    ya cargada con cv2) y devuelve la imagen canónica lista para P3, o
    un ERROR con el motivo técnico si la ficha no pudo procesarse.

    Si se pasa output_root (Decisión 3 del equipo), además:
        - guarda la ficha canonizada como PNG en
          {output_root}/normalized/{nombre}.png
        - deja lista la entrada de vision_manifest.json en
          resultado.manifest_entry (proceso_batch() la usa para
          escribir el manifest completo del lote).

    output_root representa la carpeta "work/" del lote (no
    BATCH-001/ completo): P2 no conoce ni construye la estructura
    completa del batch, solo escribe dentro de la carpeta que se le
    pase por parámetro.

    Uso esperado desde core_pipeline.py:

        resultado = process_ficha(ruta_a_la_foto, output_root=work_dir)

        if resultado.status == "ERROR":
            # mover la foto a rechazadas/, registrar issue_code en
            # reporte_observaciones.xlsx, continuar con la siguiente ficha.
            ...
        else:
            # resultado.canonical_path ya quedó escrito en disco.
            ...
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

    # --- Fase 1: marcadores (con auto-rotación, Decisión 1) ---
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
    """
    Guarda la ficha canonizada como PNG en {output_root}/normalized/
    (Decisión 2 y 3 del equipo). Retorna (path_absoluto,
    path_para_manifest), donde path_para_manifest se arma prefijado
    con el nombre de carpeta de output_root (p. ej. "work/normalized/
    ficha_001.png"), tal como muestra el ejemplo de vision_manifest.json
    acordado con el equipo.
    """
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
    """
    Corre process_ficha() sobre una lista de fotos y escribe
    {output_root}/vision_manifest.json con el resultado de todas
    (Decisión 3.1 del equipo).

    P2 no construye la estructura completa de BATCH-001/ (eso es de
    P3/core_pipeline.py) — solo escribe dentro de output_root, que
    representa la carpeta work/ del lote.
    """
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



# ---------------------------------------------------------------------------
# Utilidades de depuración visual (equivalente en espíritu a validar_centros.py)
# ---------------------------------------------------------------------------

def draw_detection_debug(image: np.ndarray, result: MarkerDetectionResult) -> np.ndarray:
    """
    Dibuja los candidatos y el resultado sobre una copia de la imagen,
    para inspección visual manual durante el desarrollo.
    """
    debug_image = image.copy()

    for candidate in result.candidates:
        color = (0, 255, 255) if candidate.has_inner_hole else (255, 180, 0)
        cv2.drawContours(debug_image, [candidate.contour], -1, color, 3)
        cx, cy = int(candidate.center[0]), int(candidate.center[1])
        cv2.circle(debug_image, (cx, cy), 6, (0, 0, 255), -1)

    if result.ordered_points:
        for name, point in result.ordered_points.items():
            cv2.putText(
                debug_image,
                name,
                (int(point[0]) + 10, int(point[1]) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

    cv2.putText(
        debug_image,
        f"status={result.status}",
        (30, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )

    return debug_image


def draw_canonical_debug(canonical_image: np.ndarray, marker_centers: dict[str, list[int]]) -> np.ndarray:
    """
    Dibuja los marcadores oficiales sobre la imagen canónica resultante,
    para verificar visualmente que el warp dejó cada marcador exactamente
    donde marcadores_centros.json dice que debería estar.
    """
    debug_image = canonical_image.copy()

    for name, (cx, cy) in marker_centers.items():
        cv2.circle(debug_image, (int(cx), int(cy)), 8, (0, 0, 255), 2)
        cv2.putText(
            debug_image,
            name,
            (int(cx) + 12, int(cy) - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    return debug_image


def draw_marker_roi_debug(
    canonical_image: np.ndarray,
    marker_centers: dict[str, list[int]],
    marker_size_px: int = 100,
) -> np.ndarray:
    """
    Genera un mosaico con la ROI de cada marcador (tal como la ve M4)
    junto a su máscara de píxeles oscuros y el % de oscuridad medido.
    Sirve para diagnosticar, esquina por esquina, por qué M4 pudo
    fallar en una foto real (sombra, blur localizado, iluminación
    desigual, etc.) en vez de solo ver el "None" en el resultado.
    """
    gray = cv2.cvtColor(canonical_image, cv2.COLOR_BGR2GRAY)
    half = marker_size_px // 2 + config.QUALITY_MARKER_ROI_MARGIN

    rows = []

    for name, (cx, cy) in marker_centers.items():
        x1 = max(0, int(cx - half))
        y1 = max(0, int(cy - half))
        x2 = min(gray.shape[1], int(cx + half))
        y2 = min(gray.shape[0], int(cy + half))

        roi = gray[y1:y2, x1:x2]

        if roi.size == 0:
            continue

        dark_mask = (roi < config.QUALITY_DARK_PIXEL_THRESHOLD).astype(np.uint8) * 255
        dark_ratio = float((roi < config.QUALITY_DARK_PIXEL_THRESHOLD).sum()) / roi.size

        roi_bgr = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        mask_bgr = cv2.cvtColor(dark_mask, cv2.COLOR_GRAY2BGR)
        row = np.hstack([roi_bgr, mask_bgr])

        label = (
            f"{name}: {dark_ratio * 100:.1f}% oscuro "
            f"(umbral {config.QUALITY_MIN_MARKER_DARK_RATIO * 100:.0f}%)"
        )
        label_bar = np.full((22, row.shape[1], 3), 255, dtype=np.uint8)
        cv2.putText(
            label_bar, label, (5, 16), cv2.FONT_HERSHEY_SIMPLEX,
            0.45, (0, 0, 255), 1, cv2.LINE_AA,
        )

        rows.append(np.vstack([label_bar, row]))

    if not rows:
        return canonical_image.copy()

    max_width = max(row.shape[1] for row in rows)
    padded_rows = []

    for row in rows:
        if row.shape[1] < max_width:
            pad = np.full((row.shape[0], max_width - row.shape[1], 3), 255, dtype=np.uint8)
            row = np.hstack([row, pad])
        padded_rows.append(row)

    return np.vstack(padded_rows)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Uso: python core_vision.py <ruta_a_foto_cruda.jpg>")
        sys.exit(1)

    input_path = sys.argv[1]
    raw_image = cv2.imread(input_path)

    if raw_image is None:
        print(f"No se pudo leer la imagen: {input_path}")
        sys.exit(1)

    detection_image, detection, rotation_applied = detect_and_autorotate(raw_image)

    print(f"status: {detection.status}")
    print(f"issue_code: {detection.issue_code}")
    print(f"message: {detection.message}")
    print(f"rotación aplicada: {rotation_applied}°")
    print(f"candidatos cuadrados detectados en total: {len(detection.candidates)}")

    if detection.ordered_points:
        print("ordered_points:")
        for name, point in detection.ordered_points.items():
            print(f"  {name}: {point}")

    debug_output = draw_detection_debug(detection_image, detection)
    output_path = "debug_marker_detection.png"
    cv2.imwrite(output_path, debug_output)
    print(f"Debug visual guardado en: {output_path}")

    if detection.status != "OK":
        print("\nNo se intenta el warp: los marcadores no están en condiciones OK.")
        sys.exit(0)

    template = template_loader.load_template()

    warp_result = correct_perspective(
        image=detection_image,
        detected_points=detection.ordered_points,
        marker_centers=template.marker_centers,
        canonical_width=template.canonical_width,
        canonical_height=template.canonical_height,
    )

    print("\n--- Warp ---")
    print(f"status: {warp_result.status}")
    print(f"issue_code: {warp_result.issue_code}")
    print(f"message: {warp_result.message}")

    if warp_result.status == "OK":
        canonical_path = "debug_canonical.png"
        cv2.imwrite(canonical_path, warp_result.canonical_image)
        print(f"Imagen canónica guardada en: {canonical_path}")

        canonical_debug = draw_canonical_debug(
            warp_result.canonical_image, template.marker_centers
        )
        canonical_debug_path = "debug_canonical_markers.png"
        cv2.imwrite(canonical_debug_path, canonical_debug)
        print(f"Debug de marcadores canónicos guardado en: {canonical_debug_path}")

        quality_result = validate_canonical_quality(
            canonical_image=warp_result.canonical_image,
            marker_centers=template.marker_centers,
        )

        print("\n--- Calidad (Anexo C) ---")
        print(f"status: {quality_result.status}")
        print(f"issue_code: {quality_result.issue_code}")
        print(f"message: {quality_result.message}")
        print(f"M1 nitidez: {quality_result.metrics.sharpness:.1f} "
              f"(passed={quality_result.metrics.sharpness_passed})")
        print(f"M2 brillo: {quality_result.metrics.brightness:.1f} "
              f"(passed={quality_result.metrics.brightness_passed})")
        print(f"M3 % zonas negras: {quality_result.metrics.dark_area_ratio * 100:.1f}% "
              f"(passed={quality_result.metrics.dark_area_passed})")
        print(f"M4 offsets de marcadores (px): {quality_result.metrics.marker_offsets_px} "
              f"(passed={quality_result.metrics.markers_passed})")

        roi_debug = draw_marker_roi_debug(
            warp_result.canonical_image, template.marker_centers
        )
        roi_debug_path = "debug_marker_rois.png"
        cv2.imwrite(roi_debug_path, roi_debug)
        print(f"Debug de ROIs de marcadores (M4) guardado en: {roi_debug_path}")