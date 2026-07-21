# app/train_classifier.py
"""
Entrenamiento reproducible del clasificador de burbujas (P1) instrumentado con MLflow.

Este script es la versión reproducible y versionable del notebook
`notebooks/clasificador_burbujas.ipynb`. El notebook queda como material de
exploración; este script es la fuente de verdad del entrenamiento:

- semilla fija (entrenamiento reproducible, requisito para versionar con MLflow);
- misma arquitectura y preprocesamiento que `app/core_classifier.py` (contrato P1);
- registra en MLflow: hiperparámetros, métricas por época, reporte de
  clasificación, matriz de confusión y el modelo entrenado;
- registra el modelo en el Model Registry como `bubble_classifier` y le asigna
  el alias `champion` (el que consume el pipeline);
- exporta el mejor modelo a la ruta estable `models/bubble_classifier_v1.pt`
  y `models/labels.json`, que es lo que carga `core_classifier.py` en runtime.

Uso:
    python -m app.train_classifier
    python -m app.train_classifier --epochs 30 --no-mlflow

Variables de entorno relevantes:
    MLFLOW_TRACKING_URI   URI del servidor MLflow (p. ej. http://mlflow:5000)
    SCANEXAM_DATA_DIR     ruta al dataset (default: <root>/data/dataset_burbujas)
    SCANEXAM_MODELS_DIR   ruta de salida de modelos (default: <root>/models)
"""

import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms
from sklearn.metrics import classification_report, confusion_matrix

# Arquitectura: se importa desde core_classifier para garantizar que
# entrenamiento e inferencia usan EXACTAMENTE la misma red (contrato P1).
try:
    from app.core_classifier import BubbleClassifier
except ImportError:  # ejecución directa: python app/train_classifier.py
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.core_classifier import BubbleClassifier


# ---------------------------------------------------------------------------
# Configuración por defecto (coincide con el notebook original)
# ---------------------------------------------------------------------------
DEFAULT_BATCH_SIZE = 32
DEFAULT_EPOCHS = 10
DEFAULT_LEARNING_RATE = 0.001
DEFAULT_VAL_SPLIT = 0.2
DEFAULT_SEED = 42

REGISTERED_MODEL_NAME = "bubble_classifier"
CHAMPION_ALIAS = "champion"
MODEL_FILENAME = "bubble_classifier_v1.pt"
LABELS_FILENAME = "labels.json"


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "README.md").exists() and (parent / "requirements.txt").exists():
            return parent
    return Path(__file__).resolve().parents[1]


