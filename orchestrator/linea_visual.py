"""Componentes de la línea visual del blog (PdC_Linea_Visual_v1).

Cada componente es un bloque HTML con estilos en línea, como el resto del sitio. El agente
no los redacta: los rellena. Así el HTML sale idéntico en cada artículo y el modelo solo
aporta el texto, que es lo único que varía.

Reglas que los componentes ya cumplen y que ningún texto debe romper:
un mensaje por caja, etiqueta + color + icono (nunca solo color), peso 400 dentro de la
caja, borde izquierdo de 4 px, contraste AA con las variantes oscuras, y ningún CTA en la
primera pantalla.
"""

from __future__ import annotations

NAVY = "#002B5B"
AZUL = "#3299E2"
ENLACE = "#0B6FA4"
CELESTE = "#00AEEF"
CELESTE_SUAVE = "#EFF8FF"
LINEA = "#CCE4F7"
VERDE = "#1B7A32"
VERDE_SUAVE = "#F0FDF4"
ROJO = "#B02A37"
ROJO_SUAVE = "#FFF5F5"
AMBAR = "#F5B700"
TINTA = "#1F2937"
GRIS = "#4B5563"

UTM = "utm_source=blog_programascontabilidad&amp;utm_medium=referral"

NORMAS = """
LÍNEA VISUAL DEL BLOG (obligatoria, no la interpretes: estos componentes ya existen).

1. Respuesta rápida al inicio, una por artículo: una frase en negrita de hasta 20 palabras que
   responde la pregunta del título, y 1-2 frases con el dato que la sostiene.
2. Cinco tipos de caja, una por mensaje, máximo 60 palabras: Respuesta rápida, Dato clave,
   Atención, Límite y Nota de método. Nunca dos cajas seguidas, salvo la Nota de método tras
   una tabla. Máximo una caja de énfasis cada 400 palabras.
3. Etiqueta + color + icono, nunca solo color: se entiende en gris y con daltonismo.
4. Tablas reales (table/thead/tbody), encabezado navy con texto blanco, primera columna como
   th, cebra suave, caption con fuente y fecha. ✓ y ✗ siempre acompañados de texto, y solo
   cuando el criterio es sí/no.
5. «Nuestra recomendación» informa y va antes del CTA final; no contiene el botón. En reseñas
   cierra con «Ideal si / Evita si»; en comparativas, con una tabla por prioridad del lector.
6. Un solo CTA final por artículo, bloque navy con botón celeste y microcopy. Nada de CTA en
   la primera pantalla. El botón dice verbo + objeto («Ver planes para Colombia →»), nunca
   «haz clic aquí». El enlace lleva target="_blank", rel="nofollow noopener" y UTM completos.
7. FAQ con <details>/<summary>, nunca con JavaScript ni acordeón.
8. Tratamiento: tuteo en Colombia, México y República Dominicana; usted en Costa Rica.
9. Nada de texto pequeño en #3299E2, #00AEEF sobre blanco ni #28A745: esos colores son para
   bordes, barras e insignias. El texto va en las variantes oscuras de la paleta.
"""


def resumen(texto: str, etiqueta: str = "En resumen") -> str:
    """Caja de resumen: una idea, en el color de énfasis de la línea visual."""
    return (
        f'<div role="note" style="background:{CELESTE_SUAVE};border:1px solid {LINEA};'
        f'border-left:4px solid {AZUL};border-radius:0 12px 12px 0;padding:18px 22px;'
        f'margin:24px 0;">'
        f'<p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{NAVY};">{etiqueta}</p>'
        f'<p style="margin:0;font-size:16px;line-height:1.65;font-weight:400;'
        f'color:{TINTA};max-width:68ch;">{texto}</p></div>'
    )


def puntos_clave(items: list[str], titulo: str = "Puntos clave") -> str:
    """Tarjeta de puntos clave: lo que decide la compra, en viñetas legibles.

    Va en tarjeta y no en caja de nota porque son varias líneas y el lector las escanea.
    """
    filas = "".join(
        f'<li style="margin:0 0 8px;font-size:16px;line-height:1.6;font-weight:400;'
        f'color:{TINTA};">{item}</li>'
        for item in items
        if str(item).strip()
    )
    return (
        f'<div style="background:#FFFFFF;border:1px solid {LINEA};border-radius:12px;'
        f'padding:0 0 18px;margin:28px 0;overflow:hidden;">'
        f'<div style="background:{NAVY};padding:12px 22px;">'
        f'<p style="margin:0;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:#FFFFFF;">{titulo}</p></div>'
        f'<ul style="margin:16px 0 0;padding-left:38px !important;">{filas}</ul></div>'
    )
