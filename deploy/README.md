# Despliegue en Coolify

Esta carpeta describe cómo corre el agente en la instancia de Hermes alojada en el Coolify
de IT. **Nada de esto se ha probado todavía en Coolify**: está escrito para que IT lo
ejecute y lo valide.

## Lo que hay

| Archivo | Para qué |
|---|---|
| `Dockerfile` | Imagen con Python, Hermes y el repositorio copiado |
| `compose.yaml` | Servicio, volúmenes persistentes y variables |
| `.env.example` | Nombres de las variables. Nunca valores |
| `backup.sh` | Respaldo nocturno del estado y del perfil de Hermes |
| `cron.md` | Tareas programadas que hay que crear dentro de Hermes |

## Variables

Se cargan en el panel de Coolify, nunca en el repositorio ni en un chat.

| Variable | Para qué | Quién la usa |
|---|---|---|
| `OPENAI_BASE_URL` | LiteLLM de Alegra | Productor, juez, corrector, imagen |
| `PDC_LLM_KEY` | Llave virtual única con presupuesto | Todos los módulos |
| `PDC_MODEL_PRODUCER` / `PDC_MODEL_JUDGE` | Modelos, de familias distintas | Productor / juez |
| `PDC_WP_URL` / `PDC_WP_TOKEN` / `PDC_WP_USER` | WordPress con el token de Leandro | Productor y publicador |
| `GSC_CUENTA_SERVICIO_JSON` | Cuenta de servicio de Search Console | Conector GSC |
| `PDC_CHAT_WEBHOOK_URL` | Webhook del espacio de PdC | Avisos |
| `PDC_STATE_DIR` | Volumen persistente de corridas | Runner |
| `PDC_MAX_PIECES_PER_DAY` | Tope diario | Publicador |

## Pasos

1. Crear el recurso en Coolify apuntando a este repositorio, con `deploy/Dockerfile`.
2. Montar dos volúmenes: uno en `/data/state` (corridas) y otro en `/data/hermes` (perfil,
   memoria y tareas). Sin ellos, cada redeploy olvida lo que se publicó.
3. Cargar las variables del panel. Ninguna en el repositorio.
4. Crear las tareas de `cron.md` con `hermes cron add`, dentro del contenedor.
5. Ejecutar `python scripts/smoke_adapters.py` con las credenciales cargadas.
6. Ejecutar `python scripts/smoke_pipeline.py` para confirmar que la cadena corre.
7. Programar `backup.sh` a las 23:30 y probar una restauración.

## Lo que falta confirmar con IT

- Que el instalador de Hermes funcione en `python:3.12-slim` (la imagen base puede cambiar).
- Que las tareas programadas de Hermes vean las variables de entorno del contenedor.
- Que el volumen de estado sobreviva a un redeploy.
- Que el token de WordPress pueda publicar, asignar autor y fijar robots en Rank Math.
