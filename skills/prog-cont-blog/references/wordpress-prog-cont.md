# WordPress + MCP de programascontabilidad.com

## Credenciales y transporte

- Base REST: `https://programascontabilidad.com/wp-json/wp/v2`
- MCP: `https://programascontabilidad.com/wp-json/mcp/mcp-adapter-default-server`
- Auth: Basic (`fernandaalva` + Application Password). La credencial vive en el config de Hermes
  (`mcp_servers.prog-cont.headers.Authorization`) y en `~/.codex/config.toml`. **Nunca** se imprime ni
  se pega en un prompt.
- El MCP exige sesión: `initialize` → `notifications/initialized` → `tools/call`, y el `Mcp-Session-Id`
  vuelve en la cabecera del `initialize`. Usa `prog-cont/scripts/mcp.py`, que ya lo resuelve.

```python
import sys; sys.path.insert(0, r"C:/Users/ferna/AppData/Local/hermes/prog-cont/scripts")
import mcp
mcp.abilities()                      # lista las ~75 abilities
mcp.execute("ewpa/create-post", {...})
mcp.wp_get("/posts?per_page=5")
```

## Abilities que importan

| Ability | Uso |
|---|---|
| `ewpa/get-posts` / `ewpa/get-post` | listar / leer con `context=edit` |
| `ewpa/create-post` | título, HTML o bloques, excerpt, status, categorías, tags (nombres), `featured_image_id`, slug, meta |
| `ewpa/update-post` | actualización parcial |
| `ewpa/upload-image` | sube desde URL y, con `post_id`, la deja como destacada |
| `ewpa/update-rankmath` | `titulo_seo`, `descripcion_seo`, `keyword`, `robots`, OG/Twitter |
| `ewpa/update-rankmath-schema` | schema por tipo; `schema_type` va con el **enum exacto** (`FAQPage`, `Article`, `HowTo`…), nunca en minúsculas |
| `ewpa/get-rankmath` | verificación del meta guardado (la respuesta del update no prueba nada) |
| `ewpa/search-replace` | correcciones de texto dentro de un post |
| `ewpa/duplicate-post` | clonar una plantilla que funciona |
| `ewpa/get-media`, `ewpa/get-users`, `ewpa/get-cpt-items` | medios, autores, CPT `recursos` |
| `rank-math/get-post-links` | auditoría de enlaces internos/externos de un post |

## Categorías (IDs reales)

| ID | Categoría |
|---|---|
| 16 | Comparativas de software |
| 15 | Análisis de herramientas |
| 20 | Gestión de empresas |
| 22 | Contabilidad (hija de 16) |
| 23 | Administración (hija de 16) |
| 21 | POS (hija de 16) |
| 25 | Nómina Electrónica (hija de 16) |
| 24 | Tienda Online (hija de 16, vacía) |
| 1 | Uncategorized (deuda: 10 posts) |

Regla: toda pieza lleva **una** categoría principal de la rama (16 o 15) + su hija temática cuando
haga falta. `Uncategorized` nunca.

Etiquetas frecuentes (nunca duplicar): `alegra` 39, `dgii` 66, `e-cf` 162, `republica-dominicana` 32,
`sistema-contable` 33, `cfdi-4-0` 139, `dian` 44, `pos` 70, `software-erp` 298.

## Autor: siempre Leandro (ID 17)

`fernandaalva` es la cuenta que autentica por API, **no** la firma del artículo. En cada creación se envía
`author_id: 17` (`ewpa/create-post`) o `author: 17` (REST). Perfil público:
`https://programascontabilidad.com/author/ngorczany/` (responde 200).

Su descripción vive en el usuario de WordPress y se repite en una **ficha técnica al cierre de cada
pieza**, siempre con este bloque:

