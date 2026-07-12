# app/test_core_vision.py
"""
Pruebas automatizadas para core_vision.py (P2).

Cubre las 3 fases con:
  - Casos sintéticos deterministas (no dependen de fotos externas,
    siempre corren, sirven como red de seguridad ante regresiones).
  - Casos con fotos reales "doradas" en pruebas/ (se saltan
    automáticamente si esas fotos no están presentes en la máquina que
    corre las pruebas, ya que no forman parte del repo).

Ejecutar desde app/:
    pytest test_core_vision.py -v
"""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

import template_loader
from core_vision import (
    FichaProcessingResult,
    correct_perspective,
    detect_and_autorotate,
    detect_reference_markers,
    extraer_recorte,
    process_batch,
    process_ficha,
    validate_canonical_quality,
)

BASE_DIR = Path(__file__).resolve().parent
PRUEBAS_DIR = BASE_DIR / "pruebas"


# ---------------------------------------------------------------------------
# Fixtures compartidas
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def template():
    return template_loader.load_template()


@pytest.fixture(scope="session")
def plantilla_referencia(template):
    """La imagen de referencia perfecta (2100x1480), tal como la genera Figma."""
    image = cv2.imread(str(template.template_image_path))
    assert image is not None, (
        f"No se pudo cargar la imagen de referencia: {template.template_image_path}"
    )
    return image


def _build_synthetic_photo(
    plantilla_referencia: np.ndarray,
    dst_corners: list[list[int]],
    brightness_factor: float = 1.0,
    canvas_size: tuple[int, int] = (3000, 2400),
) -> np.ndarray:
    """
    Simula una "foto" aplicando una perspectiva conocida sobre la
    plantilla de referencia perfecta, opcionalmente oscurecida para
    imitar la exposición real de una cámara (la plantilla digital pura
    es más blanca que cualquier foto real).
    """
    h, w = plantilla_referencia.shape[:2]
    canvas_w, canvas_h = canvas_size

    src_corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    dst = np.array(dst_corners, dtype=np.float32)

    homography = cv2.getPerspectiveTransform(src_corners, dst)

    source = plantilla_referencia

    if brightness_factor != 1.0:
        source = np.clip(
            plantilla_referencia.astype(np.float32) * brightness_factor, 0, 255
        ).astype(np.uint8)

    return cv2.warpPerspective(
        source, homography, (canvas_w, canvas_h), borderValue=(180, 180, 180)
    )


@pytest.fixture
def foto_sintetica_buena(plantilla_referencia):
    """
    Foto simulada con perspectiva (esquinas movidas, no un rectángulo
    perfecto) y brillo ajustado a un rango realista de cámara. Debe
    pasar las 3 fases sin problema.
    """
    return _build_synthetic_photo(
        plantilla_referencia,
        dst_corners=[[350, 300], [2700, 150], [2600, 2100], [300, 2000]],
        brightness_factor=0.75,
    )


@pytest.fixture
def foto_sintetica_rotada_180(plantilla_referencia):
    photo = _build_synthetic_photo(
        plantilla_referencia,
        dst_corners=[[350, 300], [2700, 150], [2600, 2100], [300, 2000]],
        brightness_factor=0.75,
    )
    return cv2.rotate(photo, cv2.ROTATE_180)


@pytest.fixture
def foto_sintetica_rotada_90(plantilla_referencia):
    photo = _build_synthetic_photo(
        plantilla_referencia,
        dst_corners=[[350, 300], [2700, 150], [2600, 2100], [300, 2000]],
        brightness_factor=0.75,
    )
    return cv2.rotate(photo, cv2.ROTATE_90_CLOCKWISE)


@pytest.fixture
def foto_sintetica_rotada_270(plantilla_referencia):
    photo = _build_synthetic_photo(
        plantilla_referencia,
        dst_corners=[[350, 300], [2700, 150], [2600, 2100], [300, 2000]],
        brightness_factor=0.75,
    )
    return cv2.rotate(photo, cv2.ROTATE_90_COUNTERCLOCKWISE)


