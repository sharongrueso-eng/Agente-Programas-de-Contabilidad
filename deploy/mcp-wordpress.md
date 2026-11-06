# MCP de WordPress

El agente publica por el MCP Adapter de WordPress, no por la API REST. El MCP escribe meta
que la API REST descarta y permite fijar el autor, que es lo que la firma de Leandro exige.

## Endpoints

| Entorno | Endpoint | Autenticación |
|---|---|---|
| Producción | `https://programascontabilidad.com/wp-json/mcp/mcp-oauth-server` | OAuth (bloqueado: ver abajo) |
| Producción (alterno) | `https://programascontabilidad.com/wp-json/mcp/mcp-adapter-default-server` | Application Password |
| Staging | `https://wordpress-1477557-6320318.cloudwaysapps.com/wp-json/mcp/mcp-adapter-default-server` | Application Password |

Staging **no tiene** servidor OAuth (`mcp-oauth-server` responde 404). Por eso el flujo que se
prueba en staging no es el mismo que usará producción.

En Hermes el servidor se configura con transporte HTTP y una cabecera:

```yaml
mcp_servers:
  pdc_stg:
    url: https://<host>/wp-json/mcp/mcp-adapter-default-server
    headers:
      Authorization: "Basic <base64 usuario:contraseña-de-aplicación>"
```

## Las tres herramientas

El adaptador expone un proxy de tres pasos; no hay una herramienta por operación:

1. `mcp-adapter-discover-abilities` — lista las abilities disponibles.
2. `mcp-adapter-get-ability-info` — parámetros exactos de una ability.
3. `mcp-adapter-execute-ability` — la ejecuta.

## Abilities que usa el agente

| Ability | Parámetros |
|---|---|
| `ewpa/create-post` | `title`, `content` (requeridos) · `excerpt`, `status`, `categories`, `tags`, `featured_image_id`, `post_date`, `author_id`, `slug`, `meta_title`, `meta_description`, `language`, `translation_of` |
| `ewpa/update-post` | mismos campos, sobre un post existente |
| `ewpa/update-post-meta` | `post_id`, `meta_key`, `meta_value` — una clave por llamada |
| `ewpa/get-post-meta` | lee las metas de un post |
| `ewpa/get-post` / `ewpa/get-posts` | consulta |
| `ewpa/upload-image` | sube medios |

**`create-post` no acepta meta.** Escribir `pdc_run_id` es una segunda llamada, y un fallo
entre las dos deja un post sin identificador.

## Orden de publicación

El orden importa más que en la API REST:

1. Crear el post con `status: draft` y `author_id: 17`.
2. Escribir `pdc_run_id` y `pdc_target_country` con `update-post-meta`.
3. Releer con `get-post-meta` y `get-post` para confirmar autor y meta.
4. Publicar con `update-post` (`status: publish`) solo si los pasos 1–3 cuadran.

Crear en borrador es lo que hace la operación recuperable: si el proceso muere después del
paso 1, queda un **borrador huérfano**, no una pieza publicada sin identificador. Al reanudar,
se busca por `slug` entre los borradores y se adopta ese post en lugar de crear otro.

## Idempotencia

No hay forma de buscar un post por meta. El agente lleva su propio mapa `run_id → post_id` y,
antes de crear, consulta el mapa y luego los borradores por `slug`. Fabio ofreció agregar un
filtro por meta en WordPress; si llega, reemplaza al mapa.

## Verificado en staging

Un borrador real (`post_id` 4518) creado solo con el MCP:

- `author` = **17** (Leandro), confirmado después por la API REST.
- `pdc_run_id` = `prueba-001` y `pdc_target_country` = `CO`, leídos con `get-post-meta`.
- La API REST del mismo post **no** expone esa meta, que es justamente la razón de usar el MCP.

## Pendiente

- **OAuth en producción**: el servidor declara `client_id_metadata_document_supported: true`,
  pero `GET /oauth/authorize` devuelve 400 «Unknown OAuth client» con el documento de
  metadatos de Hermes. Hasta que se resuelva, producción usa Application Password o queda
  bloqueada.
- Habilitar OAuth también en staging, para que la prueba reproduzca el camino real.