def caja(etiqueta: str, texto: str, tipo: str) -> str:
    """Caja de énfasis de la línea visual. tipo: dato, atencion, limite."""
    estilos = {
        "dato": ("#F5F9FD", LINEA, AZUL, NAVY, "i", TINTA),
        "atencion": ("#FFF8E1", "#F6E3A1", AMBAR, "#7A5200", "!", "#3B2F00"),
        "limite": (ROJO_SUAVE, "#F5C2C7", "#DC3545", ROJO, "✕", "#4A1A1F"),
    }
    fondo, borde, acento, color_etiqueta, icono, color_texto = estilos[tipo]
    return (
        f'<div role="note" style="background:{fondo};border:1px solid {borde};'
        f'border-left:4px solid {acento};border-radius:0 10px 10px 0;padding:18px 22px;'
        f'margin:24px 0;">'
        f'<p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{color_etiqueta};">'
        f'<span style="display:inline-block;width:20px;height:20px;line-height:20px;'
        f'border-radius:50%;background:{acento};color:#FFFFFF;text-align:center;font-size:12px;'
        f'font-weight:700;margin-right:8px;vertical-align:middle;">{icono}</span>{etiqueta}</p>'
        f'<p style="margin:0;font-size:16px;line-height:1.65;font-weight:400;'
        f'color:{color_texto};max-width:68ch;">{texto}</p></div>'
    )


def respuesta_rapida(frase: str, apoyo: str) -> str:
    return (
        f'<div style="background:{CELESTE_SUAVE};border:1px solid {LINEA};'
        f'border-left:4px solid {AZUL};border-radius:0 12px 12px 0;padding:20px 24px;'
        f'margin:24px 0;">'
        f'<p style="margin:0 0 8px;font-size:19px;line-height:1.45;font-weight:700;'
        f'color:{NAVY};max-width:68ch;">{frase}</p>'
        f'<p style="margin:0;font-size:16px;line-height:1.65;font-weight:400;color:{TINTA};'
        f'max-width:68ch;">{apoyo}</p></div>'
    )


def nota_metodo(fecha: str, fuentes: str) -> str:
    return (
        f'<div role="note" style="background:#F4F6F8;border:1px solid #E1E6EB;'
        f'border-left:4px solid {NAVY};border-radius:0 10px 10px 0;padding:18px 22px;'
        f'margin:24px 0;">'
        f'<p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{GRIS};">Nota de método</p>'
        f'<p style="margin:0;font-size:14px;line-height:1.65;font-weight:400;color:{GRIS};'
        f'max-width:68ch;">Precios consultados el {fecha} en {fuentes}. Pueden cambiar sin '
        f'aviso: confirma la cotización vigente antes de contratar.</p></div>'
    )


def cta_final(url: str, etiqueta: str, pregunta: str, subtexto: str, boton: str, fecha: str) -> str:
    return (
        f'<div style="background:{NAVY};border-radius:14px;padding:32px 32px 28px;'
        f'margin:32px 0;text-align:center;">'
        f'<p style="margin:0 0 10px;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{CELESTE};">{etiqueta}</p>'
        f'<p style="margin:0 0 10px;font-size:24px;line-height:1.3;font-weight:700;'
        f'color:#fff;">{pregunta}</p>'
        f'<p style="margin:0 auto 22px;max-width:520px;font-size:16px;line-height:1.6;'
        f'font-weight:400;color:#D6E8F5;">{subtexto}</p>'
        f'<a href="{url}" target="_blank" rel="nofollow noopener" '
        f'style="display:inline-block;background:{CELESTE};color:{NAVY};font-size:16px;'
        f'font-weight:700;line-height:1.2;padding:16px 34px;border-radius:8px;'
        f'text-decoration:none;">{boton} &rarr;</a>'
        f'<p style="margin:14px 0 0;font-size:13px;line-height:1.5;font-weight:400;'
        f'color:#A8BFD4;">Se abre el sitio del proveedor en una pestaña nueva · Precios '
        f'consultados el {fecha}</p></div>'
    )


