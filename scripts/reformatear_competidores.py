"""Convierte el análisis de competidores a componentes del kit, con criterio de restaurante.

El bloque de análisis llegó en markdown dentro del HTML: encabezados con `###`, tablas de barras
y listas con guiones. De ahí que se leyera como un párrafo pegado. Esto lo convierte a HTML
semántico, envuelve cada plataforma en una tarjeta y sustituye la tabla de todos los planes por
una de criterios que sí importan para un restaurante.
"""

from __future__ import annotations

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

from orchestrator.linea_visual import AZUL, CELESTE_SUAVE, GRIS, LINEA, NAVY, TINTA  # noqa: E402

CRITERIOS = (
    ("Facturación electrónica DIAN", ("facturación electrónica", "facturacion electronica")),
    ("Punto de venta (POS)", ("pos", "punto de venta")),
    ("Inventario y costos", ("inventario", "kardex", "costos")),
    ("Nómina electrónica", ("nómina", "nomina")),
    ("Automatización con IA", ("ia", "inteligencia artificial")),
)


def _credenciales() -> tuple[str, str, str]:
    valores: dict[str, str] = {}
    for linea in (Path.home() / ".pdc" / "wp-prod.env").read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.strip().startswith("#"):
            clave, _, valor = linea.partition("=")
            valores.setdefault(clave.strip(), valor.strip())
    return valores["PDC_PROD_URL"], valores["PDC_PROD_TOKEN"], valores["PDC_PROD_USER"]


def http(metodo: str, ruta: str, cuerpo: dict | None = None) -> tuple[int, dict]:
    import base64

    base, token, usuario = _credenciales()
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
        with urllib.request.urlopen(peticion, timeout=90) as respuesta:
            return respuesta.status, json.loads(respuesta.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "{}")


def fichas() -> dict[str, dict]:
    datos = {}
    for archivo in sorted((RAIZ / "datos" / "herramientas").glob("*-co.json")):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        datos[ficha["brand"]] = ficha
    return datos


def markdown_a_html(texto: str) -> str:
    """Markdown suelto → HTML. Sin dependencias: solo lo que el modelo produce."""
    lineas = texto.splitlines()
    salida: list[str] = []
    en_lista = False
    filas: list[str] = []

    def cerrar_lista() -> None:
        nonlocal en_lista
        if en_lista:
            salida.append("</ul>")
            en_lista = False

    def cerrar_tabla() -> None:
        nonlocal filas
        if not filas:
            return
        cabecera = [c.strip() for c in filas[0].strip("|").split("|")]
        cuerpo = [
            [c.strip() for c in fila.strip("|").split("|")]
            for fila in filas[2:]
            if fila.strip("|").strip()
        ]
        salida.append(
            f'<div class="pc-tabla" style="overflow-x:auto;margin:24px 0;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:15px;background:#FFFFFF;'
            f'border:1px solid {LINEA};border-radius:10px;">'
        )
        salida.append("<thead><tr>")
        for celda in cabecera:
            salida.append(
                f'<th style="background:{NAVY};color:#FFFFFF;text-align:left;padding:11px 14px;'
                f'font-size:13px;letter-spacing:.04em;text-transform:uppercase;">{celda}</th>'
            )
        salida.append("</tr></thead><tbody>")
        for fila in cuerpo:
            salida.append("<tr>")
            for i, celda in enumerate(fila):
                etiqueta = "th" if i == 0 else "td"
                estilo = (
                    f'background:{CELESTE_SUAVE};font-weight:700;' if etiqueta == "th" else ""
                )
                salida.append(
                    f'<{etiqueta} style="{estilo}padding:11px 14px;border-bottom:1px solid {LINEA};'
                    f'color:{TINTA};vertical-align:top;">{celda}</{etiqueta}>'
                )
            salida.append("</tr>")
        salida.append("</tbody></table></div>")
        filas = []

    for linea in lineas:
        limpia = linea.rstrip()
        if limpia.startswith("|"):
            cerrar_lista()
            filas.append(limpia)
            continue
        cerrar_tabla()
        if not limpia.strip():
            cerrar_lista()
            continue
        if limpia.startswith("###"):
            cerrar_lista()
            salida.append(f"<h3>{limpia.lstrip('#').strip()}</h3>")
            continue
        if re.match(r"^[-*]\s+", limpia):
            if not en_lista:
                salida.append(
                    f'<ul style="margin:0 0 14px;padding-left:22px;list-style:disc outside;'
                    f'color:{TINTA};">'
                )
                en_lista = True
            salida.append(
                f'<li style="margin:0 0 8px;list-style:disc outside;margin-left:16px;">'
                f"{limpia[2:].strip()}</li>"
            )
            continue
        cerrar_lista()
        salida.append(f'<p style="margin:0 0 14px;line-height:1.7;color:{TINTA};">{limpia.strip()}</p>')

    cerrar_lista()
    cerrar_tabla()
    html = "\n".join(salida)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"__(.+?)__", r"<strong>\1</strong>", html)
    return html


