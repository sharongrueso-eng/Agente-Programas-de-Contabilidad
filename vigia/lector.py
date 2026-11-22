"""Lector del vigía de precios (paso 4 de la guía).

Lee una página de precios y devuelve una *lectura*, no un precio suelto: qué cifras vio, en qué moneda,
con qué señales de país, si hay campaña y si esa lectura sirve para comparar.

Reglas de `REGLAS-VIGIA.md` que se aplican aquí:
- Los precios salen del DOM o del HTML, nunca de una captura ni de un resumen.
- Nunca se convierte la moneda: moneda distinta de la esperada es lectura dudosa.
- La página tiene que mostrar señales del país del vigía; si apuntan a otro país, es lectura dudosa o
  cambio de mercado.
- Una promoción de temporada no es un cambio de precio. El descuento anual permanente tampoco es campaña.
- Si la receta no encuentra nada, la lectura lo dice («sin_precios»), no se calla.

Uso:
    python -m vigia.lector --pais col
    python -m vigia.lector --pais col --fuente alegra-co
    python -m vigia.lector --pais col --desde-html paises/col/lecturas/2026-11-18/alegra-co.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata

from bs4 import BeautifulSoup

RAIZ = os.environ.get("VIGIA_RAIZ") or os.path.dirname(os.path.abspath(__file__))  # VIGIA_RAIZ permite que los datos vivan en el volumen del contenedor
PAQUETE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PAQUETE, "inventario"))

from numeros import valor  # noqa: E402
from pais import decidir, puntajes, senales  # noqa: E402

VIGIA_PAIS = {"col": "CO", "mex": "MX", "cri": "CR", "dom": "DO"}
PAIS_VIGIA = {v: k for k, v in VIGIA_PAIS.items()}
LOCALE = {"CO": "es-CO", "MX": "es-MX", "CR": "es-CR", "DO": "es-DO"}
ZONA = {"CO": "America/Bogota", "MX": "America/Mexico_City",
        "CR": "America/Costa_Rica", "DO": "America/Santo_Domingo"}
# Moneda que implica cada símbolo cuando la página no escribe el código. En Costa Rica y RD el símbolo
# $ es USD (ESTADO.md). Queda marcada como inferida para que se pueda auditar.
SIMBOLO_POR_PAIS = {"CO": "COP", "MX": "MXN", "CR": "USD", "DO": "USD"}
# Nombre del producto según el id del contenedor (maqueta de Alegra Colombia).
PRODUCTO_POR_ID = {"facturacion": "Facturación electrónica", "contabilidad": "Contabilidad",
                   "pos": "POS", "nomina": "Nómina electrónica", "erp": "ERP"}

# El código de moneda delante del número es parte del patrón: Alegra CR y RD escriben «USD 26.10 / mes»
# y con un patrón que solo busque el símbolo la lectura sale vacía.
PRECIO_RE = re.compile(r"(?:US\$|RD\$|₡|\$|USD|COP|CRC|MXN|DOP)\s?\d[\d.,]*")

# Insignias, cuentas regresivas y vigencias. El descuento anual («con pago anual», «facturado»,
# «ahorras») no está en esta lista a propósito: no es campaña.
CAMPANA_RE = [
    r"black\s*friday", r"cyber\s*monday", r"cyberlunes", r"cyber\s*days", r"buen\s*fin",
    r"hot\s*sale", r"navidad", r"fin\s*de\s*a[nñ]o", r"solo\s*hoy", r"[uú]ltimas\s*horas",
    r"[uú]ltimos\s*d[ií]as", r"cuenta\s*regresiva", r"promoci[oó]n\s*v[aá]lida",
    r"v[aá]lido\s*hasta", r"termina\s+(?:el|en)\s+\d", r"vigencia",
]
VIGENCIA_CERCA = ("hasta", "termina", "vence", "dias", "horas", "vigencia")


def _plano(txt: str) -> str:
    """Minúsculas y sin tildes: las marcas de campaña no dependen de cómo se escriban."""
    sin = unicodedata.normalize("NFKD", txt or "")
    return "".join(c for c in sin if not unicodedata.combining(c)).lower()


def moneda_de(token: str, pais: str) -> tuple[str, bool]:
    """(moneda, inferida_del_simbolo)."""
    t = (token or "").upper().replace(" ", "").replace("\xa0", "")
    if t.startswith("USD") or t.startswith("US$"):
        return "USD", False
    if t.startswith("RD$") or t.startswith("DOP"):
        return "DOP", False
    if t.startswith("COP"):
        return "COP", False
    if t.startswith("MXN"):
        return "MXN", False
    if t.startswith("CRC") or t.startswith("₡"):
        return "CRC", False
    if t.startswith("$"):
        return SIMBOLO_POR_PAIS.get(pais, "$"), True
    return "$", True


def detectar_campana(texto: str, titulo: str = "") -> tuple[bool, list[str]]:
    """Campaña = insignia, cuenta regresiva o vigencia. Un «% OFF» sin fecha tampoco es campaña.

    La evidencia es el texto encontrado con su contexto, no el patrón: quien lea el aviso tiene que poder
    buscar esa frase en la página.
    """
    plano = _plano(f"{titulo} {texto}")
    hallazgos = []
    for patron in CAMPANA_RE:
        m = re.search(patron, plano)
        if m:
            ini, fin = max(0, m.start() - 45), min(len(plano), m.end() + 45)
            hallazgos.append(plano[ini:fin].strip())
    if not hallazgos:
        for m in re.finditer(r"\d{1,2}\s*%\s*(?:off|dcto|descuento)", plano):
            cerca = plano[max(0, m.start() - 80): m.end() + 80]
            if any(k in cerca for k in VIGENCIA_CERCA):
                hallazgos.append(plano[max(0, m.start() - 45): min(len(plano), m.end() + 45)].strip())
    return bool(hallazgos), hallazgos


def _cifras_en(textos, pais: str) -> list[dict]:
    fuera = []
    for t in textos:
        for token in PRECIO_RE.findall(t):
            moneda, inferida = moneda_de(token, pais)
            numero = valor(re.sub(r"[^\d.,]", "", token))
            if numero is None:
                continue
            fuera.append({"texto": token.strip(), "valor": numero, "moneda": moneda,
                          "moneda_inferida": inferida})
    return fuera


def _dedupe(cifras: list[dict]) -> list[dict]:
    """La misma cifra aparece dos veces en el HTML (variante móvil y de escritorio)."""
    vistos, limpio = {}, []
    for c in cifras:
        k = (c["valor"], c["moneda"])
        if k not in vistos:
            vistos[k] = c
            limpio.append(c)
        elif len(c["texto"]) < len(vistos[k]["texto"]):
            limpio[limpio.index(vistos[k])] = c
            vistos[k] = c
    return limpio


def _producto_de(card, fuente: dict) -> tuple[str | None, str | None]:
    """Producto y grupo de una tarjeta.

    Colombia agrupa por id (`pricing-cards-<producto>`); México y RD agrupan por `data-period-group`, y el
    mapa grupo→producto vive en `fuentes.json` porque el encabezado de al lado miente (en México al bloque
    de Facturación le precede un h3 que dice «Alegra POS»).
    """
    grupo = None
    producto = None
    el = card
    for _ in range(6):
        el = el.parent
        if el is None:
            break
        ident = el.get("id") or ""
        if ident.startswith("pricing-cards-"):
            producto = PRODUCTO_POR_ID.get(ident.replace("pricing-cards-", ""))
            break
        g = el.get("data-period-group")
        if g:
            grupo = g[-8:]
            producto = (fuente.get("grupos") or {}).get(grupo)
            break
    return producto, grupo


def _producto_por_prefijo(plan: str, receta: dict) -> str | None:
    """Producto por el nombre del plan, cuando la página no lo dice en el DOM."""
    for prefijo, producto in (receta.get("producto_por_prefijo") or {}).items():
        if plan.lower().startswith(prefijo.lower()):
            return producto
    return None


def _tarjetas(soup: BeautifulSoup, pais: str, fuente: dict | None = None) -> list[dict]:
    """Tarjetas de plan: nombre, producto y cifras.

    Dos maquetas:
    - La de Alegra (`.cards-simple--card`), con el producto por contenedor o por `data-period-group`.
    - Cualquier otra, con la receta de la fuente: `contenedor` + `plan` (selector del nombre) y, si hace
      falta, `plan_filtro` (solo los planes cuyo nombre contenga ese texto).
    """
    fuente = fuente or {}
    receta = fuente.get("receta") or {}
    salida = []

    if receta.get("contenedor") and receta.get("plan"):
        for nodo in soup.select(receta["contenedor"]):
            nombre = nodo.select_one(receta["plan"])
            if not nombre:
                continue
            plan = re.sub(r"\s+", " ", nombre.get_text(" ", strip=True))
            filtro = receta.get("plan_filtro")
            if filtro and filtro.lower() not in plan.lower():
                continue
            # Insignias que no son nombre de plan («POPULAR», «RECOMENDADO»).
            if any(e.lower() in plan.lower() for e in receta.get("plan_excluir") or []):
                continue
            texto = re.sub(r"\s+", " ", nodo.get_text(" ", strip=True)).split("Facturado")[0]
            cifras = _dedupe(_cifras_en([texto], pais))
            if not cifras:
                continue
            producto, grupo = _producto_de(nodo, fuente)
            producto = producto or _producto_por_prefijo(plan, receta) or receta.get("producto")
            salida.append({"plan": plan, "producto": producto, "grupo": grupo, "cifras": cifras})
        return salida

    for card in soup.select(".cards-simple--card"):
        nombre = card.select_one(".cards-simple--plan-name")
        if not nombre:
            continue
        fila = card.select_one("p.cards-simple--price-row") or card.select_one(
            "span.cards-simple-price-and-period")
        if not fila:
            continue
        # Solo la parte del precio: si se toma la fila entera, el facturado anual se cuela como mensual.
        texto = re.sub(r"\s+", " ", fila.get_text(" ", strip=True)).split("Facturado")[0]
        cifras = _dedupe(_cifras_en([texto], pais))
        if not cifras:
            continue
        producto, grupo = _producto_de(card, fuente)
        salida.append({"plan": re.sub(r"\s+", " ", nombre.get_text(" ", strip=True)),
                       "producto": producto, "grupo": grupo, "cifras": cifras})
    return salida


def leer_html(html: str, fuente: dict, fecha: str | None = None) -> dict:
    """Lectura de una página ya descargada. Es lo que usan las pruebas (sin red)."""
    pais = fuente.get("pais") or VIGIA_PAIS.get(fuente.get("vigia") or "", "CO")
    esperada = fuente.get("moneda_esperada")
    soup = BeautifulSoup(html, "lxml")
    titulo = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()
    texto = soup.get_text(" ", strip=True)

    receta = fuente.get("receta") or {}
    if receta.get("contenedor"):
        try:
            nodos = soup.select(receta["contenedor"])
        except Exception:
            nodos = []
        textos = [n.get_text(" ", strip=True) for n in nodos] if nodos else []
        cifras = _dedupe(_cifras_en(textos, pais)) if textos else []
    else:
        cifras = _dedupe(_cifras_en([texto], pais))

    campana, evidencia = detectar_campana(texto, titulo)
    pais_detectado = decidir(puntajes(texto))
    monedas = sorted({c["moneda"] for c in cifras})

    lectura = {
        "fuente": fuente.get("id"),
        "marca": fuente.get("marca"),
        "pais": pais,
        "url": fuente.get("url"),
        "fecha": fecha or dt.date.today().isoformat(),
        "titulo": titulo[:160],
        "moneda_esperada": esperada,
        "monedas_leidas": monedas,
        "cifras": cifras,
        "n_cifras": len(cifras),
        "tarjetas": _tarjetas(soup, pais, fuente),
        "campana": campana,
        "campana_evidencia": evidencia,
        "pais_por_senales": pais_detectado,
        "senales": senales(texto)[:12],
        "resultado": "ok",
        "motivo": None,
    }

    if not cifras:
        lectura.update(resultado="sin_precios", motivo="la receta no encontró cifras en el DOM")
    elif esperada and any(m != esperada for m in monedas):
        lectura.update(resultado="moneda_distinta",
                       motivo=f"se esperaba {esperada} y la página muestra {', '.join(monedas)}")
    elif pais_detectado and pais_detectado != pais:
        lectura.update(resultado="pais_distinto",
                       motivo=f"las señales del texto apuntan a {pais_detectado}, no a {pais}")
    elif campana:
        lectura.update(resultado="campana", motivo=f"campaña detectada: {', '.join(evidencia)}")
    return lectura


def leer_fuente(fuente: dict, pais: str, fecha: str, doble: bool = True, guardar: bool = True) -> dict:
    """Abre la página con Chromium (dos contextos separados) y deja HTML y lectura en el repositorio."""
    from playwright.sync_api import sync_playwright

    lecturas, html_guardado = [], None
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for _ in range(2 if doble else 1):
            ctx = navegador.new_context(viewport={"width": 1440, "height": 900},
                                        locale=LOCALE[pais], timezone_id=ZONA[pais])
            pg = ctx.new_page()
            pg.goto(fuente["url"], wait_until="domcontentloaded", timeout=90_000)
            for _ in range(10):
                pg.mouse.wheel(0, 900)
                pg.wait_for_timeout(350)
            pg.wait_for_timeout(1500)
            html = pg.evaluate(
                "() => { const c = document.body.cloneNode(true);"
                " c.querySelectorAll('script,style,svg,noscript,iframe').forEach(e => e.remove());"
                " return '<!doctype html><html><head><meta charset=\"utf-8\"><title>' + document.title"
                " + '</title><base href=\"' + location.href + '\"></head><body>' + c.innerHTML"
                " + '</body></html>'; }"
            )
            html_guardado = html_guardado or html
            lecturas.append(leer_html(html, fuente, fecha))
            ctx.close()
        navegador.close()

    lectura = lecturas[0]
    if len(lecturas) > 1:
        firmas = [{c["valor"] for c in lec["cifras"]} for lec in lecturas]
        lectura["doble_lectura"] = {"iguales": firmas[0] == firmas[1],
                                    "cifras_1": len(firmas[0]), "cifras_2": len(firmas[1])}
        if firmas[0] != firmas[1] and lectura["resultado"] == "ok":
            lectura.update(resultado="lectura_dudosa", motivo="las dos lecturas no coinciden")

    if guardar and html_guardado is not None:
        destino = os.path.join(RAIZ, "paises", PAIS_VIGIA[pais], "lecturas", fecha)
        os.makedirs(destino, exist_ok=True)
        with open(os.path.join(destino, f"{fuente['id']}.html"), "w", encoding="utf-8") as f:
            f.write(html_guardado)
        with open(os.path.join(destino, f"{fuente['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(lectura, f, ensure_ascii=False, indent=1)
    return lectura


def fuentes_de(pais_vigia: str, solo: str | None = None, prioridad: int | None = 1) -> list[dict]:
    ruta = os.path.join(RAIZ, "paises", pais_vigia, "fuentes.json")
    datos = json.load(open(ruta, encoding="utf-8"))
    salida = []
    for f in datos["fuentes"]:
        if prioridad and f["prioridad"] != prioridad:
            continue
        if solo and f["id"] != solo:
            continue
        if f.get("modo_lectura") == "no_publica" or not f.get("url"):
            continue
        g = dict(f)
        g.setdefault("vigia", pais_vigia)
        g.setdefault("pais", VIGIA_PAIS[pais_vigia])
        salida.append(g)
    return salida


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lee las fuentes de precios de un vigía")
    ap.add_argument("--pais", required=True, choices=sorted(VIGIA_PAIS))
    ap.add_argument("--fuente")
    ap.add_argument("--fecha", default=dt.date.today().isoformat())
    ap.add_argument("--desde-html", help="lee un HTML ya guardado, sin red")
    ap.add_argument("--una-lectura", action="store_true", help="no repite la lectura")
    ap.add_argument("--no-guardar", action="store_true",
                    help="no escribe HTML ni JSON en el repositorio (prueba de humo)")
    args = ap.parse_args(argv)

    pais = VIGIA_PAIS[args.pais]
    if args.desde_html:
        fuente = {"id": args.fuente or os.path.basename(args.desde_html).rsplit(".", 1)[0],
                  "marca": None, "pais": pais, "vigia": args.pais, "url": args.desde_html,
                  "moneda_esperada": None, "receta": None}
        with open(args.desde_html, encoding="utf-8") as f:
            lec = leer_html(f.read(), fuente, args.fecha)
        print(json.dumps({k: lec[k] for k in ("fuente", "n_cifras", "monedas_leidas", "campana", "resultado")},
                         ensure_ascii=False))
        return 0

    fallas = 0
    for fuente in fuentes_de(args.pais, args.fuente):
        lec = leer_fuente(fuente, pais, args.fecha, doble=not args.una_lectura,
                          guardar=not args.no_guardar)
        ident = fuente["id"]
        print(f"[{pais}] {ident:<22} {lec['resultado']:<16} cifras={lec['n_cifras']:>3} "
              f"monedas={lec['monedas_leidas']} campana={lec['campana']} {lec['motivo'] or ''}")
        fallas += lec["resultado"] != "ok"
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())
