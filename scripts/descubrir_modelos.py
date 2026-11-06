#!/usr/bin/env python
"""Descubre qué modelos expone el gateway de LiteLLM con la llave cargada.

    python scripts/descubrir_modelos.py

Lee `~/.pdc/llm.env` (o la ruta que pases con --env). No imprime la llave en ningún
momento: solo su longitud, para que puedas comprobar que quedó pegada completa.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENV = Path.home() / ".pdc" / "llm.env"


def cargar_env(path: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not path.exists():
        return valores

    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        valores[clave.strip()] = valor.strip().strip('"').strip("'")

    return valores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    args = parser.parse_args()

    env = {**cargar_env(args.env), **{k: v for k, v in os.environ.items() if v}}
    base = env.get("OPENAI_BASE_URL", "").rstrip("/")
    key = env.get("PDC_LLM_KEY", "")

    faltan = [n for n, v in (("OPENAI_BASE_URL", base), ("PDC_LLM_KEY", key)) if not v]
    if faltan:
        print(f"Faltan en {args.env}: {', '.join(faltan)}")
        print("Abre el archivo, pega el valor y vuelve a correr el script.")
        return 2

    print(f"gateway : {base}")
    print(f"llave   : {len(key)} caracteres (no se imprime el valor)")
    print()

    peticion = urllib.request.Request(
        f"{base}/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            cuerpo = respuesta.read().decode("utf-8", "replace")
            estado = respuesta.status
    except urllib.error.HTTPError as error:
        print(f"El gateway respondió {error.code}.")
        print(error.read().decode("utf-8", "replace")[:300])
        print()
        print("401 = llave inválida o revocada · 403 = la llave no tiene permiso")
        print("404 = la URL base no termina en /v1 o el endpoint /models no está expuesto")
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"No se pudo conectar: {error}")
        return 1

    print(f"HTTP {estado}")
    try:
        datos = json.loads(cuerpo)
    except json.JSONDecodeError:
        print("Respuesta no JSON; primeros 300 caracteres:")
        print(cuerpo[:300])
        return 1

    modelos = [m.get("id") for m in datos.get("data", []) if m.get("id")]
    if not modelos:
        print("El gateway no devolvió modelos para esta llave.")
        return 1

    print(f"modelos disponibles ({len(modelos)}):")
    for modelo in sorted(modelos):
        print(f"  {modelo}")

    print()
    print("Elige uno para redactar y otro de otra familia para juzgar, y escríbelos en")
    print(f"{args.env} como PDC_MODEL_PRODUCER y PDC_MODEL_JUDGE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
