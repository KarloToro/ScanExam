# ADR-0009: Dueño del envío de correos de notificación (panel-api, no n8n)

**Estado:** Aceptada
**Fecha:** 2026-07-19

## Contexto

El sistema notifica a cada estudiante su nota por email, con un enlace a la
página de consulta y una **clave de acceso**. El envío ya está implementado en el
panel de producción (`scan-exam-panel/backend`, Go): tras disparar el pipeline,
`panel-api` genera la clave de acceso, persiste los resultados en MongoDB y envía
los correos por SMTP (mailpit) — ver `internal/exam/application/upload_exam.go`
(`gradeMessages`) y `internal/notification/`.

Surge la pregunta de si ese envío debería **moverse a n8n** como un nodo
"Send Email", dado que el [contrato 04](../informacion_relevante_entre_modulos/04_n8n_orchestration_contract.md)
lo contempla como nodo opcional del orquestador.

## Decisión

1. **Los correos de nota a estudiantes viven en `panel-api` (Go).** No se
   envían desde n8n.
2. **n8n no envía correos de nota**, para evitar duplicados y porque no dispone
   de los datos necesarios en el momento en que responde.
3. **Queda abierta (no implementada)** la opción de que n8n envíe un aviso
   distinto: notificar al **docente** que *"el lote terminó de procesarse"*. Es un
   evento a nivel de pipeline que no necesita clave de acceso ni MongoDB, no
   duplica los correos de alumnos y sería **scope adicional**, no un reemplazo.

**Razón central:** el correo depende de datos que **nacen en el panel después**
de que el pipeline terminó:

| El email necesita… | Nace en… |
| --- | --- |
| Clave de acceso (aleatoria) | `panel-api` (`domain.NewAccessKey`) |
| `result.ID` para la URL de consulta | MongoDB, al persistir |
| URL del frontend | config de `panel-api` |

Cuando n8n devuelve `resultados.json`, **todavía no existen** la clave de acceso
ni el `result.ID`. El email es el último paso de la **publicación**
(persistir → clave → notificar → consulta), que es dominio del panel, no del
pipeline.

## Consecuencias

**Positivas**
- **Cohesión:** persistir y notificar ocurren juntos, con acceso a la misma base.
- **Frontera clara** pipeline/publicación, coherente con [ADR-0001](0001-motor-de-reglas-en-python.md)
  y [ADR-0004](0004-cli-por-fases-y-orquestacion-n8n.md): n8n orquesta el pipeline;
  el panel publica y notifica.
- Ya funciona; no requiere cambios.

**Negativas / trade-offs**
- El orquestador n8n "no se ve" enviando correos de nota. Mitigado: la decisión
  inteligente visible de n8n es el enrutamiento `Switch` OK/OBSERVED/ERROR, no el
  email.

## Alternativas consideradas

- **Mover el email a un nodo Send Email en n8n:** exigiría llevar la generación
  de la clave de acceso y la escritura en MongoDB a n8n (dominio del panel), o un
  round-trip de datos panel → n8n tras persistir. Rompe la cohesión y el límite
  de responsabilidades. Descartada.
- **Enviar desde ambos (panel-api y n8n):** produce correos duplicados. Descartada.
