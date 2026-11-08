# Línea visual del blog (v1)

Fuente: `PdC_Linea_Visual_v1.docx` (6 de noviembre de 2026), en la carpeta de insumos.
Los componentes están implementados en `orchestrator/linea_visual.py`; el agente no los
redacta, los rellena.

## Qué cambia respecto a lo que había

| Elemento | Antes | Ahora |
|---|---|---|
| Cajas | una sola caja celeste para todo | cinco, cada una con su rol |
| Tablas | bloque celeste sin jerarquía | encabezado navy, cebra, caption con fuente |
| CTA | enlace de texto dentro de una caja | bloque navy con botón y microcopy |
| Recomendación | párrafos corridos | caja con veredicto e «Ideal si / Evita si» |
| FAQ | acordeón con JavaScript | `<details>`, funciona sin scripts |

## Las cinco cajas

Cada una lleva etiqueta, color e icono — nunca solo color —, borde izquierdo de 4 px y
peso 400 dentro de la caja. Máximo dos frases y una caja de énfasis cada 400 palabras.

| Caja | Cuándo | Dónde |
|---|---|---|
| Respuesta rápida | responde la pregunta del título | primera pantalla, una por artículo |
| Dato clave | un hallazgo que cambia la decisión | junto a la sección que lo justifica |
| Atención | costos o condiciones que se pasan por alto | antes de precios |
| Límite | lo que la herramienta no hace | en reservas, junto a puntos de atención |
| Nota de método | fecha y fuentes de los datos | bajo cada tabla de precios |

## Paleta con roles

Navy `#002B5B` estructura · azul `#3299E2` solo bordes y texto grande · enlace `#0B6FA4`
texto pequeño azul · celeste `#00AEEF` solo sobre navy · verde `#1B7A32` y rojo `#B02A37`
texto de ventajas y límites · tinta `#1F2937` cuerpo dentro de componentes · gris `#4B5563`
pies y notas.

Ningún texto pequeño en `#3299E2`, `#00AEEF` sobre blanco ni `#28A745`: no pasan contraste.

## Control automático

`validate()` trae el control `linea_visual`, que exige: tabla real con `caption` que cite
fuente y fecha, FAQ con `<details>`, un CTA final con `rel="nofollow noopener"` y ningún
CTA antes del primer H2. Se aplica solo a piezas que ya usan componentes con estilos en
línea: una pieza heredada se juzga por contenido, no por presentación.

## Decisiones abiertas del documento

Texto del botón (neutro o nombrando la marca), si la línea aplica solo a artículos nuevos,
si la FAQ de reseñas deja el acordeón navy, la fuente y ponderación del Score Card, y el
color único de los H2.

**Tratamiento por país:** tuteo en Colombia, México y República Dominicana; usted en Costa
Rica.
