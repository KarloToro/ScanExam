## Decisión de alcance: eliminación de variantes de examen A/B en ScanExam v1

##### Estado: Adoptada y Vigente

En versiones preliminares de la documentación se consideró que ScanExam soportaría tipos de examen A y B dentro de una misma plantilla. Sin embargo, la plantilla oficial `ficha_optica_a5_horizontal_v1` no incluye una región física para marcar el tipo de examen.

Para mantener la estabilidad de la plantilla, evitar cambios en el módulo de canonización y reducir el riesgo de integración, no se soportaran variantes A/B dentro de una misma ficha.

A partir de esta decisión, cada lote se procesará con una única clave de respuestas. Esto significa que todas las fichas incluidas en un ZIP pertenecen al mismo examen y se califican contra el mismo archivo de respuestas del lote.

Si un docente necesita aplicar versiones distintas del examen, deberá procesarlas como lotes separados, cada uno con su propia clave de respuestas.

Esta decisión simplifica el flujo de procesamiento, mantiene estable el contrato visual con P2 y evita introducir nuevas coordenadas o regiones de lectura sobre una plantilla ya validada.
