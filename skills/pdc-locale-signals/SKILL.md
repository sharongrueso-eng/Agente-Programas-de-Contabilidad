---
name: pdc-locale-signals
description: >
  Skill para implementar señales de idioma/localidad por página en Programas de
  Contabilidad. Controla html lang, og:locale e inLanguage/areaServed en el JSON-LD
  de RankMath según el país objetivo de cada post. Úsala cuando necesites asignar
  o actualizar el país de un contenido específico (reseña, comparativa, guía) para
  que los crawlers, buscadores y motores de respuesta reciban señales geográficas
  correctas en lugar de heredar el default global del sitio.
---

# Señales de idioma/localidad por página

---

## MCPs disponibles

| Entorno | MCP | URL base |
|---|---|---|
| Staging | `pdc-stg-mcp` | `https://wordpress-1477557-6320318.cloudwaysapps.com` |
| Producción | `pdc-prod-mcp` | `https://programascontabilidad.com` |

---

## Arquitectura

El plugin `custom-plugin-pdc` intercepta tres filtros de WordPress en `after_setup_theme`:

| Filtro | Señal que controla |
|---|---|
| `language_attributes` | `<html lang="es-XX">` |
| `rank_math/opengraph/locale` | `<meta property="og:locale" content="es_XX">` |
| `rank_math/json_ld` | `inLanguage` en todos los nodos del `@graph` + `areaServed` en `WebPage` y `BlogPosting` |

La fuente de datos es un único meta field por post: **`pdc_target_country`** con el código ISO 2 del país.

**Requisito:** el plugin `custom-plugin-pdc` debe estar activo y con los filtros de
localización implementados en **ambos entornos** (staging y producción) para que el
meta field tenga efecto.

---

## Países soportados

| Código | html lang | og:locale | areaServed.name |
|---|---|---|---|
| `DO` | `es-DO` | `es_DO` | República Dominicana |
| `CO` | `es-CO` | `es_CO` | Colombia |
| `MX` | `es-MX` | `es_MX` | México |
| `CR` | `es-CR` | `es_CR` | Costa Rica |
| *(sin meta)* | `es` | `es_419` | *(no se agrega)* |

Para agregar un país nuevo, actualizar el `$map` en `custom-plugin-pdc`.

---

## Flujo de implementación por post

### 1. Identificar el país objetivo

Leer el contenido del post y determinar el país. El país correcto es el que el
contenido trata explícitamente — el que menciona su regulación, moneda, entidades
fiscales u organismos locales. No inferir por el precio ni por menciones de paso.

### 2. Escribir el meta field

```
ewpa/update-post-meta {
  post_id:    {ID del post},
  meta_key:   "pdc_target_country",
  meta_value: "{código ISO}"   ← "DO", "CO", "MX" o "CR"
}
```

Eso es todo. El plugin PHP aplica los tres cambios automáticamente en el siguiente render.

### 3. Verificar

```javascript
// En devtools — todos deben coincidir con el país asignado:
const graph = JSON.parse(
  document.querySelector('head script.rank-math-schema-pro').textContent
)['@graph'];

({
  htmlLang: document.documentElement.lang,
  ogLocale: document.querySelector('meta[property="og:locale"]')?.content,
  inLanguageValues: [...new Set(
    graph.filter(n => n.inLanguage).map(n => n.inLanguage)
  )],
  areaServed: graph
    .filter(n => n.areaServed)
    .map(n => ({ type: n['@type'], name: n.areaServed?.name }))
})
```

**Resultado esperado para `DO`:**
```json
{
  "htmlLang": "es-DO",
  "ogLocale": "es_DO",
  "inLanguageValues": ["es-DO"],
  "areaServed": [
    { "type": "WebPage",     "name": "República Dominicana" },
    { "type": "BlogPosting", "name": "República Dominicana" }
  ]
}
```

---

## Reglas

- **Un meta field por post** — `pdc_target_country` es la única fuente de verdad.
- **No modificar el contenido del post** — esta skill solo escribe meta fields, nunca `post_content`.
- **`areaServed` solo en `WebPage` y `BlogPosting`** — no en `Review`, `SoftwareApplication` ni otros tipos.
- **`inLanguage` se actualiza en todos los nodos** que ya lo tengan — sin filtrar por tipo.
- **Posts sin meta = default panregional** — `html lang="es"`, `og:locale="es_419"`, sin `areaServed`.
- **No usar esta skill para cambiar el idioma del sitio globalmente** — eso se hace en RankMath → Títulos y Metadatos, no aquí.

---

## Posts ya actualizados en staging (pendientes en producción)

| Post ID | Slug | País | Estado producción |
|---|---|---|---|
| 4433 | `/analisis-de-herramientas/dgmax-resena-software/` | DO | ✅ producción |
| 4180 | `/analisis-de-herramientas/gti-costa-rica/` | CR | ✅ producción |
| 2172 | `/analisis-de-herramientas/mejores-sistemas-de-facturacion/` | DO | ✅ producción |
