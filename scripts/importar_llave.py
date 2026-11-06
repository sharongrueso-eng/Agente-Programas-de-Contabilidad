#!/usr/bin/env python
"""Importa la llave de LiteLLM desde la variable de usuario de Windows al archivo local.

La llave no se escribe en la terminal ni en el chat: se lee de HKCU\\Environment, se
escribe en ~/.pdc/llm.env y solo se reporta su longitud y sus primeros caracteres.

    python scripts/importar_llave.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_LOCAL = Path.home() / ".pdc" / "llm.env"
VARIABLES = ("LITELLM_API_KEY", "OPENAI_API_KEY", "PDC_LLM_KEY")


def leer_de_windows(nombre: str) -> str:
    """Lee una variable de usuario de Windows sin depender de PowerShell."""
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as clave:
                valor, _ = winreg.QueryValueEx(clave, nombre)
                return str(valor).strip()
        except FileNotFoundError:
            return ""

    return os.environ.get(nombre, "").strip()


def main() -> int:
    llave = ""
    origen = ""
    for nombre in VARIABLES:
        valor = leer_de_windows(nombre)
        if valor:
            llave, origen = valor, nombre
            break

    if not llave:
        print("No encontré la llave en las variables de usuario de Windows.")
        print(f"Busqué: {', '.join(VARIABLES)}")
        print("Alternativa: escríbela a mano en", ENV_LOCAL)
        return 2

    print(f"origen  : {origen} (variable de usuario de Windows)")
    print(f"llave   : {len(llave)} caracteres, empieza por {llave[:3]}...")
    print(f"valor   : {llave[:3]}{'*' * max(0, len(llave) - 6)}{llave[-3:]}")

    ENV_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_LOCAL.exists():
        print(f"No existe {ENV_LOCAL}; créalo primero con OPENAI_BASE_URL.")
        return 2

    lineas = ENV_LOCAL.read_text(encoding="utf-8").splitlines()
    for indice, linea in enumerate(lineas):
        if linea.startswith("PDC_LLM_KEY="):
            lineas[indice] = f"PDC_LLM_KEY={llave}"
            break
    else:
        lineas.append(f"PDC_LLM_KEY={llave}")

    ENV_LOCAL.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"escrito : {ENV_LOCAL} (fuera del repositorio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
