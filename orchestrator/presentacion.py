"""Presentación final de una pieza: tarjetas, tabla de criterios, panel y firma.

Los arreglos que se hacían a mano sobre el post publicado se aplican aquí, en la producción, para
que la pieza nazca bien. Todo es determinista y repetible: si algo ya está hecho, no se duplica.

Las reglas que implementa están en la skill `pdc-publicacion-articulos`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .linea_visual import (
    AZUL,
    CELESTE_SUAVE,
    GRIS,
    LINEA,
    NAVY,
    TINTA,
    AVATAR_LEANDRO as AVATAR_DE_LEANDRO,
    firma as firma_del_portal,
    normalizar_listas,
)

UTM_PRINCIPAL = "?utm_source=programascontabilidad&utm_medium=blog&utm_campaign=comparativa"
CRITERIOS = (
    ("Facturación electrónica", ("facturación electrónica", "facturacion electronica")),
    ("Punto de venta (POS)", ("pos", "punto de venta")),
    ("Inventario y costos", ("inventario", "kardex", "costos")),
    ("Nómina electrónica", ("nómina", "nomina")),
    ("Automatización con IA", ("ia", "inteligencia artificial")),
)
FUENTES = Path("datos") / "herramientas"


def _fichas(pais: str) -> dict[str, dict]:
    datos: dict[str, dict] = {}
    for archivo in sorted(FUENTES.glob(f"*-{pais.lower()}.json")):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        datos[ficha["brand"]] = ficha
    return datos


def precio_numero(valor: object) -> float:
    """El número de un precio publicado, con la coma o el punto que use el país.

    México escribe «$1,299» (coma de miles, punto decimal) y Colombia «$108.990» (punto de
    miles). Sin esto, `float("1,299")` revienta y la pieza no se presenta.
    """
    limpio = re.sub(r"[^\d.,]", "", str(valor or ""))
    if not limpio:
        return 0.0
    if "," in limpio and "." in limpio:
        # el último separador que aparece es el decimal
        decimal = "," if limpio.rfind(",") > limpio.rfind(".") else "."
        miles = "." if decimal == "," else ","
        limpio = limpio.replace(miles, "").replace(decimal, ".")
    elif "," in limpio:
        partes = limpio.split(",")
        # «1,299» son miles; «1,29» es decimal
        limpio = limpio.replace(",", "") if len(partes[-1]) == 3 else limpio.replace(",", ".")
    elif "." in limpio:
        partes = limpio.split(".")
        # «108.990» son miles (grupos de tres); «974.25» es decimal
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            limpio = "".join(partes)
    try:
        return float(limpio)
    except ValueError:
        return 0.0


def _plan_publicado(ficha: dict) -> str:
    precios = [p for p in (ficha.get("plans") or []) if p.get("publicado", True)]
    mensuales = [p for p in precios if str(p.get("billing", "")).lower() == "mensual"] or precios
    if not mensuales:
        return "Precio no publicado"
    elegido = min(mensuales, key=lambda p: precio_numero(p.get("price")))
    if not elegido.get("price"):
        return "Precio no publicado"
    return (
        f"{elegido['name']} · {elegido['price']} {elegido.get('currency', 'COP')}"
        f"/{elegido.get('period', 'mes')} · publicado"
    )


def tarjeta_marca(ficha: dict, cuerpo: str) -> str:
    fuente = ficha.get("source_url", "")
    # Sin fecha de consulta: el vigía mantiene el precio al día y la fecha envejece la pieza.
    pie = (
        f'<p style="margin:14px 0 0;font-size:13px;color:{GRIS};">Fuente del precio: '
        f'<a href="{fuente}" style="color:#0B6FA4;text-decoration:underline;">'
        f'{fuente.replace("https://", "").rstrip("/")}</a></p>'
        if fuente
        else ""
    )
    return (
        f'<div class="pc-card" style="border:1px solid {LINEA};border-radius:12px;background:#FFFFFF;'
        f'padding:22px 24px;margin:22px 0;">'
        f'<p style="margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{AZUL};">{_plan_publicado(ficha)}</p>'
        f'<h3 style="margin:0 0 12px;font-size:21px;color:{NAVY};">{ficha["brand"]}</h3>'
        f"{cuerpo}{pie}</div>"
    )


def tabla_de_criterios(datos: dict[str, dict], orden: list[str]) -> str:
    filas = []
    for etiqueta, claves in CRITERIOS:
        celdas = []
        for marca in orden:
            ficha = datos.get(marca, {})
            texto = " ".join(
                str(v)
                for k, v in ficha.items()
                if k in ("features", "electronic_invoicing", "notes")
            ).lower()
            cubre = any(clave in texto for clave in claves)
            celdas.append(
                f'<td style="padding:11px 14px;border-bottom:1px solid {LINEA};text-align:center;'
                f'color:{AZUL if cubre else GRIS};font-weight:{700 if cubre else 400};">'
                f'{"Sí" if cubre else "No publicado"}</td>'
            )
        filas.append(
            f'<tr><th style="background:{CELESTE_SUAVE};font-weight:700;text-align:left;'
            f'padding:11px 14px;border-bottom:1px solid {LINEA};color:{TINTA};">{etiqueta}</th>'
            + "".join(celdas)
            + "</tr>"
        )
    cabecera = "".join(
        f'<th style="background:{NAVY};color:#FFFFFF;text-align:center;padding:12px 14px;'
        f'font-size:13px;">{marca}</th>'
        for marca in orden
    )
    return (
        '<div class="pc-criterios" style="overflow-x:auto;margin:26px 0;">'
        f'<table data-pdc="componente" style="width:100%;border-collapse:collapse;font-size:15px;background:#FFFFFF;'
        f'border:1px solid {LINEA};border-radius:10px;">'
        f'<thead><tr><th style="background:{NAVY};color:#FFFFFF;text-align:left;padding:12px 14px;'
        f'font-size:13px;">Lo que necesita el negocio</th>{cabecera}</tr></thead><tbody>'
        + "".join(filas)
        + "</tbody></table>"
        f'<p style="margin:10px 0 0;font-size:13px;color:{GRIS};">Funciones tal como las publica '
        "cada proveedor. «No publicado» significa que su página no lo menciona.</p></div>"
    )


def panel_de_perfiles(bloques: list[tuple[str, str]]) -> str:
    fondos = ((NAVY, "#FFFFFF", "#A8BFD4"), ("#FFFFFF", NAVY, "#EAF0F5"), (AZUL, NAVY, "#D9EEFC"))
    tarjetas = []
    for i, (titulo, cuerpo) in enumerate(bloques[:3]):
        fondo, tinta, sello = fondos[i]
        borde = f"border:1px solid {LINEA};" if fondo == "#FFFFFF" else ""
        texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cuerpo)).strip()[:420]
        tarjetas.append(
            f'<div style="flex:1 1 240px;min-width:220px;background:{fondo};color:{tinta};'
            f'border-radius:12px;padding:24px;box-sizing:border-box;{borde}">'
            f'<span style="display:inline-block;font-size:13px;font-weight:700;margin-bottom:14px;'
            f'padding:6px 11px;border-radius:5px;background:{sello};color:{tinta};">0{i + 1}</span>'
            f'<h4 style="margin:0 0 12px;font-size:18px;line-height:1.35;color:{tinta};">{titulo}</h4>'
            f'<p style="margin:0;font-size:14px;line-height:1.65;color:{tinta};">{texto}</p></div>'
        )
    return (
        '<div class="pc-perfiles" style="margin:26px 0;">'
        '<div style="display:flex;gap:16px;flex-wrap:wrap;">' + "".join(tarjetas) + "</div></div>"
    )


def cta(url: str) -> str:
    return (
        f'<div class="pc-cta" style="background:{NAVY};border-radius:12px;padding:28px 26px;'
        f'margin:34px 0;">'
        f'<p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:#A8BFD4;">Si quieres comparar por tu cuenta</p>'
        f'<p style="margin:0 0 16px;font-size:18px;line-height:1.5;color:#FFFFFF;">La página de '
        f"precios muestra los planes vigentes, con el descuento anual incluido.</p>"
        f'<a href="{url}" style="display:inline-block;background:#FFFFFF;color:{NAVY};'
        f'font-weight:700;font-size:15px;padding:12px 22px;border-radius:8px;'
        f'text-decoration:none;">Ver planes publicados</a></div>'
    )


def firma() -> str:
    """La firma del portal, con la foto de Leandro.

    Aquí vivía una firma propia —un círculo de 52 px con la inicial «L»— que salía cuando el
    cuerpo no traía `pc-firma`. La ficha del autor es una sola en todo el portal y está en
    `linea_visual`, con la foto y el enlace al archivo de autor.
    """
    return firma_del_portal()


def _envolver_marcas(html: str, datos: dict[str, dict]) -> str:
    """Cada h3 de marca, con su cuerpo, dentro de una tarjeta cerrada en su propia sección."""
    if 'class="pc-card"' in html:
        return html
    inicio = html.find("<h3")
    fin = html.find("<h2", inicio) if inicio != -1 else -1
    if inicio == -1 or fin == -1:
        return html
    zona, piezas = html[inicio:fin], []
    for trozo in re.split(r"(?=<h3)", zona):
        encontrado = re.match(r"\s*<h3[^>]*>(.*?)</h3>", trozo, re.DOTALL)
        if not encontrado:
            continue
        titulo = re.sub(r"<[^>]+>", "", encontrado.group(1)).strip()
        ficha = next((f for m, f in datos.items() if m.lower() == titulo.lower()), None)
        if ficha:
            cuerpo = re.sub(r"^\s*#{1,6}\s*[^<\n]*", "", trozo[encontrado.end() :]).strip()
            piezas.append(tarjeta_marca(ficha, cuerpo))
    if not piezas:
        return html
    orden = [f["brand"] for f in datos.values() if f["brand"] in zona]
    return html[:inicio] + "".join(piezas) + tabla_de_criterios(datos, orden) + html[fin:]


def _panel_veredicto(html: str) -> str:
    encontrado = re.search(r"<h2[^>]*>\s*Veredicto", html, re.IGNORECASE)
    if not encontrado or "pc-perfiles" in html:
        return html
    inicio = encontrado.start()
    fin = html.find("<h2", inicio + 5)
    fin = len(html) if fin == -1 else fin
    seccion = html[inicio:fin]
    bloques = []
    for trozo in re.split(r"(?=<h3)", seccion):
        cabecera = re.match(r"\s*<h3[^>]*>(.*?)</h3>", trozo, re.DOTALL)
        if cabecera:
            bloques.append((re.sub(r"<[^>]+>", "", cabecera.group(1)).strip(), trozo[cabecera.end() :]))
    if len(bloques) < 2:
        return html
    titulo = re.match(r"<h2[^>]*>.*?</h2>", seccion, re.DOTALL)
    return html[:inicio] + (titulo.group(0) if titulo else "") + panel_de_perfiles(bloques) + html[fin:]


def viñetas(html: str) -> str:
    html = html.replace(
        'style="margin:16px 0 0;padding-left:38px;"',
        'style="margin:16px 0 0;padding-left:22px;list-style:disc outside;"',
    )
    return html.replace(
        'style="margin:0 0 8px;font-size:16px;line-height:1.6;font-weight:400;color:#1F2937;"',
        'style="margin:0 0 8px;font-size:16px;line-height:1.6;color:#1F2937;list-style:disc outside;'
        'margin-left:16px;"',
    )


def utm(html: str, pais: str = "CO") -> str:
    """La UTM de la pieza lleva la campaña de su país: `col_`, `mex_`, `cri_`, `dom_`."""
    from .reglas_editoriales import campana as _campana

    def poner(m: re.Match[str]) -> str:
        url = m.group(1).replace("&amp;", "&")
        if "utm_source=" in url:
            return 'href="' + url + '"'
        consulta = (
            "?utm_source=programascontabilidad&utm_medium=blog"
            f"&utm_campaign={_campana(pais)}_articulo_tmd_content"
        )
        return 'href="' + url + ("&" if "?" in url else "?") + consulta[1:] + '"'

    return re.sub(r'href="(https://www\.alegra\.com[^"]*)"', poner, html)


def tablas_con_fondo(html: str, color: str = "#cce4f7") -> str:
    """Toda tabla lleva el fondo del portal. Antes se ponía a mano en cada pieza y se olvidaba.

    La clase `has-background` es la que el tema respeta; el color va también en el atributo
    `style` para que se vea igual aunque el editor reescriba las clases.
    """

    def arreglar(etiqueta: str) -> str:
        if "has-background" in etiqueta:
            return etiqueta
        clases = re.search(r'class="([^"]*)"', etiqueta)
        if clases:
            nueva = (clases.group(1) + " has-background has-fixed-layout").strip()
            etiqueta = etiqueta.replace(clases.group(0), f'class="{nueva}"', 1)
        else:
            etiqueta = etiqueta.replace("<table", '<table class="has-background has-fixed-layout"', 1)
        if "style=" not in etiqueta:
            etiqueta = etiqueta[:-1] + f' style="background-color:{color}">'
        return etiqueta

    return re.sub(r"<table[^>]*>", lambda m: arreglar(m.group(0)), html)


def presentar(
    html: str,
    *,
    pais: str,
    url_cta: str = "",
    keyword: str = "",
) -> str:
    """Aplica la presentación completa a una pieza recién escrita."""
    from .reglas_editoriales import MAX_ENLACES_ALEGRA, corregir as corregir_forma, marcas

    # Forma primero: el <h1> que duplica el título, las secciones repetidas y los enlaces a la
    # versión de Alegra de otro país (una pieza de México enlazaba a /colombia/precios).
    html, _tocados = corregir_forma(html, pais=pais)
    datos = _fichas(pais)
    html = viñetas(html)
    if datos:
        html = _envolver_marcas(html, datos)
    html = _panel_veredicto(html)
    html = utm(html, pais)
    if "pc-cta" not in html:
        from .reglas_editoriales import MAX_ENLACES_ALEGRA, recortar_alegra, ruta_principal

        # El CTA final es el único enlace a Alegra del cuerpo: lo que quede antes se desenlaza.
        html = recortar_alegra(html, MAX_ENLACES_ALEGRA - 1)
        destino = url_cta or f"https://www.alegra.com{ruta_principal(pais)}precios/"
        if "utm_source=" not in destino:
            from .reglas_editoriales import campana as _campana

            destino += (
                "?utm_source=programascontabilidad&utm_medium=blog"
                f"&utm_campaign={_campana(pais)}_articulo_tmd_content"
            )
        indice = html.find("<h2", html.find("Veredicto"))
        html = (html[:indice] + cta(destino) + html[indice:]) if indice != -1 else html + cta(destino)
    if "pc-firma" not in html and AVATAR_DE_LEANDRO not in html:
        html += firma()
    elif AVATAR_DE_LEANDRO not in html:
        # Una firma sin la foto no es la del portal: se cambia por la canónica, una sola vez.
        html = re.sub(r'<div class="pc-firma".*?</div>\s*</div>', "", html, flags=re.S)
        html += firma()
    # El video del canal entra solo si el tema coincide y es del mismo mercado (regla B49).
    from . import youtube

    html, _video = youtube.anadir(html, pais, keyword=keyword, marcas=sorted(marcas(html, pais)))
    html = tablas_con_fondo(html)
    html = normalizar_listas(html)
    return html
