# Auditoría completa del portal → decisiones editoriales

Cuando piden «cómo viene el blog», «auditoría completa» o «métricas para decidir». El entregable no es un
panel de datos: es un documento con **decisiones priorizadas** y un plan 30/60/90. Sin decisiones, la
auditoría no sirve.

## 1. Inventario del contenido (MCP `prog-cont`)

Trae las publicadas con contenido y calcula por pieza: palabras, H2, H3, imágenes en el cuerpo,
`featured_media`, si tiene `faq_schema_jsonld` y si menciona a Alegra. Agrupa por año, por mes del año en
curso, por categoría, y lista los borradores con `modified`.

```python
for page in range(1, 5):
    d = mcp.wp_get(f"/posts?per_page=100&page={page}&status=publish&_fields=id,title,slug,date,categories,featured_media,meta,content")
```

Ojo: `/posts?status=draft&per_page=100&page=2` devuelve **400** cuando hay menos de 100 borradores. Pide
solo la página 1 y no pidas paginar si `len(d) < 100`.

## 2. Tráfico medido (GA4) — la única fuente de verdad de visitas

1. Canales de los últimos 28 días (incluye `engagementRate` y `averageSessionDuration`).
2. Landings de búsqueda orgánica **con `limit: 500`** y guarda el resultado en disco (spillea a archivo).
3. **La métrica que decide:** cruza esas landings contra los slugs publicados y cuenta cuántas entradas no
   recibieron **ni una** sesión orgánica. En este portal ronda la mitad del archivo; es el argumento para
   podar y el mejor titular de la auditoría.

Señales que conviene reportar aparte: el canal `Direct` con engagement bajo (ruido/bots) y el canal
`AI Assistant`, que ya existe y mide el tráfico que llega desde asistentes.

## 3. Estimación competitiva (Ahrefs) — tendencia, no verdad

`site_explorer_metrics` + `site_explorer_top_pages` (y `site_explorer_organic_keywords` para el mapa de
keywords del portal). **Contrasta siempre con GA4 antes de citarlo:** el
mismo dominio puede reportar cifras muy distintas en pocas semanas y atribuir cientos de visitas a una URL
que GA4 no ve en su top. Si no cuadra, dilo en el informe y sigue con GA4.

## 4. SERP (Ahrefs)

`serp_overview` con `type=organic`, `top_positions=10` y `select=position,url,title`, una llamada por
cabeza de categoría y país. Devuelve posición, URL y título: con eso se ve quién ocupa el top, qué puesto
tenemos y si el hueco es alcanzable.

- **Sin `type=organic`** llegan filas duplicadas y filas con `url: null` (AIO, People Also Ask, anuncios).
  Filtra `url` no nulo y deduplica por posición.
- `positions` **omite huecos**: si el puesto 1 es un anuncio, la primera fila es `position: 2`.
- Coste: 3 unidades por fila (~30 por SERP de 10). Se guarda 24 h en caché antes de repetir la consulta.

Regla que se aprendió midiendo: **la presencia en la respuesta generada cambia con la redacción exacta de
la consulta.** «software contable mexico» puede no citarnos mientras «software contable en mexico» sí.
Prueba la variante exacta que te importa, no una aproximación.

## 5. Menciones en asistentes de IA (AEO) — Ahrefs Brand Radar

Se lee con `brand_radar_ai_responses` (preguntas y respuestas que nos mencionan, con fuentes citadas) y
`brand_radar_cited_pages` / `brand_radar_cited_domains` (qué páginas y dominios se citan). Filtra por
`data_source`: `chatgpt`, `google_ai_overviews`, `gemini`, `perplexity`, `copilot`, `grok`.

**Requisito:** el dominio necesita un **report de Brand Radar** propio. `management_brand_radar_reports`
lista los que existen — hoy hay de Alegra México, Colombia, Costa Rica y República Dominicana, **ninguno de
programascontabilidad.com**. Sin report no hay datos de AEO de este portal: si la auditoría lo pide, se
declara el hueco y se propone crear el report (`management_brand_radar_reports_create`), no se inventa.

Con la lista se construyen las dos tablas que importan: **qué preguntas nos citan** y **qué páginas
nuestras citan** (las que más aparecen son las que hay que defender y actualizar primero). Los huecos
—cabezas de categoría donde no aparecemos— se contrastan con el SERP de §4 para saber quién los ocupa.

## 6. Canibalización: agrupar por intención, no por parecido de título

Normaliza el título (minúsculas, sin tildes), detecta país, producto y tipo (comparativa / precio /
guía-reseña) y agrupa. Los grupos con **3 o más URLs** son la deuda; los de 2 con títulos casi idénticos
son la emergencia.

```python
T = str.maketrans('áéíóúñ', 'aeioun')
# país → producto (software contable, facturación, POS, ERP…) → tipo
```

## 7. Técnico AEO

- `llms.txt` del dominio: tamaño y número de entradas listadas.
- `sitemap_index.xml` y cuántas URLs trae el `post-sitemap.xml`.
- Cobertura de FAQ schema (posts con `faq_schema_jsonld` sobre publicadas).

## 8. Estructura del entregable

1. **Resumen: cinco números que deciden** (arriba, sin adornos).
2. Estado del contenido (tabla) + cadencia por mes + borradores que merecen decisión.
3. Tráfico medido: canales, top 10 landings y el patrón de lo que funciona.
4. SEO: keywords, top páginas y grupos de canibalización.
5. AEO: menciones, páginas citadas, dónde sí y **dónde no** (con tabla de quién se lleva el AIO).
6. Diagnóstico en 5 puntos (no en 15).
7. **Decisiones numeradas** (D1…Dn), cada una con alcance, plazo («esta semana», «semana 2») y qué se
   espera mover. Prohibido cerrar con «seguir publicando».
8. Plan 30/60/90 con metas numéricas.
9. Anexo: **lo que no se pudo medir** (sin Search Console, sin eventos de conversión, fuente inestable).

## 9. Regla de honestidad

Separa siempre **medido** (GA4, WordPress) de **estimado** (Ahrefs) de **observado en SERP** (Ahrefs `serp_overview`,
que es una foto del día). Si falta Search Console, escríbelo en el resumen y en el anexo: es el dato que
más pesa y el que no se puede sustituir con estimaciones.

## 10. Reporte al equipo

Manda al Chat la versión corta con los cinco números, las decisiones y el bloqueante; el documento completo
se queda como archivo del proyecto. Formato en SKILL.md §7b.