def tabla_de_criterios(datos: dict[str, dict], orden: list[str]) -> str:
    """Una tabla útil para restaurantes: qué cubre cada plataforma, no todos sus planes."""
    filas = []
    for etiqueta, claves in CRITERIOS:
        celdas = []
        for marca in orden:
            ficha = datos.get(marca, {})
            texto = " ".join(
                str(v) for k, v in ficha.items() if k in ("features", "electronic_invoicing", "notes")
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
        f'font-size:13px;letter-spacing:.03em;">{marca}</th>'
        for marca in orden
    )
    return (
        '<div class="pc-tabla" style="overflow-x:auto;margin:26px 0;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:15px;background:#FFFFFF;'
        f'border:1px solid {LINEA};border-radius:10px;">'
        f'<thead><tr><th style="background:{NAVY};color:#FFFFFF;text-align:left;padding:12px 14px;'
        f'font-size:13px;letter-spacing:.03em;">Lo que necesita un restaurante</th>{cabecera}'
        "</tr></thead><tbody>" + "".join(filas) + "</tbody></table>"
        f'<p style="margin:10px 0 0;font-size:13px;color:{GRIS};">Funciones tal como las publica '
        "cada proveedor en su sitio, consultadas el 11 de noviembre de 2026. «No publicado» "
        "significa que la página revisada no lo menciona.</p></div>"
    )


def tarjeta(marca: str, cuerpo_html: str, ficha: dict) -> str:
    """Cada plataforma en su tarjeta: el texto deja de ser un párrafo pegado."""
    plan = ""
    precios = [p for p in (ficha.get("plans") or []) if p.get("publicado", True)]
    mensuales = [p for p in precios if str(p.get("billing", "")).lower() == "mensual"] or precios
    if mensuales:
        primero = min(
            mensuales, key=lambda p: float(str(p.get("price") or "0").replace(".", "") or 0)
        )
        if primero.get("price"):
            plan = f"{primero['name']} · {primero['price']} {primero.get('currency','COP')}/{primero.get('period','mes')}"
    etiqueta = (
        f'<p style="margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{AZUL};">{plan or "Precio no publicado"}</p>'
    )
    cuerpo = re.sub(r"^\s*<h3>.*?</h3>", "", cuerpo_html, count=1, flags=re.DOTALL)
    cuerpo = re.sub(r"^\s*#{1,6}\s*[^<]*", "", cuerpo)
    cuerpo = re.sub(r"\s*#{1,6}\s*", " ", cuerpo)
    return (
        f'<div class="pc-card" style="border:1px solid {LINEA};border-radius:12px;background:#FFFFFF;'
        f'padding:20px 22px;margin:22px 0;">'
        f'<h3 style="margin:0 0 4px;font-size:20px;color:{NAVY};">{marca}</h3>{etiqueta}{cuerpo}</div>'
    )


def main() -> int:
    post_id = int(sys.argv[1]) if len(sys.argv) > 1 else 5309
    codigo, post = http("GET", f"/wp-json/wp/v2/posts/{post_id}?context=edit")
    if codigo != 200:
        print("no se pudo leer el post:", codigo)
        return 2
    html = (post.get("content") or {}).get("raw", "")

    # 1) Solo la zona de competidores: entre el primer <h3> y el siguiente <h2>.
    inicio = html.find("<h3")
    fin = html.find("<h2", inicio) if inicio != -1 else -1
    antes_md = 0
    if inicio != -1 and fin != -1:
        zona = html[inicio:fin]
        antes_md = len(re.findall(r"^###|^\|", zona, re.MULTILINE))
        html = html[:inicio] + markdown_a_html(zona) + html[fin:]
    print("líneas de markdown convertidas:", antes_md)

    # 2) cada plataforma, en su tarjeta
    datos = fichas()
    orden = [m for m in datos if m in html]
    trozos = re.split(r"(?=<h3)", html)
    reconstruido = []
    for trozo in trozos:
        encontrado = re.match(r"\s*<h3>(.*?)</h3>", trozo, re.DOTALL)
        if encontrado:
            nombre = re.sub(r"<[^>]+>", "", encontrado.group(1)).strip()
            for marca, ficha in datos.items():
                if marca.lower() in nombre.lower() and "World Office" not in nombre:
                    trozo = tarjeta(marca, trozo, ficha)
                    break
                if marca.lower() == nombre.lower():
                    trozo = tarjeta(marca, trozo, ficha)
                    break
        reconstruido.append(trozo)
    html = "".join(reconstruido)

    # 3) fuera las tablas de todos los planes; entra la de criterios
    html = re.sub(
        r'<div class="pc-tabla"[^>]*>\s*<table[^>]*>(?:(?!</table>).)*?Precio mensualidad.*?</table>\s*</div>',
        "",
        html,
        flags=re.DOTALL,
    )
    def _quitar_tablas_de_planes(html: str) -> str:
        def borrar(m: re.Match[str]) -> str:
            trozo = m.group(0)
            return "" if "pc-criterios" not in trozo and "precio" in trozo.lower() else trozo

        return re.sub(r'<div class="pc-tabla".*?</div>', borrar, html, flags=re.DOTALL)

    html = _quitar_tablas_de_planes(html)

    if "pc-criterios" not in html:
        ancla = html.find("<h2")
        bloque = f'<div class="pc-criterios">{tabla_de_criterios(datos, orden)}</div>'
        html = html[:ancla] + bloque + html[ancla:]

    if "--dry" in sys.argv:
        Path("state/reformado.html").write_text(html, encoding="utf-8")
        print("ensayo: state/reformado.html · tarjetas:", html.count("pc-card"))
        return 0

    codigo, respuesta = http("POST", f"/wp-json/wp/v2/posts/{post_id}", {"content": html})
    print("actualización:", codigo, "· caracteres:", len(html))
    print("tarjetas:", html.count("pc-card"), "· tabla de criterios:", "pc-criterios" in html)
    return 0 if codigo == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
