# Architecture Decision Records (ADR) — ScanExam AI

Este directorio registra las **decisiones de arquitectura** relevantes del proyecto:
por qué se tomaron, qué alternativas se descartaron y qué consecuencias implican.
El objetivo es que cualquier integrante (o el docente evaluador) entienda el
*porqué* detrás del código, no solo el *qué*.

## Formato

Cada ADR sigue el estilo [Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):

```
# ADR-NNNN: Título
Estado: Propuesta | Aceptada | Vigente | Reemplazada por ADR-XXXX
Fecha: AAAA-MM-DD

## Contexto     — el problema y las fuerzas en juego
## Decisión     — lo que se decidió hacer
## Consecuencias — efectos positivos y negativos (trade-offs)
## Alternativas consideradas — qué más se evaluó y por qué se descartó
```

## Índice

| ADR | Título | Estado |
| --- | ------ | ------ |
| [0001](0001-motor-de-reglas-en-python.md) | Motor de reglas y scoring en Python (no en n8n) | Aceptada |
| [0002](0002-paralelismo-en-python.md) | Paralelismo del procesamiento en Python (no en n8n) | Aceptada |
| [0003](0003-versionado-del-modelo-con-mlflow.md) | Versionado del modelo con MLflow y alias `champion` | Aceptada |
| [0004](0004-cli-por-fases-y-orquestacion-n8n.md) | CLI por fases de P3 y orquestación por n8n | Aceptada |
| [0005](0005-panel-docente-stub-minimo.md) | Panel docente (P4) como stub mínimo | Aceptada |
| [0006](0006-contenerizacion-y-entorno.md) | Contenerización y decisiones de entorno | Aceptada |
| [0007](0007-confidence-por-pregunta.md) | Cálculo del `confidence` por pregunta | Aceptada |
| [0008](0008-reconstruccion-codigo-estudiante.md) | Reconstrucción del código de estudiante e identificación | Aceptada |

> Nota: la decisión de alcance sobre variantes A/B vive en
> [`../decision_not_support_for_A_B_exams.md`](../decision_not_support_for_A_B_exams.md)
> (previa a la adopción de este formato).
