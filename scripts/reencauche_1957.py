"""Reencauche del post 1957: facturación Siigo frente a Alegra (Colombia).

La pieza la escribió el agente el 13-nov-2026 y salió publicada con cinco tablas, dos de ellas
sostenidas en cifras que el registro no tiene (Siigo Nube 1.751.920, POS GastroBar 1.049.930,
Nómina PRO 1.402.425, y un cuadro de «casos reales» con porcentajes calculados). Este reencauche
la deja dentro del presupuesto del formato:

1. **Cinco tablas → tres.** Se van la de «precios por línea» y la de «casos reales»: la primera
   repite lo que ya dice la tabla de planes y la segunda fabrica comparaciones.
2. **Tabla de Alegra con las tres líneas** (facturación, POS, contabilidad), no una sola columna
   por plan con precios que no son del mismo producto.
3. **Pie de fuente y fecha en las tres tablas** (la línea visual lo exige).
4. **Fuera el «ahorra el 46 %»**: afirmación de mejora sin respaldo en el registro.
5. **FAQ en `<details>`**, que abre sin JavaScript.
6. **SEO**: H1, primera frase y meta con la keyword foco; título SEO a 60 caracteres.
7. **Un enlace interno más** (de 4 a 5).

Uso:
    python scripts/reencauche_1957.py --respaldo state/respaldos/post-1957-....json
    python scripts/reencauche_1957.py --respaldo ... --aplicar
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.respaldar_post import (  # noqa: E402
    cargar_entorno,
    endpoint,
    leer_post,
    leer_seo,
)
from scripts.reencauche_5309 import _bloque_heading, _details, _inicio_bloque  # noqa: E402
from orchestrator.mcp_client import cliente_desde_entorno, _desenvolver  # noqa: E402

POST_ID = 1957
FECHA = "13 de noviembre de 2026"

KEYWORD = "Facturación siigo"
H1 = "Facturación Siigo 2026: precios, funciones y comparativa con Alegra"
TITULO_SEO = "Facturación Siigo vs Alegra: planes y precios 2026"
META = (
    "Facturación Siigo y Alegra comparadas con precios publicados en 2026: planes por línea, "
    "cupos de documentos, inteligencia artificial y cuándo conviene cada una."
)

SECCIONES_FUERA = (
    "Planes Siigo 2026: precios por línea",
    "Cuánto cuesta cada uno en casos reales",
)

TABLA_ALEGRA = (
    "<thead><tr><th>Producto</th><th>Plan</th><th>Mensual</th>"
    "<th>Equivalente con pago anual</th></tr></thead><tbody>"
    "<tr><td>Facturación electrónica</td><td>Emprendedor</td><td>$17.900 COP</td>"
    "<td>$13.425 COP</td></tr>"
    "<tr><td>Facturación electrónica</td><td>Pyme</td><td>$49.900 COP</td>"
    "<td>$37.425 COP</td></tr>"
    "<tr><td>Facturación electrónica</td><td>Pro</td><td>$99.900 COP</td>"
    "<td>$74.925 COP</td></tr>"
    "<tr><td>Facturación electrónica</td><td>Plus</td><td>$179.900 COP</td>"
    "<td>$134.925 COP</td></tr>"
    "<tr><td>POS</td><td>Emprendedor</td><td>$25.900 COP</td><td>$19.425 COP</td></tr>"
    "<tr><td>POS</td><td>Pyme</td><td>$79.900 COP</td><td>$59.925 COP</td></tr>"
    "<tr><td>Contabilidad</td><td>Emprendedor</td><td>$74.900 COP</td>"
    "<td>$56.175 COP</td></tr>"
    "<tr><td>Contabilidad</td><td>Pyme</td><td>$163.900 COP</td>"
    "<td>$122.925 COP</td></tr>"
    "</tbody>"
)

PIES = (
    f"Precios de lista de Siigo leídos en siigo.com/precios-siigo el {FECHA}.",
    f"Tarifas de Alegra leídas en alegra.com/colombia/precios el {FECHA}.",
    f"Comparación construida con las páginas oficiales de Siigo y Alegra, consultadas el {FECHA}.",
)

ENLACES_NUEVOS = (
    "https://programascontabilidad.com/comparativas-de-software/siigo-contabilidad/",
    "https://programascontabilidad.com/analisis-de-herramientas/mejor-software-de-facturacion-electronica-colombia/",
)


def _fin_bloque(h: str, inicio: int) -> int:
    """Fin del bloque de heading que empieza en `inicio`."""
    cierre = h.find("<!-- /wp:heading -->", inicio)
    if cierre < 0:
        raise SystemExit("bloque de heading sin cierre")
    return cierre + len("<!-- /wp:heading -->")


def quitar_secciones(h: str) -> tuple[str, str]:
    quitadas = []
    for titulo in SECCIONES_FUERA:
        if titulo not in h:
            continue
        ini = _inicio_bloque(h, titulo)
        fin_heading = _fin_bloque(h, ini)
        # El siguiente H2 se busca desde el final del heading actual.
        candidatos = [m.start() for m in re.finditer(r"<!-- wp:heading", h[fin_heading:])]
        if not candidatos:
            raise SystemExit(f"no hay bloque siguiente tras «{titulo}»")
        fin = fin_heading + candidatos[0]
        h = h[:ini] + h[fin:]
        quitadas.append(titulo)
    return h, "quitadas: " + " · ".join(quitadas) if quitadas else "ya estaba"


def quitar_porcentaje(h: str) -> tuple[str, str]:
    frase = "Alegra reporta que la lectura automática ahorra el 46 % del tiempo de creación de facturas frente al registro manual."
    if frase not in h:
        return h, "ya estaba"
    return h.replace(" " + frase, "", 1), "retirada la afirmación del 46 %"


def tabla_alegra(h: str) -> tuple[str, str]:
    if ">Producto</th>" in h and "Equivalente con pago anual" in h:
        return h, "ya estaba"
    patron = re.compile(r"<table[^>]*>(?:(?!</table>).)*?Emprendedor(?:(?!</table>).)*?</table>", re.S)
    encontrado = patron.search(h)
    if not encontrado:
        raise SystemExit("no se encontró la tabla de planes de Alegra")
    nueva = (
        '<table class="has-background has-fixed-layout" style="background-color:#cce4f7">'
        + TABLA_ALEGRA
        + "</table>"
    )
    return h[: encontrado.start()] + nueva + h[encontrado.end() :], "tabla de Alegra con las tres líneas"


def pies_de_tabla(h: str) -> tuple[str, str]:
    tablas = list(re.finditer(r"<table[^>]*>", h))
    if not tablas:
        raise SystemExit("no hay tablas")
    salida, ultimo, puestos = [], 0, 0
    for i, m in enumerate(tablas):
        salida.append(h[ultimo : m.end()])
        trozo = h[m.end() : h.find("</table>", m.end())]
        if "<caption" in trozo.lower():
            salida.append("")
        else:
            pie = PIES[i] if i < len(PIES) else PIES[-1]
            salida.append(
                '<caption style="caption-side:bottom;text-align:left;padding:10px 16px;'
                'font-size:13px;line-height:1.5;font-weight:400;color:#4B5563;">'
                + pie
                + "</caption>"
            )
            puestos += 1
        ultimo = m.end()
    salida.append(h[ultimo:])
    if puestos == 0:
        return h, "ya estaba"
    return "".join(salida), f"{puestos} tablas con pie de fuente"


def faq_en_details(h: str) -> tuple[str, str]:
    if "<details" in h:
        return h, "ya estaba"
    preguntas = re.findall(
        r'<!-- wp:heading \{"level":3\} -->\s*<h3[^>]*>(.*?)</h3>\s*<!-- /wp:heading -->',
        h,
        re.S,
    )
    if not preguntas:
        raise SystemExit("la FAQ no tiene preguntas en H3")
    cambios = 0
    for pregunta in preguntas:
        # Los bloques de esta pieza vienen en varias líneas: se localizan por patrón.
        patron = re.compile(
            r'<!-- wp:heading \{"level":3\} -->\s*<h3[^>]*>'
            + re.escape(pregunta)
            + r"</h3>\s*<!-- /wp:heading -->",
            re.S,
        )
        encontrado = patron.search(h)
        if not encontrado:
            continue
        ini, fin_bloque = encontrado.start(), encontrado.end()
        p_ini = h.find("<!-- wp:paragraph -->", fin_bloque)
        if p_ini < 0 or p_ini - fin_bloque > 8:
            continue
        p_fin = h.find("<!-- /wp:paragraph -->", p_ini) + len("<!-- /wp:paragraph -->")
        parrafo = re.search(r"<p[^>]*>.*?</p>", h[p_ini:p_fin], re.S)
        if not parrafo:
            continue
        h = h[:ini] + _details(pregunta, parrafo.group(0)) + h[p_fin:]
        cambios += 1
    return h, f"{cambios} preguntas en <details>"


def pisar_seo(h: str) -> tuple[str, str]:
    cambios = []
    viejo_h1 = "Planes Siigo 2026: precios, funciones y comparativa con Alegra para Colombia"
    if viejo_h1 in h:
        h = h.replace(viejo_h1, H1, 1)
        cambios.append("H1 con la keyword")
    viejo_intro = "<p>Los <strong>planes Siigo</strong> para facturación electrónica en Colombia arrancan"
    nuevo_intro = "<p>La <strong>facturación Siigo</strong> en Colombia arranca"
    if viejo_intro in h:
        h = h.replace(viejo_intro, nuevo_intro, 1)
        cambios.append("primera frase con la keyword")
    return h, ", ".join(cambios) or "ya estaba"


def enlace_interno(h: str) -> tuple[str, str]:
    pendientes = [url for url in ENLACES_NUEVOS if url not in h]
    if not pendientes:
        return h, "ya estaba"
    ancla = "Cómo pasar de Siigo a Alegra"
    ini = _inicio_bloque(h, ancla)
    if ini < 0:
        raise SystemExit("no se encontró la sección de migración")
    fin = _fin_bloque(h, ini)
    parrafo = (
        "<!-- wp:paragraph --><p>Para dos decisiones concretas del cierre hay piezas del portal "
        'con el detalle: <a href="'
        + ENLACES_NUEVOS[0]
        + '">el módulo de contabilidad de Siigo</a> y la comparativa de '
        '<a href="'
        + ENLACES_NUEVOS[1]
        + '">mejor software de facturación electrónica en Colombia</a>. '
        "Ambas se apoyan en las mismas páginas oficiales que esta comparación.</p>"
        "<!-- /wp:paragraph -->"
    )
    return h[:fin] + parrafo + h[fin:], "dos enlaces internos añadidos"


def quitar_cifra_sin_fuente(h: str) -> tuple[str, str]:
    """La nómina de Alegra se citaba a 269.100 COP, y esa cifra no está en su página de planes."""
    viejo = (
        "En las dos se contrata aparte y por tramo de empleados: Siigo desde 119.900 COP al año "
        "(1 a 2 empleados) y Alegra desde 269.100 (1 a 10)."
    )
    nuevo = (
        "En las dos se contrata aparte y por tramo de empleados: Siigo publica nómina "
        "electrónica desde 119.900 COP al año para 1 o 2 empleados."
    )
    if viejo not in h:
        return h, "ya estaba"
    return h.replace(viejo, nuevo, 1), "retirada la cifra de nómina de Alegra que no está publicada"


PASOS = (
    ("quitar_secciones", quitar_secciones),
    ("quitar_porcentaje", quitar_porcentaje),
    ("quitar_cifra_sin_fuente", quitar_cifra_sin_fuente),
    ("tabla_alegra", tabla_alegra),
    ("pies_de_tabla", pies_de_tabla),
    ("faq_details", faq_en_details),
    ("seo", pisar_seo),
    ("enlace_interno", enlace_interno),
)


def transformar(h: str) -> tuple[str, list[dict]]:
    informe = []
    for nombre, paso in PASOS:
        antes = len(h)
        h, nota = paso(h)
        informe.append({"paso": nombre, "nota": nota, "antes": antes, "despues": len(h)})
    return h, informe


def comprobar(h: str) -> dict:
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
    return {
        "tablas": h.count("<table"),
        "tablas_con_pie": sum(
            1
            for t in re.findall(r"<table\b.*?</table>", h, re.S)
            if "<caption" in t.lower()
        ),
        "h2": len(re.findall(r"<h2", h)),
        "h3": len(re.findall(r"<h3", h)),
        "details": h.count("<details"),
        "enlaces_internos": len(
            re.findall(
                r'href="(?:https://programascontabilidad\.com)?/(?:[a-z-]+/)+[^"]*"', h
            )
        ),
        "palabras": len(texto.split()),
        "keyword_en_h1": KEYWORD.lower() in re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S).group(1).lower()
        if re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
        else False,
        "porcentaje_46": "46 %" in texto,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reencauche del post 1957.")
    parser.add_argument("--respaldo", type=Path, required=True)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)

    original = json.loads(args.respaldo.read_text(encoding="utf-8"))["contenido"]
    nuevo, informe = transformar(original)

    for fila in informe:
        print(f"  {fila['paso']:<18} {fila['antes']:>6} -> {fila['despues']:>6}  {fila['nota']}")
    print("\n== comprobación ==")
    print(json.dumps(comprobar(nuevo), ensure_ascii=False, indent=2))
    print(f"\nmeta: {len(META)} chars · título SEO: {len(TITULO_SEO)} chars")

    if not (140 <= len(META) <= 165) or len(TITULO_SEO) > 60:
        print("ERROR: meta o título SEO fuera de rango")
        return 2

    if not args.aplicar:
        Path("state/reencauche-1957-preview.html").write_text(nuevo, encoding="utf-8")
        print("\npreview: state/reencauche-1957-preview.html")
        return 0

    cargar_entorno(Path.home() / ".pdc" / "wp-prod.env")
    os.environ["PDC_PROD_URL"] = endpoint("PDC_PROD")
    cliente = cliente_desde_entorno("PDC_PROD")

    previo = leer_post(cliente, POST_ID)
    if str(previo.get("post_status")) != "publish":
        print(f"ERROR: el post {POST_ID} no está publicado ({previo.get('post_status')})")
        return 3

    print("\nupdate-post:", json.dumps(_desenvolver(cliente.ejecutar(
        "ewpa/update-post", {"post_id": POST_ID, "content": nuevo, "title": H1}
    )), ensure_ascii=False)[:200])
    print("update-rankmath:", json.dumps(_desenvolver(cliente.ejecutar(
        "ewpa/update-rankmath",
        {"post_id": POST_ID, "titulo_seo": TITULO_SEO, "descripcion_seo": META},
    )), ensure_ascii=False)[:200])

    final = leer_post(cliente, POST_ID)
    contenido = str(final.get("post_content") or "")
    seo = leer_seo(cliente, POST_ID)
    huella = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
    veredicto = {
        "post_id": POST_ID,
        "estado": final.get("post_status"),
        "chars_escritos": len(nuevo),
        "chars_leidos": len(contenido),
        "contenido_identico": huella(nuevo) == huella(contenido),
        "seo_titulo": seo.get("titulo_seo"),
        "seo_titulo_chars": len(str(seo.get("titulo_seo") or "")),
        "meta_chars": len(str(seo.get("descripcion_seo") or "")),
        "estructura": comprobar(contenido),
    }
    print("\n== verificación ==")
    print(json.dumps(veredicto, ensure_ascii=False, indent=2))
    return 0 if veredicto["contenido_identico"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
