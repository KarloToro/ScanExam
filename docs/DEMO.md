# 🎬 Runbook de la demo — ScanExam AI

Guía para **levantar todo y demostrar el flujo completo**, por terminal y por
navegador. Pensada para la exposición. Para entender los componentes ver
[`ARQUITECTURA.md`](ARQUITECTURA.md).

---

## 0. Prerrequisitos

```bash
sudo systemctl start docker          # el daemon no arranca solo
cd ~/Documents/anycodef/ScanExam
```

## 1. Construir imágenes

```bash
DOCKER_BUILDKIT=0 docker compose build
```
> Compila `scanexam-app` (pipeline Python), `panel-api` (Go) y `panel-web` (Nuxt).
> `DOCKER_BUILDKIT=0` usa el builder legacy (esta máquina no tiene buildx).

## 2. Entrenar y versionar el modelo (MLflow)

**Mínimo — el champion directo:**
```bash
docker compose up -d mlflow
docker compose run --rm trainer python -m app.train_classifier --epochs 30 --run-name champion-f1-f9
```
> Entrena sobre `data/dataset_burbujas` (f1–f9), registra `bubble_classifier@champion`
> y exporta `models/bubble_classifier_v1.pt`.

**Plus para la expo — los 3 experimentos (compara curaciones de datos):**
```bash
docker compose up -d mlflow
IMG=scanexam-app:latest
RUN="docker run --rm -v $(pwd):/workspace -w /workspace -e PYTHONPATH=/workspace:/workspace/app $IMG"

$RUN python app/dataset_builder/build_variant.py --output data/_exp/f1_f6 \
  fotos_crudas_dataset/f1_especial.jpeg fotos_crudas_dataset/f2_especial.jpeg fotos_crudas_dataset/f3.jpg \
  fotos_crudas_dataset/f4.jpg fotos_crudas_dataset/f5.jpeg fotos_crudas_dataset/f6_recontra_especial.jpeg
$RUN python app/dataset_builder/build_variant.py --output data/_exp/f1_f9 \
  fotos_crudas_dataset/f1_especial.jpeg fotos_crudas_dataset/f2_especial.jpeg fotos_crudas_dataset/f3.jpg \
  fotos_crudas_dataset/f4.jpg fotos_crudas_dataset/f5.jpeg fotos_crudas_dataset/f6_recontra_especial.jpeg \
  fotos_crudas_dataset/f7_especial.jpeg fotos_crudas_dataset/f8_especial.jpeg fotos_crudas_dataset/f9_recontra_especial.jpeg
$RUN python app/dataset_builder/build_variant.py --output data/_exp/f1_f12 \
  fotos_crudas_dataset/f1_especial.jpeg fotos_crudas_dataset/f2_especial.jpeg fotos_crudas_dataset/f3.jpg \
  fotos_crudas_dataset/f4.jpg fotos_crudas_dataset/f5.jpeg fotos_crudas_dataset/f6_recontra_especial.jpeg \
  fotos_crudas_dataset/f7_especial.jpeg fotos_crudas_dataset/f8_especial.jpeg fotos_crudas_dataset/f9_recontra_especial.jpeg \
  "fotos_crudas_dataset/extra data/f10_recontra_especial.jpeg" \
  "fotos_crudas_dataset/extra data/f11_recontra_especial.jpeg" \
  "fotos_crudas_dataset/extra data/f12_recontra_especial.jpeg"

docker compose run --rm -e SCANEXAM_DATA_DIR=data/_exp/f1_f6  trainer python -m app.train_classifier --epochs 30 --run-name exp1-f1-f6
docker compose run --rm -e SCANEXAM_DATA_DIR=data/_exp/f1_f12 trainer python -m app.train_classifier --epochs 30 --run-name exp2-f1-f12
docker compose run --rm -e SCANEXAM_DATA_DIR=data/_exp/f1_f9  trainer python -m app.train_classifier --epochs 30 --run-name exp3-f1-f9
```
> **Narrativa:** más datos no siempre es mejor — `f1–f12` mete fichas degradadas
> que desbalancean; `f1–f9` es el champion. Se comparan en http://localhost:5000.

## 3. Levantar la plataforma completa

