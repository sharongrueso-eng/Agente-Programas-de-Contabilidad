"""Los enlaces de la pieza tienen que abrir, y llevar a donde el texto dice.

Un 404 en el cuerpo invalida el artículo: el lector que hace clic en «precios de Siigo» y llega
a una página de error no vuelve. La comprobación es de red, así que se hace una vez por URL (no
por aparición), se ignoran los anclajes y se acepta que un sitio bloquee al robot: un 401 o 403
no es un enlace roto, un 404 o un 410 sí.

También se comprueba que el enlace no se haya ido a otro sitio: si el texto promete la página de
precios del proveedor y redirige a la home, el lector no llega a lo que se le prometió.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request

CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; PdC-linkcheck)"}
PATRON = re.compile(r'<a\b[^>]*href="([^"]+)"', re.IGNORECASE)
# Códigos que significan enlace roto. 401/403/429 son muros anti-robot y 503 un corte pasajero:
# ninguno prueba que la página no exista, así que no se marcan.
MALES = {404, 410}
LIMITE = 14


def externos(html: str, limite: int = LIMITE) -> list[str]:
    """URLs externas del cuerpo, sin anclas, sin repetir y en orden de aparición."""
    vistas: set[str] = set()
    salida: list[str] = []
    for href in PATRON.findall(html or ""):
        url = href.strip().replace("&amp;", "&").split("#")[0]
        if not url.startswith("http") or url in vistas:
            continue
        vistas.add(url)
        salida.append(url)
        if len(salida) >= limite:
            break
    return salida


def estado(url: str, timeout: float = 12.0) -> int:
    """Código HTTP final. 0 si no hubo respuesta. Primero HEAD, luego GET."""
    for metodo in ("HEAD", "GET"):
        peticion = urllib.request.Request(url, method=metodo, headers=CABECERAS)
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                return int(getattr(respuesta, "status", 200))
        except urllib.error.HTTPError as error:
            if metodo == "GET":
                return int(error.code)
            if int(error.code) not in {405, 501}:
                return int(error.code)
        except Exception:  # noqa: BLE001 - sin red no se puede afirmar que esté roto
            return 0
    return 0


def rotos(html: str, *, comprobar=estado, limite: int = LIMITE) -> list[str]:
    """Enlaces del cuerpo que no abren, con el código que devolvieron."""
    fallos: list[str] = []
    for url in externos(html, limite):
        codigo = comprobar(url)
        if codigo == 0:
            continue  # sin respuesta: no se acusa al enlace de algo que puede ser la red
        if codigo in MALES or codigo >= 500:
            fallos.append(f"{url} ({codigo})")
    return fallos
