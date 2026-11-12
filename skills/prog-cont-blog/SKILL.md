---
name: prog-cont-blog
description: Reseñas y comparativas en programascontabilidad.com.
version: 0.1.0
author: Fernanda Alva, Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [seo, wordpress, comparativas, resenas, alegra, programascontabilidad]
    related_skills: [ie-panama, ie-pan-publicacion-wordpress]
---

# Programas de Contabilidad — agente editorial

## When to Use

- Cuando haya que crear, refrescar o auditar una pieza de `programascontabilidad.com`.
- Cuando pidan una **auditoría del portal completo** (contenido, tráfico, SEO y AEO) para decidir qué
  publicar, qué refrescar y qué podar: procedimiento y estructura del entregable en
  `references/auditoria-blog-seo-aeo.md`.
- Cuando se pida una reseña, comparativa o guía operativa de software contable/facturación.
- Cuando haya que decidir si un tema ya está cubierto antes de producir (anti-canibalización).
- Cuando se configuren o revisen los crons de este portal.
- Cuando haya que construir o revisar el **agente autónomo** del portal (qué produce solo, con qué datos y
  con qué reglas): diseño, huecos y plan de arranque en `prog-cont/FLUJO-AGENTE-AUTONOMO.md`.


Produce y actualiza reseñas y comparativas de software contable/facturación en
`https://programascontabilidad.com` (portal afiliado de Alegra, multi-país: México, Colombia,
Costa Rica, República Dominicana, Perú, Panamá).

Una entrada **no está terminada** si le falta: portada (foto limpia, sin texto ni logo), tabla
comparativa, FAQ en H3 con schema, fuentes con fecha de consulta e interlinks internos reales.

## Alcance

- Software contable, facturación electrónica, POS, ERP, nómina y gestión de empresas.
- ICP: dueño de pyme, contador independiente y despacho pequeño que está **eligiendo herramienta**.
- Tercera persona, español neutro latinoamericano. Precios en moneda local del país de la pieza.
- **Una pieza por país, no una pieza multi-país**: el mismo software se reseña y se compara una vez por
  México, Colombia, Costa Rica y República Dominicana (países de arranque), cada una con sus precios, su
  norma fiscal, su vocabulario y su CTA. Es la decisión editorial del equipo: "publicación por versión"
  significa versión por país. El tracker guarda una fila por pieza con país y fecha de verificación.
- **Alegra se sugiere, no se impone** (ver §4).

## 0. Fuentes de datos: **solo Ahrefs** (+ GSC y GA4)

DataForSEO **está retirado** de este portal. No hay proveedor de respaldo: si Ahrefs no responde, el dato
falta, se escribe «sin volumen medido» en el log y baja la confianza de la decisión. Nunca se rellena el
hueco con una estimación del modelo ni se lee un ranking sin volumen como «no hay demanda».

| Pregunta | Herramienta Ahrefs |
|---|---|
| ¿Cuánta demanda tiene esta consulta? | `keywords_explorer_overview` (`select=keyword,volume,difficulty,traffic_potential,intents`) |
| ¿Quién está en el top 10 y en qué puesto? | `serp_overview` con `type=organic`, `top_positions=10` |
| ¿Qué keywords trae un competidor? | `site_explorer_organic_keywords` |
| ¿Rinde mi URL hoy? | `gsc_pages` / `gsc_keywords` (y GA4 por landing) |
| ¿Nos citan los asistentes de IA? | `brand_radar_ai_responses` + `brand_radar_cited_pages` (necesita un report de Brand Radar del dominio) |
| ¿Cuántas unidades quedan? | `subscription_info_limits_and_usage` |

Trampas del SERP de Ahrefs, comprobadas el 3-nov-2026:

- **Sin `type=organic` el resultado trae filas duplicadas y filas con `url: null`** (esas son AI Overview,
  People Also Ask y anuncios). Filtra `url` no nulo y deduplica por posición antes de contar nada.
- `positions` **omite los huecos**: si el puesto 1 es un anuncio, la primera fila es `position: 2`. No se
  interpreta como «no hay nadie en el 1».
- `select` es obligatorio y se cobra completo: pedir de más no ahorra.
- Coste medido: **3 unidades por fila** de SERP, **41 por fila** de keyword. Un preflight normal (1 keyword
  de volumen + 1 SERP de 10) son ~50 unidades. Un plan Advanced son 2.000.000 al mes.
