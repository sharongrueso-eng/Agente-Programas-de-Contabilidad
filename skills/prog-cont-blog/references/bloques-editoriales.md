# Bloques y estructura de la pieza

Salido del artículo de referencia que Sharon editó a mano (post 1957, «Facturación Siigo 2026:
precios, funciones y comparativa con Alegra», 14 de noviembre de 2026). Ese artículo es el
patrón: cuando una pieza se desvía de aquí, se desvía de lo que ella aprobó.

Los componentes viven en `orchestrator/linea_visual.py` (`respuesta_rapida`, `caja`,
`procedimiento`, `tabla`, `faq`, `firma`, `cta_final`). La biblioteca de componentes visuales
del portal —tech cards, comparador, dashboard— está en
`kit_visual_html_programas_contabilidad_hermes.md`.

## Paleta de los bloques

| Token | Color | Uso |
|---|---|---|
| Navy | `#002B5B` | píldora de la respuesta rápida, cabecera del procedimiento, texto de titular |
| Azul vivo | `#159bd7` | borde izquierdo, píldoras de «dato clave», círculos de los pasos |
| Celeste fondo | `#cce4f7` | fondo de la respuesta rápida, píldora de «atención» |
| Tinta bloque | `#18283F` | fondo de «atención», texto de los bloques claros |
| Gris dato | `#F4F6F8` | fondo de «dato clave» |
| Línea | `#CCE4F7` | bordes de tarjetas y FAQ |

Nada de colores nuevos: si hace falta uno, no es un bloque nuevo, es una pieza mal planteada.

## 1. Respuesta rápida (va arriba, sin CTA)

```html
<div role="note" data-pdc="componente" style="background:#cce4f7;border-left:8px solid #159bd7;border-radius:10px;padding:22px 28px;margin:24px 0;color:#18283F;">
  <p style="margin:0 0 10px;"><span style="display:inline-block;background:#002B5B;color:#ffffff;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:4px 12px;border-radius:999px;">Respuesta rápida</span></p>
  <p style="margin:0 0 12px;font-size:18px;line-height:1.45;font-weight:700;color:#002B5B;">La respuesta en una frase: quién gana, para quién y por qué.</p>
  <ul style="margin:0 0 16px 20px;padding:0;font-size:15px;line-height:1.6;color:#18283F;">
    <li style="margin:0 0 6px;"><strong>Criterio:</strong> el dato que lo sostiene.</li>
    <li style="margin:0;"><strong>Otro criterio:</strong> su dato.</li>
  </ul>
  <p style="margin:0;padding-top:12px;border-top:1px solid #8fc3ea;font-size:14px;line-height:1.5;color:#18283F;"><strong>Cuándo conviene el otro:</strong> el caso en que la respuesta cambia.</p>
</div>
```

Reglas: una frase + 3-4 viñetas máximo + un remate que dice cuándo NO aplica. Va en la primera
pantalla y nunca lleva botón.

## 2. Dato clave, atención y límite

Misma estructura, color distinto. `dato` explica una cifra que cambia la decisión; `atencion`
avisa de una trampa; `limite` señala lo que el producto no hace.

```html
<!-- Dato clave -->
<div role="note" data-pdc="componente" style="background:#F4F6F8;border-left:8px solid #002B5B;border-radius:10px;padding:22px 28px;margin:24px 0;color:#18283F;">
  <p style="margin:0 0 10px;"><span style="display:inline-block;background:#159bd7;color:#ffffff;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:4px 12px;border-radius:999px;">Dato clave</span></p>
  <p style="margin:0;font-size:18px;line-height:1.45;font-weight:700;color:#18283F;">La cifra o la condición que el lector no esperaba, en una frase.</p>
</div>

<!-- Atención: fondo navy, texto blanco -->
<div role="note" data-pdc="componente" style="background:#18283F;border-radius:10px;padding:22px 28px;margin:24px 0;color:#ffffff;">
  <p style="margin:0 0 10px;"><span style="display:inline-block;background:#cce4f7;color:#002B5B;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:4px 12px;border-radius:999px;">⚠ Atención</span></p>
  <p style="margin:0;font-size:18px;line-height:1.45;font-weight:700;color:#ffffff;">El caso concreto en que el lector se equivoca si no lo sabe.</p>
</div>
```

Dos o tres bloques por pieza como máximo, y nunca dos seguidos: se leen como publicidad.

## 3. Procedimiento (pasos numerados)

```html
<div data-pdc="componente" style="background:#ffffff;border:1px solid #cce4f7;border-radius:10px;margin:24px 0;overflow:hidden;color:#18283F;">
  <div style="background:#002B5B;padding:14px 24px;">
    <p style="margin:0;font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#cce4f7;">Procedimiento</p>
    <p style="margin:4px 0 0;font-size:18px;line-height:1.4;font-weight:700;color:#ffffff;">Cómo decidir en N pasos, sin depender de la demo</p>
  </div>
  <div style="padding:8px 24px 18px;">
    <div style="display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-bottom:1px solid #E5EEF7;">
      <span style="flex:0 0 32px;width:32px;height:32px;border-radius:50%;background:#159bd7;color:#ffffff;font-weight:700;font-size:15px;line-height:32px;text-align:center;">1</span>
      <p style="margin:0;font-size:15px;line-height:1.55;"><strong style="color:#002B5B;">Verbo + objeto.</strong> El paso, con la cifra o el criterio que lo hace ejecutable.</p>
    </div>
  </div>
</div>
```