```bash
docker compose up -d scanexam-app n8n mongo mailpit panel-api panel-web mongo-express
docker compose ps                    # verificar Up/healthy
```
> `mongo-express` es la UI web para ver las colecciones de MongoDB (http://localhost:8081).

## 4. Arreglar permisos de `uploads/` (workaround temporal — [ADR-0010](adr/0010-permisos-volumen-compartido.md))

```bash
docker exec scanexam-app sh -c "mkdir -p /workspace/uploads && chmod -R 777 /workspace/uploads"
```
> Necesario hasta que P4 resuelva el uid de `panel-api`. Sin esto, el primer upload falla.

## 5. Importar y activar el workflow de n8n

```bash
docker exec scanexam-n8n n8n import:workflow --input=/workspace/n8n_workflows/scanexam_flujo_principal.json
docker exec scanexam-n8n n8n publish:workflow --id=scanexamMain0001
docker restart scanexam-n8n          # imprescindible para registrar el webhook
```

---

## 6. 🖥️ Demo por NAVEGADOR (la parte funcional)

**Paquete listo para cargar:** [`data/lotes_prueba/demo_panel/`](../data/lotes_prueba/demo_panel/)
- `ficha_sintetica.png` — ficha bien llenada (código `22200100`, sale **16/20**).
- `estudiantes.csv` — lista de matriculados (importable).
- `respuestas.csv` — clave de respuestas (importable).

> Si `ficha_sintetica.png` no existe (repo recién clonado), genérala:
> ```bash
> docker exec scanexam-app python -m app.utilitarios.generar_ficha_sintetica \
>   --code 22200100 --answers A,B,C,A,E,A,B,C,D,A \
>   --output data/lotes_prueba/demo_panel/ficha_sintetica.png
> ```

**Pasos en el navegador:**
1. Abre **http://localhost:3000** → **inicia sesión**: `admin` / `admin123`.
2. Nuevo examen → nombre p. ej. *"Parcial Demo"*.
3. **Estudiantes:** importa `estudiantes.csv` (o escribe en la tabla).
4. **Respuestas:** importa `respuestas.csv` (o escribe la clave).
5. **Fichas:** sube `ficha_sintetica.png`.
6. **Enviar** → el panel dispara el pipeline y muestra el resultado (**16/20**).
7. **http://localhost:8025** (mailpit) → verás el correo con la nota + clave de acceso.
8. Abre el enlace de consulta del correo (`/consulta/<id>`) → el alumno ve su nota
   ingresando la **clave de acceso**.
9. *(Opcional, para mostrar la persistencia)* **http://localhost:8081** (mongo-express)
   → base **`exams`** → colección **`results`**: ahí está el documento con la nota
   y la clave de acceso; en **`batches`**, el resumen del lote.

---

## 7. 🧪 Demo por TERMINAL (alternativa / verificación)

```bash
# 1. Login -> JWT
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H "Content-Type: application/json" \
  -d '{"login":"admin","password":"admin123"}' | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")

# 2. Subir el examen (dispara TODO el pipeline)
curl -s -X POST http://localhost:8080/exams/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "name=Parcial Demo" \
  -F "images=@data/lotes_prueba/demo_panel/ficha_sintetica.png" \
  -F "students=@data/lotes_prueba/demo_panel/estudiantes.csv" \
  -F "answers=@data/lotes_prueba/demo_panel/respuestas.csv" | python3 -m json.tool

# 3. Ver el correo en mailpit
curl -s http://localhost:8025/api/v1/messages | python3 -c "import json,sys;m=json.load(sys.stdin)['messages'][0];print('para:',m['To'][0]['Address'],'| asunto:',m['Subject'])"
```

Pipeline directo (sin panel), por el webhook de n8n:
```bash
curl -s -X POST http://localhost:5678/webhook/scanexam -H "Content-Type: application/json" \
  -d '{"batch_id":"BATCH-DEMO","source":"data/lotes_prueba/sintetico"}' | python3 -m json.tool
```

---

## 8. URLs de la demo

| URL | Qué mostrar |
| --- | --- |
| http://localhost:3000 | Panel docente (`admin`/`admin123`) |
| http://localhost:8025 | Mailpit — correo con nota + clave |
| http://localhost:8081 | mongo-express — colecciones (`exams`: batches/results, `users`) |
| http://localhost:5000 | MLflow — 3 experimentos + champion |
| http://localhost:5678 | n8n — workflow / Executions |
| http://localhost:8000/docs | Swagger de la API del pipeline |

## 9. Comandos de rescate

```bash
docker compose ps                    # estado de todos los servicios
docker compose logs -f panel-api     # logs de un servicio
docker compose down                  # apagar (mantiene datos)
docker compose down -v               # apagar y BORRAR datos (mongo, mlflow, n8n)
```
