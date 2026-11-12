# Refresco de precios en lote

Cuando el proveedor cambia tarifas y decenas de entradas repiten las viejas. El riesgo no es el reemplazo:
es dejar cifras viejas vivas o romper el marcado de bloques. Procedimiento:

## 1. Una sola fuente, guardada

Consigue la tabla oficial (producto, plan, mensual, equivalente anual, moneda, descuento, fecha de
lectura) y guárdala como JSON en el proyecto. **Cada edición cita esa tabla**, no el post anterior: los
posts viejos son justamente lo que hay que corregir.

La tabla se lee del **marcado** de la página oficial, no de una captura ni de un resumen: en
`alegra.com/{pais}/precios/` cada producto vive en un contenedor `pricing-cards-<producto>` y publica el
precio mensual junto al «Facturado $X anualmente», del que se deduce el equivalente mensual con descuento.
Antes de refrescar, confirma que el producto sigue siendo el mismo y opera en el mismo mercado (dominio,
moneda, idioma, norma fiscal): si cambió de mercado, el refresco de precios no aplica y la pieza se
reescribe con otro ángulo (SKILL.md §1.3).

## 2. Mapa URL → post ID

`GET /posts?slug=<slug>&status=any`. Si el slug no devuelve nada, la URL es una redirección: el post vivo
está en el destino (ver el pitfall del 301 en SKILL.md §6). Refresca el destino.

## 3. Inventario antes de tocar

Por cada post, extrae las frases con cifras y cuenta las imágenes que ya tiene:

```python
texto = re.sub(r'<[^>]+>', ' ', raw)
frases = re.findall(r'[^.]{0,190}\$\s?[\d.,]+[^.]{0,190}\.', texto)
```

Sirve para saber cuántas menciones hay (un post puede repetir la misma tabla dos veces) y si le falta la
captura de landing.

## 4. Dry-run con conteos

Un diccionario `{pid: [(viejo, nuevo), …]}` y por cada par `count(viejo)`. Aplica **solo** cuando todos
los pares dieron ≥1: un cero significa que la cadena no es la que crees y el reemplazo siguiente se
pierde en silencio.

## 5. La cadena casi nunca coincide tal cual

Los precios viven dentro de `<strong>`, `<td style=…>`, spans de color y `&nbsp;`. Dos salidas:

- buscar solo el fragmento de texto, sin las etiquetas que lo envuelven;
- o copiar el fragmento exacto del raw (con sus etiquetas) y reemplazar ese bloque completo.

## 6. Valores que se pisan entre sí

Si el valor nuevo de un plan es el valor viejo de otro (3.790 → 4.890 mientras 4.890 → 6.090), sustituye
primero **todos** los viejos por marcadores (`@@A@@`, `@@B@@`) y en una segunda pasada cambia los
marcadores por los valores finales. Si no, el segundo reemplazo convierte lo que acabas de escribir.

## 7. Tablas y listas: el marcado se rompe fácil

Un `<li>` nuevo necesita su `<!-- wp:list-item -->` **y** su `<!-- /wp:list-item -->`; la lista necesita
su `<!-- wp:list -->` y su `<!-- /wp:list -->`. Después de editar cuenta aperturas y cierres de
`wp:list-item` y de `wp:list`: deben coincidir. Un cierre huérfano tras `</ul>` deja el bloque abierto y el
siguiente bloque (una imagen, un H2) se lo traga.

## 8. Auditoría de residuos

Lista de tokens viejos (`$138`, `$499`, `RFCs ilimitados`, nombres de plan retirados) contra todos los
posts y revisa **cada** acierto: algunos son legítimos (el precio del competidor, el precio del propio
competidor que casualmente coincide con la cifra vieja de Alegra).

## 9. Verifica en la página, no solo en la API

Descarga la URL pública y busca la cifra nueva y `<figure class="wp-block-image`. El HTML servido puede
traer la copia vieja aunque el `content.raw` ya esté actualizado (caché de servidor o plugin de
rendimiento). Si el HTML no cambia, `ewpa/clear-cache` con el `post_id` y vuelve a comprobar.

## 10. Reporta lo que no verificaste

Si una cifra del competidor no se pudo contrastar contra su página oficial, dilo en el reporte en vez de
cambiarla a ojo. Un número inventado en una tabla de precios es el error más caro del portal.
