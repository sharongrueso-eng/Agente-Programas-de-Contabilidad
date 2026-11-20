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
    hallado: list[str] = []
    for ficha in fichas:
        for plan in ficha.get("plans") or ():
            nombre = _plano(str(plan.get("name", "")))
            precio = re.sub(r"(?<=\d)[,.\s](?=\d{3}\b)", "", str(plan.get("price", "")).strip())
            if not precio or not re.search(r"\d", precio):
                continue
            # El precio se publica «al mes» bien cuando el plan es mensual, bien cuando la ficha
            # da el equivalente mensual del pago anual. El error es publicar al mes un precio que
            # la ficha da por año (el caso Conecta Bind: 2.799 era el año, no el mes).
            periodo = _plano(str(plan.get("period", "")))
            por_ano = periodo in {"año", "ano", "anual"} or (
                "anual" in nombre and not periodo
            )
            # Solo es error si el precio es de año y se publica al mes. Un complemento mensual
            # citado al mes está bien: la palabra «complemento» no lo vuelve anual.
            if not por_ano:
                continue
            variantes = {precio, f"{precio}.00"}
            for variante in variantes:
                patron = re.escape(variante) + r"[^\d]{0,60}?(?:al mes|por mes|\bmensual\b)"
                if re.search(patron, texto):
                    hallado.append(
                        f"«{variante}» es {plan.get('name')} ({plan.get('period') or plan.get('billing')}) "
                        "y la pieza lo publica al mes"
                    )
                    break

    if hallado:
        detalle = hallado[0] + (f" (+{len(hallado) - 1} más)" if len(hallado) > 1 else "")
        salida.append({"codigo": "precio_periodo", "pasa": False, "detalle": detalle, "grave": True})

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
    problemas: list[str] = []
    if len(enlaces) > MAX_ENLACES_ALEGRA:
        problemas.append(f"{len(enlaces)} enlaces a alegra.com; el máximo es {MAX_ENLACES_ALEGRA}")
    ruta = rutas(pais)
    for enlace in enlaces:
        if ruta and not any(r in enlace for r in ruta):
            problemas.append(f"enlace a otra versión de país: {enlace[:90]}")
        if UTM.format(pais=_plano(pais)) not in enlace.replace("%7B", "{"):
            problemas.append(f"enlace sin la UTM {UTM.format(pais=_plano(pais))}: {enlace[:90]}")
    if problemas:
        detalle = problemas[0] + (f" (+{len(problemas) - 1} más)" if len(problemas) > 1 else "")
        salida.append({"codigo": "enlaces_alegra", "pasa": False, "detalle": detalle, "grave": True})
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


MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# «consultada el 18 de noviembre de 2026», «consultados entre el 11 y el 18 de noviembre de 2026».
FECHA_DE_CONSULTA = re.compile(
    r"(?i)\b(?:consultad|actualizad|revisad|verificad|tomad)[oa]s?\b"
    r"(?:\s+(?:el|entre\s+el|desde\s+el|hasta\s+el))?[^.;:()]{0,60}?"
    r"\b(?:de\s+)?(?:" + "|".join(MESES) + r")\s+de\s+\d{4}"
)
FECHA_DE_HOY = re.compile(
    r"(?i)\b(?:a\s+fecha\s+de|al\s+cierre\s+de|con\s+datos\s+de)\s+(?:" + "|".join(MESES) + r")\s+de\s+\d{4}"
)
MESES_TEXTO = re.compile(r"(?i)\b(?:" + "|".join(MESES) + r")\s+de\s+\d{4}\b")

MONEDAS = re.compile(r"(?i)(?:US\$|RD\$|₡|\$|USD|COP|MXN|DOP|CRC)\s?[\d.,]+|\b[\d.,]+\s?(?:USD|COP|MXN|DOP|CRC)\b")
PERIODOS = re.compile(r"(?i)\b(al\s+mes|por\s+mes|mensual|al\s+año|por\s+año|anual|trimestral|semestral)\b")

# Palabras de pregunta y conectores que no distinguen un subtítulo de otro.
VACIAS = frozenset(
    """que cual cuales como cuando donde porque para por con sin sobre entre desde hasta
    sistema software contabilidad contable programa programas mejor mejores elegir opcion
    opciones guia comparativa comparar dominicana republica colombia mexico costa rica 2026""".split()
)


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9áéíóúñ]{4,}", _plano(texto)) if p not in VACIAS}


