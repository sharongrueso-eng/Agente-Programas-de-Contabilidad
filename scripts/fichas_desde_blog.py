"""Busca datos de competidores en artículos ya publicados del blog.

Es una fuente secundaria: el precio que aparece en un post puede ser de la fecha del post, no
de hoy. Por eso se marca como tal y se revisa contra la landing antes de darlo por bueno.
"""

from __future__ import annotations

import json
import re
import urllib.request
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.competidores import cargar
from orchestrator.mercado import pais_de_pagina
from orchestrator.sitemap import urls_del_sitio

AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PRECIO = re.compile(
    r"(?:RD\$|US\$|COP|MXN|CRC|\$)\s?\d[\d.,]*|\d[\d.,]{2,}\s?(?:COP|MXN|CRC|pesos|dólares)",
    re.IGNORECASE,
)


def texto(url: str, timeout: float = 25.0) -> str:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as r:
            crudo = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    limpio = re.sub(r"<script.*?</script>|<style.*?</style>", " ", crudo, flags=re.S | re.I)
    return " ".join(re.sub(r"<[^>]+>", " ", limpio).split())


def main() -> int:
    urls = urls_del_sitio(maximo=40)
    por_mercado: dict[str, list[str]] = {}
    for url in urls:
        mercado = pais_de_pagina(url, [], "CO").pais
        por_mercado.setdefault(mercado, []).append(url)

    salida: dict[str, dict] = {}
    for pais in ("MX", "CR", "DO"):
        relacion = cargar(pais)
        hallazgos: dict[str, dict] = {}
        for url in por_mercado.get(pais, [])[:8]:
            cuerpo = texto(url)
            if not cuerpo:
                continue
            for marca in relacion.competidores:
                if marca.lower() not in cuerpo.lower():
                    continue
                entrada = hallazgos.setdefault(marca, {"urls": [], "precios": []})
                entrada["urls"].append(url)
                ventana = cuerpo.lower().find(marca.lower())
                trozo = cuerpo[max(0, ventana - 300) : ventana + 600]
                for precio in PRECIO.findall(trozo):
                    limpio = precio.strip()
                    if limpio not in entrada["precios"]:
                        entrada["precios"].append(limpio)
        salida[pais] = hallazgos
        print(f"\n=== {pais} · {len(por_mercado.get(pais, []))} urls revisadas")
        for marca, datos in hallazgos.items():
            print(f"  {marca}: {len(datos['urls'])} posts · precios: {datos['precios'][:6] or 'ninguno'}")

    destino = Path("state") / "fichas-blog.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps({"fecha": date.today().isoformat(), "datos": salida}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\nguardado en {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