def tabla(caption: str, encabezados: list[str], filas: list[list[str]]) -> str:
    """Tabla con encabezado navy, primera columna como th y cebra suave."""
    cabecera = "".join(
        f'<th scope="col" style="background:{NAVY};color:#fff;text-align:left;'
        f"padding:14px 16px;font-size:14px;line-height:1.35;font-weight:700;"
        f'vertical-align:bottom;">{h}</th>'
        for h in encabezados
    )
    cuerpo = []
    for i, fila in enumerate(filas):
        fondo = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
        celdas = "".join(
            f'<td style="background:{fondo};padding:13px 16px;border-top:1px solid #E5EDF5;'
            f'font-size:15px;line-height:1.5;font-weight:400;color:{TINTA};'
            f'vertical-align:top;">{c}</td>'
            for c in fila[1:]
        )
        cuerpo.append(
            f'<tr><th scope="row" style="background:{fondo};color:{NAVY};text-align:left;'
            f'padding:13px 16px;border-top:1px solid #E5EDF5;font-size:15px;line-height:1.5;'
            f'font-weight:700;vertical-align:top;">{fila[0]}</th>{celdas}</tr>'
        )
    return (
        f'<div style="overflow-x:auto;margin:24px 0;border:1px solid {LINEA};'
        f'border-radius:10px;"><table style="width:100%;border-collapse:collapse;">'
        f'<caption style="caption-side:bottom;text-align:left;padding:10px 16px;'
        f'font-size:13px;line-height:1.5;font-weight:400;color:{GRIS};">{caption}</caption>'
        f"<thead><tr>{cabecera}</tr></thead><tbody>{''.join(cuerpo)}</tbody></table></div>"
    )


def faq(preguntas: list[tuple[str, str]]) -> str:
    """FAQ con details: funciona sin JavaScript y el texto queda en el HTML."""
    piezas = []
    for i, (pregunta, respuesta) in enumerate(preguntas):
        abierto = " open" if i == 0 else ""
        piezas.append(
            f'<details{abierto} style="border:1px solid {LINEA};border-radius:10px;'
            f'margin:0 0 10px;background:#fff;">'
            f'<summary style="cursor:pointer;padding:16px 20px;font-size:16px;line-height:1.4;'
            f'font-weight:700;color:{NAVY};">{pregunta}</summary>'
            f'<div style="padding:0 20px 18px;"><p style="margin:0;font-size:16px;'
            f'line-height:1.65;font-weight:400;color:{TINTA};max-width:68ch;">{respuesta}</p>'
            f"</div></details>"
        )
    return "".join(piezas)


def recomendacion(titulo: str, justificacion: str, ideal: list[str], evita: list[str]) -> str:
    """Caja informativa del veredicto. No lleva botón: el CTA va aparte."""

    def lista(items: list[str], color: str, fondo: str, etiqueta: str, icono: str) -> str:
        filas = "".join(
            f'<li style="margin:0 0 6px;font-size:15px;line-height:1.55;font-weight:400;'
            f'color:{TINTA};">{t}</li>'
            for t in items
        )
        return (
            f'<div style="flex:1 1 260px;background:{fondo};border-radius:8px;'
            f'padding:14px 18px 8px;">'
            f'<p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:.08em;'
            f'text-transform:uppercase;color:{color};">'
            f'<span style="display:inline-block;width:20px;height:20px;line-height:20px;'
            f'border-radius:50%;background:{color};color:#fff;text-align:center;font-size:12px;'
            f'font-weight:700;margin-right:8px;vertical-align:middle;">{icono}</span>'
            f'{etiqueta}</p><ul style="margin:0;padding-left:20px !important;">{filas}</ul></div>'
        )

    return (
        f'<div style="border:2px solid {NAVY};border-radius:12px;overflow:hidden;margin:28px 0;">'
        f'<div style="background:{NAVY};padding:11px 24px;">'
        f'<p style="margin:0;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:#fff;">Nuestra recomendación</p></div>'
        f'<div style="padding:22px 24px 20px;">'
        f'<p style="margin:0 0 8px;font-size:22px;line-height:1.3;font-weight:700;'
        f'color:{NAVY};">{titulo}</p>'
        f'<p style="margin:0 0 18px;font-size:16px;line-height:1.65;font-weight:400;'
        f'color:{TINTA};max-width:68ch;">{justificacion}</p>'
        f'<div style="display:flex;gap:14px;flex-wrap:wrap;">'
        + lista(ideal, VERDE, VERDE_SUAVE, "Ideal si", "✓")
        + lista(evita, ROJO, ROJO_SUAVE, "Evita si", "✕")
        + "</div></div></div>"
    )


