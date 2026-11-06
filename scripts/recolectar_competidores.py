#!/usr/bin/env python
"""Recolecta precios y funcionalidades de las landings de los competidores.

    python scripts/recolectar_competidores.py            # todos los del catálogo
    python scripts/recolectar_competidores.py --marca Siigo

El modelo propone la extracción; `orchestrator.recolector` descarta todo lo que no aparezca
literalmente en la página. Cada lectura queda fechada y con su historial de cambios.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import LiteLlmClient  # noqa: E402
from orchestrator.recolector import recolectar  # noqa: E402

CATALOGO = RAIZ / "datos" / "competidores.json"
DESTINO = RAIZ / "datos" / "herramientas"

ESQUEMA = """Devuelve SOLO este JSON, sin texto antes ni después:
{
  "product": "nombre del producto o suite",
  "plans": [{"name": "...", "price": "solo el número tal como aparece", "currency": "COP|MXN|USD|CRC|DOP", "period": "mes|año"}],
  "features": ["funcionalidad tal como la nombra la página"],
  "notes": "aclaraciones, por ejemplo si un plan se cotiza"
}
Reglas: copia los precios y los NOMBRES DE PLAN exactamente como aparecen en el texto, sin
redondear, sin convertir y sin parafrasear el nombre. El nombre debe ser el que el competidor
usa, no una descripción tuya.
Si un plan no muestra precio, deja "price" vacío en vez de inventarlo."""


def descargar(url: str) -> str:
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "es-CO,es;q=0.9",
        },
    )
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        return respuesta.read().decode("utf-8", "replace")


def hacer_extractor(llm: LiteLlmClient):
    def extraer(texto: str, marca: str, pais: str) -> dict:
        mensajes = [
            {"role": "system", "content": ESQUEMA},
            {
                "role": "user",
                "content": f"Marca: {marca}\nPaís: {pais}\n\nTexto de la página:\n{texto[:12000]}",
            },
        ]
        crudo = llm.complete(mensajes).strip()
        if crudo.startswith("```"):
            crudo = crudo.split("```")[1]
            crudo = crudo.split("\n", 1)[1] if "\n" in crudo else crudo
        return json.loads(crudo)

    return extraer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marca", default="", help="solo esta marca")
    args = parser.parse_args()

    env: dict[str, str] = {}
    for archivo in ("llm.env", "mcp.env"):
        ruta = Path.home() / ".pdc" / archivo
        if not ruta.exists():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                clave, _, valor = linea.partition("=")
                env[clave.strip()] = valor.strip()

    import os

    for clave, valor in env.items():
        os.environ.setdefault(clave, valor)

    if not CATALOGO.exists():
        print(f"falta el catálogo {CATALOGO}")
        return 2

    marcas = json.loads(CATALOGO.read_text(encoding="utf-8"))
    if args.marca:
        marcas = [m for m in marcas if m["brand"].lower() == args.marca.lower()]
    if not marcas:
        print("no hay marcas que recolectar con ese filtro")
        return 2

    llm = LiteLlmClient(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["PDC_LLM_KEY"],
        model=os.environ.get("PDC_MODEL_EXTRACTOR", "deepseek/deepseek-v4-flash"),
        max_tokens=8000,
        timeout=180,
    )
    extraer = hacer_extractor(llm)

    for marca in marcas:
        print(f"\n== {marca['brand']} · {marca['country']} · {marca['url']}")
        try:
            salida = recolectar(
                brand=marca["brand"],
                country=marca["country"],
                url=marca["url"],
                descargar=descargar,
                extraer=extraer,
                carpeta=DESTINO,
            )
        except Exception as error:  # noqa: BLE001
            print(f"   FALLÓ: {type(error).__name__}: {error}")
            continue

        registro = salida["registro"]
        print(f"   planes: {len(registro['plans'])} | funcionalidades: {len(registro['features'])}")
        for plan in registro["plans"]:
            precio = f"{plan['price']} {plan['currency']}" if plan["price"] else "sin precio publicado"
            print(f"     - {plan['name']:<22} {precio}")
        if registro["descartado"]:
            print(f"   descartado por no estar en la página: {len(registro['descartado'])}")
            for item in registro["descartado"][:5]:
                print(f"     x {item}")
        for cambio in salida["cambios"]:
            print(f"   cambio: {cambio}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
