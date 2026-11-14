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
| `OPENAI_BASE_URL` | LiteLLM de Alegra (`https://alegra-litellm.alegra.com/v1`) | Productor, juez, corrector, imagen |
| `PDC_LLM_KEY` | Llave virtual única con presupuesto | Todos los módulos |
| `PDC_MODEL_PRODUCER` / `PDC_MODEL_JUDGE` / `PDC_MODEL_CORRECTOR` | Modelos, de familias distintas | Productor / juez / corrector |
| `PDC_PROD_URL` / `PDC_PROD_USER` / `PDC_PROD_TOKEN` / `PDC_PROD_AUTHOR_ID` | WordPress de producción por la API (lectura y verificación) | Productor y publicador |
| `PDC_MCP_URL` / `PDC_MCP_USER` / `PDC_MCP_TOKEN` | MCP de WordPress, el canal por el que se escribe | Publicador |
| `GSC_SERVICE_ACCOUNT_JSON` | Cuenta de servicio de Search Console, en una línea | Conector GSC |
| `PDC_CHAT_WEBHOOK_URL` | Webhook del espacio de PdC | Avisos |
| `PDC_STATE_DIR` | Volumen persistente de corridas | Runner |
| `PDC_MODO` / `PDC_PAUSA` / `PDC_PAISES` / `PDC_VENTANA_INICIO` / `PDC_VENTANA_FIN` | Comportamiento: modo, pausa, mercados y ventana | Wrapper |

Los nombres son los que el código lee de verdad (`grep -rhoE "PDC_[A-Z_]+" scripts orchestrator`).
Una variable con otro nombre —`PDC_WP_TOKEN`, `GSC_CUENTA_SERVICIO_JSON`— no rompe el arranque:
simplemente no existe para el proceso y la corrida se detiene nombrando la que falta.

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
