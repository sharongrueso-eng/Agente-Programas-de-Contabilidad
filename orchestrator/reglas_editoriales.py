"""Las reglas editoriales que un reencauche de México incumplió y que ahora se comprueban.

Salieron del borrador 5704, que Claude corrigió a mano el 18-nov-2026: la comparativa no incluía a
Alegra, un precio anual de complemento se publicó como mensual, «Bind» y «Bind ERP» aparecieron
como dos proveedores, la pieza enlazaba a Alegra Colombia, tenía un `<h1>` dentro del contenido y
secciones duplicadas, y el reencauche perdió las marcas que el post vivo comparaba.

Todo es determinista: no juzga estilo, comprueba hechos verificables contra el registro del país.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

# Nombre canónico de cada marca: el mismo producto escrito de dos formas es un solo proveedor.
ALIAS: Mapping[str, str] = {
    "bind erp": "bind",
    "bind": "bind",
    "miskuentas": "miskuentas",
    "mis cuentas": "miskuentas",
    "quickbooks": "quickbooks",
    "quick books": "quickbooks",
    "contpaqi": "contpaqi",
    "contpaq i": "contpaqi",
    "aspel coi": "aspel",
    "aspel": "aspel",
    "world office cloud": "world office",
    "world office escritorio": "world office",
    "world office": "world office",
    "siigo aspel": "aspel",
}

# Rutas de país del sitio de Alegra. Cada país acepta más de una forma: Colombia vive en /co/ y
# también en /colombia/, y México respondió /mexico/precios/ cuando /mx/ no existía.
RUTA_ALEGRA: Mapping[str, tuple[str, ...]] = {
    "CO": ("/colombia/", "/co/"),
    "MX": ("/mexico/", "/mx/"),
    "CR": ("/costarica/", "/cr/"),
    "DO": ("/rdominicana/", "/do/"),
}


def rutas(pais: str) -> tuple[str, ...]:
    """Las rutas de país que valen para la pieza. Sin país, cualquiera."""
    return RUTA_ALEGRA.get(pais, ())


def ruta_principal(pais: str) -> str:
    """La ruta que se usa para construir el enlace cuando hay que corregirlo."""
    elegidas = rutas(pais)
    return elegidas[0] if elegidas else "/colombia/"

UTM = "{pais}_articulo_tmd_content"
MAX_ENLACES_ALEGRA = 2
MIN_MARCAS_COMPARATIVA = 4

INTENCIONES_CON_ELENCO = {"compare", "price", "best", "learn"}


def _plano(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos.lower())


def _visible(html: str) -> str:
    return _plano(re.sub(r"<[^>]+>", " ", html or ""))


def canonica(nombre: str) -> str:
    limpio = re.sub(r"[^a-z0-9 ]+", " ", _plano(nombre)).strip()
    return ALIAS.get(limpio, limpio)


def marcas_nombradas(html: str, fichas: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Marca canónica → primera forma en que aparece. Deduplica alias."""
    texto = _visible(html)
    encontradas: dict[str, str] = {}
    for ficha in fichas:
        nombre = str(ficha.get("brand", "")).strip()
        if not nombre:
            continue
        patron = r"\b" + re.escape(_plano(nombre)).replace(r"\ ", r"\s+") + r"\b"
        if re.search(patron, texto):
            clave = canonica(nombre)
            encontradas.setdefault(clave, nombre)
    # Alegra se cuenta siempre, aunque la ficha no esté en la lista recibida.
    if re.search(r"\balegra\b", texto):
        encontradas.setdefault("alegra", "Alegra")
    return encontradas


