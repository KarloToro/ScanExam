# app/config.py

TEMPLATE_ID = "ficha_optica_a5_horizontal_v1"

OPTIONS = ["A", "B", "C", "D", "E"]

SUPPORTED_EXAM_TYPES = ["A", "B"]

SUPPORTED_INPUT_FORMATS = [".jpg", ".jpeg", ".png"]

NORMALIZED_IMAGE_FORMAT = "png"

STUDENT_CODE_DIGITS = 8

MIN_CLASSIFICATION_CONFIDENCE = 0.80

MIN_STUDENT_CODE_CONFIDENCE = 0.75

QUALITY_STATUS = [
    "OK",
    "ERROR"
]

PROCESSING_STATUS = [
    "OK",
    "OBSERVED",
    "ERROR"
]

MARK_STATUS = [
    "SINGLE_MARK",
    "BLANK",
    "DOUBLE_MARK",
    "UNCERTAIN"
]

QUESTION_STATUS = [
    "CORRECT",
    "INCORRECT",
    "BLANK",
    "DOUBLE_MARK",
    "UNCERTAIN"
]

BUBBLE_CLASSES = [
    "EMPTY",
    "MARKED",
    "GHOST"
]

ISSUE_CODES = [
    "LOW_STUDENT_CODE_CONFIDENCE",
    "STUDENT_NOT_FOUND",
    "DUPLICATED_STUDENT_CODE",
    "MISSING_STUDENT_CODE",
    "UNCERTAIN_MARK",
    "DOUBLE_MARK",
    "INVALID_EXAM_TYPE",
    "MISSING_REFERENCE_MARKERS",
    "EXTREME_PERSPECTIVE",
    "TEMPLATE_MISMATCH",
    "CORRUPT_FILE"
]

ANNOTATION_COLORS = {
    "CORRECT": (0, 180, 0),
    "INCORRECT": (0, 0, 255),
    "BLANK": (140, 140, 140),
    "DOUBLE_MARK": (180, 0, 180),
    "UNCERTAIN": (0, 180, 255)
}

# ---------------------------------------------------------------------------
# P2 — Fase 1: Detección de marcadores de referencia
# ---------------------------------------------------------------------------
# Estas constantes controlan la búsqueda de los 4 cuadrados de referencia
# sobre la FOTO CRUDA (antes de canonizar). No confundir con
# marcadores_centros.json, que describe las coordenadas de los marcadores
# ya sobre la imagen canónica.
#
# Como la foto cruda puede tomarse a distintas distancias/ángulos, no se
# puede asumir un tamaño absoluto de marcador en píxeles: se filtra por
# forma (cuadrado) y por proporción del área de la imagen completa.

# Un marcador válido no puede ser más pequeño que este % del área total
# de la foto, ni más grande que el máximo. Evita ruido y evita confundir
# el marco completo de la hoja con un marcador.
MARKER_MIN_AREA_RATIO = 0.0008
MARKER_MAX_AREA_RATIO = 0.05

# Tolerancia de "cuadratura": ancho/alto del contorno candidato debe
# estar entre [1 - tol, 1 + tol].
MARKER_ASPECT_RATIO_TOLERANCE = 0.25

# Tolerancia del approxPolyDP para aceptar el contorno como polígono de 4 lados.
MARKER_POLY_APPROX_EPSILON_RATIO = 0.03

# Marcador especial que define la orientación (debe tener un cuadrado
# claro/hueco en su interior). Debe coincidir con "orientation_marker"
# en marcadores_centros.json.
ORIENTATION_MARKER_POSITION = "top_right"

# Umbral binario para separar zonas oscuras (marcador) de zonas claras (hoja).
# Se usa como fallback si Otsu no converge bien.
MARKER_BINARY_THRESHOLD_FALLBACK = 100

