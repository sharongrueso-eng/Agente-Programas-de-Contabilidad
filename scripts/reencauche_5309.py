"""Reencauche del post 5309: software contable para restaurantes en Colombia.

Seis arreglos, todos deterministas y repetibles (si ya están hechos, no los repite):

1. **Tabla comparativa reparada.** La tabla de entrada quedó abierta a mitad de fila y se
   tragó el resto del artículo: el «Procedimiento», la ficha de Alegra y su tabla de planes
   quedaron dentro de un `<tbody>` sin cerrar. Aquí se reconstruye con los datos verificados
   el 13-nov-2026 y se cierra antes de la prosa.
2. **Precio de Alegra corregido.** El artículo llamaba «Contabilidad Emprendedor» a $17.900:
   ese precio es hoy *Facturación electrónica* (sin módulo contable). Contabilidad Emprendedor
   son $74.900 y el POS Emprendedor $25.900; se rehace la tabla con las tres líneas.
3. **Respuesta de costo real** en lugar de «el proveedor no publica ese precio».
4. **FAQ en H2 → preguntas en H3**, bajo un H2 «Preguntas frecuentes».
5. **Orden del cierre**: veredicto → FAQ → fuentes → CTA (hoy el veredicto va después de fuentes).
6. **Dos enlaces internos más** (de 3 a 5), a piezas que existen en el sitemap.

Uso:
    python scripts/reencauche_5309.py --respaldo state/respaldos/post-5309-....json
    python scripts/reencauche_5309.py --respaldo ... --aplicar
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.respaldar_post import (  # noqa: E402
    cargar_entorno,
    endpoint,
    leer_post,
    leer_seo,
)
from orchestrator.mcp_client import cliente_desde_entorno, _desenvolver  # noqa: E402

FECHA_CONSULTA = "13 de noviembre de 2026"
POST_ID = 5309

META_DESCRIPCION = (
    "Comparativa de software contable para restaurantes en Colombia: precios publicados de "
    "Alegra, Loggro, Siigo y World Office, POS y facturación electrónica DIAN."
)

ENLACES_NUEVOS = (
    "https://programascontabilidad.com/comparativas-de-software/pos/sistema-pos-para-restaurantes/",
    "https://programascontabilidad.com/comparativas-de-software/mejor-sistema-pos-en-colombia/",
)


# --------------------------------------------------------------------------- tabla 1

TABLA_COMPARATIVA = (
    '<table class="has-background has-fixed-layout" style="background-color:#cce4f7">'
    '<caption style="caption-side:bottom;text-align:left;padding:10px 16px;font-size:13px;'
    'line-height:1.5;font-weight:400;color:#4B5563;">Precios y datos consultados el '
    + FECHA_CONSULTA
    + " en las páginas oficiales de cada proveedor.</caption>"
    "<thead><tr><th>Aspecto</th><th>Loggro Restobar</th><th>Alegra</th><th>Siigo</th>"
    "<th>World Office Cloud POS</th></tr></thead><tbody>"
    "<tr><td>Precio de entrada publicado</td>"
    "<td>120.990&nbsp;COP/mes<br>(Restobar Básico)</td>"
    "<td>25.900&nbsp;COP/mes<br>(POS Emprendedor)</td>"
    "<td>28.750&nbsp;COP/mes<br>(POS Esencial)</td>"
    "<td>680.000&nbsp;COP/año<br>(Cloud POS, ≈56.667&nbsp;COP/mes)</td></tr>"
    "<tr><td>Contabilidad en el mismo plan</td>"
    "<td>Complemento a $49.990&nbsp;COP/mes</td>"
    "<td>Línea Contabilidad desde $74.900&nbsp;COP/mes</td>"
    "<td>Producto aparte; no incluida en los planes de facturación publicados</td>"
    "<td>Incluida en el plan Cloud POS</td></tr>"
    "<tr><td>Módulo para restaurante (comandas, mesas)</td>"
    "<td>Sí: comandas, zonas de salón e integración con Rappi</td>"
    "<td>No publicado</td>"
    "<td>No publicado</td>"
    "<td>No publicado</td></tr>"
    "<tr><td>Facturación electrónica DIAN</td>"
    "<td>Sí</td><td>Sí</td><td>Sí</td><td>Sí</td></tr>"
    "<tr><td>Tarifas en la página oficial</td>"
    "<td>Publicadas</td><td>Publicadas</td><td>Publicadas</td><td>Publicadas</td></tr>"
    "</tbody></table></figure><!-- /wp:table -->"
)

TABLA_PLANES_ALEGRA = (
    '<caption style="caption-side:bottom;text-align:left;padding:10px 16px;font-size:13px;'
    'line-height:1.5;font-weight:400;color:#4B5563;">Tarifas de lista leídas en '
    "alegra.com/colombia/precios el " + FECHA_CONSULTA + ". El equivalente anual aplica el "
    "25 % de descuento para usuarios nuevos.</caption>"
    "<thead><tr><th>Producto</th><th>Plan</th><th>Mensual</th>"
    "<th>Equivalente con pago anual</th></tr></thead><tbody>"
    "<tr><td>Facturación electrónica</td><td>Emprendedor</td><td>$17.900 COP</td>"
    "<td>$13.425 COP</td></tr>"
    "<tr><td>Facturación electrónica</td><td>Pyme</td><td>$49.900 COP</td>"
    "<td>$37.425 COP</td></tr>"
    "<tr><td>POS</td><td>Emprendedor</td><td>$25.900 COP</td><td>$19.425 COP</td></tr>"
    "<tr><td>POS</td><td>Pyme</td><td>$79.900 COP</td><td>$59.925 COP</td></tr>"
    "<tr><td>Contabilidad</td><td>Emprendedor</td><td>$74.900 COP</td>"
    "<td>$56.175 COP</td></tr>"
    "<tr><td>Contabilidad</td><td>Pyme</td><td>$163.900 COP</td>"
    "<td>$122.925 COP</td></tr>"
    "</tbody>"
)

RESPUESTA_COSTO = (
    "<p>Los planes de entrada publicados arrancan en $17.900&nbsp;COP al mes, pero ese es el "
    "precio de <strong>facturación electrónica sin módulo contable</strong> de Alegra. Para un "
    "restaurante que necesita caja y contabilidad en la misma plataforma la referencia útil es "
    "otra: Alegra POS desde $25.900&nbsp;COP/mes, Siigo POS Esencial $28.750&nbsp;COP/mes y "
    "World Office Cloud POS $680.000&nbsp;COP al año (≈$56.667 al mes). Si además se lleva "
    "contabilidad en Alegra, esa línea arranca en $74.900&nbsp;COP/mes. Y sobre la tarifa base "
    "hay que sumar usuarios, cajas o establecimientos adicionales, que cambian el total real. "
    "Loggro Restobar, el único con comandas publicadas, parte de $120.990&nbsp;COP/mes. "
    "Precios leídos en las páginas oficiales el " + FECHA_CONSULTA + ".</p>"
)

PARRAFO_ENLACES = (
    "<!-- wp:paragraph --><p>Si lo que estás comparando es el punto de venta y no el módulo "
    'contable, conviene revisar la guía de <a href="'
    + ENLACES_NUEVOS[0]
    + '">sistema POS para restaurantes</a> y la comparativa de '
    '<a href="'
    + ENLACES_NUEVOS[1]
    + '">mejor sistema POS en Colombia</a>: ahí el criterio de elección es la operación de '
    "salón, no la contabilidad.</p><!-- /wp:paragraph -->"
)


def _aplicado(h: str, sello: str) -> bool:
    return sello in h


# --------------------------------------------------------------------------- pasos


def reparar_tabla(h: str) -> tuple[str, str]:
    if _aplicado(h, "POS Emprendedor") and "Procedimiento" not in h[h.find("POS Emprendedor") : h.find("POS Emprendedor") + 400]:
        return h, "ya estaba reparada"
    inicio = h.find('<table class="has-background')
    marca = '<!-- wp:heading {"level":2} --><h2>Procedimiento'
    fin = h.find(marca)
    if inicio < 0 or fin < 0 or fin < inicio:
        raise SystemExit("no se encontró la tabla rota en el punto esperado")
    return h[:inicio] + TABLA_COMPARATIVA + h[fin:], "tabla reconstruida y cerrada"


def corregir_alegra(h: str) -> tuple[str, str]:
    cambios = []
    viejo = "Emprendedor · 17.900 COP/mes · publicado"
    nuevo = "Facturación electrónica · desde 17.900 COP/mes · publicado"
    if viejo in h:
        h = h.replace(viejo, nuevo)
        cambios.append("etiqueta de la ficha")

    patron_planes = re.compile(
        r"(<thead><tr><th>Plan</th><th>Mensual</th><th>Equivalente con pago anual</th></tr>"
        r"</thead><tbody>).*?(</tbody>)",
        re.S,
    )
    if "<th>Producto</th>" not in h:
        h, n = patron_planes.subn(lambda m: TABLA_PLANES_ALEGRA, h, count=1)
        if not n:
            raise SystemExit("no se encontró la tabla de planes de Alegra")
        cambios.append("tabla de planes por línea de producto")
    return h, ", ".join(cambios) or "ya estaba"


def responder_costo(h: str) -> tuple[str, str]:
    patron = re.compile(r"<p>Depende del módulo y del plan\. El proveedor no publica ese precio[^<]*</p>")
    if "POS Emprendedor" in h and "$25.900&nbsp;COP/mes" in h:
        return h, "ya estaba"
    h, n = patron.subn(RESPUESTA_COSTO, h, count=1)
    if not n:
        raise SystemExit("no se encontró la respuesta de costo a corregir")
    return h, "respuesta de costo con cifras publicadas"


PREGUNTAS_FAQ = (
    "¿Cuál es el mejor software contable para restaurantes en Colombia?",
    "¿Cuánto cuesta un software contable para restaurantes en Colombia?",
    "¿El sistema debe emitir facturación electrónica de la DIAN?",
    "¿Puedo tener POS y contabilidad en la misma plataforma?",
)


def _inicio_bloque(h: str, texto: str) -> int:
    """Posición del comentario `<!-- wp:...` que abre el bloque que contiene `texto`."""
    pos = h.find(texto)
    if pos < 0:
        return -1
    return h.rfind("<!-- wp:", 0, pos)


def _bloque_heading(nivel: int, titulo: str) -> str:
    return (
        f'<!-- wp:heading {{"level":{nivel}}} --><h{nivel} class="wp-block-heading">{titulo}'
        f"</h{nivel}><!-- /wp:heading -->"
    )


def arreglar_faq(h: str) -> tuple[str, str]:
    if "Preguntas frecuentes sobre software contable" in h:
        return h, "ya estaba"
    faltan = [p for p in PREGUNTAS_FAQ if p not in h]
    if faltan:
        raise SystemExit(f"faltan preguntas de FAQ: {faltan}")

    # Cada pregunta pasa a ser su propio bloque H3, con su comentario Gutenberg.
    for pregunta in PREGUNTAS_FAQ:
        ini = _inicio_bloque(h, pregunta)
        if ini < 0:
            raise SystemExit(f"no se localizó el bloque de «{pregunta}»")
        fin = h.find("<!-- /wp:heading -->", ini)
        if fin < 0:
            raise SystemExit(f"bloque sin cierre: «{pregunta}»")
        fin += len("<!-- /wp:heading -->")
        h = h[:ini] + _bloque_heading(3, pregunta) + h[fin:]

    # El H2 que agrupa la sección, delante de la primera pregunta.
    ini = _inicio_bloque(h, PREGUNTAS_FAQ[0])
    h = (
        h[:ini]
        + _bloque_heading(
            2, "Preguntas frecuentes sobre software contable para restaurantes"
        )
        + h[ini:]
    )
    return h, "FAQ agrupada y preguntas en H3"


ESTILO_DETALLE = (
    'class="pdc-faq" style="border:1px solid #CCE4F7;border-radius:10px;background:#FFFFFF;'
    'padding:14px 18px;margin:0 0 12px;"'
)


def _details(pregunta: str, respuesta: str) -> str:
    """FAQ que abre sin JavaScript, con el H3 dentro del `summary` (como el bloque de Rank Math)."""
    return (
        "<!-- wp:html --><details "
        + ESTILO_DETALLE
        + '><summary style="cursor:pointer;">'
        + f'<h3 style="margin:0;font-size:18px;color:#002B5B;">{pregunta}</h3></summary>'
        + '<div style="padding-top:10px;">'
        + respuesta
        + "</div></details><!-- /wp:html -->"
    )


def faq_desplegable(h: str) -> tuple[str, str]:
    if "<details" in h:
        return h, "ya estaba"
    cambios = 0
    for pregunta in PREGUNTAS_FAQ:
        bloque = _bloque_heading(3, pregunta)
        ini = h.find(bloque)
        if ini < 0:
            raise SystemExit(f"no se encontró el bloque H3 de «{pregunta}»")
        fin_bloque = ini + len(bloque)
        p_ini = h.find("<!-- wp:paragraph -->", fin_bloque)
        if p_ini < 0 or p_ini - fin_bloque > 40:
            continue
        p_fin = h.find("<!-- /wp:paragraph -->", p_ini) + len("<!-- /wp:paragraph -->")
        parrafo = re.search(r"<p[^>]*>.*?</p>", h[p_ini:p_fin], re.S)
        if not parrafo:
            continue
        h = h[:ini] + _details(pregunta, parrafo.group(0)) + h[p_fin:]
        cambios += 1
    return h, f"{cambios} preguntas en <details>"


def reordenar(h: str) -> tuple[str, str]:
    faq = _inicio_bloque(h, "Preguntas frecuentes sobre software contable")
    fuentes = _inicio_bloque(h, ">Fuentes y fecha de actualización</h2>")
    veredicto = _inicio_bloque(h, ">Veredicto: qué conviene según el tipo de restaurante</h2>")
    if min(faq, fuentes, veredicto) < 0:
        raise SystemExit("no se localizaron los bloques del cierre")
    if veredicto < faq:
        return h, "ya estaba"
    cta = h.find("¿Quieres comparar el costo real")
    if cta < 0:
        raise SystemExit("no se encontró el CTA final")
    inicio_cta = h.rfind("<div", 0, cta)

    pre = h[: min(faq, fuentes, veredicto)]
    # Los tres bloques se cortan en sus comentarios de apertura, nunca dentro de una etiqueta.
    bloque_veredicto = h[veredicto:inicio_cta]
    bloque_faq = h[faq:fuentes]
    bloque_fuentes = h[fuentes:veredicto]
    bloque_cta = h[inicio_cta:]
    return pre + bloque_veredicto + bloque_faq + bloque_fuentes + bloque_cta, "veredicto antes de FAQ y fuentes"


def anadir_enlaces(h: str) -> tuple[str, str]:
    if ENLACES_NUEVOS[0] in h and ENLACES_NUEVOS[1] in h:
        return h, "ya estaba"
    ancla = "Este procedimiento es la parte práctica de la comparativa"
    pos = h.find(ancla)
    if pos < 0:
        raise SystemExit("no se encontró el párrafo de cierre del procedimiento")
    fin = h.find("</p>", pos)
    cierre_parrafo = h.find("<!-- /wp:paragraph -->", fin)
    if fin < 0 or cierre_parrafo < 0:
        raise SystemExit("no se pudo delimitar el párrafo")
    corte = cierre_parrafo + len("<!-- /wp:paragraph -->")
    return h[:corte] + PARRAFO_ENLACES + h[corte:], "dos enlaces internos añadidos"


PASOS = (
    ("tabla_comparativa", reparar_tabla),
    ("precio_alegra", corregir_alegra),
    ("respuesta_costo", responder_costo),
    ("faq", arreglar_faq),
    ("faq_desplegable", faq_desplegable),
    ("orden_cierre", reordenar),
    ("enlaces_internos", anadir_enlaces),
)


def transformar(h: str) -> tuple[str, list[dict]]:
    informe = []
    for nombre, paso in PASOS:
        antes = h
        h, nota = paso(h)
        informe.append(
            {"paso": nombre, "nota": nota, "chars_antes": len(antes), "chars_despues": len(h)}
        )
    return h, informe


def comprobar(h: str) -> dict:
    texto = re.sub(r"<[^>]+>", " ", h)
    return {
        "tablas_abren": h.count("<table"),
        "tablas_cierran": h.count("</table>"),
        "h2": len(re.findall(r"<h2", h)),
        "h3": len(re.findall(r"<h3", h)),
        "enlaces_internos": len(
            re.findall(r'href="(?:https://programascontabilidad\.com)?/(?:[a-z-]+/)+[^"]*"', h)
        ),
        "precio_contabilidad_falso": "17.900&nbsp;COP/mes<br>(Contabilidad" in h,
        "pos_emprendedor_presente": "POS Emprendedor" in h,
        "faq_h3": '<h3 class="wp-block-heading">¿Cuál es el mejor software contable' in h,
        "veredicto_antes_de_fuentes": h.find(">Veredicto:") < h.find(">Fuentes y fecha"),
        "palabras": len(texto.split()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reencauche del post 5309.")
    parser.add_argument("--respaldo", type=Path, required=True)
    parser.add_argument("--aplicar", action="store_true", help="escribe en WordPress")
    args = parser.parse_args(argv)

    datos = json.loads(args.respaldo.read_text(encoding="utf-8"))
    original = datos["contenido"]
    nuevo, informe = transformar(original) if False else transformar(original)

    print("== pasos ==")
    for fila in informe:
        print(f"  {fila['paso']:<18} {fila['chars_antes']:>6} -> {fila['chars_despues']:>6}  {fila['nota']}")
    print("\n== comprobación ==")
    print(json.dumps(comprobar(nuevo), ensure_ascii=False, indent=2))
    print(f"\nmeta: {len(META_DESCRIPCION)} chars")

    if len(META_DESCRIPCION) < 140 or len(META_DESCRIPCION) > 165:
        print(f"ERROR: la meta descripción tiene {len(META_DESCRIPCION)} caracteres (140-165)")
        return 2

    if not args.aplicar:
        Path("state/reencauche-5309-preview.html").write_text(nuevo, encoding="utf-8")
        print("\npreview: state/reencauche-5309-preview.html (sin escribir en WordPress)")
        return 0

    # --- escritura -----------------------------------------------------------
    prefijo = "PDC_PROD"
    cargar_entorno(Path.home() / ".pdc" / "wp-prod.env")
    import os

    os.environ[f"{prefijo}_URL"] = endpoint(prefijo)
    cliente = cliente_desde_entorno(prefijo)

    previo = leer_post(cliente, POST_ID)
    if str(previo.get("post_status")) != "publish":
        print(f"ERROR: el post {POST_ID} no está publicado ({previo.get('post_status')}); no se escribe")
        return 3

    respuesta = _desenvolver(
        cliente.ejecutar("ewpa/update-post", {"post_id": POST_ID, "content": nuevo})
    )
    print("\nupdate-post:", json.dumps(respuesta, ensure_ascii=False)[:300])

    seo = _desenvolver(
        cliente.ejecutar(
            "ewpa/update-rankmath",
            {"post_id": POST_ID, "descripcion_seo": META_DESCRIPCION},
        )
    )
    print("update-rankmath:", json.dumps(seo, ensure_ascii=False)[:300] if seo else "sin respuesta")

    # --- verificación por lectura -------------------------------------------
    final = leer_post(cliente, POST_ID)
    contenido_final = str(final.get("post_content") or "")
    seo_final = leer_seo(cliente, POST_ID)
    huella = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

    veredicto = {
        "post_id": POST_ID,
        "estado": final.get("post_status"),
        "chars_escritos": len(nuevo),
        "chars_leidos": len(contenido_final),
        "hash_escrito": huella(nuevo),
        "hash_leido": huella(contenido_final),
        "contenido_identico": huella(nuevo) == huella(contenido_final),
        "meta_leida_chars": len(str(seo_final.get("descripcion_seo") or "")),
        "meta_leida": seo_final.get("descripcion_seo") or "",
        "titulo_seo": seo_final.get("titulo_seo") or "",
        "keyword": seo_final.get("keywords") or "",
        "estructura": comprobar(contenido_final),
    }
    print("\n== verificación ==")
    print(json.dumps(veredicto, ensure_ascii=False, indent=2))
    return 0 if veredicto["contenido_identico"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
