"""Reencauche del post 3106: reseña de Adm Cloud (República Dominicana).

La pieza llegó con los comentarios de bloque envueltos en `<p>` (600 veces), comentarios
desbalanceados, un acordeón de FAQ que depende de JavaScript y trece H2. Aquí se reconstruye
con bloques válidos, conservando el texto de la propia pieza:

1. **Ocho secciones** en lugar de trece H2, fusionando las que ya decían lo mismo.
2. **Ficha rápida y tabla de precios** construidas con los datos de la ficha del mercado.
3. **FAQ en `<details>`**, sin JavaScript.
4. **Elenco cerrado**: solo Adm Cloud. Se retira la mención a otro software que traía el
   párrafo de cierre; la comparativa del portal se enlaza sin nombrar marcas.
5. **Meta descripción** de 140 a 160 caracteres con la keyword foco.

Uso:
    python scripts/reencauche_3106.py --respaldo state/respaldos/post-3106-....json
    python scripts/reencauche_3106.py --respaldo ... --aplicar
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

from scripts.reencauche_5309 import _details  # noqa: E402
from scripts.respaldar_post import (  # noqa: E402
    cargar_entorno,
    endpoint,
    leer_post,
    leer_seo,
)
from scripts.unidades_post import faq_pares, texto, unidades  # noqa: E402
from orchestrator.linea_visual import (  # noqa: E402
    firma,
    ROJO,
    ROJO_SUAVE,
    VERDE,
    VERDE_SUAVE,
    caja,
    dos_columnas,
    lista as lista_visual,
)
from orchestrator.mcp_client import cliente_desde_entorno, _desenvolver  # noqa: E402

POST_ID = 3106
FECHA = "13 de noviembre de 2026"
KEYWORD = "Adm Cloud reseña"
H1 = "Adm Cloud reseña: precios, funciones y para quién conviene en República Dominicana"
TITULO_SEO = "Adm Cloud reseña: precios, funciones y para quién conviene"
META = (
    "Adm Cloud reseña para República Dominicana: módulos, precios publicados en dólares, "
    "facturación electrónica e-CF y qué confirmar antes de contratar."
)

COMPARATIVA = "https://programascontabilidad.com/comparativas-de-software/adm-cloud-software-comparacion/"

ENLACES_RD = {
    "facturacion": (
        (
            "https://programascontabilidad.com/comparativas-de-software/proveedores-de-facturacion-electronica-republica-dominicana/",
            "proveedores de facturación electrónica en República Dominicana",
        ),
        (
            "https://programascontabilidad.com/analisis-de-herramientas/facturacion-electronica-en-republica-dominicana/",
            "qué exige la facturación electrónica en el país",
        ),
    ),
    "operacion": (
        (
            "https://programascontabilidad.com/comparativas-de-software/psfe-facturacion-electronica-republica-dominicana/",
            "los PSFE autorizados por la DGII",
        ),
        (
            "https://programascontabilidad.com/analisis-de-herramientas/sistemas-pos-para-almacenes-republica-dominicana/",
            "sistemas POS para almacenes en República Dominicana",
        ),
    ),
}

CTA = (
    "<!-- wp:html --><div style=\"background:#002B5B;border-radius:14px;padding:34px 30px;"
    'margin:36px 0;text-align:center;color:#fff;"><p style="margin:0 0 10px;font-size:22px;'
    'font-weight:700;">¿Quieres ver cómo se compara con otras opciones del país?</p>'
    '<p style="margin:0 auto 22px;max-width:520px;font-size:16px;line-height:1.6;color:#D6E8F5;">'
    "La comparativa de software para República Dominicana usa los mismos criterios de esta "
    'reseña y cita cada precio con su fecha.</p>'
    f'<a href="{COMPARATIVA}" rel="nofollow noopener" style="display:inline-block;background:#00AEEF;'
    'color:#002B5B;font-size:16px;font-weight:700;padding:16px 34px;border-radius:8px;'
    'text-decoration:none;">Ver la comparativa &rarr;</a></div><!-- /wp:html -->'
)

FILAS_FICHA = (
    ("Tipo de solución", "ERP y gestión empresarial en la nube"),
    ("Proveedor", "ForTech"),
    ("Mercado revisado", "República Dominicana"),
    ("Precio de entrada publicado", "18,00 USD al mes (plan Billing)"),
    ("Módulos publicados", "Contabilidad, ventas, compras, bancos, inventario, nómina, CRM y manufactura"),
    ("Facturación electrónica", "e-CF y reportes fiscales 606, 607 y 608"),
    ("Prueba", "15 días gratis"),
    ("Última revisión", "Noviembre de 2026"),
)

PLANES = (
    ("Billing", "18,00", "15,00"),
    ("Start", "24,00", "20,00"),
    ("Basic", "36,00", "30,00"),
    ("Standard", "60,00", "50,00"),
    ("Premium", "84,00", "70,00"),
    ("Premium Plus", "108,00", "90,00"),
    ("Premium Plus Nómina", "144,00", "120,00"),
    ("Premium Plus Manufactura", "144,00", "120,00"),
)

FUENTES = (
    ("https://www.admcloud.net/", "Adm Cloud — sitio oficial"),
    ("https://www.admcloud.net/planes", "Adm Cloud — planes y precios"),
    ("https://www.dgii.gov.do/", "DGII — Dirección General de Impuestos Internos"),
)


# --------------------------------------------------------------------------- bloques


def _p(html: str) -> str:
    return f"<!-- wp:paragraph --><p>{html}</p><!-- /wp:paragraph -->"


def _sinc_comentarios(html: str) -> str:
    """Quita comentarios de bloque y listas anidadas que quedaron dentro del texto rescatado."""
    limpio = re.sub(r"<!--\s*/?wp:[^>]*?-->", "", html or "")
    limpio = re.sub(r"</?ul[^>]*>", "", limpio)
    limpio = re.sub(r"</?li[^>]*>", "", limpio)
    return re.sub(r"\s{2,}", " ", limpio).strip()


def _lista(items) -> str:
    if not items:
        return ""
    # La sangría va en línea: el tema no le da `padding-left` a `ul.wp-block-list` y la viñeta
    # se sale del marco del artículo.
    return "<!-- wp:html -->" + lista_visual([_sinc_comentarios(i) for i in items]) + "<!-- /wp:html -->"


def _h2(titulo: str) -> str:
    return f'<!-- wp:heading --><h2 class="wp-block-heading">{titulo}</h2><!-- /wp:heading -->'


def _tabla(filas, cabecera, pie: str) -> str:
    cab = "".join(f"<th>{c}</th>" for c in cabecera)
    cuerpo = "".join(
        "<tr>" + "".join(f"<td>{celda}</td>" for celda in fila) + "</tr>" for fila in filas
    )
    return (
        '<!-- wp:table {"className":"is-style-stripes","style":{"color":{"background":"#cce4f7"}}} -->'
        '<figure class="wp-block-table is-style-stripes">'
        '<table class="has-background has-fixed-layout" style="background-color:#cce4f7">'
        '<caption style="caption-side:bottom;text-align:left;padding:10px 16px;font-size:13px;'
        f'line-height:1.5;font-weight:400;color:#4B5563;">{pie}</caption>'
        f"<thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></figure><!-- /wp:table -->"
    )


def _puntaje() -> str:
    return (
        "<!-- wp:html --><div style=\"background:#002B5B;border-radius:14px;padding:22px 26px;"
        'margin:28px 0;color:#fff;"><p style="margin:0;font-size:13px;letter-spacing:.08em;'
        'text-transform:uppercase;color:#A8BFD4;">Evaluación editorial</p>'
        '<p style="margin:6px 0 0;font-size:34px;font-weight:700;line-height:1;">7,8 '
        '<span style="font-size:16px;font-weight:400;color:#A8BFD4;">/ 10</span></p>'
        '<p style="margin:8px 0 0;font-size:13px;color:#A8BFD4;">Con base en información pública '
        "del proveedor, revisada en noviembre de 2026.</p></div><!-- /wp:html -->"
    )


# --------------------------------------------------------------------------- plan


def _grupos(h: str) -> dict[str, list[dict]]:
    """Agrupa las unidades por el H2 que las precede."""
    grupos: dict[str, list[dict]] = {}
    actual = ""
    for unidad in unidades(h):
        if unidad["tipo"] == "h2":
            actual = texto(unidad["html"])
            grupos[actual] = []
        else:
            grupos.setdefault(actual, []).append(unidad)
    return grupos


def _tomar(grupo: list[dict], tipo: str) -> list[str]:
    return [u["html"] for u in grupo if u["tipo"] == tipo]


def _limpiar_componente(items: list[str]) -> list[str]:
    """Quita los textos que eran tarjetas de componentes y ahora se reconstruyen como tabla."""
    fuera = {
        "score adm cloud",
        "/ 10",
        "7.8",
        "evaluación editorial",
        "flujo de gestión en adm cloud",
        "premium plus",
        "premium plus nómina",
        "premium plus manufactura",
    }
    limpios = []
    for item in items:
        plano = texto(item).lower().strip(" .")
        if plano in fuera:
            continue
        if re.fullmatch(r"\$?\s?\d{1,3}\s?/mes", plano):
            continue
        limpios.append(item)
    return limpios


def construir(h: str) -> str:
    g = _grupos(h)
    salida: list[str] = []

    intro = _limpiar_componente(_tomar(g.get("", []), "p"))
    for parrafo in intro[:2]:
        salida.append(_p(parrafo))
    salida.append(_puntaje())

    salida.append(_h2("Adm Cloud reseña: ficha rápida"))
    salida.append(
        _tabla(
            FILAS_FICHA,
            ("Aspecto", "Dato"),
            f"Datos del proveedor y de su página de planes, consultados el {FECHA}.",
        )
    )

    que_es = g.get("¿Qué es Adm Cloud?", [])
    como = g.get("¿Cómo funciona Adm Cloud?", [])
    salida.append(_h2("Qué es Adm Cloud y cómo funciona"))
    for parrafo in _tomar(que_es, "p")[:2]:
        salida.append(_p(parrafo))
    for parrafo in _tomar(como, "p")[:1]:
        salida.append(_p(parrafo))
    for cita in _tomar(como, "blockquote")[:1]:
        salida.append(f"<!-- wp:quote --><blockquote class=\"wp-block-quote\">{cita}</blockquote><!-- /wp:quote -->")
    flujo = _limpiar_componente(_tomar(como, "p")[1:])
    # «Diferencia clave» es un mensaje, no un paso del flujo: va en su caja y no en la lista.
    avisos = [t for t in flujo if t.lstrip().startswith("⚠")]
    pasos = [t for t in flujo if t not in avisos]
    if pasos:
        salida.append(_lista(pasos))
    for aviso in avisos:
        limpio = re.sub(r"^[^A-Za-zÁÉÍÓÚÑ¿]*", "", aviso).strip()
        etiqueta, _, cuerpo = limpio.partition(":")
        salida.append(
            "<!-- wp:html -->"
            + caja(etiqueta.strip() or "Diferencia clave", cuerpo.strip() or limpio, "dato")
            + "<!-- /wp:html -->"
        )

    funciones = _tomar(g.get("Funciones y módulos principales", []), "li")
    salida.append(_h2("Funciones y módulos principales"))
    salida.append(_lista(funciones))

    salida.append(_h2("Precios publicados de Adm Cloud en 2026"))
    salida.append(
        _p(
            "La página de planes publica ocho tarifas mensuales en dólares, con un precio menor "
            "si se paga anual. El plan de entrada es <strong>Billing</strong>, con facturación "
            "electrónica incluida, un usuario y 100 transacciones al mes."
        )
    )
    salida.append(
        _tabla(
            PLANES,
            ("Plan", "Pago mensual (USD)", "Pagando anual (USD/mes)"),
            f"Tarifas de lista de admcloud.net/planes, consultadas el {FECHA}. "
            "Facturación electrónica incluida en todos los planes.",
        )
    )
    salida.append(
        _p(
            "<strong>Revise el costo total:</strong> confirme usuarios, transacciones, módulos, "
            "implementación y soporte antes de firmar, porque el precio de lista no siempre es "
            "el costo del primer año."
        )
    )

    facturacion = _tomar(
        g.get("Adm Cloud y la facturación electrónica en República Dominicana", []), "p"
    )
    salida.append(_h2("Adm Cloud y la facturación electrónica en República Dominicana"))
    for parrafo in facturacion[:1]:
        salida.append(_p(parrafo))
    enlaces_fe = " y ".join(
        f'<a href="{url}">{etiqueta}</a>' for url, etiqueta in ENLACES_RD["facturacion"]
    )
    salida.append(
        _p(
            "Para situar la oferta de Adm Cloud en el mercado conviene leer también la lista de "
            f"{enlaces_fe}, que el portal revisa con las páginas oficiales de cada proveedor."
        )
    )

    salida.append(_h2("Ventajas y puntos de atención"))
    ventajas = _tomar(g.get("Ventajas y puntos de atención de Adm Cloud", []), "li")
    # El signo viene dentro de un `<strong>` en la pieza original: se lee sobre el texto y se
    # retira del HTML, porque la columna ya trae su propio icono.
    def marca(item: str) -> str:
        return texto(item).strip()[:1]

    def sin_marca(item: str) -> str:
        limpio = re.sub(r"^\s*<strong[^>]*>\s*[+−-]\s*</strong>\s*", "", item)
        limpio = re.sub(r"^\s*[+−-]\s*", "", limpio)
        return _sinc_comentarios(limpio)

    pros = [sin_marca(v) for v in ventajas if marca(v) == "+"]
    contras = [sin_marca(v) for v in ventajas if marca(v) in {"−", "-"}]
    if pros or contras:
        salida.append(
            "<!-- wp:html -->"
            + dos_columnas(
                ("Ventajas", pros, VERDE, VERDE_SUAVE, "✓"),
                ("Puntos de atención", contras, ROJO, ROJO_SUAVE, "✕"),
            )
            + "<!-- /wp:html -->"
        )
    else:
        salida.append(_lista(ventajas))
    salida.append(_p("<strong>Posibles limitaciones y puntos que debe confirmar</strong>"))
    salida.append(_lista(_tomar(g.get("Posibles limitaciones y puntos que debe confirmar", []), "li")))

    salida.append(_h2("¿Para quién conviene y qué preguntar antes de contratar?"))
    for grupo in ("¿Para quién puede ser adecuado Adm Cloud?", "¿Qué debe preguntar antes de implementar Adm Cloud?"):
        for parrafo in _tomar(g.get(grupo, []), "p"):
            if texto(parrafo).startswith("☑"):
                continue
            salida.append(_p(parrafo))
    checklist = _tomar(g.get("¿Qué debe preguntar antes de implementar Adm Cloud?", []), "p")
    if checklist:
        salida.append(_lista(checklist))
    enlaces_op = " y ".join(
        f'<a href="{url}">{etiqueta}</a>' for url, etiqueta in ENLACES_RD["operacion"]
    )
    salida.append(
        _p(
            "Si la operación incluye punto de venta o varias bodegas, el portal tiene revisados "
            f"{enlaces_op}, útiles para contrastar alcance antes de decidir."
        )
    )

    salida.append(_h2("Veredicto: ¿vale la pena Adm Cloud?"))
    for parrafo in _tomar(g.get("Veredicto: ¿vale la pena Adm Cloud?", []), "p"):
        if COMPARATIVA in parrafo:
            continue
        salida.append(_p(parrafo))
    salida.append(
        _p(
            "Para comparar Adm Cloud bajo los mismos criterios, el portal tiene una "
            f'<a href="{COMPARATIVA}">comparativa de software para República Dominicana</a> '
            "construida con las páginas oficiales de cada proveedor."
        )
    )

    pares = faq_pares(h)
    if not pares:
        raise SystemExit("no se pudieron rescatar las preguntas de la FAQ")
    salida.append(_h2("Preguntas frecuentes"))
    for pregunta, respuesta in pares:
        salida.append(_details(pregunta, f"<p>{respuesta}</p>"))

    salida.append(_h2("Fuentes"))
    salida.append(
        _lista(
            [
                f'<a href="{url}" target="_blank" rel="noopener nofollow">{nombre}</a>'
                f". Consultada el {FECHA}."
                for url, nombre in FUENTES
            ]
        )
    )
    salida.append("<!-- wp:html -->" + firma() + "<!-- /wp:html -->")
    salida.append(CTA)
    return _pulir("\n\n".join(salida) + "\n")


def _pulir(html: str) -> str:
    """Quita restos del editor anterior y separa frases que venían pegadas."""
    html = re.sub(r"\[embed\][^\[]*\[/embed\]", "", html)
    html = re.sub(r"</p>\s*<p>\s*</p>", "</p>", html)
    # «reportes.Las» → «reportes. Las»
    html = re.sub(r"(?<=[a-záéíóúñ\)])\.(?=[A-ZÁÉÍÓÚÑ])", ". ", html)
    return html


def comprobar(h: str) -> dict:
    plano = texto(h)
    return {
        "h2": len(re.findall(r"<h2", h)),
        "h3": len(re.findall(r"<h3", h)),
        "tablas": h.count("<table"),
        "tablas_con_pie": sum(
            1 for t in re.findall(r"<table\b.*?</table>", h, re.S) if "<caption" in t.lower()
        ),
        "details": h.count("<details"),
        "p_sueltos_con_comentario": len(re.findall(r"<p>\s*<!--", h)),
        "comentarios_balanceados": h.count("<!-- /wp:") >= h.count("<!-- wp:") - 2,
        "palabras": len(plano.split()),
        "menciona_alegra": "alegra" in plano.lower(),
        "menciona_siigo": "siigo" in plano.lower(),
        "menciona_loggro": "loggro" in plano.lower(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reencauche del post 3106.")
    parser.add_argument("--respaldo", type=Path, required=True)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args(argv)

    original = json.loads(args.respaldo.read_text(encoding="utf-8"))["contenido"]
    nuevo = construir(original)

    print("== comprobación ==")
    print(json.dumps(comprobar(nuevo), ensure_ascii=False, indent=2))
    print(f"\nchars: {len(original)} -> {len(nuevo)} | meta: {len(META)}")

    if not (140 <= len(META) <= 165):
        print("ERROR: meta fuera de rango")
        return 2

    if not args.aplicar:
        Path("state/reencauche-3106-preview.html").write_text(nuevo, encoding="utf-8")
        print("\npreview: state/reencauche-3106-preview.html")
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
        "meta_chars": len(str(seo.get("descripcion_seo") or "")),
        "estructura": comprobar(contenido),
    }
    print("\n== verificación ==")
    print(json.dumps(veredicto, ensure_ascii=False, indent=2))
    return 0 if veredicto["contenido_identico"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
