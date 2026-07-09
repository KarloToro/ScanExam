# calculadora_origen_identificacion.py

from pathlib import Path

TOTAL_COLUMNAS = 8
VALORES = range(10)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_TXT = BASE_DIR / "scanexam_identificacion_xy.txt"

lineas = []

print("Calculadora de origen para código de estudiante")
print("Genera el insumo para generar_json_centros_identificacion.py")
print("Ingresa X e Y desde Figma.")
print("X e Y deben ser la esquina superior izquierda del círculo.")
print("Formato generado: id,x,y")
print("Orden esperado: id_c08_v0, id_c08_v1, ..., id_c08_v9, id_c07_v0, ... id_c01_v9")
print("Presiona Ctrl + C para terminar y guardar lo capturado.\n")

try:
    for columna in range(TOTAL_COLUMNAS, 0, -1):
        for valor in VALORES:
            bubble_id = f"id_c{columna:02d}_v{valor}"

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
            "# scanexam_identificacion_xy.txt",
            "# Formato: id,x,y",
            "# x,y son la esquina superior izquierda del círculo en Figma.",
            "# Sistema de coordenadas:",
            "# - Origen (0,0): esquina superior izquierda del frame.",
            "# - X crece hacia la derecha.",
            "# - Y crece hacia abajo.",
            "# - No invertir X/Y.",
            "# Nomenclatura:",
            "# - id_c08_v0 = identificación, columna 8, valor 0.",
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