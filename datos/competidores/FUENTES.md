# Competidores por mercado — fuente oficial

Los principales competidores de cada mercado no se adivinan ni se dejan fijos en código:
viven en la wiki de Alegra, en un documento por país. El agente los lee de ahí y actualiza
las fichas de `datos/herramientas/` con lo que cada landing publique.

| Mercado | Documento de la wiki |
|---|---|
| Colombia | `colombia-seoaeo-2026-luxzhM4svS` |
| México | `mexico-seoaeo-2026-SFq4rTAa1e` |
| República Dominicana | `alegra-republica-dominicana-search-y-llms-2026-seo-aeo-2026-P34lDcpvNm` |
| Costa Rica | `alegra-costa-rica-search-y-llms-seo-geo-2026-dHa145a3Ei` |

## Regla de cobertura

El blog publica sobre **cuatro mercados**. Una corrida no puede asumir Colombia: el mercado
de la pieza lo decide la página que se va a tocar (su URL, su título y su normativa) y la
auditoría debe poder elegir turno en cualquiera de los cuatro.

Un mercado con una sola ficha no permite comparar, así que el vigía mantiene al menos tres
competidores por país, releídos de su landing oficial.

## Cómo se usa

1. El documento del país dice qué competidores importan y por qué.
2. De cada competidor se entra a **su landing oficial** y se extraen planes, precios con su
   periodicidad y funciones: la ficha es lo que el proveedor publica, no lo que recordamos.
3. Si un dato no está publicado, la ficha dice «no publicado» y el artículo lo declara. Nunca
   se estima ni se deduce, y nunca se detiene la publicación por eso.
