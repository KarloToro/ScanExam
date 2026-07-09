## Política de procesamiento por lote / zip

Para agilizar el desarrollo de la demo ScanExam sigue la siguiente politica:

Solo se pasa a una nueva etapa 
Un lote solo se considera exitoso cuando todas las fichas incluidas en el ZIP de entrada pueden transformarse correctamente a imagen canónica y ser procesadas por el pipeline.

Si una o más fichas fallan durante la corrección de perspectiva, el lote completo se marca como `ERROR_BATCH_INCOMPLETE`. En ese caso, el sistema no genera un archivo final de notas, sino un ZIP de diagnóstico con las fichas rechazadas y el motivo del rechazo.

Esta decisión evita implementar fusión automática de resultados entre múltiples subidas, reemplazo individual de imágenes, historial de intentos o estado persistente de lote.

### Flujo con error

Si el docente sube 30 fichas y 3 no pueden corregirse por perspectiva:

- el lote se marca como incompleto;
- las fichas fallidas se copian en `rechazadas/`;
- el sistema genera un reporte de observaciones;
- el docente debe tomar nuevamente foto a esas fichas;
- el docente debe reemplazarlas en el ZIP original;
- el docente debe subir nuevamente el ZIP completo.

### ZIP de diagnóstico

```text
diagnostico_E_Parcial_Seccion_A.zip
├── instrucciones_reintento.txt
├── resumen_procesamiento.json
├── reporte_observaciones.xlsx
└── rechazadas/
    ├── ficha_007_MARKERS_NOT_FOUND.jpg
    ├── ficha_013_LOW_CONFIDENCE.jpg
    └── ficha_021_WARP_FAILED.jpg