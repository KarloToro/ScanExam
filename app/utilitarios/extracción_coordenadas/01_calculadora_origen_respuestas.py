# calculadora_origen_burbuja.py

from pathlib import Path

OPTIONS = ["A", "B", "C", "D", "E"]
TOTAL_QUESTIONS = 10

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_TXT = BASE_DIR / "scanexam_respuestas_xy.txt"

lineas = []

print("Calculadora de origen de burbujas")
print("Genera el insumo para generar_json_centros.py")
print("Ingresa X e Y desde Figma.")
print("X e Y deben ser la esquina superior izquierda del círculo.")
print("Formato generado: id,x,y")
print("Orden esperado: q_01_A, q_01_B, ..., q_01_E, q_02_A, ... q_10_E")
print("Presiona Ctrl + C para terminar y guardar lo capturado.\n")

try:
    for question in range(1, TOTAL_QUESTIONS + 1):
        for option in OPTIONS:
            bubble_id = f"q_{question:02d}_{option}"

            print(f"Burbuja actual: {bubble_id}")

            x = input("X: ").strip()
            y = input("Y: ").strip()

            # Validación básica
            float(x)
            float(y)

            linea = f"{bubble_id},{x},{y}"
            lineas.append(linea)

            print(linea)
            print("-" * 35)

except ValueError:
    print("\nError: ingresa solo números.")

except KeyboardInterrupt:
    print("\nCaptura interrumpida por el usuario.")

finally:
    if lineas:
        contenido = "\n".join([
            "# scanexam_respuestas_xy.txt",
            "# Formato: id,x,y",
            "# x,y son la esquina superior izquierda del círculo en Figma.",
            "# Sistema de coordenadas:",
            "# - Origen (0,0): esquina superior izquierda del frame.",
            "# - X crece hacia la derecha.",
            "# - Y crece hacia abajo.",
            "# - No invertir X/Y.",
            "",
            *lineas
        ])

        OUTPUT_TXT.write_text(contenido, encoding="utf-8")

        print("\nTXT generado correctamente:")
        print(OUTPUT_TXT)

        print("\nContenido generado:")
        print(contenido)
    else:
        print("\nNo se capturaron coordenadas.")