def lista(items: list[str]) -> str:
    """Lista de viñetas que no se sale del ancho del contenido.

    El tema no le da `padding-left` a `ul.wp-block-list`: la viñeta queda fuera del marco y en
    móvil se corta. La sangría se fija aquí, en línea, para que el componente no dependa de la
    hoja de estilos de turno.
    """
    filas = "".join(
        f'<li style="margin:0 0 8px;font-size:16px;line-height:1.65;font-weight:400;'
        f'color:{TINTA};">{item}</li>'
        for item in items
        if str(item).strip()
    )
    return f'<ul style="margin:0 0 18px;padding-left:1.35em !important;">{filas}</ul>'


def dos_columnas(izquierda: tuple, derecha: tuple) -> str:
    """Dos bloques lado a lado —ventajas y puntos de atención— en una sola fila.

    Cada columna es `(etiqueta, items, color, fondo, icono)`. Se apilan solas cuando no hay
    ancho: `flex-wrap` y `flex:1 1 260px`, sin media queries.
    """

    def columna(etiqueta: str, items, color: str, fondo: str, icono: str) -> str:
        filas = "".join(
            f'<li style="margin:0 0 8px;font-size:15px;line-height:1.6;font-weight:400;'
            f'color:{TINTA};">{item}</li>'
            for item in items
            if str(item).strip()
        )
        return (
            f'<div style="flex:1 1 260px;min-width:0;background:{fondo};border:1px solid '
            f'{LINEA};border-radius:12px;padding:16px 20px 10px;box-sizing:border-box;">'
            f'<p style="margin:0 0 10px;font-size:12px;font-weight:700;letter-spacing:.08em;'
            f'text-transform:uppercase;color:{color};">'
            f'<span style="display:inline-block;width:20px;height:20px;line-height:20px;'
            f'border-radius:50%;background:{color};color:#fff;text-align:center;font-size:12px;'
            f'font-weight:700;margin-right:8px;vertical-align:middle;">{icono}</span>'
            f"{etiqueta}</p>"
            f'<ul style="margin:0;padding-left:1.25em !important;">{filas}</ul></div>'
        )

    return (
        '<div style="display:flex;flex-wrap:wrap;gap:16px;margin:24px 0;">'
        + columna(*izquierda)
        + columna(*derecha)
        + "</div>"
    )


AVATAR_LEANDRO = (
    "https://programascontabilidad.com/wp-content/uploads/2024/06/"
    "Leandro-banner-home-100x100.png"
)
AUTOR_URL = "https://programascontabilidad.com/author/ngorczany/"

FIRMA_AUTOR = (
    '<div style="background:#f5f9fd;border:1px solid #cce4f7;border-radius:12px;'
    'padding:20px 24px;margin:32px 0;display:flex;gap:16px;align-items:flex-start">'
    f'<img src="{AVATAR_LEANDRO}" width="72" height="72" '
    'alt="Leandro, analista y fundador de Programas de Contabilidad" '
    'style="border-radius:50%;flex-shrink:0;margin:0">'
    "<div>"
    '<p style="margin:0 0 6px"><strong>Leandro</strong> · Analista y fundador de Programas '
    "de Contabilidad</p>"
    '<p style="margin:0;font-size:15px;line-height:1.5">Analista colombiano y fundador de '
    "programascontabilidad. Con 37 años, combino la experiencia técnica con una visión "
    "analítica para ofrecer las comparativas más profundas del sector. Ayudo a profesionales "
    "y empresas a navegar la transformación digital contable con criterio y claridad.</p>"
    f'<p style="margin:10px 0 0"><a href="{AUTOR_URL}" rel="author">Ver todas sus '
    "comparativas</a></p>"
    "</div></div>"
)


def firma() -> str:
    """Ficha del autor que cierra la pieza. Idéntica en todo el portal."""
    return FIRMA_AUTOR
