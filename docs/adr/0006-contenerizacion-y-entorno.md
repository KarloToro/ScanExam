# ADR-0006: Contenerización y decisiones de entorno

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

El sistema debe correr localmente sobre una VM Ubuntu con Docker Compose (n8n +
scanexam-app + MLflow). Al montar el entorno aparecieron varias restricciones
concretas del host y del ecosistema de dependencias que condicionan la
contenerización.

## Decisión

1. **Una sola imagen reutilizable `scanexam-app`** (`docker/app.Dockerfile`, base
   `python:3.12-slim`) que sirve para: entrenamiento (P1), servidor MLflow, pipeline
   (P3) y stub del panel (P4). El código se monta como volumen (`./:/workspace`) para
   iterar sin reconstruir.
2. **MLflow corre desde la misma imagen** (ya trae `mlflow`), evitando depender de
   descargar imágenes externas.
3. **`PYTHONPATH=/workspace:/workspace/app`** en el servicio, porque `core_classifier.py`
   (P1) hace `import config` (sin prefijo de paquete). Se resuelve por entorno para no
   modificar el archivo de P1.
4. **`pandas<3` + `mlflow==3.14.0`** en la imagen: MLflow (todas las versiones
   disponibles) exige `pandas<3`; el código de P3/P4 no usa APIs exclusivas de
   pandas 3.

## Consecuencias y notas de operación

- **Docker daemon no arranca solo:** requiere `sudo systemctl start docker`.
- **Falta el plugin `buildx`:** los builds usan el builder clásico
  (`DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0`).
- **Máquina CPU-only:** `pip install torch` trae por defecto el wheel con CUDA
  (~2.5 GB, imagen ~5.95 GB) que no se usa.
  **TODO (optimización, no bloqueante):** instalar torch desde el índice CPU
  (`--index-url https://download.pytorch.org/whl/cpu`) para bajar la imagen a
  ~1.5 GB y acelerar rebuilds.
- **MLflow 3.x:** requiere `--allowed-hosts` (protección anti DNS-rebinding) para
  aceptar el header `Host: mlflow:5000`, y `serialization_format="pickle"` al
  registrar el modelo (el default `pt2` traza el grafo y falla con esta CNN).

## Alternativas consideradas

- **Imagen oficial de MLflow (ghcr):** añade una descarga externa y una imagen más que
  mantener; se prefirió reutilizar la imagen de app. Descartada.
- **Instalar dependencias en un venv del host (sin Docker):** contradice la decisión de
  contenerizar todo; se mantiene solo como fallback de emergencia. Descartada.
