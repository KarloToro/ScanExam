# Contrato de Orquestación y Motor de Reglas (n8n)

## Propósito

Este documento define la estructura, responsabilidades y el diseño del flujo de trabajo (workflow) gestionado por n8n dentro de la arquitectura de ScanExam AI.

Para cumplir con los requerimientos técnicos y arquitectónicos del proyecto, n8n no actúa como un simple disparador secuencial. n8n opera como el **orquestador central y motor de decisiones lógicas**. El flujo delega el procesamiento pesado a los módulos de Python (Visión y Red Neuronal), recupera los resultados y ejecuta la inferencia de reglas académicas directamente en sus nodos.

---

## Fases del Workflow

### 1. Recepción del Evento de Inicio
*   **Nodo n8n:** `Webhook`
*   **Descripción:** El flujo se inicializa mediante una arquitectura orientada a eventos.
*   **Integración:** Una vez que el Módulo Frontend (P4) valida estructuralmente el archivo ZIP y extrae los elementos en la carpeta `input/` del lote correspondiente, emite una petición HTTP (POST) a la URL del Webhook de n8n.
*   **Formato del Payload:**
    ```json
    {
      "batch_id": "BATCH-001"
    }
    ```
*   **Justificación Arquitectónica:** Cumple con el requerimiento de implementar un "sistema basado en eventos".

---

### 2. Delegación de Visión Computacional (Módulo P2)
*   **Nodo n8n:** `Execute Command`
*   **Descripción:** n8n invoca el procesamiento geométrico y la validación de calidad visual.
*   **Comando de ejecución:**
    ```bash
    python app/core_vision.py --batch BATCH-001
    ```
*   **Integración:** n8n pausa el flujo hasta que el script finaliza. El Módulo P2 no toma decisiones de negocio; su alcance es estrictamente trigonométrico y visual, retornando la imagen canónica (PNG) y el artefacto `vision_manifest.json`.

---

### 3. Enrutamiento Lógico y Control de Calidad
*   **Nodos n8n:** `Read/Write Files`, `Loop` (o `Item Lists`), `If` (o `Switch`)
*   **Descripción:** n8n lee el `vision_manifest.json` emitido por P2 e itera sobre cada ficha procesada.
*   **Integración:** El orquestador divide el flujo de procesamiento basado en variables de estado:
    *   **Camino A (`status == "OK"`):** La ficha supera los umbrales de calidad y avanza a la fase de Inteligencia Artificial.
    *   **Camino B (`status == "ERROR"`):** n8n enruta la ficha directamente a la lista de "Fichas observadas/rechazadas", deteniendo su procesamiento individual.
*   **Justificación Arquitectónica:** Demuestra la toma de decisiones y control de flujo condicional dentro del orquestador.

---

### 4. Delegación de Clasificación Inteligente (Módulo P1)
*   **Nodo n8n:** `Execute Command`
*   **Descripción:** Para las fichas validadas (Camino A), n8n ordena la generación de recortes (crops) y la inferencia en la red neuronal (CNN).
*   **Comando de ejecución:**
    ```bash
    python app/core_classifier.py --image work/normalized/ficha_001.png
    ```
*   **Integración:** La CNN realiza una evaluación visual pura y retorna el archivo `bubble_predictions.json`. 
    *   **Nota de alcance:** La red neuronal *no* dictamina la correctitud de la respuesta ni aplica reglas académicas; se limita a clasificar la naturaleza visual del trazo (`EMPTY`, `MARKED`, `GHOST`).
    *   **Formato esperado:**
        ```json
        [
          {"crop_id": "q_01_A", "predicted_class": "MARKED"},
          {"crop_id": "q_01_B", "predicted_class": "GHOST"}
        ]
        ```

---

### 5. Motor de Reglas Inteligentes (Core Académico)
*   **Nodos n8n:** `Code` (JavaScript) o conjunto de nodos lógicos (`If`, `Switch`)
*   **Descripción:** n8n asume el rol de motor de inferencia, aplicando las reglas del sistema para interpretar las marcas.
*   **Integración:**
    1. n8n lee los archivos `bubble_predictions.json` y `Respuestas.csv`.
    2. **Aplicación de reglas:** El orquestador evalúa los estados de las burbujas. Si coexisten un `MARKED` y un `GHOST`, el código en n8n decide ignorar el `GHOST` (Regla de oro). Si identifica múltiples `MARKED`, el nodo deduce un `DOUBLE_MARK`.
    3. **Cálculo de puntaje:** n8n compara la decisión interpretada con la clave del docente (`Respuestas.csv`) y calcula los puntos obtenidos.
*   **Justificación Arquitectónica:** Este componente cumple directamente con el requerimiento de "Incorporar al menos un mecanismo de decisión inteligente (reglas, clasificación...)". Al residir el motor de evaluación en los flujos lógicos de n8n, se consolida su rol como orquestador inteligente y no como un simple disparador de scripts.

---

### 6. Consolidación y Salida
*   **Nodos n8n:** `Read/Write Files`, (Opcional: `Send Email`, `HTTP Request`)
*   **Descripción:** n8n consolida todas las evaluaciones individuales y formaliza el cierre del proceso.
*   **Integración:** 
    *   El orquestador agrupa la data generada y escribe el archivo final `resultados.json`.
    *   *(Opcional)*: Se pueden integrar notificaciones asíncronas, como el envío automático de un correo al docente o un aviso HTTP al Módulo Frontend (P4) para activar indicadores visuales/sonoros de finalización.