# Desplegar el agente PdC en Coolify

El agente corre **un proceso por corrida**, no un servicio permanente: Coolify lo programa y
el contenedor termina. El estado vive en un volumen para que sobreviva entre corridas.

## Lo que hay que tener antes

| Cosa | De dónde sale |
|---|---|
| Repositorio | `sharongrueso-eng/Agente-Programas-de-Contabilidad`, rama `main` |
| Llave del gateway | variable `LITELLM_API_KEY` (la inyecta IT en Coolify) |
| WordPress de producción | usuario + contraseña de aplicación de la cuenta editora |
| MCP de WordPress | URL del adaptador y la misma credencial |
| Google Chat | URL del webhook del espacio |
| Search Console | archivo JSON de la cuenta de servicio |

Ninguna de esas vive en el repositorio. El código solo las lee del entorno.

## 1. Crear la aplicación

En Coolify: **New Resource → Dockerfile**, apuntando al repositorio y a `deploy/Dockerfile`
como ruta del archivo.

- **Puerto:** ninguno. No expone HTTP.
- **Volumen persistente:** montar un volumen en `/data`. Ahí viven `state/`, la caché de
  Search Console, el sitemap y los mapas de publicación.
- **Usuario:** el de la imagen (`pdc`, uid 10001). No hace falta root.

## 2. Variables de entorno

Obligatorias:

```
OPENAI_BASE_URL=https://alegra-litellm.alegra.com/v1
PDC_LLM_KEY=<llave del gateway>
PDC_MODEL_PRODUCER=deepseek/deepseek-v4-pro
PDC_MODEL_JUDGE=zai/glm-5.2
PDC_MODEL_CORRECTOR=zai/glm-5.3

PDC_PROD_URL=https://programascontabilidad.com
PDC_PROD_USER=<usuario editor>
PDC_PROD_TOKEN=<contraseña de aplicación>
PDC_PROD_AUTHOR_ID=17

PDC_MCP_URL=https://programascontabilidad.com/wp-json/mcp/mcp-adapter-default-server
PDC_MCP_USER=<usuario editor>
PDC_MCP_TOKEN=<contraseña de aplicación>

PDC_CHAT_WEBHOOK_URL=<webhook del espacio>
GSC_SERVICE_ACCOUNT_JSON=<contenido del JSON, en una línea>
```

De comportamiento:

```
PDC_MODO=borrador          # borrador mientras se prueba; publicar cuando se autorice
PDC_PAUSA=0                # 1 detiene todo sin tocar el calendario
PDC_PAISES=CO,MX,CR,DO     # los cuatro mercados del portal; un quinto se ignora
PDC_VENTANA_INICIO=06:00
PDC_VENTANA_FIN=17:30
PDC_FIN_DE_SEMANA=1        # 1 publica también sábado y domingo
PDC_STATE_DIR=/data/state
```

Opcionales del diagnóstico:

```
AHREFS_API_KEY=<llave de la API v3>   # sin ella no hay volumen, SERP ni citas en IA; GSC decide igual
PDC_AHREFS_MAXIMO=6                   # oportunidades del ranking que reciben evidencia de Ahrefs
PDC_MODEL_INTENCION=deepseek/deepseek-v4-flash   # desempata la intención ambigua
PDC_INTENCION_MAX_NUEVAS=40           # consultas nuevas al modelo por corrida; el resto, otro día
```

## 3. La tarea programada

Coolify → **Scheduled Tasks** de la aplicación. Una tarea por corrida:

```
Comando:  python scripts/corrida_diaria.py
Cron:     10 6 * * 1-5
Zona:     America/Bogota
```

El script comprueba la ventana, la pausa y el mercado del día antes de trabajar, así que una
ejecución fuera de horario no hace nada y lo deja escrito en el registro.

Para dos corridas diarias, duplicar la tarea con `10 7 * * 1-5`.

## 4. Comprobar que quedó bien

1. **Ejecutar la tarea a mano** desde Coolify y leer el registro: debe imprimir
   `corrida: CO · modo borrador` y terminar con el JSON del resultado.
2. **Ver el aviso en Google Chat.** Si no llega, el webhook está mal y las corridas siguientes
   fallarán en silencio.
3. **Revisar el volumen:** `/data/state/corridas/<task_id>/` debe tener `borrador.json`,
   `consumo.json` y `publicacion.json`.
4. **Confirmar el post en WordPress** y que el autor sea Leandro (ID 17).

## 5. Operación diaria

- **Qué publica solo:** artículos nuevos. La corrida diaria pasa `--solo-nuevos`, así que un
  reencauche (actualizar una URL que ya vive) nunca sale por calendario: se lanza a mano con
  `python scripts/corrida_completa.py --url <slug> --en-vivo --reusar`.
- **Mercados:** solo CO, MX, CR, DO. Un artículo de Perú, Chile o España se descarta en la
  auditoría: reescribirlo con normativa local destruye lo que posiciona en su país.
- **Pausar:** `PDC_PAUSA=1` y redesplegar. No hace falta tocar el cron.
- **Volver a publicar de verdad:** `PDC_MODO=publicar`.
- **Revertir un snippet:** `python scripts/corrida_completa.py --revertir <post_id>`; usa el
  respaldo guardado en la corrida que lo cambió.
- **Respaldo del estado:** copiar `/data` a diario; es lo único que no se puede reconstruir.

## Lo que todavía no está resuelto

- El agente no reintenta la llamada MCP ante un corte de red: la corrida falla y hay que
  esperar a la siguiente.
- Si el listado de mercado falla, la corrida se detiene en vez de adivinar. Es deliberado.
- El costo por pieza se mide y se guarda en `consumo.json`; conviene revisarlo la primera
  semana para decidir si el redactor baja de modelo.