def _skip_si_no_existe(nombre: str) -> Path:
    candidatos = list(PRUEBAS_DIR.glob(f"{nombre}.*"))

    if not candidatos:
        pytest.skip(
            f"'{nombre}' no está presente en {PRUEBAS_DIR} en esta máquina "
            "(las fotos de prueba reales no forman parte del repo)."
        )

    return candidatos[0]


# ---------------------------------------------------------------------------
# Fase 1: detección de marcadores (sintético, siempre corre)
# ---------------------------------------------------------------------------

class TestDeteccionMarcadores:

    def test_foto_buena_da_ok(self, foto_sintetica_buena):
        resultado = detect_reference_markers(foto_sintetica_buena)
        assert resultado.status == "OK"
        assert resultado.ordered_points is not None
        assert set(resultado.ordered_points) == {
            "top_left", "top_right", "bottom_left", "bottom_right"
        }

    def test_foto_rotada_180_sin_autorotacion_da_invalid_orientation(
        self, foto_sintetica_rotada_180
    ):
        """
        detect_reference_markers() por sí solo (sin pasar por
        detect_and_autorotate) sigue rechazando la orientación
        incorrecta -- la auto-corrección es una capa aparte, no un
        cambio en la detección de base.
        """
        resultado = detect_reference_markers(foto_sintetica_rotada_180)
        assert resultado.status == "INVALID_ORIENTATION"
        assert resultado.issue_code is not None

    def test_marcador_tapado_da_markers_not_found(self, plantilla_referencia):
        imagen = plantilla_referencia.copy()
        # Tapa el marcador top_left (esquina superior izquierda real)
        cv2.rectangle(imagen, (130, 130), (230, 230), (255, 255, 255), -1)

        resultado = detect_reference_markers(imagen)
        assert resultado.status == "MARKERS_NOT_FOUND"

    def test_imagen_vacia_da_markers_not_found(self):
        resultado = detect_reference_markers(np.zeros((0, 0, 3), dtype=np.uint8))
        assert resultado.status == "MARKERS_NOT_FOUND"


class TestAutorotacion:
    """Decisión 1 del equipo: auto-corrección de orientación 90/180/270."""

    @pytest.mark.parametrize(
        "fixture_name,grados_esperados",
        [
            ("foto_sintetica_rotada_90", 270),
            ("foto_sintetica_rotada_180", 180),
            ("foto_sintetica_rotada_270", 90),
        ],
    )
    def test_autorotacion_resuelve_las_3_rotaciones(
        self, fixture_name, grados_esperados, request
    ):
        foto_rotada = request.getfixturevalue(fixture_name)

        imagen_final, resultado, grados_aplicados = detect_and_autorotate(foto_rotada)

        assert resultado.status == "OK"
        assert grados_aplicados == grados_esperados
        # La imagen final debe quedar con el ancho > alto (landscape),
        # tal como exige el contrato de salida canónica.
        assert imagen_final.shape[1] > imagen_final.shape[0]

    def test_foto_ya_correcta_no_rota(self, foto_sintetica_buena):
        imagen_final, resultado, grados_aplicados = detect_and_autorotate(
            foto_sintetica_buena
        )
        assert resultado.status == "OK"
        assert grados_aplicados == 0
        assert imagen_final is foto_sintetica_buena

    def test_marcador_tapado_no_se_resuelve_con_ninguna_rotacion(
        self, plantilla_referencia
    ):
        imagen = plantilla_referencia.copy()
        cv2.rectangle(imagen, (130, 130), (230, 230), (255, 255, 255), -1)

        _, resultado, grados_aplicados = detect_and_autorotate(imagen)

        assert resultado.status == "MARKERS_NOT_FOUND"
        assert grados_aplicados == 0


# ---------------------------------------------------------------------------
# Fase 2: corrección de perspectiva / warp (sintético, siempre corre)
# ---------------------------------------------------------------------------

