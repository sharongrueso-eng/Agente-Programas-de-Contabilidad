# Imagen destacada — programascontabilidad.com

Receta comprobada para cubrir una entrada nueva sin pedirle nada a diseño.

## Estilo que ya usa el portal (no inventarlo)

Las destacadas del sitio son **fotos limpias**, no gráficos de marca:

- **Sin texto, sin logo, sin marco ni degradados.** El tema ya muestra el título al lado de la
  miniatura; quemarlo encima la ensucia.
- Composición con el **sujeto en el tercio derecho y espacio negativo a la izquierda**.
- Paleta neutra con acentos fríos (blanco, gris, azul marino, verde de planta). Luz natural.
- Los archivos existentes miden ~2560 px de ancho (≈2,35:1) o 1672×941. Una foto 16:9 se ve bien; un
  gráfico 1200×630 con titular **desentona** con el archivo.

Temática: dueño de pyme o contador trabajando (laptop, facturas, mostrador, oficina en casa). Nunca
capturas de la interfaz del software reseñado con datos reales.

## Generar la foto

Se reutiliza el generador de la skill `ie-pan-portadas-blog` en vez de escribir la llamada a Gemini:

```python
import importlib.util
spec = importlib.util.spec_from_file_location(
    "portada", r"C:/Users/ferna/AppData/Local/hermes/ie-panama/portadas/portada.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.generar_foto(prompt, "portadas/<slug>.jpg", modelo="gemini-3-pro-image",
               clave=m.clave_gemini(), aspecto="16:9")
```

El prompt debe cerrar con: *"No text, no letters, no signs, no logos, no watermarks."* y pedir el sujeto
en el tercio derecho con espacio negativo a la izquierda.

**Revisa la foto con `vision_analyze` antes de subirla**: confirma que no trae letras deformes y que
sirve como destacada. No ver la imagen no exime de revisarla.

## Subirla y asignarla

`ewpa/upload-image` **solo acepta un `url`**: para un archivo local hay que subirlo por REST a
`/wp-json/wp/v2/media` con `--data-binary`. Esta es la forma que funciona (la variante con `curl -u`
devuelve respuesta vacía):

```bash
curl -sS -A "curl/8.7.1" \
  -H "Authorization: $AUTH" \
  -X POST "https://programascontabilidad.com/wp-json/wp/v2/media" \
  -H "Content-Disposition: attachment; filename=<slug>.jpg" \
  -H "Content-Type: image/jpeg" \
  --data-binary @"C:/ruta/portadas/<slug>.jpg"
# -> {"id":5187, ...}   ese id es el medio
```

Luego se asigna y se confirma:

```python
mcp.execute("ewpa/update-post", {"post_id": PID, "featured_image_id": MID})
mcp.wp_get(f"/posts/{PID}?context=edit&_fields=featured_media")   # debe devolver MID
```

## Captura de una landing (para dentro del artículo)

Chrome headless en **primer plano se cuelga** con estas páginas (levanta 30+ procesos hijos y el shell no
retorna; se llegó a esperar 7 minutos). Lo que sí funciona: `--headless=old`, un `--user-data-dir` propio
y la corrida **en background**.

```bash
# terminal(background=true, notify=true)
CHROME="/c/Program Files/Google/Chrome/Application/chrome.exe"
"$CHROME" --headless=old --disable-gpu --no-sandbox --no-first-run --disable-extensions \
  --disable-dev-shm-usage --user-data-dir="<scratch>/cap1" \
  --window-size=1440,1200 --virtual-time-budget=6000 --timeout=40000 \
  --screenshot="C:/.../capturas/facturama-planes.png" "https://facturama.mx/planes-facturacion"
```

Sale ~1440×1200 (o el alto que pidas). Entre 339 KB y 490 KB es normal. **Revisa con
`vision_analyze`** que el hero o la tabla de precios se lea antes de subirla.

Se suben igual que una destacada (REST + `--data-binary`, con `-H "Content-Type: image/png"` si es PNG) y
se insertan como bloque `wp:image` con `figcaption` que diga qué se ve y la fecha de consulta.

### Dónde va dentro del artículo

Ancla preferida, en este orden:

1. el H2 que contenga «Precio» o «Precios» (la captura acompaña a la tabla);
2. el H2 de «Planes»;
3. el H2 de «Preguntas frecuentes»;
4. si no hay ninguno de los tres —pasa en las guías cuyos H2 son todos preguntas—, justo después del primer
   `</h2>`.

Localiza el `<!-- wp:heading` inmediatamente anterior al H2 elegido e inserta ahí el bloque (antes del
comentario, no dentro del `<h2>`). El `figcaption` nombra el producto y la fecha: «Landing de Alegra POS
en México, consultada el 21 de octubre de 2026.»

Después de insertar, confirma que el número de `wp-block-image` coincide en el raw y en
`content.rendered`, y que el render **no** tiene `<!-- wp:` sin parsear. Una comparativa que ya tenía
imágenes no necesita más: comprueba antes de duplicar.

## Pitfalls

- **Las rutas de `curl` en Windows son nativas.** `curl` es un binario nativo: `-o /c/Users/...` no se
  traduce y la escritura falla con `curl: (23) client returned ERROR on write` (o deja el archivo
  vacío). Escribe siempre `-o "C:/Users/..."` con barra normal; para el cuerpo de un POST,
  `--data-binary @C:/...`.
- **No reutilices la imagen de otro post.** Cambia el sujeto y el nombre del archivo; la biblioteca
  tiene 900+ medios y duplicar destacadas se nota en la portada del portal.
- **Alt text obligatorio**: el mismo texto del `alt` que usarías en el artículo (`Facturama precios`),
  no el nombre del archivo. El plugin de accesibilidad del sitio audita imágenes sin `alt`.
- Si la foto sale con manos o caras deformes, **regenera** en vez de recortar: el portal es un sitio
  comercial y la portada es lo primero que se ve en Discover.
- **La captura de landing no es la destacada.** La destacada es la foto editorial; las capturas de la
  landing del producto van **dentro del cuerpo**, junto a la sección de precios, y no se usan como
  `featured_media`.