def set_seed(seed: int) -> None:
    """Fija todas las fuentes de aleatoriedad para un entrenamiento reproducible."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_transform() -> transforms.Compose:
    # Idéntico al preprocesamiento de core_classifier.py y del notebook.
    return transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((64, 64)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5]),  # [-1, 1]
    ])


def load_datasets(data_dir: Path, batch_size: int, val_split: float, seed: int):
    full_dataset = datasets.ImageFolder(root=str(data_dir), transform=build_transform())
    class_to_idx = full_dataset.class_to_idx  # {'EMPTY': 0, 'GHOST': 1, 'MARKED': 2}
    class_names = full_dataset.classes

    val_size = int(val_split * len(full_dataset))
    train_size = len(full_dataset) - val_size

    # Semilla fija en el split => reproducible (el notebook original no la fijaba).
    generator = torch.Generator().manual_seed(seed)
    train_dataset, val_dataset = random_split(
        full_dataset, [train_size, val_size], generator=generator
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    return train_loader, val_loader, class_names, class_to_idx


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    all_labels, all_preds = [], []
    with torch.no_grad():
        for inputs, labels in loader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            total_loss += criterion(outputs, labels).item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            all_labels.extend(labels.cpu().numpy())
            all_preds.extend(predicted.cpu().numpy())
    return total_loss / total, correct / total, all_labels, all_preds


def save_confusion_matrix(all_labels, all_preds, class_names, out_path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    cm = confusion_matrix(all_labels, all_preds)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=class_names, yticklabels=class_names)
    plt.title("Matriz de Confusión - Bubble Classifier")
    plt.ylabel("Clase Real")
    plt.xlabel("Clase Predicha")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300)
    plt.close()


def promote_to_champion(client, model_name: str, version: str) -> None:
    """Asigna el alias `champion` a la versión recién registrada."""
    client.set_registered_model_alias(model_name, CHAMPION_ALIAS, version)


def main():
    parser = argparse.ArgumentParser(description="Entrena el clasificador de burbujas (P1).")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--val-split", type=float, default=DEFAULT_VAL_SPLIT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--no-mlflow", action="store_true",
                        help="Entrena y exporta el .pt sin registrar en MLflow.")
    parser.add_argument("--run-name", default=None,
                        help="Nombre de la corrida en MLflow (para comparar experimentos).")
    args = parser.parse_args()

    root = find_project_root()
    data_dir = Path(os.environ.get("SCANEXAM_DATA_DIR", root / "data" / "dataset_burbujas"))
    models_dir = Path(os.environ.get("SCANEXAM_MODELS_DIR", root / "models"))
    models_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    set_seed(args.seed)

    print(f"[train] dispositivo   : {device}")
    print(f"[train] dataset       : {data_dir}")
    print(f"[train] salida modelos: {models_dir}")

    train_loader, val_loader, class_names, class_to_idx = load_datasets(
        data_dir, args.batch_size, args.val_split, args.seed
    )
    print(f"[train] clases        : {class_to_idx}")
    print(f"[train] train/val     : {len(train_loader.dataset)}/{len(val_loader.dataset)}")

    # labels.json en formato {"0": "EMPTY", ...} (contrato de core_classifier).
    labels_map = {str(idx): name for name, idx in class_to_idx.items()}
    labels_path = models_dir / LABELS_FILENAME
    with labels_path.open("w", encoding="utf-8") as f:
        json.dump(labels_map, f, indent=4)

    model = BubbleClassifier(num_classes=len(class_names)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    # --- MLflow (opcional) ---
    use_mlflow = not args.no_mlflow
    mlflow = None
    active_run = None
    if use_mlflow:
        try:
            import mlflow as _mlflow
            mlflow = _mlflow
            tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment("scanexam-bubble-classifier")
            active_run = mlflow.start_run(run_name=args.run_name)
            mlflow.log_params({
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.lr,
                "val_split": args.val_split,
                "seed": args.seed,
                "data_dir": str(data_dir),
                "train_size": len(train_loader.dataset),
                "val_size": len(val_loader.dataset),
                "architecture": "BubbleClassifier",
                "num_classes": len(class_names),
                "classes": ",".join(class_names),
            })
            print(f"[mlflow] tracking_uri : {mlflow.get_tracking_uri()}")
        except Exception as exc:  # noqa: BLE001
            print(f"[mlflow] deshabilitado (no disponible): {exc}")
            use_mlflow, mlflow, active_run = False, None, None

    model_save_path = models_dir / MODEL_FILENAME
    best_val_acc = 0.0

    print("[train] iniciando entrenamiento...")
    for epoch in range(args.epochs):
        model.train()
        running_loss, correct, total = 0.0, 0, 0
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        train_loss, train_acc = running_loss / total, correct / total
        val_loss, val_acc, _, _ = evaluate(model, val_loader, criterion, device)

        print(f"[train] epoch {epoch + 1:>2}/{args.epochs} "
              f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
              f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}")

        if use_mlflow:
            mlflow.log_metrics({
                "train_loss": train_loss, "train_acc": train_acc,
                "val_loss": val_loss, "val_acc": val_acc,
            }, step=epoch)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), model_save_path)
            print(f"[train]   -> nuevo mejor modelo (val_acc={val_acc:.4f})")

    print(f"[train] entrenamiento completado. best_val_acc={best_val_acc:.4f}")

    # --- Métricas formales sobre el mejor modelo ---
    model.load_state_dict(torch.load(model_save_path, map_location=device))
    _, final_val_acc, all_labels, all_preds = evaluate(model, val_loader, criterion, device)
    report = classification_report(all_labels, all_preds, target_names=class_names,
                                   digits=4, zero_division=0)
    print("\n--- Reporte de Clasificación ---\n" + report)

    cm_path = root / "docs" / "evidencia_modelo" / "matriz_confusion.png"
    save_confusion_matrix(all_labels, all_preds, class_names, cm_path)
    print(f"[train] matriz de confusión: {cm_path}")

    # --- Registro final en MLflow ---
    if use_mlflow:
        mlflow.log_metric("best_val_acc", best_val_acc)
        mlflow.log_artifact(str(labels_path))
        mlflow.log_artifact(str(cm_path))
        report_path = models_dir / "classification_report.txt"
        report_path.write_text(report, encoding="utf-8")
        mlflow.log_artifact(str(report_path))

        # Registrar el modelo y promoverlo a champion.
        model.load_state_dict(torch.load(model_save_path, map_location=device))
        model.eval()
        try:
            # MLflow 3.x: `name` reemplaza a `artifact_path`. El formato por
            # defecto 'pt2' traza el grafo con torch.export y es frágil con
            # esta CNN (falla dynamic_dim). Usamos 'pickle' (state_dict clásico),
            # que no traza y es suficiente para versionar/servir el modelo.
            input_example = np.zeros((1, 1, 64, 64), dtype=np.float32)
            info = mlflow.pytorch.log_model(
                pytorch_model=model,
                name="model",
                input_example=input_example,
                serialization_format=mlflow.pytorch.SERIALIZATION_FORMAT_PICKLE,
                registered_model_name=REGISTERED_MODEL_NAME,
            )
            from mlflow.tracking import MlflowClient
            client = MlflowClient()
            # La versión recién registrada es la más alta.
            versions = client.search_model_versions(f"name='{REGISTERED_MODEL_NAME}'")
            latest = max(versions, key=lambda v: int(v.version))
            promote_to_champion(client, REGISTERED_MODEL_NAME, latest.version)
            print(f"[mlflow] modelo registrado v{latest.version} "
                  f"con alias '@{CHAMPION_ALIAS}'")
        except Exception as exc:  # noqa: BLE001
            print(f"[mlflow] no se pudo registrar en el Model Registry: {exc}")

        mlflow.end_run()

    print(f"\n[train] modelo listo en: {model_save_path}")
    print(f"[train] labels en      : {labels_path}")


if __name__ == "__main__":
    main()
