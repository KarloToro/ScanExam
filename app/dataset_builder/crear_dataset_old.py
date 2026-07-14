import cv2
import sys
from pathlib import Path

# --- AJUSTE DE IMPORTACIONES ---
# Obtenemos la ruta absoluta de este script (app/dataset_builder/crear_dataset.py)
SCRIPT_DIR = Path(__file__).resolve().parent
# Subimos un nivel para llegar a la carpeta 'app/'
APP_DIR = SCRIPT_DIR.parent
# Agregamos 'app/' al path de Python para que reconozca los módulos hermanos
sys.path.append(str(APP_DIR))

# Ahora podemos importar los módulos de P2 sin problemas
from template_loader import load_template
from core_vision import process_ficha, extraer_recorte

def main():
    print("Iniciando extracción de crops para dataset...")
    
    # 1. Cargar la plantilla (obtiene centros y tamaño de crop automágicamente)
    template = load_template()
    crop_size = template.crop_size_px
    
    # 2. Definir rutas relativas a la raíz del proyecto
    # Subimos un nivel más desde 'app/' para llegar a la raíz del proyecto
    PROJECT_ROOT = APP_DIR.parent 
    
    # Directorio donde pondrás tus fotos tomadas con el celular/escáner
    input_dir = PROJECT_ROOT / "fotos_crudas_dataset" 
    # Directorio donde se guardarán los recortes (64x64) generados
    output_dir = PROJECT_ROOT / "data" / "dataset_burbujas" / "sin_etiquetar"
    
    # Creamos las carpetas si no existen para evitar errores
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fotos = list(input_dir.glob("*.jpg")) + list(input_dir.glob("*.jpeg")) + list(input_dir.glob("*.png"))
    
    if not fotos:
        print(f"No se encontraron imágenes en {input_dir}. Añade fotos crudas y vuelve a ejecutar.")
        return

    # 3. Procesar cada imagen en la carpeta
    for image_path in fotos:
        print(f"Procesando {image_path.name}...")
        
        # 4. Canonizar la ficha usando P2
        resultado = process_ficha(image_path)
        
        if resultado.status != "OK":
            print(f"  -> Error al canonizar: {resultado.message}")
            continue
            
        imagen_canonica = resultado.canonical_image
        
        # 5. Extraer crops de respuestas
        for bubble_id, center in template.answers_centers.items():
            crop = extraer_recorte(imagen_canonica, center, crop_size)
            nombre_salida = output_dir / f"{image_path.stem}_{bubble_id}.png"
            cv2.imwrite(str(nombre_salida), crop)
            
        # 6. Extraer crops de identificación
        for bubble_id, center in template.student_id_centers.items():
            crop = extraer_recorte(imagen_canonica, center, crop_size)
            nombre_salida = output_dir / f"{image_path.stem}_{bubble_id}.png"
            cv2.imwrite(str(nombre_salida), crop)
            
    print(f"¡Extracción finalizada! Revisa los recortes en: {output_dir}")

if __name__ == "__main__":
    main()