def _subtitulos(html: str, nivel: int) -> list[str]:
    patron = rf"<h{nivel}[^>]*>(.*?)</h{nivel}>"
    return [_plano(re.sub(r"<[^>]+>", "", t)) for t in re.findall(patron, html or "", re.I | re.S)]


PREFIJOS = re.compile(
    r"(?i)^(?:veredicto|conclusi[oó]n|resumen|en resumen|respuesta r[aá]pida|lo esencial)\s*:?\s*"
)


def _normalizar_titulo(titulo: str) -> list[str]:
    limpio = PREFIJOS.sub("", _plano(titulo))
    return re.findall(r"[a-z0-9áéíóúñ]{2,}", limpio)


def _similares(html: str, nivel: int = 2, umbral: float = 0.55) -> list[tuple[str, str, float]]:
    """Pares de subtítulos que hablan de lo mismo.

    Dos formas de repetirse: con las mismas palabras en otro orden (Jaccard) o repitiendo la
    misma frase de cuatro palabras tras un prefijo distinto. «¿Qué sistema de contabilidad
    conviene en RD?» y «Veredicto: qué sistema de contabilidad conviene según el tamaño» son el
    mismo subtítulo dos veces.
    """
    titulos = [t for t in _subtitulos(html, nivel) if t]
    salida: list[tuple[str, str, float]] = []
    for i, uno in enumerate(titulos):
        for otro in titulos[i + 1 :]:
            a_palabras, b_palabras = _normalizar_titulo(uno), _normalizar_titulo(otro)
            a, b = _palabras(uno), _palabras(otro)
            jaccard = len(a & b) / len(a | b) if (a or b) else 0.0
            # La cabeza del título (lo que va después de «Veredicto:») es lo que lo identifica.
            # «Qué es un sistema de contabilidad» y «Errores al elegir un sistema de contabilidad»
            # comparten cuatro palabras y no son el mismo subtítulo.
            misma_cabeza = a_palabras[:4] == b_palabras[:4] and len(a_palabras) >= 4
            if misma_cabeza or jaccard >= umbral:
                salida.append((uno, otro, round(max(jaccard, 0.99 if misma_cabeza else 0.0), 2)))
    return salida


def _bloques_de_marca(html: str, marcas_ajenas: set[str]) -> list[tuple[str, str]]:
    """(título, cuerpo) de cada H3 que es el nombre de un competidor."""
    bloques = []
    formas = [_plano(m) for m in marcas_ajenas if m]
    partes = re.split(r"(<h3[^>]*>.*?</h3>)", html or "", flags=re.I | re.S)
    for i in range(1, len(partes), 2):
        titulo = _plano(re.sub(r"<[^>]+>", "", partes[i]))
        cuerpo = partes[i + 1] if i + 1 < len(partes) else ""
        # Una pregunta de FAQ que nombra dos marcas no es la ficha de una de ellas.
        if "?" in titulo or "¿" in re.sub(r"<[^>]+>", "", partes[i]):
            continue
        if any(titulo.startswith(m) or f" {m} " in f" {titulo} " for m in formas):
            bloques.append((titulo, cuerpo))
    return bloques


