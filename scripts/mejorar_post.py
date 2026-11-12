"""Mejora un post ya publicado: metadatos, enlaces, viñetas, tabla, CTA y firma.

Cada arreglo es determinista y se puede repetir sin dañar el artículo: si el cambio ya está
hecho, no lo duplica. Se pensó para corregir el post 5309 y para que las corridas siguientes
nazcan con estas reglas.

Uso:
    python scripts/mejorar_post.py --post 5309 --categoria 16 --subcategoria 21 \
        --etiquetas "alegra,siigo,world office,restaurantes,pos" \
        --titulo-seo "..." --meta "..." --keyword "..."
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.linea_visual import AZUL, CELESTE_SUAVE, LINEA, NAVY, TINTA  # noqa: E402


def env(nombre: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    for archivo in (Path.home() / ".pdc" / nombre,):
        if not archivo.exists():
            continue
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                clave, _, valor = linea.partition("=")
                valores.setdefault(clave.strip(), valor.strip())
    return valores


def sesion() -> tuple[str, str, str]:
    datos = env("wp-prod.env")
    return datos["PDC_PROD_URL"], datos["PDC_PROD_TOKEN"], datos["PDC_PROD_USER"]


def http(metodo: str, ruta: str, cuerpo: dict | None = None) -> tuple[int, dict | list]:
    base, token, usuario = sesion()
    import base64

    peticion = urllib.request.Request(
        base.rstrip("/") + ruta,
        method=metodo,
        data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{usuario}:{token}".encode()).decode(),
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            return respuesta.status, json.loads(respuesta.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "{}")


def estado_de(url: str) -> int:
    try:
        peticion = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return respuesta.status
    except urllib.error.HTTPError as error:
        return error.code
    except Exception:  # noqa: BLE001
        return 0


def urls_reales() -> list[str]:
    from orchestrator.sitemap import urls_del_sitio

    return urls_del_sitio(maximo=60)


OTROS_MERCADOS = ("/rd/", "-rd/", "mexico", "costa-rica", "panama", "republica-dominicana")
VACIAS = {"de", "la", "el", "los", "las", "en", "y", "para", "que", "con", "por", "un", "una", "del"}


def _mejor_candidata(slug: str, reales: list[str]) -> str:
    """El reemplazo más parecido por tema y compatible por país.

    Un enlace de precios no puede acabar en una comparativa con otro proveedor, ni un artículo
    colombiano en uno de República Dominicana: se exige coincidencia de tema, no de una palabra.
    """
    # Se comparan raíces, no palabras: "factura" y "facturacion" son el mismo tema.
    palabras = {p[:6] for p in slug.split("-") if len(p) > 3 and p not in VACIAS}
    puntajes: list[tuple[int, str]] = []
    for candidata in reales:
        if any(marca in candidata for marca in OTROS_MERCADOS):
            continue
        suyas = {p[:6] for p in candidata.rstrip("/").rsplit("/", 1)[-1].split("-") if len(p) > 3}
        puntajes.append((len(palabras & suyas), candidata))
    if not puntajes:
        return ""
    puntajes.sort(reverse=True)
    mejor_puntaje, mejor = puntajes[0]
    segundo = puntajes[1][0] if len(puntajes) > 1 else 0
    # Ante un empate, desenlazar: es mejor sin enlace que con el artículo equivocado.
    return mejor if mejor_puntaje >= 2 and mejor_puntaje > segundo else ""


def arreglar_enlaces(html: str, reales: list[str]) -> tuple[str, list[str]]:
    """Un enlace interno roto se sustituye por uno real del sitemap, o se desenlaza."""
    cambios: list[str] = []
    for url in sorted(set(re.findall(r'href="(https://programascontabilidad\.com[^"]*)"', html))):
        if estado_de(url) == 200:
            continue
        candidata = _mejor_candidata(url.rstrip("/").rsplit("/", 1)[-1], reales)
        if candidata:
            html = html.replace(f'href="{url}"', f'href="{candidata}"')
            cambios.append(f"{url} → {candidata}")
        else:
            html = re.sub(
                rf'<a [^>]*href="{re.escape(url)}"[^>]*>(.*?)</a>', r"\1", html, flags=re.DOTALL
            )
            cambios.append(f"{url} (desenlazado)")
    return html, cambios


def arreglar_utm(html: str) -> tuple[str, int]:
    """Todo enlace a Alegra lleva UTM: es la única forma de medir lo que trae el blog."""
    patron = re.compile(r'href="(https://www\.alegra\.com[^"]*)"')

    def con_utm(m: re.Match[str]) -> str:
        url = m.group(1).replace("&amp;", "&")
        if "utm_source=" in url:
            return 'href="' + url + '"'
        separador = "&" if "?" in url else "?"
        return (
            'href="'
            + f"{url}{separador}utm_source=programascontabilidad&utm_medium=blog"
            "&utm_campaign=comparativa-restaurantes-co"
            + '"'
        )

    nuevo, cuantos = patron.subn(con_utm, html)
    return nuevo, cuantos


def viñetas_visibles(html: str) -> str:
    """El tema borra el marcador de las listas: sin list-style no se ve la viñeta."""
    html = html.replace(
        'style="margin:16px 0 0;padding-left:38px;"',
        'style="margin:16px 0 0;padding-left:22px;list-style:disc outside;"',
    )
    return html.replace(
        'style="margin:0 0 8px;font-size:16px;line-height:1.6;font-weight:400;color:#1F2937;"',
        'style="margin:0 0 8px;font-size:16px;line-height:1.6;font-weight:400;color:#1F2937;'
        'list-style:disc outside;margin-left:16px;"',
    )


def quitar_promesa_de_plantilla(html: str) -> tuple[str, bool]:
    """Prometía una plantilla de cierre que no existe: se retira la promesa y su enlace."""
    marca = "#descargar-plantilla-cierre-restaurantes"
    if marca not in html:
        return html, False
    html = re.sub(
        r"<p[^>]*>[^<]*<a[^>]*" + re.escape(marca) + r"[^>]*>.*?</a>.*?</p>",
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(r"<a[^>]*" + re.escape(marca) + r'[^>]*>(.*?)</a>', r"\1", html, flags=re.DOTALL)
    return html, True


def tabla_con_estilo(html: str) -> tuple[str, int]:
    """La tabla del tema sale sin color y cortada: se envuelve y se le da la línea visual."""
    if 'class="pc-tabla"' in html:
        return html, 0
    cuantas = 0

    def envolver(m: re.Match[str]) -> str:
        nonlocal cuantas
        cuantas += 1
        tabla = m.group(0)
        tabla = re.sub(
            r"<table[^>]*>",
            f'<table style="width:100%;border-collapse:collapse;font-size:15px;'
            f'background:#FFFFFF;border:1px solid {LINEA};border-radius:10px;overflow:hidden;">',
            tabla,
            count=1,
        )
        tabla = re.sub(
            r"<th([^>]*)>",
            f'<th\\1 style="background:{NAVY};color:#FFFFFF;font-weight:700;text-align:left;'
            f'padding:12px 14px;font-size:13px;letter-spacing:.04em;text-transform:uppercase;">',
            tabla,
        )
        tabla = re.sub(
            r"<td([^>]*)>",
            f'<td\\1 style="padding:12px 14px;border-bottom:1px solid {LINEA};color:{TINTA};'
            f'vertical-align:top;">',
            tabla,
        )
        return (
            '<div class="pc-tabla" style="overflow-x:auto;margin:28px 0;'
            f'-webkit-overflow-scrolling:touch;">{tabla}</div>'
        )

    html = re.sub(r"<table[^>]*>.*?</table>", envolver, html, flags=re.DOTALL)
    return html, cuantas


def cta_sutil(html: str, url: str) -> tuple[str, bool]:
    """Un solo CTA, en caja oscura y con tono sobrio: el artículo ya enlaza a Alegra en el texto."""
    if 'class="pc-cta"' in html:
        return html, False
    bloque = (
        f'<div class="pc-cta" style="background:{NAVY};border-radius:12px;padding:28px 26px;'
        f'margin:34px 0;">'
        f'<p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:#A8BFD4;">Si quieres comparar por tu cuenta</p>'
        f'<p style="margin:0 0 16px;font-size:18px;line-height:1.5;font-weight:400;'
        f'color:#FFFFFF;">La página de precios de Alegra muestra los planes vigentes, '
        f'con el descuento anual incluido.</p>'
        f'<a href="{url}" style="display:inline-block;background:#FFFFFF;color:{NAVY};'
        f'font-weight:700;font-size:15px;padding:12px 22px;border-radius:8px;'
        f'text-decoration:none;">Ver planes publicados</a></div>'
    )
    # entra antes del veredicto, donde el lector ya tiene criterio para decidir
    indice = html.find("<h2")
    veredicto = html.find("Veredicto:")
    if veredicto == -1:
        return html + bloque, True
    inicio = html.rfind("<h2", 0, veredicto if veredicto > 0 else indice)
    return html[:inicio] + bloque + html[inicio:], True


def firma(html: str) -> tuple[str, bool]:
    """El post se firma con Leandro y su descripción, como el resto del blog."""
    if 'class="pc-firma"' in html:
        return html, False
    bloque = (
        f'<div class="pc-firma" style="border-top:1px solid {LINEA};margin-top:40px;'
        f'padding-top:22px;display:flex;gap:16px;align-items:flex-start;">'
        f'<div style="width:52px;height:52px;border-radius:50%;background:{CELESTE_SUAVE};'
        f'border:1px solid {LINEA};display:flex;align-items:center;justify-content:center;'
        f'font-weight:700;color:{NAVY};font-size:18px;">L</div>'
        f'<div><p style="margin:0 0 4px;font-size:16px;font-weight:700;color:{NAVY};">Leandro</p>'
        f'<p style="margin:0;font-size:14px;line-height:1.6;color:{TINTA};max-width:62ch;">'
        f'Analista de software contable en programascontabilidad.com. Trabaja con datos '
        f'publicados por cada proveedor y con la normativa de cada país; cuando un dato no '
        f'está publicado, lo dice en lugar de estimarlo.</p></div></div>'
    )
    return html + bloque, True


def reemplazar_veredicto_adelantado(html: str) -> tuple[str, bool]:
    """El artículo abría con un veredicto. Se cambia por lo que el lector necesita saber."""
    inicio = html.find("La opción más conveniente para la mayoría de restaurantes")
    if inicio == -1:
        return html, False
    fin = html.find("</p>", inicio)
    if fin == -1:
        return html, False
    fin += 4
    nuevo = (
        '<p style="margin:0 0 14px;">Antes de comparar precios conviene saber qué le pide un '
        "restaurante a su software. Estas son las tres cosas que no pueden fallar:</p>"
        f'<ul style="margin:0 0 6px;padding-left:22px;list-style:disc outside;color:{TINTA};">'
        '<li style="margin:0 0 8px;list-style:disc outside;margin-left:16px;">Facturar ante la '
        "DIAN con validación en línea, incluido el documento equivalente de los tiquetes del "
        "POS.</li>"
        '<li style="margin:0 0 8px;list-style:disc outside;margin-left:16px;">Costear cada plato '
        "con compras, mermas y recetas, no solo con el total del día.</li>"
        '<li style="margin:0 0 8px;list-style:disc outside;margin-left:16px;">Cuadrar la nómina '
        "y el cierre contable sin repetir la información en dos sistemas.</li></ul>"
    )
    return html[:inicio] + nuevo + html[fin:], True


def etiquetas_por_nombre(nombres: list[str]) -> list[int]:
    ids: list[int] = []
    for nombre in nombres:
        nombre = nombre.strip()
        if not nombre:
            continue
        codigo, datos = http("POST", "/wp-json/wp/v2/tags", {"name": nombre})
        if codigo in (200, 201):
            ids.append(int(datos["id"]))
            continue
        codigo, datos = http("GET", f"/wp-json/wp/v2/tags?search={urllib.parse.quote(nombre)}")
        if codigo == 200 and datos:
            ids.append(int(datos[0]["id"]))
    return ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", type=int, required=True)
    parser.add_argument("--categoria", type=int, default=0)
    parser.add_argument("--subcategoria", type=int, default=0)
    parser.add_argument("--etiquetas", default="")
    parser.add_argument("--titulo-seo", default="")
    parser.add_argument("--meta", default="")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--solo-html", action="store_true")
    args = parser.parse_args()

    codigo, post = http("GET", f"/wp-json/wp/v2/posts/{args.post}?context=edit")
    if codigo != 200:
        print("no se pudo leer el post:", codigo)
        return 2
    html = (post.get("content") or {}).get("raw", "")

    reales = urls_reales()
    html, rotos = arreglar_enlaces(html, reales)
    html, utms = arreglar_utm(html)
    html = viñetas_visibles(html)
    html, plantilla = quitar_promesa_de_plantilla(html)
    html, tablas = tabla_con_estilo(html)
    html, veredicto = reemplazar_veredicto_adelantado(html)
    base = env("wp-prod.env").get("PDC_PROD_URL", "https://programascontabilidad.com")
    destino_cta = (
        "https://www.alegra.com/colombia/precios/"
        "?utm_source=programascontabilidad&utm_medium=blog"
        "&utm_campaign=comparativa-restaurantes-co"
    )
    html, cta = cta_sutil(html, destino_cta)
    html, firmado = firma(html)

    print("enlaces corregidos:", len(rotos))
    for r in rotos:
        print("   ", r)
    print("enlaces con UTM completados:", utms)
    print("tablas con estilo:", tablas)
    print("promesa de plantilla retirada:", plantilla)
    print("veredicto adelantado reemplazado:", veredicto)
    print("CTA insertado:", cta, "· firma insertada:", firmado)

    if args.solo_html:
        Path("state/reparado.html").write_text(html, encoding="utf-8")
        print("html guardado en state/reparado.html")
        return 0

    ids = []
    if args.categoria:
        ids.append(args.categoria)
    if args.subcategoria:
        ids.append(args.subcategoria)

    actualizacion: dict = {"content": html}
    if ids:
        actualizacion["categories"] = ids
    if args.etiquetas:
        etiquetas = etiquetas_por_nombre(args.etiquetas.split(","))
        if etiquetas:
            actualizacion["tags"] = etiquetas
    metadatos = {}
    if args.titulo_seo:
        metadatos["rank_math_title"] = args.titulo_seo
    if args.meta:
        metadatos["rank_math_description"] = args.meta
    if args.keyword:
        metadatos["rank_math_focus_keyword"] = args.keyword
    if metadatos:
        actualizacion["meta"] = metadatos

    codigo, respuesta = http("POST", f"/wp-json/wp/v2/posts/{args.post}", actualizacion)
    print("actualización:", codigo)
    if codigo not in (200, 201):
        print(json.dumps(respuesta, ensure_ascii=False)[:400])
        if metadatos:
            actualizacion.pop("meta", None)
            codigo, respuesta = http("POST", f"/wp-json/wp/v2/posts/{args.post}", actualizacion)
            print("sin meta (Rank Math no expone esas claves por REST):", codigo)
            print("las claves intentadas fueron:", ", ".join(metadatos))
    print("categorías:", respuesta.get("categories"), "· etiquetas:", respuesta.get("tags"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