```html
<!-- wp:html -->
<div style="background:#f5f9fd;border:1px solid #cce4f7;border-radius:12px;padding:20px 24px;margin:32px 0;display:flex;gap:16px;align-items:flex-start">
<img src="https://programascontabilidad.com/wp-content/uploads/2024/06/Leandro-banner-home-100x100.png" width="72" height="72" alt="Leandro, analista y fundador de Programas de Contabilidad" style="border-radius:50%;flex-shrink:0;margin:0" />
<div>
<p style="margin:0 0 6px"><strong>Leandro</strong> · Analista y fundador de Programas de Contabilidad</p>
<p style="margin:0;font-size:15px;line-height:1.5">Analista colombiano y fundador de programascontabilidad. Con 37 años, combino la experiencia técnica con una visión analítica para ofrecer las comparativas más profundas del sector. Ayudo a profesionales y empresas a navegar la transformación digital contable con criterio y claridad.</p>
<p style="margin:10px 0 0"><a href="https://programascontabilidad.com/author/ngorczany/">Ver todas sus comparativas</a></p>
</div>
</div>
<!-- /wp:html -->
```

## La imagen destacada SÍ se ve (no la repitas en el cuerpo)

El tema (Genesis + Magazine Pro) imprime la imagen destacada arriba del contenido con
`class="singular-image entry-image"` (variante 750×420). Verificado en el HTML de las entradas publicadas.

Por eso:

1. `featured_media` con `alt_text` relleno — es la única imagen de cabecera que hace falta.
2. **No añadir un bloque `wp:image` con la misma foto al cuerpo**: el lector ve la imagen dos veces.
   Las capturas de landing (archivos distintos) sí van dentro del cuerpo.

Comprobación: dentro de `<article>` la portada debe aparecer **una vez**; después vienen las capturas y,
si la hay, la ficha del autor.

```html
<!-- wp:image {"id":5187,"sizeSlug":"large","linkDestination":"none"} -->
<figure class="wp-block-image size-large"><img src="https://programascontabilidad.com/wp-content/uploads/2026/10/archivo-1024x572.jpg" alt="Texto alternativo" class="wp-image-5187"/></figure>
<!-- /wp:image -->
```

## Verificación (obligatoria, leyendo el sitio)

```python
p = mcp.wp_get("/posts/12345?context=edit&_fields=content,excerpt,tags,status,slug,featured_media")
assert p["excerpt"]["raw"].strip()               # excerpt fabricado != excerpt propio
mcp.execute("ewpa/get-rankmath", {"post_id": 12345})   # titulo_seo / descripcion_seo / keyword
```

- `getHead` del sitio no sirve para borradores (devuelve plantilla de "no encontrado"): usa
  `ewpa/get-rankmath`.
- Un `POST` con 200 **no** prueba que el meta quedó: lee siempre.

## Pitfalls

- Cloudflare bloquea el `User-Agent` de Python (`403 error code: 1010`): manda `curl/8.7.1`.
- `POST {"status":"trash"}` no manda nada a la papelera; usa `DELETE /wp-json/wp/v2/posts/<id>` y
  confirma con un `GET`. Antes, comprueba que el post **no** esté publicado.
- `Breeze` y `HeadLess WordPress Plugin` cachean: tras un cambio, verifica con `?nocache=` o pide
  `ewpa/clear-cache` con el `post_id`.
- `wp-sitemap.xml` responde 301; el sitemap real es `sitemap_index.xml` (Rank Math).
- `llms.txt` está activo y se regenera con Rank Math: un post sin meta description aparece ahí con un
  extracto cortado a media idea.
- **`mcp.execute` solo entiende JSON.** Cuando una ability responde con un mensaje de texto (validación de
  entrada, permisos, CPT no soportado) lanza `JSONDecodeError` y parece un fallo de red o del servidor. Lee
  el mensaje real con `mcp._session.rpc("tools/call", {...})["content"][0]["text"]` antes de diagnosticar.
- **`schema_type` va con el enum exacto.** Un alias en minúsculas (`faq`) vuelve como texto plano: «La
  capacidad … tiene una entrada no válida». Los valores válidos son los del enum de la ability; para
  consultarlos, `mcp-adapter-get-ability-info` con `ability_name`.
- **Los CPT del propio plugin no son editables por la API.** `ewpa/create-cpt-item` y `ewpa/get-cpt-item`
  responden «Este tipo de contenido tiene capacidades dedicadas» para redirecciones de Rank Math y snippets.
  No insistas por esa vía; las redirecciones se resuelven como explica SKILL.md §7c.
- **Un script de publicación no es transaccional.** Sube portada y capturas primero y, si falla un paso de
  metadatos, escribe un segundo script que retome metadatos y schema: reejecutar el primero crea medios
  duplicados, porque cada subida es un adjunto nuevo en la biblioteca.