def _graves(
    html: str, pais: str, keyword: str, fichas: Sequence[Mapping[str, Any]], *, comparativa: bool = True
) -> list[dict]:
    """Los incumplimientos que bloquean: elenco, precios, duplicados y enlaces."""
    salida: list[dict] = []
    marcas = marcas_nombradas(html, fichas)
    total = len(marcas)

    # 1. Alegra siempre, y la comparativa lleva al menos cuatro sistemas del país. Solo aplica a
    # las piezas de comparativa: una reseña de una marca no tiene elenco que completar.
    if comparativa and "alegra" not in marcas:
        salida.append(
            {
                "codigo": "alegra_ausente",
                "pasa": False,
                "detalle": "la pieza compara sistemas y no incluye a Alegra",
                "grave": True,
            }
        )
    if comparativa and total < MIN_MARCAS_COMPARATIVA:
        salida.append(
            {
                "codigo": "elenco_insuficiente",
                "pasa": False,
                "detalle": f"{total} marca(s) en la comparativa; el mínimo es {MIN_MARCAS_COMPARATIVA} "
                f"({', '.join(sorted(marcas))})",
                "grave": True,
            }
        )

    # 2. Un precio anual o de complemento no se publica «al mes». Se comparan cifras sin el
    # separador de miles para que «2,799» y «2799» sean el mismo número.
    texto = re.sub(r"(?<=\d)[,.\s](?=\d{3}\b)", "", _visible(html))
    for ficha in fichas:
        for plan in ficha.get("plans") or ():
            nombre = _plano(str(plan.get("name", "")))
            precio = re.sub(r"(?<=\d)[,.\s](?=\d{3}\b)", "", str(plan.get("price", "")).strip())
            if not precio or not re.search(r"\d", precio):
                continue
            anual = _plano(str(plan.get("billing", ""))) == "anual" or "anual" in nombre
            complemento = "complemento" in nombre or "conecta" in nombre or "complemento" in _plano(
                str(plan.get("note", ""))
            )
            if not (anual or complemento):
                continue
            variantes = {precio, f"{precio}.00"}
            for variante in variantes:
                patron = re.escape(variante) + r"[^\d]{0,60}?(?:al mes|por mes|mensual)"
                if re.search(patron, texto):
                    salida.append(
                        {
                            "codigo": "precio_periodo",
                            "pasa": False,
                            "detalle": f"«{variante}» es {plan.get('name')} "
                            f"({plan.get('billing')}) y la pieza lo publica al mes",
                            "grave": True,
                        }
                    )
                    break

    # 3. Dos alias de la misma marca no son dos proveedores.
    for clave in {canonica(f.get("brand", "")) for f in fichas}:
        formas = {
            _plano(str(f.get("brand", "")))
            for f in fichas
            if canonica(f.get("brand", "")) == clave and _plano(str(f.get("brand", ""))) in texto
        }
        if len(formas) > 1:
            salida.append(
                {
                    "codigo": "marca_duplicada",
                    "pasa": False,
                    "detalle": f"la misma marca aparece como {sorted(formas)}",
                    "grave": True,
                }
            )

    # 4. Enlaces a Alegra: máximo dos, del país de la pieza y con su UTM.
    enlaces = re.findall(r'href="(https?://[^"]*alegra\.com[^"]*)"', html or "", re.I)
    if len(enlaces) > MAX_ENLACES_ALEGRA:
        salida.append(
            {
                "codigo": "enlaces_alegra",
                "pasa": False,
                "detalle": f"{len(enlaces)} enlaces a alegra.com; el máximo es {MAX_ENLACES_ALEGRA}",
                "grave": True,
            }
        )
    ruta = rutas(pais)
    for enlace in enlaces:
        if ruta and not any(r in enlace for r in ruta):
            salida.append(
                {
                    "codigo": "enlaces_alegra",
                    "pasa": False,
                    "detalle": f"enlace a otra versión de país: {enlace[:110]}",
                    "grave": True,
                }
            )
        if UTM.format(pais=_plano(pais)) not in enlace.replace("%7B", "{"):
            salida.append(
                {
                    "codigo": "enlaces_alegra",
                    "pasa": False,
                    "detalle": f"enlace sin la UTM del artículo: {enlace[:110]}",
                    "grave": True,
                }
            )
    return salida


MARCAS_CONOCIDAS = (
    "Alegra", "Siigo", "Loggro", "World Office", "Zeus", "Helisa", "SAP Business One",
    "QuickBooks", "CONTPAQi", "Aspel COI", "Aspel", "Bind ERP", "misKuentas", "Contabilium",
    "Xero", "Odoo", "Sage", "Soft Restaurant", "Ilimitado", "Siscon", "SAP",
)