- Los códigos de país son los del mercado: `mx`, `co`, `cr`, `do`, `pe`, `pa`.

## 1. Preflight obligatorio (antes de escribir una línea)

1. **Lee el mapa de canibalización** (`prog-cont/auditoria.json` + tracker). Si ya existe una URL
   publicada para esa intención, la tarea es **refrescar esa URL**, nunca crear otra. Este portal ya
   tiene 9 URLs peleando por "facturación electrónica RD" y dos posts idénticos de "mejor software
   contable Colombia 2026" (ids 40 y 3211): no añadir una décima.
   La comprobación se hace con datos, no de memoria: (a) SERP del término en el país del artículo
   (`serp_overview` de Ahrefs, `type=organic`, `top_positions=10`), (b) el focus
   keyword de cada entrada vecina con `ewpa/get-rankmath`, (c) `GET /posts?search=<término>` para ver quién
   lo menciona. Si ninguna URL propia aparece en el top 10 y ningún vecino declara la keyword, la
   intención está libre; si un vecino la declara, **se reparte el tema** (la comparación en una pieza, los
   precios y la reseña en otra, enlazadas) en vez de duplicarlo.
   **Un cluster temático no es canibalización.** Solo hay canibalización cuando dos URLs compiten por la
   *misma consulta*: mismo título, mismo slug o mismo rival comparado. Agrupar por tema (producto + tipo
   de pieza) infla la lista y lleva a proponer 301 sobre artículos que en realidad cubren temas distintos;
   antes de recomendar una redirección, exige esa evidencia en el título y en la URL, y separa los lotes
   en «duplicado exacto», «misma intención, redacción distinta» y «temas hermanos sin tráfico» (estos
   últimos se podan o se consolidan, no se redirigen).
2. Verifica que la keyword tenga demanda medida. **GSC y Ahrefs son la fuente**; el volumen de una
   herramienta gratis en este nicho vale poco. Si no hay GSC todavía, usa Ahrefs
   (`site_explorer_organic_keywords` del competidor + `keywords_explorer_overview`) y anota la fuente.
3. Revisa precios y funciones del software reseñado **en su página oficial ese mismo día**. Cada cifra
   lleva su fecha de consulta. **En un refresco, extrae del post cada precio y cada cifra y verifica uno
   por uno contra la fuente viva**: los planes cambian de nombre y de tarifa sin aviso, y el artículo
   termina contradiciendo a su propia fuente (hay posts con las cuatro tarifas de un plan por debajo del
   precio real). Para corregir varias entradas de golpe, `references/refresco-de-precios.md` tiene el
   procedimiento por lotes con dry-run, colisiones de valores y auditoría de residuos.
   **Comprueba también que el producto siga siendo el mismo.** Una comparativa vieja no se invalida solo
   por tarifas: el competidor pudo cambiar de mercado, de país fiscal o de idioma. Revisa dominio, moneda,
   idioma y norma fiscal de su landing; si hoy vende para otro país (precios en otra moneda, impuesto de
   otro régimen, interfaz en otro idioma), **no escribas «precios actualizados para {país}»**: reescribe la
   pieza con el ángulo honesto —qué ofrece cada uno hoy y por qué cambió la comparación—, conserva el slug
   y redirige la intención a los proveedores que sí operan en el país. Convertir la moneda para que la
   tabla «cuadre» es fabricar datos y quema la credibilidad del portal.
4. Elige 2-4 enlaces internos reales (verifica con `GET /wp-json/wp/v2/posts?slug=` que existan).
5. Decide país y CTA (tabla §3). Un solo CTA de Alegra por artículo.

## 1b. Antes de proponer un 301 o un cambio de URL (regla dura)

Nunca se propone una redirección por parecido de títulos o de keywords. Hay que presentar tres datos y
decidir con ellos:

1. **Posición actual de cada URL por su consulta** (SERP real: `serp_overview` de Ahrefs). Si una de
   las dos está en top 10 y la otra no, redirigir destruye la única posición que existe.
2. **Si las SERP de las dos keywords son la misma o no.** Conjuntos de resultados distintos = intenciones
   distintas = **no se redirige, se diferencia el contenido**.
