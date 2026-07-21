# ADR-0010: Permisos del volumen compartido (`uploads/`) entre panel-api y el pipeline

**Estado:** Propuesta (pendiente de decisión de **P4 / @diegoafg1009**)
**Fecha:** 2026-07-21

## Contexto

El panel (`panel-api`, Go) escribe el lote subido en `uploads/<BATCH_ID>/`
(`Fichas/ Estudiantes/ Respuestas/`) dentro del volumen compartido `./:/workspace`,
y el pipeline (`scanexam-app`) lo lee para procesarlo. Al levantar el sistema
**completo por primera vez en un entorno limpio**, el upload falla:

```
{"ok":false,"message":"create Fichas directory:
  mkdir /workspace/uploads/BATCH-2026...: permission denied"}
```

**Causa — desalineación de UID en el bind-mount `./:/workspace`:**

| Servicio | Corre como | Notas |
| --- | --- | --- |
| `panel-api` | **appuser (uid 10001)** | su Dockerfile crea el usuario y hace `USER appuser` |
| `scanexam-app`, `mlflow`, `trainer` | **root (uid 0)** | |
| Host (dueño del repo montado) | **uid 1000** | |

El `chown -R appuser:appuser /workspace` del Dockerfile de `panel-api` se aplica
en **build**, pero el **bind-mount en runtime lo sobreescribe** con la propiedad
del host (uid 1000). Resultado: `appuser` (10001) **no puede crear** `uploads/`
(ni escribir dentro si es de otro dueño).

**Fix temporal aplicado solo para la demo:** `chmod 777 uploads/` desde el
contenedor root (`docker exec scanexam-app chmod -R 777 /workspace/uploads`).
**No es reproducible ni seguro** — en un entorno limpio el primer upload vuelve a
fallar, y `777` no debe quedar en un despliegue real.

## Decisión (pendiente — la toma P4 / @diegoafg1009)

Falta elegir un **fix definitivo**. Como toca el `Dockerfile`/compose del panel
(dominio de P4), lo dejamos a decisión de Diego. Opciones evaluadas:

- **A) Alinear el UID del panel-api con el dueño del volumen.** En `docker-compose.yml`,
  `user: "0:0"` (o el uid del host) para `panel-api`, o quitar `USER appuser`.
  *Simple; pero corre como root o uid ajeno al de la imagen.*
- **B) Entrypoint que ajusta permisos y baja privilegios.** El contenedor arranca
  como root, hace `mkdir -p uploads && chown appuser uploads`, y luego baja a
  `appuser` (`gosu`/`su-exec`). *Correcto y seguro; algo más de trabajo.*
- **C) `uploads/` como volumen nombrado de Docker** (no bind-mount), montado en
  `panel-api` y `scanexam-app`, con permisos gestionados por Docker.
  *Evita el conflicto con el uid del host.*
- **D) Que un init/root gestione `uploads/` al arrancar** (p. ej. `scanexam-app`
  crea `uploads/` con permisos abiertos antes de que el panel escriba).

**Sugerencia para discutir (no vinculante):** A (con `user:` en compose) o C
(volumen nombrado) suelen ser lo más limpio, pero **la decisión es de P4**.

## Consecuencias

- **Bloqueante para un despliegue de cero:** sin el fix, el primer upload falla.
- El `chmod 777` temporal es **inseguro** y no debe persistir.
- No afecta al pipeline ni a la lógica de negocio: es puramente de
  empaquetado/permisos del panel sobre el volumen compartido.

## Alternativas consideradas

- **Dejar el `chmod 777`** como solución permanente: descartada por inseguridad y
  porque no arregla la causa (el desajuste de uid).