def _voz(html: str, pais: str, fichas: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Fechas en el cuerpo, protagonismo y densidad de Alegra, subtítulos repetidos y precios."""
    salida: list[dict] = []
    texto = _visible(html)

    # 1. Sin fechas de consulta: el vigía mantiene los precios al día y la fecha envejece el post.
    fechas = FECHA_DE_CONSULTA.findall(html or "") + FECHA_DE_HOY.findall(html or "")
    if fechas or re.search(r"(?i)<h2[^>]*>[^<]*fecha\s+de\s+consulta", html or ""):
        salida.append(
            {
                "codigo": "fecha_de_consulta",
                "pasa": False,
                "detalle": "el cuerpo lleva la fecha en que se consultó la fuente o el precio "
                "(va en la ficha del vigía, no en el artículo)",
                "grave": False,
            }
        )

    # 2. Alegra no abre la pieza: entra como una alternativa más y cierra como la recomendada.
    formas = {str(f.get("brand", "")) for f in fichas} | set(MARCAS_CONOCIDAS)
    nombres_ajenos = {
        n
        for n in formas
        if n and n.lower() != "alegra"
        and re.search(r"\b" + re.escape(_plano(n)) + r"\b", texto)
    }
    ajenas = nombres_ajenos
    # El arranque es lo que se lee antes del primer H2: ahí no puede estar Alegra sola.
    arranque_html = (html or "").split("<h2")[0] if "<h2" in (html or "") else (html or "")[:2500]
    arranque = _visible(arranque_html)
    if re.search(r"(?i)\balegra\b", arranque) and not any(
        re.search(r"\b" + re.escape(_plano(m)) + r"\b", arranque) for m in ajenas
    ):
        salida.append(
            {
                "codigo": "alegra_protagonista",
                "pasa": False,
                "detalle": "el artículo abre con Alegra y ninguna otra marca: la comparación "
                "empieza por el mercado y Alegra entra como una alternativa",
                "grave": False,
            }
        )

    # 3. Densidad: Alegra nombrada una y otra vez deja de ser una comparación.
    menciones = len(re.findall(r"(?i)\balegra\b", texto))
    # Una comparativa de cuatro marcas necesita nombrar a Alegra en su apartado, en la tabla y en el
    # veredicto. El tope sube con el elenco (4 por competidor); el 5711 tenía 50 menciones para un
    # solo competidor y sigue disparando.
    tope = 4 * max(1, len({canonica(n) for n in ajenas})) + 4
    if menciones > tope:
        salida.append(
            {
                "codigo": "alegra_densidad",
                "pasa": False,
                "detalle": f"Alegra aparece {menciones} veces para {len(ajenas)} competidor(es); "
                f"el tope es {tope}",
                "grave": False,
            }
        )

    # 4. Cada sistema se describe solo: Alegra no se cuela en la ficha de otro.
    for titulo, cuerpo in _bloques_de_marca(html or "", ajenas):
        # Dentro de la ficha de otra marca se mira la prosa, no las tablas: una tabla de criterios
        # compara marcas por columnas y ahí el nombre de Alegra es una columna, no una digresión.
        limpio = re.sub(r"<table[^>]*>.*?</table>", " ", cuerpo or "", flags=re.S | re.I)
        if re.search(r"(?i)\balegra\b", _visible(limpio)):
            salida.append(
                {
                    "codigo": "alegra_en_otra_ficha",
                    "pasa": False,
                    "detalle": f"la ficha «{titulo[:60]}» nombra a Alegra: cada sistema se "
                    "describe por separado",
                    "grave": False,
                }
            )
            break

    # 5. Subtítulos repetidos con otras palabras.
    repetidos = _similares(html or "", 2) + _similares(html or "", 3, 0.7)
    if repetidos:
        uno, otro, cuanto = repetidos[0]
        salida.append(
            {
                "codigo": "subtitulos_similares",
                "pasa": False,
                "detalle": f"«{uno[:48]}» y «{otro[:48]}» cuentan lo mismo ({cuanto})",
                "grave": False,
            }
        )

    # 6. Si hay precios, tienen que poder compararse: misma moneda y mismo periodo.
    precios = MONEDAS.findall(html or "")
    if len(precios) >= 3:
        vistas = set()
        for precio in precios:
            marca = re.search(r"(?i)(USD|COP|MXN|DOP|CRC)", precio)
            if marca:
                vistas.add(marca.group(1).upper())
            elif "US$" in precio:
                vistas.add("USD")
            elif "RD$" in precio:
                vistas.add("DOP")
            elif "₡" in precio:
                vistas.add("CRC")
            else:
                vistas.add("?")
        local = {"CO": "COP", "MX": "MXN", "CR": "CRC", "DO": "DOP"}.get(pais, "")
        mezcla = {m for m in vistas if m and m != "?"}
        if local and mezcla and (len(mezcla) > 1 or local not in mezcla):
            salida.append(
                {
                    "codigo": "moneda_incomparable",
                    "pasa": False,
                    "detalle": f"los precios no están en la moneda del país ({local}): "
                    f"{', '.join(sorted(mezcla))}",
                    "grave": False,
                }
            )
        periodos = {p.lower() for p in PERIODOS.findall(html or "")}
        mensual = {p for p in periodos if "mes" in p or "mensual" in p}
        anual = {p for p in periodos if "año" in p or "anual" in p}
        # Si el texto declara la equivalencia («680.000 al año, unos 56.667 al mes»), la mezcla de
        # periodos es la comparación bien hecha, no un defecto.
        equivalente = re.search(r"(?i)al a[ñn]o[^.]{0,80}?\bal mes\b", texto)
        if mensual and anual and not equivalente:
            salida.append(
                {
                    "codigo": "periodo_incomparable",
                    "pasa": False,
                    "detalle": "los precios mezclan mensual y anual: hay que llevar a un solo periodo",
                    "grave": False,
                }
            )

    # 7. Una tabla con todos los planes de todos los competidores no se lee.
    for tabla_html in re.findall(r"<table[^>]*>.*?</table>", html or "", re.I | re.S):
        filas = re.findall(r"<tr[^>]*>(.*?)</tr>", tabla_html, re.I | re.S)
        con_precio = sum(1 for f in filas if MONEDAS.search(f))
        if con_precio > 10:
            salida.append(
                {
                    "codigo": "tabla_de_precios_gigante",
                    "pasa": False,
                    "detalle": f"una tabla compara {con_precio} precios: se comparan los planes "
                    "equivalentes, no todos los de todos",
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
    return (
        _graves(html, pais, keyword, fichas, comparativa=comparativa)
        + _forma(html)
        + _voz(html, pais, fichas)
    )


def recortar_alegra(html: str, maximo: int = MAX_ENLACES_ALEGRA) -> str:
    """Deja como mucho `maximo` enlaces a Alegra: los demás pierden el ancla y conservan el texto."""
    enlaces = list(
        re.finditer(r'<a\b[^>]*href="https?://[^"]*alegra\.com[^"]*"[^>]*>(.*?)</a>', html, re.I | re.S)
    )
    for extra in reversed(enlaces[maximo:]):
        html = html[: extra.start()] + extra.group(1) + html[extra.end() :]
    return html


def corregir(html: str, *, pais: str) -> tuple[str, list[str]]:
    """Arreglos deterministas: fechas de consulta, h1, secciones y enlaces a Alegra."""
    tocados: list[str] = []
    original = html

    # Sin fechas de consulta: el vigía mantiene el precio al día y la fecha en el texto envejece
    # el artículo. Se quita la cláusula y se limpia la puntuación que queda suelta.
    sin_fechas, cuantas_fechas = FECHA_DE_CONSULTA.subn("", html or "")
    sin_fechas, cuantas_hoy = FECHA_DE_HOY.subn("", sin_fechas)
    if cuantas_fechas + cuantas_hoy:
        sin_fechas = re.sub(r"[ \t]{2,}", " ", sin_fechas)
        sin_fechas = re.sub(r"\s+([,.;:])", r"\1", sin_fechas)
        sin_fechas = re.sub(r"\(\s*[;,]\s*\)", "", sin_fechas)
        sin_fechas = re.sub(r"\s+</(p|li|div)>", r"</\1>", sin_fechas)
        html = sin_fechas
        tocados.append(f"fecha de consulta retirada ({cuantas_fechas + cuantas_hoy})")

    # «Fuentes y fecha de consulta» pasa a «Fuentes»: sin fecha no hay nada más que anunciar.
    html, secciones = re.subn(
        r"(?i)(<h2[^>]*>)\s*Fuentes\s+y\s+fecha\s+de\s+consulta\s*(</h2>)", r"\1Fuentes\2", html
    )
    if secciones:
        tocados.append("«Fuentes y fecha de consulta» → «Fuentes»")

    # El tema imprime el título: un <h1> dentro del cuerpo duplica el encabezado.
    sin_h1, cuantos = re.subn(r"<h1[^>]*>.*?</h1>\s*", "", html or "", flags=re.I | re.S)
    if cuantos:
        html = sin_h1
        tocados.append(f"h1 retirado ({cuantos})")

    # Secciones repetidas: se deja la primera aparición con su cuerpo hasta el siguiente h2.
    vistos: set[str] = set()
    salida: list[str] = []
    posicion = 0
    podado = False
    for encontrado in re.finditer(r"(<h2[^>]*>)(.*?)(</h2>)", html, re.I | re.S):
        titulo = _plano(re.sub(r"<[^>]+>", "", encontrado.group(2)))
        if titulo in vistos:
            salida.append(html[posicion : encontrado.start()])
            posicion = encontrado.end()
            podado = True
            tocados.append(f"sección duplicada: {titulo[:40]}")
        vistos.add(titulo)
    if podado:
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
