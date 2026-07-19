# Imagen scanexam-app: entrenamiento (P1), pipeline de integración (P3),
# servidor MLflow y panel stub (P4). Una sola imagen reutilizable.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libGL/glib: requeridas por opencv aunque sea headless en algunas rutas.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Instalar dependencias primero (capa cacheable). torch se toma de PyPI (CPU).
COPY docker/requirements-app.txt /tmp/requirements-app.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements-app.txt

# El código se monta como volumen en desarrollo (ver docker-compose.yml),
# por eso no se hace COPY del proyecto aquí: mantiene la imagen liviana y
# permite iterar sin reconstruir.

CMD ["python", "-m", "app.train_classifier"]