3. **Clics/impresiones por URL.** Sin GSC se usa GA4 (sesiones por landing) y se dice expresamente que es
   una estimación; nunca se afirma «esta URL no sirve» sin el dato.

Caso que fijó la regla (RD, oct-2026): «programas de facturación electrónica», «mejor software de
facturación electrónica» y «mejores sistemas de facturación electrónica» parecían la misma intención. Las
tres SERP devolvieron resultados distintos y la única posición top-10 (puesto 8) estaba en «programas»,
justo la URL que se iba a redirigir. Se canceló el 301 y se diferenciaron las tres piezas:

| URL | Intención | Rol de la pieza |
|---|---|---|
| `/programas-de-facturacion-electronica/` | «programas» | Guía informacional: qué son, marco DGII, PSFE autorizados, costos |
| `/mejor-software-de-facturacion-electronica/` | «mejor software» | Comparativa por perfil y presupuesto |
| `/mejores-sistemas-de-facturacion/` | «sistemas» | Comparativa técnica (XSD, contingencias, ERP) |

Cada pieza cierra enlazando a las otras dos: el clúster se refuerza, no se canibaliza.

## 2. Producción

Formatos exactos en `references/formatos.md`:

- **Reseña** (~1.300-1.500 palabras): ficha rápida → qué es → funciones y módulos → cómo funciona →
  precios publicados → cumplimiento fiscal del país → ventajas y puntos de atención → para quién es →
  qué preguntar antes de implementar → veredicto → FAQ → Fuentes.
- **Comparativa** (~1.300-1.600 palabras): respuesta rápida → tabla comparativa → qué es cada una →
  precios publicados de cada una → cuándo conviene cada una (por tipo de operación) → checklist antes
  de contratar → veredicto → FAQ → Fuentes.
- **Guía operativa** ("cómo hacer X en [software]", "certificado de retención en World Office"): el
  formato que **más tráfico trae** en este portal. Priorízalo cuando la intención sea de uso, no de
  compra.

Reglas de forma: párrafos de máximo 4 líneas, mínimo 6 H2 con H3 intercalados, al menos 1 tabla, FAQ
siempre en H2 con cada pregunta en H3, y sección `Fuentes` cerrando el artículo.

### Capturas de las landings (obligatorio)

Cada reseña y cada comparativa lleva **1 a 3 capturas reales de la landing del producto**: hero de la
página y, cuando exista, la sección de precios. Es el patrón que usan las entradas que mejor convierten
del portal (la de Bind vs Alegra ERP tiene la captura de Alegra ERP y la de Bind).

- Se capturan con Chrome headless a 1440 px de ancho (ver `references/portada-y-medios.md`).
- Van como bloque `wp:image` dentro del cuerpo, con `figcaption` que diga qué se ve y **la fecha de
  consulta**.
- Nunca se recortan precios ni se editan las cifras de la captura: si el precio cambió, se vuelve a
  capturar.
- **Los precios se leen del HTML o del DOM, nunca de la captura.** Una cifra pequeña se confunde con
  facilidad al mirar la imagen (`$155.000` leído como `$135.000`) y el error se propaga al artículo y a la
  tabla comparativa. La captura muestra la página; el dato sale del marcado. Si la tabla del artículo y la
  captura no coinciden, vuelve a capturar y vuelve a leer el HTML.
- Referencia de precios de Alegra México para comparar: `references/precios-alegra-mx.md`.

## 3. Alegra: módulos y CTA por país

**Antes de escribir el nombre de un módulo, abre `references/alegra-modulos-por-pais.md`.** Alegra no
ofrece los mismos módulos en todos los países y el artículo no puede prometer lo que no existe (es la
diferencia entre un CTA que convierte y uno que manda al usuario a un 404).

Resumen de lo que **no** existe: **nómina** (módulo completo) en Costa Rica, Perú y Panamá · **ERP** en
Perú y Panamá · **CRM** fuera de Colombia (en CR y RD va dentro del ERP).

Ojo con dos cosas que **sí** existen y hay que dejar disponibles: **timbrado de nómina en México**
(CFDI de nómina, dentro de los planes de contadores) y **ERP en Colombia** (publicado como *software
administrativo*, en `/colombia/software-administrativo/`). En México nunca se aclara que el módulo
completo no está; simplemente se ofrece el timbrado.