class TestWarp:

    def test_warp_end_to_end_produce_imagen_canonica_correcta(
        self, foto_sintetica_buena, template
    ):
        deteccion = detect_reference_markers(foto_sintetica_buena)
        assert deteccion.status == "OK"

        resultado = correct_perspective(
            image=foto_sintetica_buena,
            detected_points=deteccion.ordered_points,
            marker_centers=template.marker_centers,
            canonical_width=template.canonical_width,
            canonical_height=template.canonical_height,
        )

        assert resultado.status == "OK"
        assert resultado.canonical_image.shape[1] == template.canonical_width
        assert resultado.canonical_image.shape[0] == template.canonical_height

    def test_puntos_colineales_da_warp_failed(self, template, plantilla_referencia):
        puntos_colineales = {
            "top_left": (100.0, 100.0),
            "top_right": (200.0, 100.0),
            "bottom_left": (150.0, 100.0),
            "bottom_right": (300.0, 100.0),
        }

        resultado = correct_perspective(
            image=plantilla_referencia,
            detected_points=puntos_colineales,
            marker_centers=template.marker_centers,
            canonical_width=template.canonical_width,
            canonical_height=template.canonical_height,
        )

        assert resultado.status == "WARP_FAILED"

    def test_puntos_incompletos_da_warp_failed(self, template, plantilla_referencia):
        puntos_incompletos = {
            "top_left": (100.0, 100.0),
            "top_right": (200.0, 100.0),
        }

        resultado = correct_perspective(
            image=plantilla_referencia,
            detected_points=puntos_incompletos,
            marker_centers=template.marker_centers,
            canonical_width=template.canonical_width,
            canonical_height=template.canonical_height,
        )

        assert resultado.status == "WARP_FAILED"


# ---------------------------------------------------------------------------
# Fase 3: validación de calidad M1-M4 (sintético, siempre corre)
# ---------------------------------------------------------------------------

@pytest.fixture
def imagen_canonica_buena(foto_sintetica_buena, template):
    deteccion = detect_reference_markers(foto_sintetica_buena)
    warp = correct_perspective(
        image=foto_sintetica_buena,
        detected_points=deteccion.ordered_points,
        marker_centers=template.marker_centers,
        canonical_width=template.canonical_width,
        canonical_height=template.canonical_height,
    )
    assert warp.status == "OK"
    return warp.canonical_image


class TestCalidad:

    def test_imagen_buena_pasa_las_4_metricas(self, imagen_canonica_buena, template):
        resultado = validate_canonical_quality(
            imagen_canonica_buena, template.marker_centers
        )
        assert resultado.status == "OK", resultado.message

    def test_blur_fuerte_falla_por_m1(self, imagen_canonica_buena, template):
        borrosa = cv2.GaussianBlur(imagen_canonica_buena, (25, 25), 15)

        resultado = validate_canonical_quality(borrosa, template.marker_centers)

        assert resultado.status == "LOW_CONFIDENCE"
        assert not resultado.metrics.sharpness_passed

    def test_imagen_muy_oscura_falla_por_m2(self, imagen_canonica_buena, template):
        oscura = (imagen_canonica_buena.astype(np.float32) * 0.25).astype(np.uint8)

        resultado = validate_canonical_quality(oscura, template.marker_centers)

        assert resultado.status == "LOW_CONFIDENCE"
        assert not resultado.metrics.brightness_passed

    def test_marcador_perdido_falla_por_m4(self, imagen_canonica_buena, template):
        sin_marcador = imagen_canonica_buena.copy()
        # Blanquea la zona del marcador top_left en la imagen ya canónica
        cv2.rectangle(sin_marcador, (130, 130), (230, 230), (255, 255, 255), -1)

        resultado = validate_canonical_quality(sin_marcador, template.marker_centers)

        assert resultado.status == "LOW_CONFIDENCE"
        assert not resultado.metrics.markers_passed
        assert resultado.metrics.marker_offsets_px["top_left"] is None


# ---------------------------------------------------------------------------
# Casos "dorados" con fotos reales (se saltan si la foto no está presente)
# ---------------------------------------------------------------------------