Pasos numerados, no viñetas: el orden importa. Entre 3 y 5 pasos; cada uno empieza con un verbo.

## 4. Tablas

Formato del tema, no componente propio: `has-fixed-layout` y todas las celdas alineadas a la
izquierda con `data-align`. El pie va abajo y cita fuente y fecha.

```html
<table class="has-fixed-layout" data-pdc="componente">
  <caption style="caption-side:bottom;text-align:left;padding:10px 16px;font-size:13px;line-height:1.5;font-weight:400;color:#4B5563;">Precios de lista leídos en siigo.com/precios-siigo el 13 de noviembre de 2026.</caption>
  <thead><tr>
    <th class="has-text-align-left" data-align="left" scope="col">Plan</th>
    <th class="has-text-align-left" data-align="left" scope="col">Documentos al año</th>
    <th class="has-text-align-left" data-align="left" scope="col">COP al año</th>
  </tr></thead>
  <tbody><tr>
    <td class="has-text-align-left" data-align="left">Facturación 24</td>
    <td class="has-text-align-left" data-align="left">24</td>
    <td class="has-text-align-left" data-align="left">119.900</td>
  </tr></tbody>
</table>
```

Una tabla por idea. Si hay que comparar seis planes, no es una tabla: es una lista de tarjetas.

## 5. Preguntas frecuentes

`<details>` para que funcione sin JavaScript, con la clase `pdc-faq`. La pregunta va en `h3` con
cursiva dentro del `summary`, y la respuesta en un `div` con aire arriba.

```html
<details class="pdc-faq" data-pdc="componente" style="border:1px solid #CCE4F7;border-radius:10px;background:#FFFFFF;padding:14px 18px;margin:0 0 12px;">
  <summary style="cursor:pointer;"><h3 style="margin:0;font-size:18px;color:#002B5B;"><em>¿Pregunta concreta que el lector buscaría?</em></h3></summary>
  <div style="padding-top:10px;"><p>Respuesta que se sostiene con el registro, sin promesas.</p></div>
</details>
```

Todas cerradas por defecto: abrir la primera empuja el resto fuera de pantalla.

## 6. Orden de la pieza (comparativa de dos marcas)

1. Párrafo de entrada con el dato que decide (precio de entrada de cada una).
2. **Respuesta rápida**.
3. `h2` Cómo cobra la marca del título → **dato clave** de periodicidad y cupos.
4. `h2` Procedimiento para decidir → **bloque de pasos**.
5. `h2` Qué incluye cada plan (uno por línea de producto, con `h3`).
6. `h2` Planes de Alegra en el país.
7. `h2` Comparación por dimensión → **tabla**.
8. `h2` IA: qué automatiza cada uno.
9. `h2` Cómo pasar de una a otra.
10. `h2` Veredicto (panel de tres bloques por perfil).
11. `h2` Preguntas frecuentes → **details**.
12. `h2` Fuentes y fecha de actualización.
13. Firma del autor, y el CTA final al cierre.

En una comparativa de **dos** marcas no se nombra un tercer competidor: el lector que llega
buscando «A vs B» quiere decidir entre esas dos. Si el tema exige más marcas, el formato no es
comparativa de dos.

## 7. Reglas que se rompen y vuelven a aparecer

- **El bloque va como fragmento, nunca como documento.** En el post 1957 apareció un bloque
  pegado como `<!DOCTYPE html><html><head><style>body{…}</style>…`, con su `body` afectando a toda
  la página. Un bloque es el `<div>` y nada más: sin `html`, `head`, `body` ni `<style>` global.
- **La viñeta no puede salir del marco.** El tema fuerza `padding-left:0 !important` en
  `.entry-content ul`. La sangría va en `margin` (`margin:0 0 16px 20px`), o con
  `padding-left` **también** `!important`. Nunca `padding-left` sin `!important`: la viñeta se
  dibuja fuera del artículo y en móvil se corta.
- **Los enlaces se comprueban.** `orchestrator/enlaces.py` recorre los `href` del cuerpo, ignora
  anclas y repetidos, y marca 404, 410 y 5xx. Un 401/403 es un muro anti-robot, no un enlace
  roto. El control `enlaces_rotos` corre antes de publicar y manda a corregir.
- **No se promete lo que no hay.** «Los 7 mejores», «top 10», «N plataformas» se contrastan con
  las fichas del registro (`brand_count`). Prometer un listado que no se puede llenar es el
  mismo error que inventar un precio.
- **Cada precio lleva fuente y fecha dentro del bloque o en el pie de la tabla.** Si el
  proveedor no lo publica, se escribe «No publicado»; no se estima.
