# models/

Artefactos del clasificador de burbujas (P1) que consume el pipeline en runtime.

Los pesos (`*.pt`) están **ignorados por Git** (ver `.gitignore`): son binarios grandes
y su fuente de verdad es el entrenamiento versionado con MLflow. Esta carpeta se
mantiene en el repo solo por su estructura (`.gitkeep` + este README).

## Archivos esperados

| Archivo                     | Generado por                     | Consumido por            |
| --------------------------- | -------------------------------- | ------------------------ |
| `bubble_classifier_v1.pt`   | `app/train_classifier.py`        | `app/core_classifier.py` |
| `labels.json`               | `app/train_classifier.py`        | `app/core_classifier.py` |

`labels.json` mapea índice → clase, p. ej.:

```json
{ "0": "EMPTY", "1": "GHOST", "2": "MARKED" }
```

## Cómo generarlos (versionado con MLflow)

```bash
# Levanta MLflow y entrena; registra el modelo como bubble_classifier@champion
# y exporta el .pt + labels.json a esta carpeta.
docker compose up --build mlflow trainer
```

MLflow UI: http://localhost:5000 — experimento `scanexam-bubble-classifier`,
modelo registrado `bubble_classifier` (alias `@champion`).

También se puede entrenar sin MLflow (solo produce el `.pt`):

```bash
python -m app.train_classifier --no-mlflow
```