# issue_codes específicos de Fase 1 (ya están cubiertos por ISSUE_CODES,
# se listan aparte para referencia rápida desde core_vision.py)
MARKER_ISSUE_CODES = {
    "NOT_FOUND": "MISSING_REFERENCE_MARKERS",
    "INVALID_ORIENTATION": "EXTREME_PERSPECTIVE",
}

# ---------------------------------------------------------------------------
# P2 — Fase 2: Corrección de perspectiva (warp a imagen canónica)
# ---------------------------------------------------------------------------

# Orden fijo en el que se arman los arrays de puntos origen/destino para
# cv2.getPerspectiveTransform. El orden en sí no importa siempre y cuando
# origen y destino usen exactamente el mismo, por eso se centraliza aquí.
WARP_POINT_ORDER = ["top_left", "top_right", "bottom_right", "bottom_left"]

# Intensidad de gris promedio mínima aceptable en la imagen canónica
# resultante. Un warp que produce una imagen casi negra suele indicar que
# la homografía fue degenerada o que los puntos de origen estaban mal.
# Esto es solo una validación mínima de sanidad: la validación completa
# de zonas negras vive en la métrica M3 (Fase 3, Anexo C).
WARP_MIN_MEAN_GRAY_INTENSITY = 15

# issue_code de WARP_FAILED (ver Anexo A). No hay un código dedicado en
# ISSUE_CODES; se reutiliza TEMPLATE_MISMATCH ya que un warp fallido
# significa que la imagen resultante no respeta el contrato de la
# plantilla (tamaño/orientación/estructura canónica esperada).
WARP_FAILED_ISSUE_CODE = "TEMPLATE_MISMATCH"

# ---------------------------------------------------------------------------
# P2 — Fase 3: Validación de calidad visual (Anexo C: M1-M4)
# ---------------------------------------------------------------------------
# Todas las métricas se evalúan sobre la imagen YA CANONIZADA (después
# del warp de Fase 2), tal como indica el Anexo C.
#
# Los umbrales son valores empíricos de partida (placeholders
# razonables). Deben calibrarse con un set real de fotos buenas,
# borrosas, oscuras, sobreexpuestas y mal canonizadas (tal como sugiere
# el propio Anexo C), no quedarse en los valores aquí puestos.

# M1: Nitidez — varianza del Laplaciano sobre la imagen canónica en
# escala de grises. Por debajo de este valor se considera borrosa.
QUALITY_MIN_SHARPNESS = 75.0

# M2: Brillo — promedio de intensidad de píxeles (0-255).
QUALITY_MIN_BRIGHTNESS = 60
QUALITY_MAX_BRIGHTNESS = 220

# M3: Zonas negras/vacías — un píxel se considera "oscuro" por debajo
# de este valor de gris, y se mide qué % de la imagen canónica ocupa.
QUALITY_DARK_PIXEL_THRESHOLD = 60
QUALITY_MAX_DARK_AREA_RATIO = 0.15

# M4: Verificación de marcadores en posiciones esperadas.
# Margen adicional (px) alrededor del marcador oficial para recortar la
# región de interés donde se busca el marcador ya canonizado.
QUALITY_MARKER_ROI_MARGIN = 20
# % mínimo de píxeles oscuros dentro de la ROI para considerar que el
# marcador efectivamente está ahí (y no se perdió/deformó en el warp).
QUALITY_MIN_MARKER_DARK_RATIO = 0.25
# Tolerancia (px) entre el centroide oscuro encontrado y el centro
# oficial esperado (marcadores_centros.json).
QUALITY_MARKER_POSITION_TOLERANCE_PX = 15

# issue_code de LOW_CONFIDENCE (ver Anexo A). Tampoco hay un código
# dedicado en ISSUE_CODES para esto — se deja explícito como pendiente
# de confirmar con el equipo (P1/P3), igual que WARP_FAILED_ISSUE_CODE
# y MARKER_ISSUE_CODES["INVALID_ORIENTATION"].
QUALITY_LOW_CONFIDENCE_ISSUE_CODE = "CORRUPT_FILE"