Todas las URLs del CTA, verificadas 200. Añade siempre el UTM:
`?utm_source=blog_programascontabilidad&utm_medium=referral&utm_campaign={pais}_articulo_tmd_content&utm_term={keyword}`

| País | CTA según lo que prometa el artículo | Campaña |
|---|---|---|
| México | `/mexico/contabilidad/` · `/mexico/facturacion-electronica/` · `/mexico/pos/` · `/mexico/erp/` · `/mexico/precios/` | `mex_` |
| Colombia | `/colombia/contabilidad/` · `/colombia/facturacion-electronica/` · `/colombia/nomina-electronica/` · `/colombia/pos/` · `/colombia/alegra-crm/` · **migración: `/colombia/contabilidad/migracion/{siigo|loggro|world-office}/`** (ver `references/migracion-colombia.md`) | `col_` |
| Costa Rica | `/costarica/contabilidad/` · `/costarica/facturacion-electronica/` · `/costarica/pos/` · `/costarica/erp/` | `cri_` |
| República Dominicana | `/rdominicana/contabilidad/` · **`/rdominicana/factura-electronica/`** · `/rdominicana/pos/` · `/rdominicana/erp/` · `/rdominicana/nomina/` | `dom_` |
| Perú | `/peru/contabilidad/` · `/peru/factura-electronica/` · `/peru/boleta-electronica/` · **`/peru/punto-venta/`** | `per_` |
| Panamá | `/panama/contabilidad/` · `/panama/facturacion-electronica/` · `/panama/pos/` | `pan_` |

Si el artículo es de **nómina/planilla**: en **México** se ofrece **timbrado de nómina** (CFDI) con CTA a
`/mexico/contabilidad/`; en **Colombia** y **RD** hay módulo de nómina completo; en **Costa Rica, Perú y
Panamá** el producto es **Alegra Contabilidad** y no se menciona nómina.

## 4. La regla de la sugerencia sutil (la que pidió el equipo)

Una comparativa **no** termina con "el ganador es Alegra". Se hace así:

- **Una** mención contextual en el cuerpo: "si tu prioridad es facturar y llevar contabilidad en la
  misma herramienta, Alegra suele encajar porque…" — siempre condicionada a un tipo de operación.
- **Un** CTA al cierre, con el UTM de §3, en frase neutra ("puedes comparar planes vigentes en…"),
  nunca con urgencia falsa ni superlativos sin dato.
- La tabla comparativa es **simétrica y honesta**: si el competidor es mejor en algo, se dice. La
  credibilidad es el activo del portal; un veredicto comprado quema la SERP.
- **Prohibido**: decir que Alegra es "el mejor" sin dato, inventar funciones, prometer producto que no
  existe en ese país, o poner más de un enlace de Alegra en el cuerpo.
- **Prohibido sobre todo prometer un módulo que Alegra no tiene en ese país** (nómina completa en
  CR/PE/PA; ERP en PE/PA) **o insinuar que falta algo que sí existe** (timbrado de nómina en México, ERP
  en Colombia). Cada módulo nombrado debe aparecer en `references/alegra-modulos-por-pais.md`.

## 5. Publicación (MCP `prog-cont`)

Receta completa en `references/wordpress-prog-cont.md`. Orden:

1. Crear el post en `draft` (`ewpa/create-post`), contenido en bloques Gutenberg y `excerpt` propio,
   con **`author_id: 17`** (Leandro). La cuenta que autentica por API es `fernandaalva`, no la firma:
   si no se envía el autor, el artículo sale firmado por ella.
2. Subir portada y confirmar `featured_media`. `ewpa/upload-image` **solo acepta una URL**: para un
   archivo local se sube por REST a `/wp-json/wp/v2/media` con `--data-binary`. Rellena `alt_text` en el
   medio. Estilo de la foto, comando exacto y pitfalls en `references/portada-y-medios.md`.
3. **No añadir la portada al cuerpo.** El tema Genesis imprime la imagen destacada arriba del contenido con
   `class="singular-image entry-image"`: si además se pone un bloque `wp:image` con la misma foto, el lector ve
   la imagen **dos veces**. Solo la destacada; las capturas de landing sí van en el cuerpo (son otras imágenes).
