# programascontabilidad.com — estado del proyecto

*Informe generado el 12 de noviembre de 2026. Datos leídos del sitio en vivo y del proyecto local.*

## 1. El portal

| Dato | Valor |
| --- | --- |
| URL | https://programascontabilidad.com |
| Contenido publicado | 343 entradas |
| Borradores | 25 |
| Programadas | 0 |
| Países | México, Colombia, Costa Rica, República Dominicana, Perú, Panamá |
| Modelo editorial | Una pieza por país (no piezas multi-país): cada país tiene sus precios, su norma fiscal, su vocabulario y su CTA |
| ICP | Dueño de pyme, contador independiente y despacho pequeño que está eligiendo herramienta |

Formatos que se producen: reseña (~1.300-1.500 palabras), comparativa (~1.300-1.600 palabras) y
guía operativa (el formato que más tráfico trae).

## 2. Qué cubre la automatización

El procedimiento completo vive en la skill `prog-cont-blog`, con nueve documentos de referencia:

| Referencia | Contenido |
| --- | --- |
| `formatos.md` | Estructura exacta de reseña, comparativa y guía operativa |
| `wordpress-prog-cont.md` | Receta de publicación: draft, autor, Rank Math, schema FAQ |
| `portada-y-medios.md` | Capturas de landing con Chrome headless y estilo de portada |
| `precios-alegra-mx.md`, `precios-alegra-co.md` | Tarifas oficiales verificadas de Alegra |
| `refresco-de-precios.md` | Refresco de precios por lotes con dry-run |
| `alegra-modulos-por-pais.md` | Qué módulo de Alegra existe y cuál no en cada país |
| `migracion-colombia.md` | Landings de migración Siigo / Loggro / World Office |
| `auditoria-blog-seo-aeo.md` | Auditoría completa del portal (SEO + AEO) |

Reglas de fondo de la skill:

- **Preflight obligatorio**: ningún artículo se escribe sin revisar antes el mapa de canibalización.
- **Una intención, una URL**: el portal ya tiene URLs compitiendo entre sí; el error más caro es crear una más.
- **Precios con fecha**: cada cifra se verifica contra la página oficial del fabricante el mismo día.
- **Alegra se sugiere, no se impone**: una mención contextual en el cuerpo, un CTA al cierre, tabla comparativa simétrica y honesta.
- **Nunca prometer un módulo que Alegra no tiene en ese país** (nómina en CR/PE/PA; ERP en PE/PA).
- **No se publica automáticamente**: los borradores esperan aprobación humana.

## 3. Estado del proyecto

| Archivo | Qué contiene |
| --- | --- |
| `auditoria.json` | Auditoría de 342 entradas: palabras, H2/H3, enlaces externos y de Alegra, año viejo, portada, largo del extracto |
| `AUDITORIA-COMPLETA-2026-10-21.md` | Auditoría SEO + AEO del portal |
| `PLAN-CANIBALIZACION-2026-10-21.md` + `plan-canibalizacion.csv` | Mapa de canibalización y lotes de trabajo |
| `VALIDACION-REDIRECCIONES-2026-10-22.md` | Validación de los 301 |
| `tracker.md` | Estado pieza por pieza, con fecha de verificación de precios |
| `backlog-precios-mx.md` | Backlog de precios de México con estado |
| `FLUJO-AGENTE-AUTONOMO.md` | Diseño del agente autónomo del portal (3-nov-2026) |
| `contenido/`, `portadas/`, `capturas/`, `scripts/` | HTML de las piezas, imágenes y scripts de lote |

## 4. Pendientes al 22 de octubre de 2026

1. **Cinco redirecciones 301 sin crear.** No son automatizables por API (Rank Math guarda las reglas en
   una tabla propia y el endpoint REST que responde "creada" no escribe nada). Hay que crearlas a mano en
   Rank Math → Redirecciones, con la ruta de origen relativa (sin barra inicial) y destino en URL completa:
   `87 → 88`, `3742 → 3075`, `109 → 35`, `3234 → 2172`, `3163 → 2172`.
2. **Borrador sin publicar: id 5186**, reseña de Facturama (México), esperando aprobación.
3. **42 enlaces de Alegra con ruta vieja** (redirigen 301) por corregir al refrescar cada pieza.
4. **Enlace roto** `/rdomincana/contacto/` (falta la "i" de dominicana).
5. **El agente autónomo está diseñado pero no programado**: no hay ninguna tarea recurrente activa.

## 5. Medición

Ahrefs es la única fuente de datos del portal (DataForSEO se retiró). Coste medido: ~41 unidades por
fila de keyword, **3 unidades por fila** de SERP. Un preflight normal (1 keyword + 1 SERP de 10) cuesta
~50 unidades.

Trampas comprobadas del SERP de Ahrefs: sin `type=organic` llegan filas duplicadas y filas con `url` nula
(AI Overview, People Also Ask, anuncios); hay que filtrar y deduplicar antes de contar. La lista
`positions` omite huecos: si el puesto 1 es un anuncio, la primera fila es `position: 2`.

## 6. Trampas de publicación ya documentadas

- La portada **no** se repite en el cuerpo: el tema ya imprime la imagen destacada y ponerla otra vez la duplica.
- Las tablas necesitan el formato de marca (`is-style-stripes` + fondo `#cce4f7`), no el de Gutenberg por defecto.
- El extracto propio es obligatorio: si falta, WordPress lo fabrica y no pasa el control de calidad (138-160 caracteres).
- El autor se envía explícito en el payload; si se omite, la pieza queda firmada por la cuenta que autentica por API.
- Antes de refrescar una URL hay que comprobar que no responda 301: si redirige, el contenido vivo está en el destino.
- Cloudflare cachea los 200 y los 404: para verificar estados hay que pedir la URL con un cache-buster.
- En scripts, el User-Agent por defecto de Python se bloquea: hay que enviar `User-Agent: curl/8.7.1`.
