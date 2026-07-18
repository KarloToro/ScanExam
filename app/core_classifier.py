# app/core_classifier.py
import json
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path

import config

# ---------------------------------------------------------------------------
# Definición de la Arquitectura (Debe coincidir exactamente con el entrenamiento)
# ---------------------------------------------------------------------------
class BubbleClassifier(nn.Module):
    def __init__(self, num_classes=3):
        super(BubbleClassifier, self).__init__()
        
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(2, 2)
        
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(2, 2)
        
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.relu3 = nn.ReLU()
        self.pool3 = nn.MaxPool2d(2, 2)
        
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(64 * 8 * 8, 128)
        self.relu4 = nn.ReLU()
        self.dropout = nn.Dropout(0.5)
        self.fc2 = nn.Linear(128, num_classes)
        
    def forward(self, x):
        x = self.pool1(self.relu1(self.conv1(x)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = self.pool3(self.relu3(self.conv3(x)))
        
        x = self.flatten(x)
        x = self.relu4(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x

# ---------------------------------------------------------------------------
# Variables globales para Caching
# ---------------------------------------------------------------------------
_model = None
_labels_map = None
_device = None

def _initialize():
    """Carga el modelo y las etiquetas en memoria la primera vez que se necesita."""
    global _model, _labels_map, _device
    if _model is not None:
        return

    # Buscar la raíz del proyecto para ubicar la carpeta models/
    current = Path(__file__).resolve()
    project_root = current.parents[1]
    
    models_dir = project_root / "models"
    model_path = models_dir / "bubble_classifier_v1.pt"
    labels_path = models_dir / "labels.json"
    
    if not model_path.exists() or not labels_path.exists():
        raise FileNotFoundError(f"No se encontraron los archivos del modelo en {models_dir}")
        
    with open(labels_path, "r", encoding="utf-8") as f:
        _labels_map = json.load(f)
        
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    _model = BubbleClassifier(num_classes=len(_labels_map))
    _model.load_state_dict(torch.load(model_path, map_location=_device))
    _model.to(_device)
    _model.eval() # Modo inferencia (desactiva dropout, etc.)

# ---------------------------------------------------------------------------
# Funciones del Contrato Público para P3
# ---------------------------------------------------------------------------

def classify_bubble(image_source: str | Path | np.ndarray) -> dict:
    """
    Clasifica un recorte individual de 64x64 px.
    Recibe una ruta de archivo o un array de numpy (OpenCV).
    """
    _initialize()
    
    # 1. Cargar imagen si es una ruta
    if isinstance(image_source, (str, Path)):
        img = cv2.imread(str(image_source))
        if img is None:
            raise ValueError(f"No se pudo leer la imagen en {image_source}")
    else:
        img = image_source.copy()

    # 2. Preprocesamiento idéntico al entrenamiento
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
    if img.shape != (64, 64):
        img = cv2.resize(img, (64, 64))
        
    # Normalización manual a [-1, 1] y conversión a Tensor [Batch, Channel, H, W]
    img_float = img.astype(np.float32) / 255.0
    img_norm = (img_float - 0.5) / 0.5
    img_tensor = torch.from_numpy(img_norm).unsqueeze(0).unsqueeze(0).to(_device)

    # 3. Inferencia
    with torch.no_grad():
        outputs = _model(img_tensor)
        probabilities = F.softmax(outputs, dim=1)
        confidence, predicted_idx = torch.max(probabilities, 1)
        
    confidence_val = float(confidence.item())
    predicted_class = _labels_map[str(predicted_idx.item())]
    
    # 4. Regla de negocio: Forzar a GHOST si la confianza es baja
    if predicted_class in ["MARKED", "EMPTY"] and confidence_val < config.MIN_CLASSIFICATION_CONFIDENCE:
        predicted_class = "GHOST"

    return {
        "predicted_class": predicted_class,
        "confidence": round(confidence_val, 4)
    }

def classify_crop_with_id(crop_id: str, image_source: str | Path | np.ndarray) -> dict:
    """
    Función de conveniencia para empaquetar el ID del recorte junto con la predicción.
    """
    result = classify_bubble(image_source)
    return {
        "crop_id": crop_id,
        "predicted_class": result["predicted_class"],
        "confidence": result["confidence"]
    }

def classify_crops(crops: list[dict]) -> list[dict]:
    """
    Procesa un lote de recortes. 
    Espera una lista de diccionarios con formato: {"crop_id": "...", "path": "..."}
    Devuelve la estructura JSON completa esperada por el pipeline.
    """
    predictions = []
    for crop in crops:
        pred = classify_crop_with_id(crop["crop_id"], crop["path"])
        predictions.append(pred)
        
    return predictions

if __name__ == "__main__":
    #---------------------------------------------------
    #Prueba rápida si ejecutas el script directamente
    #print("El módulo de clasificación está listo para integrarse.")
    #---------------------------------------------------
    from pathlib import Path
    
    # 1. Buscamos un par de imágenes de prueba en tu dataset generado
    project_root = Path(__file__).resolve().parents[1]
    dataset_dir = project_root / "data" / "dataset_burbujas"
    
    # Tomamos la primera imagen que encontremos en MARKED y EMPTY
    img_marked = next((dataset_dir / "MARKED").glob("*.png"), None)
    img_empty = next((dataset_dir / "EMPTY").glob("*.png"), None)
    
    print("Iniciando prueba de integración del clasificador...\n")
    
    if img_marked:
        resultado = classify_bubble(img_marked)
        print(f"Prueba MARKED ({img_marked.name}):")
        print(f"  -> {resultado}")
        
    if img_empty:
        resultado = classify_crop_with_id("q_01_A", img_empty)
        print(f"\nPrueba EMPTY con ID ({img_empty.name}):")
        print(f"  -> {resultado}")
        
    # Prueba de lote (simulando a P3)
    if img_marked and img_empty:
        lote = [
            {"crop_id": "q_02_B", "path": str(img_marked)},
            {"crop_id": "q_03_C", "path": str(img_empty)}
        ]
        resultados_lote = classify_crops(lote)
        print("\nPrueba de Lote completo:")
        for res in resultados_lote:
            print(f"  -> {res}")