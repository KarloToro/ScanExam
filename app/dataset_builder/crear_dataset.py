import cv2
import sys
from pathlib import Path

# --- AJUSTE DE IMPORTACIONES ---
SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent
sys.path.append(str(APP_DIR))

from template_loader import load_template
from core_vision import process_ficha, extraer_recorte

def obtener_etiqueta_respuesta(bubble_id: str) -> str:
    """
    Mapea opciones de respuestas a sus etiquetas de entrenamiento.
    Convención: A -> EMPTY | B, C -> MARKED | D, E -> GHOST
    """
    opcion = bubble_id.split('_')[-1]  # Ej: de "q_01_A" extrae "A"
    
    if opcion == 'A':
        return "EMPTY"
    elif opcion in ['B', 'C']:
        return "MARKED"
    elif opcion in ['D', 'E']:
        return "GHOST"
    return "sin_etiquetar"

def obtener_etiqueta_identificacion(bubble_id: str) -> str:
    """
    Mapea columnas de identificación a sus etiquetas de entrenamiento.
    Convención: col 1, 2 -> EMPTY | col 3, 4, 5 -> MARKED | col 6, 7, 8 -> GHOST
    """
    # Ej: de "id_c08_v0" extrae "c08" y luego el número 8
    parte_columna = bubble_id.split('_')[1]
    numero_columna = int(parte_columna.replace('c', ''))
    
    if numero_columna in [8, 7]:
        return "EMPTY"
    elif numero_columna in [6, 5, 4]:
        return "MARKED"
    elif numero_columna in [3, 2, 1]:
        return "GHOST"
    return "sin_etiquetar"

def main():
    print("Iniciando extracción y auto-etiquetado de crops...")
    
    template = load_template()
    crop_size = template.crop_size_px
    
    PROJECT_ROOT = APP_DIR.parent 
    input_dir = PROJECT_ROOT / "fotos_crudas_dataset" 
    base_output_dir = PROJECT_ROOT / "data" / "dataset_burbujas"
    
    input_dir.mkdir(parents=True, exist_ok=True)
    
    # Crear carpetas de clases
    clases = ["EMPTY", "MARKED", "GHOST", "sin_etiquetar"]
    for clase in clases:
        (base_output_dir / clase).mkdir(parents=True, exist_ok=True)
    
    fotos = list(input_dir.glob("*.jpg")) + list(input_dir.glob("*.jpeg")) + list(input_dir.glob("*.png"))
    
    if not fotos:
        print(f"No se encontraron imágenes en {input_dir}. Añade tus fichas maestras y vuelve a ejecutar.")
        return

    for image_path in fotos:
        print(f"Procesando {image_path.name}...")
        
        resultado = process_ficha(image_path)
        
        if resultado.status != "OK":
            print(f"  -> Error al canonizar: {resultado.message}")
            continue
            
        imagen_canonica = resultado.canonical_image
        
        # Procesar crops de respuestas
        for bubble_id, center in template.answers_centers.items():
            crop = extraer_recorte(imagen_canonica, center, crop_size)
            etiqueta = obtener_etiqueta_respuesta(bubble_id)
            
            nombre_salida = base_output_dir / etiqueta / f"{image_path.stem}_{bubble_id}.png"
            cv2.imwrite(str(nombre_salida), crop)
            
        # Procesar crops de identificación
        for bubble_id, center in template.student_id_centers.items():
            crop = extraer_recorte(imagen_canonica, center, crop_size)
            etiqueta = obtener_etiqueta_identificacion(bubble_id)
            
            nombre_salida = base_output_dir / etiqueta / f"{image_path.stem}_{bubble_id}.png"
            cv2.imwrite(str(nombre_salida), crop)
            
    print(f"¡Extracción finalizada! Revisa tu dataset estructurado en: {base_output_dir}")

if __name__ == "__main__":
    main()