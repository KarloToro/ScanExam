> **Nota de Evolución:** Este documento reemplaza a la v7 y a la documentación de integración distribuida. El sistema ha evolucionado de un ecosistema complejo (orquestado por n8n, con microservicios en Go/Nuxt y persistencia en MongoDB) hacia un **monolito ligero, sin estado y de ejecución instantánea**. Las reglas académicas y de visión por computadora se mantienen intactas.

## 1. Descripción General

ScanExam AI es un sistema de ejecución local para la corrección automática de hojas de respuestas ópticas a partir de fotografías. Está diseñado para docentes que necesitan evaluar exámenes en papel de manera rápida, combinando la eficiencia digital con la transparencia del papel.

El sistema no busca reemplazar la revisión docente; automatiza la corrección de las fichas confiables y separa los casos que requieren intervención humana.

## 2. Decisiones Técnicas Implementadas (El Nuevo Paradigma)

Para maximizar la adopción por parte de docentes no técnicos en entornos Windows, la arquitectura se ha rediseñado bajo el principio de simplicidad extrema:

- **Monolito FastAPI:** Todo el backend y la lógica de negocio se unifican en una sola aplicación de Python servida por FastAPI.

- **Procesamiento Stateless y en Memoria (Cero I/O)**: La aplicación procesa los exámenes enteramente en la memoria RAM del servidor. FastAPI recibe las imágenes en bruto (UploadFile) y las convierte mediante OpenCV en arreglos de NumPy. Los 130 recortes (crops) por ficha se calculan y recortan matemáticamente en memoria, evitando por completo escribir archivos temporales (como carpetas work/crops/ o imágenes intermedias .png) en el disco duro. Al finalizar, se emite el Excel en un buffer y la RAM se limpia de inmediato.

- **Frontend Modular sin dependencias:** La interfaz de usuario abandona los frameworks pesados de JavaScript. Se sirve directamente desde FastAPI usando `Jinja2`, `Bootstrap 5` (vía CDN) y `PapaParse` para que el docente pueda editar los CSV de estudiantes y respuestas directamente en el navegador.
    

## 3. Lo que se elimina (Reducción de Complejidad)

Para lograr la versión 8, se ha purgado intencionalmente la siguiente deuda técnica y complejidad arquitectónica:

- **n8n (Orquestador):** Se elimina el orquestador asíncrono. El flujo ahora es secuencial y atómico dentro de Python, eliminando la sobrecarga de red interna.
    
- **Microservicios de Go y Nuxt:** Se eliminan `panel-api` (escrito en Go) y `panel-web` (escrito en Nuxt/Vue).
    
- **MongoDB:** Se elimina la persistencia de usuarios, lotes y resultados en bases de datos NoSQL.
    
- **Mailpit y Notificaciones SMTP:** Se elimina el envío automático de correos con claves de acceso a los estudiantes. El output final del sistema vuelve a ser un archivo Excel manejable por el docente.
    
- **Archivos ZIP:** El sistema ya no recibe un archivo `.zip` con carpetas internas. El frontend envía directamente las fotos y los JSON (CSVs parseados) vía `multipart/form-data`.
    
- **MLflow en Producción:** El servidor de MLflow se retira del entorno de producción; el sistema simplemente carga el archivo de pesos `.pt` de forma estática.
    

## 4. Reglas Centrales del Sistema (El Corazón Académico)

ScanExam califica automáticamente una ficha únicamente cuando se cumplen dos condiciones:

1. La imagen corresponde a una ficha óptica válida y procesable.
    
2. El estudiante fue identificado correctamente a partir del código marcado.
    

### 4.1 Estados de Procesamiento

- **OK:** La ficha fue procesada, el estudiante identificado, se generó nota y el resultado es publicable.
    
- **OBSERVED:** La ficha es procesable visualmente, pero el estudiante no fue identificado de forma confiable. Pasa a revisión docente y no genera nota (`score = null`).
    
- **ERROR:** La ficha no pudo procesarse por un problema técnico, visual o geométrico extremo.
    

### 4.2 Reglas de Interpretación por Pregunta

El modelo clasifica las burbujas en tres estados: `EMPTY`, `MARKED` o `GHOST`. La regla de oro del sistema es:

- **`MARKED` manda, `GHOST` solo advierte.** Si coexisten una marca fuerte (`MARKED`) y un borrón residual (`GHOST`), el sistema ignora el `GHOST` y acepta la marca fuerte.
    
- Si hay dos o más opciones `MARKED`, se considera doble marca (`DOUBLE_MARK`) y el puntaje es 0.
    
- Si solo hay borrones (`GHOST`), la pregunta se marca como dudosa (`UNCERTAIN`) y el puntaje es 0.
    
- El puntaje solo se asigna si la respuesta aceptada coincide exactamente con la clave correcta.
    

## 5. El Nuevo Flujo Final (v8)

1. El docente accede a la web local, sube sus archivos CSV (`Estudiantes.csv` y `Respuestas.csv`) y los valida/edita visualmente en el navegador.
    
2. El docente selecciona las fotografías de las fichas ópticas y hace clic en "Procesar".
    
3. El frontend empaqueta las imágenes y los datos estructurados en un solo request HTTP hacia el endpoint `/upload` de FastAPI.
    
4. **Capa de Visión:** Normaliza las fotos en memoria y extrae las coordenadas.
    
5. **IA y Reglas:** La CNN clasifica los recortes y el motor académico aplica las reglas deterministas de calificación.
    
6. El backend construye un `DataFrame` de Pandas con las notas de todas las fichas `OK` (y detalla los motivos de los casos `OBSERVED`/`ERROR`).
    
7. El sistema devuelve un archivo `.xlsx` (Excel) generado en memoria directamente como descarga automática para el docente.

8. El Patrón Adaptador (main.py): La capa web de FastAPI actúa puramente como un traductor. Toma los JSONs planos del navegador (parseados con PapaParse desde los CSVs) y los adapta a las estructuras que el motor determinista de Python ya espera (scoring_engine.py), conectando la web con las funciones de PyTorch sin romper el dominio original.