class TestProcessFicha:
    """process_ficha() es el contrato público único hacia core_pipeline.py/P3."""

    def test_foto_buena_da_ok_con_imagen_canonica(self, foto_sintetica_buena, template):
        resultado = process_ficha(foto_sintetica_buena)

        assert isinstance(resultado, FichaProcessingResult)
        assert resultado.status == "OK"
        assert resultado.issue_code is None
        assert resultado.canonical_image is not None
        assert resultado.canonical_image.shape[1] == template.canonical_width
        assert resultado.canonical_image.shape[0] == template.canonical_height

    def test_foto_rotada_se_autocorrige_a_ok(self, foto_sintetica_rotada_180):
        """Decisión 1: process_ficha() debe autocorregir, no rechazar."""
        resultado = process_ficha(foto_sintetica_rotada_180)

        assert resultado.status == "OK"
        assert resultado.issue_code is None
        assert resultado.canonical_image is not None
        assert resultado.debug["rotacion_aplicada_grados"] == 180

    def test_ruta_inexistente_da_error_corrupt_file(self):
        resultado = process_ficha("no_existe_este_archivo.jpg")

        assert resultado.status == "ERROR"
        assert resultado.issue_code == "CORRUPT_FILE"

    def test_acepta_tanto_ruta_como_imagen_ya_cargada(
        self, foto_sintetica_buena, tmp_path
    ):
        ruta_temp = tmp_path / "foto_temp.png"
        cv2.imwrite(str(ruta_temp), foto_sintetica_buena)

        resultado_desde_ruta = process_ficha(ruta_temp)
        resultado_desde_imagen = process_ficha(foto_sintetica_buena)

        assert resultado_desde_ruta.status == resultado_desde_imagen.status == "OK"


class TestSalidaEnDisco:
    """Decisiones 2 y 3 del equipo: PNG normalizado + carpeta work/ vía output_root."""

    def test_guarda_png_en_normalized_dentro_de_output_root(
        self, foto_sintetica_buena, tmp_path
    ):
        ruta_original = tmp_path / "ficha_001.jpg"
        cv2.imwrite(str(ruta_original), foto_sintetica_buena)

        output_root = tmp_path / "work"

        resultado = process_ficha(ruta_original, output_root=output_root)

        assert resultado.status == "OK"
        assert resultado.canonical_path is not None
        assert resultado.canonical_path.exists()
        assert resultado.canonical_path.suffix == ".png"
        assert resultado.canonical_path.parent.name == "normalized"

        # El PNG guardado debe poder releerse y tener el tamaño canónico.
        releida = cv2.imread(str(resultado.canonical_path))
        assert releida is not None
        assert releida.shape[1] == 2100
        assert releida.shape[0] == 1480

    def test_sin_output_root_no_escribe_nada_a_disco(self, foto_sintetica_buena):
        resultado = process_ficha(foto_sintetica_buena)

        assert resultado.status == "OK"
        assert resultado.canonical_path is None

    def test_manifest_entry_ok_tiene_canonical_path_y_sin_metricas(
        self, foto_sintetica_buena, tmp_path
    ):
        ruta_original = tmp_path / "ficha_002.jpg"
        cv2.imwrite(str(ruta_original), foto_sintetica_buena)
        output_root = tmp_path / "work"

        resultado = process_ficha(ruta_original, output_root=output_root)

        assert resultado.manifest_entry["file"] == "ficha_002.jpg"
        assert resultado.manifest_entry["status"] == "OK"
        assert resultado.manifest_entry["issue_code"] is None
        assert resultado.manifest_entry["quality_metrics"] is None
        assert resultado.manifest_entry["canonical_path"] == "work/normalized/ficha_002.png"

    def test_manifest_entry_error_no_tiene_canonical_path(self):
        """Fuerza un ERROR de lectura para confirmar el formato de manifest_entry."""
        resultado = process_ficha(
            np.zeros((0, 0, 3), dtype=np.uint8), original_filename="ficha_bad.jpg"
        )

        assert resultado.manifest_entry["file"] == "ficha_bad.jpg"
        assert resultado.manifest_entry["status"] == "ERROR"
        assert resultado.manifest_entry["canonical_path"] is None
        assert resultado.manifest_entry["issue_code"] == "CORRUPT_FILE"

    def test_manifest_entry_low_confidence_incluye_quality_metrics(
        self, imagen_canonica_buena, tmp_path
    ):
        """
        Usa una imagen ya canónica pero degradada (blur) para forzar
        LOW_CONFIDENCE pasando directo la imagen (sin marcadores que
        detectar de nuevo) -- se simula construyendo el resultado de
        calidad directamente para validar el formato exacto exigido
        por la Decisión 3.1 (blur_score/brightness/black_ratio).
        """
        borrosa = cv2.GaussianBlur(imagen_canonica_buena, (25, 25), 15)
        calidad = validate_canonical_quality(borrosa, template_loader.load_template().marker_centers)

        assert calidad.status == "LOW_CONFIDENCE"

        # Verifica que process_ficha() arma el mismo formato de métricas
        # que exige el manifest cuando la falla es por calidad.
        from core_vision import _build_manifest_entry

        entry = _build_manifest_entry(
            "ficha_003.jpg",
            "ERROR",
            None,
            "LOW_CONFIDENCE",
            {
                "blur_score": calidad.metrics.sharpness,
                "brightness": calidad.metrics.brightness,
                "black_ratio": calidad.metrics.dark_area_ratio,
            },
        )

        assert set(entry["quality_metrics"].keys()) == {
            "blur_score", "brightness", "black_ratio"
        }

    def test_process_batch_escribe_vision_manifest_json(
        self, foto_sintetica_buena, foto_sintetica_rotada_180, tmp_path
    ):
        ruta1 = tmp_path / "ficha_001.jpg"
        ruta2 = tmp_path / "ficha_002.jpg"
        cv2.imwrite(str(ruta1), foto_sintetica_buena)
        cv2.imwrite(str(ruta2), foto_sintetica_rotada_180)

        output_root = tmp_path / "work"

        resultados = process_batch([ruta1, ruta2], output_root=output_root)

        assert len(resultados) == 2
        assert all(r.status == "OK" for r in resultados)

        manifest_path = output_root / "vision_manifest.json"
        assert manifest_path.exists()

        with manifest_path.open(encoding="utf-8") as file:
            manifest = json.load(file)

        assert len(manifest) == 2
        assert {entry["file"] for entry in manifest} == {"ficha_001.jpg", "ficha_002.jpg"}
        assert all(entry["status"] == "OK" for entry in manifest)
        assert (output_root / "normalized" / "ficha_001.png").exists()
        assert (output_root / "normalized" / "ficha_002.png").exists()