4. `ewpa/update-rankmath` (titulo_seo ≤60, descripcion_seo 140-160, keyword, robots index/follow).
5. Escribir el schema FAQ (`ewpa/update-rankmath-schema` o meta `faq_schema_jsonld`) con **todas** las
   preguntas del artículo.
6. **Cerrar con la ficha técnica del autor** (bloque `<!-- wp:html -->` con avatar, nombre, rol,
   descripción y enlace a `/author/ngorczany/`). HTML exacto en `references/wordpress-prog-cont.md`.
7. **Verificar leyendo**: `ewpa/get-post` + `ewpa/get-rankmath` + contar H3 de FAQ contra el schema.
   Un POST con 200 no prueba nada.

## 6. Pitfalls comprobados

- **La portada se duplica si el script la antepone además de rellenar la plantilla.** Los HTML de pieza ya traen un
  bloque `wp:image` con el marcador `{{PORTADA}}`. Si el script, además de reemplazar el marcador, antepone su
  propio `img_block()`, el artículo sale con **la misma foto dos veces en el cuerpo**. Se reemplaza el marcador y
  nada más. Comprobación obligatoria después de guardar: contar en el HTML renderizado las `figure.wp-block-image`
  cuya `src` sea la de la portada — debe ser **exactamente 1**.
- **Las tablas llevan el formato de marca, no el de Gutenberg por defecto.** `{"className":"is-style-stripes"}`
  a secas deja la tabla sin fondo y desentona con el resto del portal. El bloque tiene que ir así:
  `<!-- wp:table {"className":"is-style-stripes","style":{"color":{"background":"#cce4f7"}}} -->` y la
  etiqueta `<table class="has-background has-fixed-layout" style="background-color:#cce4f7">`.
  Verificar en el render: `sum('has-background' in t for t in tablas)` == número de tablas.
- **No crear un post nuevo cuando ya existe la intención.** Es el error más caro del portal.
- **No fusionar URLs por parecido de keyword.** Tres sinónimos pueden ser tres intenciones: comprueba la SERP
  de cada uno y la posición actual antes de tocar nada (ver §1b). Un 301 sobre la única URL en top 10 es una
  pérdida neta.
- **`ewpa/update-rankmath-schema` exige `schema_type` del enum, no un slug libre.** Se envía `"FAQPage"`
  con mayúsculas; con `"faq"` la ability contesta un mensaje de validación en texto plano y rompe cualquier
  cliente que espere JSON (el `mcp.execute` revienta con `JSONDecodeError`). Igual con `ewpa/get-post-meta`,
  que exige `meta_key`, y con `ewpa/update-post-meta`, que rechaza `meta_value` si no es string: no sirve
  para metas serializadas de Rank Math (`rank_math_redirect` es un array, no se puede escribir por API).
- **Reescribir varias entradas se hace con un script de lote, no a mano.** Patrón probado:
  `prog-cont/scripts/reescribir_<tema>.py` con el HTML en `prog-cont/contenido/`, placeholders
  `{{PORTADA}}` y `{{CAPTURA_X}}`, cache `{ruta: (media_id, url)}` para no subir dos veces el mismo archivo,
  `assert` de excerpt 138-160 / SEO title ≤60 / descripción 140-160 **antes** de enviar, y modo dry-run por
  defecto (`--aplicar` para escribir).
- **El autor se escribe a mano: Leandro (ID 17) en toda pieza.** Si se omite, queda firmada por la cuenta
  de API (`fernandaalva`). La ficha técnica del autor se agrega al final del contenido; el tema no la
  genera.
- **El tema SÍ muestra la imagen destacada** (verificado en el HTML: `class="singular-image entry-image"`).
  La regla anterior —«el tema no la imprime, hay que repetirla en el cuerpo»— era falsa y provocó portadas
  duplicadas en todo el portal. Comprobación tras guardar: contar las `img` dentro de `<article>`; la portada
  debe aparecer **una vez** (la del tema) y las siguientes deben ser capturas o el avatar del autor.
- **La portada se duplica si el script la antepone además de rellenar la plantilla.** Los HTML de pieza ya traen un
  bloque `wp:image` con el marcador `{{PORTADA}}`; si el script, además de reemplazarlo, antepone su propio
  `img_block()`, sale dos veces. Lo correcto ahora es **no poner ninguna portada en el cuerpo**.
