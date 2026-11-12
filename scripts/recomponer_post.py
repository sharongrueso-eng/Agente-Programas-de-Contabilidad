"""Recompone el artículo desde el borrador: tarjetas acotadas y veredicto en tres bloques.

La reparación anterior cerraba cada tarjeta en el siguiente `<h3>`, y el último bloque de marca no
tenía tope: se tragó «Errores frecuentes» y todo lo que venía detrás. Aquí la zona de análisis se
acota a la sección que le corresponde, y el veredicto se rehace en tres tarjetas, como el panel que
se pidió, con los colores de la guía.

Uso:
    python scripts/recomponer_post.py 5309 --dry
    python scripts/recomponer_post.py 5309
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.linea_visual import AZUL, CELESTE_SUAVE, GRIS, LINEA, NAVY, TINTA  # noqa: E402
from scripts.mejorar_post import (  # noqa: E402
    arreglar_enlaces,
    arreglar_utm,
    cta_sutil,
    firma,
    quitar_promesa_de_plantilla,
    reemplazar_veredicto_adelantado,
    tabla_con_estilo,
    urls_reales,
    viñetas_visibles,
)
from scripts.reformatear_competidores import (  # noqa: E402
    CRITERIOS,
    fichas,
    http,
    markdown_a_html,
    tabla_de_criterios,
)

BORRADOR = Path("state/corridas/prod-2026-11-11-CO-restaurantes/borrador.json")


def _bloques_por_h3(zona: str) -> list[tuple[str, str]]:
    """Trocea una zona en (título, cuerpo) por cada h3, sin desbordarse."""
    partes = re.split(r"(?=<h3)", zona)
    salida: list[tuple[str, str]] = []
    for parte in partes:
        encontrado = re.match(r"\s*<h3[^>]*>(.*?)</h3>", parte, re.DOTALL)
        if not encontrado:
            continue
        titulo = re.sub(r"<[^>]+>", "", encontrado.group(1)).strip()
        cuerpo = parte[encontrado.end() :]
        salida.append((titulo, cuerpo.strip()))
    return salida


def _tarjeta_marca(marca: str, cuerpo: str, ficha: dict) -> str:
    precios = [p for p in (ficha.get("plans") or []) if p.get("publicado", True)]
    mensuales = [p for p in precios if str(p.get("billing", "")).lower() == "mensual"] or precios
    etiqueta = "Precio no publicado"
    if mensuales:
        elegido = min(
            mensuales, key=lambda p: float(str(p.get("price") or "0").replace(".", "") or 0)
        )
        if elegido.get("price"):
            etiqueta = (
                f"{elegido['name']} · {elegido['price']} {elegido.get('currency', 'COP')}/"
                f"{elegido.get('period', 'mes')} · publicado"
            )
    return (
        f'<div class="pc-card" style="border:1px solid {LINEA};border-radius:12px;background:#FFFFFF;'
        f'padding:22px 24px;margin:22px 0;">'
        f'<p style="margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:.1em;'
        f'text-transform:uppercase;color:{AZUL};">{etiqueta}</p>'
        f'<h3 style="margin:0 0 12px;font-size:21px;color:{NAVY};">{marca}</h3>{cuerpo}</div>'
    )


def _panel_veredicto(bloques: list[tuple[str, str]]) -> str:
    """Tres perfiles, tres tarjetas, como el panel de referencia."""
    fondos = (
        (NAVY, "#FFFFFF", "#A8BFD4"),
        ("#FFFFFF", NAVY, "#EAF0F5"),
        (AZUL, NAVY, "rgba(0,43,91,0.14)"),
    )
    tarjetas = []
    for i, (titulo, cuerpo) in enumerate(bloques[:3]):
        fondo, tinta, sello = fondos[i]
        borde = f"border:1px solid {LINEA};" if fondo == "#FFFFFF" else ""
        texto = re.sub(r"<[^>]+>", " ", cuerpo)
        texto = re.sub(r"\s+", " ", texto).strip()[:420]
        tarjetas.append(
            f'<div style="flex:1 1 240px;min-width:220px;background:{fondo};color:{tinta};'
            f'border-radius:12px;padding:24px;box-sizing:border-box;{borde}">'
            f'<span style="display:inline-block;font-size:13px;font-weight:700;margin-bottom:14px;'
            f'padding:6px 11px;border-radius:5px;background:{sello};color:{tinta};">0{i + 1}</span>'
            f'<h4 style="margin:0 0 12px;font-size:18px;line-height:1.35;color:{tinta};">{titulo}</h4>'
            f'<p style="margin:0;font-size:14px;line-height:1.65;color:{tinta};">{texto}</p></div>'
        )
    return (
        '<div class="pc-veredicto" style="margin:26px 0;">'
        '<p style="margin:0 0 16px;font-size:12px;font-weight:700;letter-spacing:.12em;'
        f'text-transform:uppercase;color:{NAVY};">Perfil de restaurante</p>'
        '<div style="display:flex;gap:16px;flex-wrap:wrap;">' + "".join(tarjetas) + "</div></div>"
    )


def main() -> int:
    post_id = int(sys.argv[1]) if len(sys.argv) > 1 else 5309
    html = json.loads(BORRADOR.read_text(encoding="utf-8"))["html"]

    # 1) zona de competidores: del primer h3 al siguiente h2
    inicio = html.find("<h3")
    fin = html.find("<h2", inicio)
    zona = html[inicio:fin]
    zona = markdown_a_html(zona)
    datos = fichas()
    orden = [m for m in datos if m.lower() in zona.lower()]
    piezas = []
    for titulo, cuerpo in _bloques_por_h3(zona):
        ficha = next((f for m, f in datos.items() if m.lower() == titulo.lower()), None)
        if ficha:
            cuerpo = re.sub(r"^\s*#{1,6}\s*[^<\n]*", "", cuerpo)
            piezas.append(_tarjeta_marca(ficha["brand"], cuerpo, ficha))
    criterios = '<div class="pc-criterios">' + tabla_de_criterios(datos, orden) + "</div>"
    html = html[:inicio] + "".join(piezas) + criterios + html[fin:]

    # 2) veredicto en tres bloques
    # El h2 que abre el veredicto, no la primera vez que aparece la palabra.
    encontrado = re.search(r"<h2[^>]*>\s*Veredicto", html, re.IGNORECASE)
    v_inicio = encontrado.start() if encontrado else -1
    v_fin = html.find("<h2", v_inicio + 5) if v_inicio != -1 else -1
    if v_inicio != -1:
        v_fin = len(html) if v_fin == -1 else v_fin
        seccion = html[v_inicio:v_fin]
        cabecera = re.match(r"<h2[^>]*>.*?</h2>", seccion, re.DOTALL)
        titulo_h2 = cabecera.group(0) if cabecera else "<h2>Veredicto</h2>"
        bloques = _bloques_por_h3(seccion)
        if len(bloques) >= 2:
            html = (
                html[:v_inicio]
                + titulo_h2
                + _panel_veredicto(bloques)
                + html[v_fin:]
            )

    # 3) el resto de la línea visual, en el mismo orden que la reparación
    html, _ = quitar_promesa_de_plantilla(html)
    # La caja prometía descargar una plantilla que no existe: se convierte en recomendación.
    html = __import__("re").sub(
        r"Prepare una evaluación concreta[\s\S]*?compare los resultados",
        "Prepare una evaluación concreta: durante una semana, registre ventas, propinas, "
        "mermas, compras a proveedores y totales con su operación actual. Después compare los resultados",
        html,
    )
    html, _ = reemplazar_veredicto_adelantado(html)
    html, _ = arreglar_utm(html)
    html, _ = arreglar_enlaces(html, urls_reales())
    html = viñetas_visibles(html)
    # Las tablas de todos los planes no aportan al producto que se vende: fuera.
    def _sin_tablas_de_planes(fragmento: str) -> str:
        def borrar(m):
            cabeceras = " ".join(re.findall(r"<th[^>]*>(.*?)</th>", m.group(0), re.DOTALL)).lower()
            return "" if ("precio mensualidad" in cabeceras or "precio publicado" in cabeceras) else m.group(0)

        return re.sub(r"<table.*?</table>", borrar, fragmento, flags=re.DOTALL)

    html = _sin_tablas_de_planes(html)
    html, _ = tabla_con_estilo(html)
    destino = (
        "https://www.alegra.com/colombia/precios/?utm_source=programascontabilidad"
        "&utm_medium=blog&utm_campaign=comparativa-restaurantes-co"
    )
    html, _ = cta_sutil(html, destino)
    html, _ = firma(html)

    if "--dry" in sys.argv:
        Path("state/recompuesto.html").write_text(html, encoding="utf-8")
        print(
            "ensayo: state/recompuesto.html ·",
            len(html),
            "caracteres · tarjetas:",
            html.count("pc-card"),
            "· veredicto:",
            "pc-veredicto" in html,
        )
        return 0

    codigo, _ = http("POST", f"/wp-json/wp/v2/posts/{post_id}", {"content": html})
    print("actualización:", codigo, "· caracteres:", len(html))
    return 0 if codigo == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