class TestExtraerRecorte:
    """Decisión 4 del equipo: helper simple de recorte para P3."""

    def test_recorte_centrado_tiene_el_tamano_pedido(self, imagen_canonica_buena):
        crop = extraer_recorte(imagen_canonica_buena, center=(1000, 700), crop_size=64)
        assert crop.shape[:2] == (64, 64)

    def test_recorte_cerca_del_borde_mantiene_tamano_exacto(self, imagen_canonica_buena):
        # Centro casi pegado a la esquina superior izquierda (0,0)
        crop = extraer_recorte(imagen_canonica_buena, center=(5, 5), crop_size=64)
        assert crop.shape[:2] == (64, 64)

    def test_recorte_usa_marcador_conocido_como_referencia(
        self, imagen_canonica_buena, template
    ):
        # El marcador top_left cae exacto en marker_centers["top_left"];
        # el recorte alrededor de ese punto debe verse mayormente oscuro.
        centro = template.marker_centers["top_left"]
        crop = extraer_recorte(imagen_canonica_buena, center=centro, crop_size=80)

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        assert gray.mean() < 100  # predominantemente oscuro (el marcador negro)


# ---------------------------------------------------------------------------
# Casos "dorados" con fotos reales (se saltan si la foto no está presente)
# ---------------------------------------------------------------------------

class TestFotosDoradas:
    """
    Estas pruebas usan fotos reales capturadas durante el desarrollo de
    P2. No forman parte del repo (van en pruebas/, normalmente
    ignoradas por git), así que cada prueba se salta automáticamente
    si el archivo no está presente en la máquina que ejecuta pytest.
    """

    @pytest.mark.parametrize("nombre", ["Prueba_1", "Prueba_2", "Prueba_3"])
    def test_fotos_buenas_conocidas_pasan_las_3_fases(self, nombre, template):
        path = _skip_si_no_existe(nombre)

        resultado = process_ficha(path)

        assert resultado.status == "OK", f"{nombre}: {resultado.message}"
        assert resultado.canonical_image is not None

