# generar_json_centros_identificacion.py

import json
from pathlib import Path

BUBBLE_SIZE = 48

BASE_DIR = Path(__file__).resolve().parent

INPUT_TXT = BASE_DIR / "scanexam_identificacion_xy.txt"
OUTPUT_JSON = BASE_DIR / "scanexam_identificacion_centros.json"


def parse_line(line: str, line_number: int):
    line = line.strip()

    if not line or line.startswith("#"):
        return None

    parts = [part.strip() for part in line.split(",")]

    if len(parts) != 3:
        raise ValueError(
            f"Línea {line_number}: formato inválido. Usa: id,x,y"
        )

    bubble_id, x_raw, y_raw = parts

    try:
        x = float(x_raw)
        y = float(y_raw)
    except ValueError:
        raise ValueError(
            f"Línea {line_number}: X e Y deben ser numéricos."
        )

    return bubble_id, x, y


def main():
    input_path = INPUT_TXT
    output_path = OUTPUT_JSON

    if not input_path.exists():
        raise FileNotFoundError(
            f"No se encontró {input_path}"
        )

    half = BUBBLE_SIZE / 2
    centers = {}

    with input_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            parsed = parse_line(line, line_number)

            if parsed is None:
                continue

            bubble_id, x, y = parsed

            if bubble_id in centers:
                raise ValueError(
                    f"Línea {line_number}: id repetido: {bubble_id}"
                )

            cx = round(x + half)
            cy = round(y + half)

            centers[bubble_id] = [cx, cy]

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(centers, file, indent=4, ensure_ascii=False)

    print("JSON generado correctamente:")
    print(output_path)
    print()
    print(json.dumps(centers, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()