- **No cambiar slugs publicados.** Rompe redirecciones y rankings.
- **Antes de refrescar una URL, comprueba que no responda 301.** `curl -o /dev/null -w '%{http_code} %{redirect_url}'`
  **sin** `-L`. Si redirige, el post que estás editando no lo ve nadie: el contenido vivo está en el
  destino y ahí es donde se refresca. Editar el origen y reportar el cambio como hecho es trabajo
  invisible.
- **Al añadir o reescribir elementos de lista, cierra los pares de comentarios y cuéntalos.** Cada `<li>`
  necesita `<!-- wp:list-item -->` y `<!-- /wp:list-item -->`, y la lista su `<!-- wp:list -->` y
  `<!-- /wp:list -->`. Un cierre huérfano después de `</ul>` deja el bloque abierto y el bloque siguiente
  (una imagen, un H2) se lo traga. Al contar, ojo: `<!-- wp:list -->` **no** lleva espacio, así que
  `count("<!-- wp:list ")` descuadra el balance y hace creer que falta un cierre.
- **El meta `faq_schema_jsonld` se ignora cuando el post tiene schema propio de Rank Math.** La página
  imprime los `FAQPage` que viven en `rank_math_schema_*` (a veces cuatro bloques de una sola pregunta).
  Revisa el schema en el **HTML renderizado** y exige que cada pregunta del schema exista en el texto
  visible: si no coincide, el rich result incumple la política de Google aunque el meta esté perfecto.
- **El extracto vacío no se nota en la API**: WordPress fabrica uno cortando el primer párrafo. Exige
  `excerpt` propio en el payload y verifícalo con `context=edit`.
- **El schema FAQ no se regenera solo**: si cambias el texto de una pregunta, reescribe el JSON-LD o el
  rich result contradice la página.
- **`ewpa/create-post` devuelve `post_id`, no `id`** (el cliente `mcp.execute` ya entrega el `data`):
  lee el id del campo correcto antes de encadenar la portada y los metadatos.
- **El extracto que se escribe se queda corto o largo**: 169 caracteres no pasa el postflight. Calcula el
  largo antes de enviar y ajusta a 138-160; reescribirlo después obliga a un segundo POST.
- **Cloudflare/WAF**: en scripts Python manda `User-Agent: curl/8.7.1`; el UA por defecto se bloquea.
- **El MCP exige `Mcp-Session-Id`**: initialize → notifications/initialized → tools/call. Ya resuelto en
  `prog-cont/scripts/mcp.py`; úsalo, no reimplementes el handshake.