def fichas_del_pais(pais: str) -> list[dict]:
    """Las fichas del registro para un país; vacío si no hay carpeta de datos."""
    from pathlib import Path
    import json

    carpeta = Path("datos") / "herramientas"
    if not carpeta.is_dir():
        return []
    salida = []
    for archivo in sorted(carpeta.glob(f"*-{pais.lower()}.json")):
        try:
            salida.append(json.loads(archivo.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return salida


def marcas(texto_html: str, pais: str = "") -> set[str]:
    """Marcas de software que nombra un texto, ya normalizadas por alias.

    Un reencauche que pierde marcas pierde lo que la página viva ya cubría: el vivo 3544 comparaba
    Alegra, QuickBooks, CONTPAQi, Aspel COI, Bind ERP y misKuentas, y el borrador dejó una sola.
    """
    texto = _visible(texto_html)
    encontradas: set[str] = set()
    candidatas = list(MARCAS_CONOCIDAS) + [str(f.get("brand", "")) for f in fichas_del_pais(pais)]
    for nombre in candidatas:
        if not nombre:
            continue
        patron = r"\b" + re.escape(_plano(nombre)).replace(r"\ ", r"\s+") + r"\b"
        if re.search(patron, texto):
            encontradas.add(canonica(nombre))
    return encontradas


def _forma(html: str) -> list[dict]:
    """Defectos de forma que se corrigen solos: h1, secciones duplicadas, frases cortadas."""
    salida: list[dict] = []
    if re.search(r"<h1[^>]*>", html or "", re.I):
        salida.append(
            {
                "codigo": "h1_en_contenido",
                "pasa": False,
                "detalle": "el contenido trae un <h1>; el título lo imprime el tema",
                "grave": False,
            }
        )
    titulos = [
        _plano(re.sub(r"<[^>]+>", "", t))
        for t in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html or "", re.I | re.S)
    ]
    repetidos = sorted({t for t in titulos if titulos.count(t) > 1 and t})
    if repetidos:
        salida.append(
            {
                "codigo": "seccion_duplicada",
                "pasa": False,
                "detalle": f"secciones repetidas: {', '.join(repetidos[:4])}",
                "grave": False,
            }
        )
    for parrafo in re.findall(r"<(?:p|div|li)[^>]*>(.*?)</(?:p|div|li)>", html or "", re.I | re.S):
        texto = re.sub(r"<[^>]+>", "", parrafo).strip()
        if len(texto) > 20 and re.search(r"(?i)\b(con|de|del|en|para|por|sin|un|una|el|la|los|las|y|o|que)\s*$", texto):
            salida.append(
                {
                    "codigo": "frase_truncada",
                    "pasa": False,
                    "detalle": f"texto cortado: «…{texto[-60:]}»",
                    "grave": False,
                }
            )
            break
    return salida


def revisar(
    html: str,
    *,
    pais: str,
    keyword: str = "",
    fichas: Sequence[Mapping[str, Any]] = (),
    comparativa: bool = True,
) -> list[dict]:
    """Todos los controles editoriales. Los `grave` bloquean; el resto se corrige."""
    return _graves(html, pais, keyword, fichas, comparativa=comparativa) + _forma(html)


def recortar_alegra(html: str, maximo: int = MAX_ENLACES_ALEGRA) -> str:
    """Deja como mucho `maximo` enlaces a Alegra: los demás pierden el ancla y conservan el texto."""
    enlaces = list(
        re.finditer(r'<a\b[^>]*href="https?://[^"]*alegra\.com[^"]*"[^>]*>(.*?)</a>', html, re.I | re.S)
    )
    for extra in reversed(enlaces[maximo:]):
        html = html[: extra.start()] + extra.group(1) + html[extra.end() :]
    return html


def corregir(html: str, *, pais: str) -> tuple[str, list[str]]:
    """Arreglos deterministas: quita el h1, deduplica secciones y arregla los enlaces a Alegra."""
    tocados: list[str] = []
    original = html

    # El tema imprime el título: un <h1> dentro del cuerpo duplica el encabezado.
    sin_h1, cuantos = re.subn(r"<h1[^>]*>.*?</h1>\s*", "", html or "", flags=re.I | re.S)
    if cuantos:
        html = sin_h1
        tocados.append(f"h1 retirado ({cuantos})")

    # Secciones repetidas: se deja la primera aparición con su cuerpo hasta el siguiente h2.
    vistos: set[str] = set()
    salida: list[str] = []
    posicion = 0
    for encontrado in re.finditer(r"(<h2[^>]*>)(.*?)(</h2>)", html, re.I | re.S):
        titulo = _plano(re.sub(r"<[^>]+>", "", encontrado.group(2)))
        if titulo in vistos:
            salida.append(html[posicion : encontrado.start()])
            posicion = encontrado.end()
            tocados.append(f"sección duplicada: {titulo[:40]}")
        vistos.add(titulo)
    if tocados:
        salida.append(html[posicion:])
        html = "".join(salida)

    # Enlaces a Alegra: se fuerzan al país de la pieza y a la UTM del artículo.
    destinos = rutas(pais)

    def _enlace(coincidencia: re.Match[str]) -> str:
        url = coincidencia.group(1)
        if destinos and not any(r in url for r in destinos):
            url = re.sub(r"alegra\.com/[a-z\-]+/", f"alegra.com{ruta_principal(pais)}", url)
        marca = UTM.format(pais=_plano(pais))
        if marca not in url:
            if "utm_campaign=" in url:
                url = re.sub(r"utm_campaign=[^&]+", f"utm_campaign={marca}", url)
            else:
                url += ("&" if "?" in url else "?") + f"utm_campaign={marca}"
        return f'href="{url}"'

    nuevo = re.sub(r'href="(https?://[^"]*alegra\.com[^"]*)"', _enlace, html, flags=re.I)
    if nuevo != html:
        html = nuevo
        tocados.append("enlaces a Alegra normalizados")

    # Como mucho dos enlaces a Alegra: los siguientes pierden el ancla y conservan el texto.
    enlaces = list(re.finditer(r'<a\b[^>]*href="https?://[^"]*alegra\.com[^"]*"[^>]*>(.*?)</a>', html, re.I | re.S))
    for extra in reversed(enlaces[MAX_ENLACES_ALEGRA:]):
        html = html[: extra.start()] + extra.group(1) + html[extra.end() :]
        tocados.append("enlace a Alegra retirado")

    return html, tocados if html != original else []
