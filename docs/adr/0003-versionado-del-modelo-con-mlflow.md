# ADR-0003: Versionado del modelo con MLflow y alias `champion`

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

El clasificador de burbujas (CNN) fue desarrollado por el equipo de P1 y entregado
como **notebook** (`notebooks/clasificador_burbujas.ipynb`), sin los pesos entrenados
ni tracking de experimentos. Nuestra responsabilidad es **integrar**, no re-diseñar
el modelo (P3 "no entrena la CNN, la consume"). Se necesita, sin embargo, versionar
de forma reproducible el modelo que consume el pipeline.

Un notebook ejecutado "una vez" no es reproducible ni versionable.

## Decisión

1. **Entrenamiento reproducible:** se extrae la lógica del notebook a un script
   `app/train_classifier.py` con **semilla fija**, misma arquitectura y
   preprocesamiento que `app/core_classifier.py`. El notebook queda como material de
   exploración.
2. **Versionado con MLflow:** el entrenamiento registra en MLflow los
   hiperparámetros, métricas por época, reporte de clasificación, matriz de confusión
   y el modelo. El modelo se registra en el **Model Registry** como
   `bubble_classifier` y se le asigna el alias **`champion`**.
3. **Infraestructura:** servidor MLflow dockerizado (`docker-compose.yml`, servicio
   `mlflow`) con backend SQLite y artefactos servidos por el propio server.
4. **Contrato de runtime estable:** el pipeline carga el modelo desde la ruta fija
   `models/bubble_classifier_v1.pt` (+ `labels.json`), que el entrenamiento exporta.
   MLflow es la fuente de verdad del *linaje*; el runtime no depende de MLflow.

## Consecuencias

**Positivas**
- Ingesta estándar de un modelo externo (práctica común de MLOps); el notebook de
  otro equipo no es impedimento.
- Trazabilidad completa (params, métricas, artefactos) para la defensa técnica.
- El runtime queda desacoplado: si MLflow no está disponible, el pipeline igual carga
  el `.pt` de la ruta estable.

**Negativas / trade-offs**
- Un servicio adicional (MLflow) que mantener.
- Se debió ajustar la API de MLflow 3.x: `--allowed-hosts` (protección anti
  DNS-rebinding) y `serialization_format="pickle"` (el default `pt2` falla al trazar
  esta CNN).

## Notas / limitaciones

- El `val_acc` reportado (~100%) es engañoso por **fuga de datos** en el dataset de
  P1: las variantes aumentadas `v0..v9` del mismo recorte se reparten entre train y
  validación. Es una limitación del dataset, no del pipeline; se registra para no
  presentar esa métrica como real.

## Alternativas consideradas

- **Ejecutar el notebook headless (papermill/nbconvert):** más rápido pero no produce
  un artefacto reproducible ni limpio. Descartada.
- **Solo Git/DVC del `.pt`, sin MLflow:** más simple pero se pierde el tracking de
  experimentos y el registro con alias. Descartada.