- Los scripts de lote viven en `C:\Users\ferna\AppData\Local\hermes\prog-cont\scripts\`, nunca en el
  scratch (se purga solo).

## 7. Rutas del proyecto

| Qué | Dónde |
|---|---|
| Cliente MCP | `prog-cont/scripts/mcp.py` |
| **Matriz de módulos de Alegra por país** | `prog-cont/alegra-modulos-por-pais.md` + `references/alegra-modulos-por-pais.md` |
| Auditoría del archivo (343 posts) | `prog-cont/auditoria.json`, `prog-cont/auditoria-*.json`, `prog-cont/AUDITORIA-COMPLETA-*.md` |
| **Procedimiento de auditoría completa (SEO + AEO)** | `references/auditoria-blog-seo-aeo.md` |
| Tracker de reseñas y versiones | `prog-cont/tracker.md` |
| Procedimiento de refresco de precios por lotes | `references/refresco-de-precios.md` |
| **Precios oficiales de Alegra por país** (tabla verificada + cómo extraerla del HTML) | `references/precios-alegra-mx.md`, `references/precios-alegra-co.md` |
| Backlog de precios con estado | `prog-cont/backlog-precios-mx.md` |
| **Reportes a Google Chat** | `prog-cont/scripts/gchat.py` (`enviar()`, `estado()`, `--solo-si-hay`) |
| Portadas y capturas | `prog-cont/portadas/`, `prog-cont/capturas/` |
| Servidor MCP en Hermes | `mcp_servers.prog-cont` (verificado con `hermes mcp test prog-cont`) |
| **Diseño del agente autónomo + revisión del flujo** | `prog-cont/FLUJO-AGENTE-AUTONOMO.md` |

## 7c. Redirecciones 301 — trampa confirmada

Las 261 redirecciones del sitio viven en una **tabla propia de Rank Math**, no en posts: los ids
que devuelve `rank-math/get-redirections` (269, 268…) **no existen** como posts de WP.

- El MCP solo expone lectura (`rank-math/get-redirections`). **No hay ability para crear redirecciones.**
- `POST /wp-json/rankmath/v1/updateRedirection` responde `{"action":"new","message":"Nueva redirección creada."}`
  pero **no escribe nada**: el meta `rank_math_redirect` del post queda vacío (`found: false`), el total de
  reglas no cambia y la URL sigue dando 200. No confiar en esa respuesta.
- `ewpa/create-cpt-item` y `ewpa/get-cpt-item` rechazan tipos con capacidades dedicadas, así que tampoco se
  puede insertar la regla como CPT.
- Para automatizar de verdad hace falta el plugin **Redirection** (tiene REST propio:
  `/wp-json/redirection/v1/redirect`) o acceso a wp-cli/SFTP. Con lo que hay hoy, las reglas nuevas se crean
  a mano en Rank Math → Redirecciones (fuente = ruta relativa **sin** barra inicial, destino = URL completa, 301).
  **En la práctica las crea Fernanda**, así que la tarea del agente es entregarle la lista exacta y luego
  verificarlas con `curl -I` + cache-buster: no darlas por hechas ni decir que «quedaron aplicadas».
- **Cloudflare cachea los 200 y los 404** de estas URLs: para verificar hay que pedir la URL con un
  cache-buster (`?cb=991`), o se lee un estado viejo y se diagnostica mal. Comprobar siempre con cache-buster
  y mirar `x-cache`.

## 7b. Reportes al equipo (Google Chat)
Se reporta al espacio configurado en `GCHAT_WEBHOOK_URL` (el `.env` de Hermes). **Siempre** se avisa
cuando:

- quedan **borradores o pendientes** al terminar una corrida, con el enlace de edición de cada uno;
- se aplica un **lote de correcciones** (qué se cambió y en qué URLs);
- se entregan **métricas** (keywords, visitas, sesiones) o cambia una meta.

```python
import sys; sys.path.insert(0, r"C:/Users/ferna/AppData/Local/hermes/prog-cont/scripts")
import gchat
gchat.enviar("*Reporte* ...")
```

Formato: `*negrita*`, viñetas con `•`, enlaces completos (Chat los hace clicables), menos de 4.000
caracteres, en español y arrancando por lo que la persona tiene que hacer. Para cron: `python
gchat.py --solo-si-hay` no manda nada si no hay novedad, para no hacer ruido.

**El webhook se compara completo, no por espacio.** Un mismo espacio de Chat puede tener varios webhooks y
el token del `.env` puede estar rotado: si la URL que pasa la persona tiene el mismo `spaces/<id>` pero
distinto `key`/`token`, es otro webhook y hay que reemplazar la variable. Compara la cadena entera (o su
hash), nunca solo el id del espacio, y confirma el envío por el `name` que devuelve la API
(`spaces/<id>/messages/<msg>`): eso es la prueba de que salió, no el código 200.

## 8. Verificación final (postflight)

No se informa "listo" hasta confirmar, leyendo el sitio:

- `status` draft (o publish solo con autorización), slug correcto, portada asignada.
- **`author` = 17 (Leandro)** y **ficha técnica del autor presente** al cierre del contenido.
- **Imagen visible en el cuerpo** (primer bloque `wp:image`), no solo en `featured_media`, y con `alt`.
- `excerpt.raw` no vacío entre 138 y 160 caracteres.
- Rank Math con keyword, título ≤60 y descripción 140-160.
- FAQ: número de H3 en la sección = número de preguntas del schema.
- Al menos 1 tabla y 2-4 enlaces internos que respondan 200.
- Sección `Fuentes` con al menos 2 fuentes oficiales o del fabricante y fecha de consulta.
- Un solo enlace de Alegra en el cuerpo + CTA final con UTM.
- **Módulos nombrados contra la matriz del país:** ningún módulo que la tabla marque ❌ para ese país
  aparece en el texto ni en el enlace del CTA (grep del artículo contra
  `references/alegra-modulos-por-pais.md`).

Un éxito parcial nunca se reporta como éxito completo.
