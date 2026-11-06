#!/usr/bin/env python
"""Smoke test de credenciales: LiteLLM, WordPress, Search Console y Chat.

    python scripts/smoke_adapters.py

Lee estas variables de entorno y no imprime ni registra sus valores:

    OPENAI_BASE_URL, PDC_LLM_KEY, PDC_MODEL_PRODUCER   LiteLLM
    PDC_WP_URL, PDC_WP_TOKEN, PDC_WP_USER               WordPress
    GSC_CUENTA_SERVICIO_JSON o GSC_ACCESS_TOKEN         Search Console
    PDC_CHAT_WEBHOOK_URL                                Google Chat

Sin las obligatorias sale con código 2 y las nombra, sin tocar la red. Solo escribe una
cosa en los sistemas reales: un mensaje de prueba en el espacio de Chat.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.adapters import LiteLlmClient, WordPressClient  # noqa: E402
from orchestrator.gsc_api import GscClient  # noqa: E402
from orchestrator.notices import send  # noqa: E402

REQUIRED = {
    "OPENAI_BASE_URL": "URL del LiteLLM de Alegra",
    "PDC_LLM_KEY": "llave virtual del productor",
    "PDC_MODEL_PRODUCER": "modelo del productor",
    "PDC_WP_URL": "URL de WordPress",
    "PDC_WP_TOKEN": "token de API de WordPress",
    "PDC_CHAT_WEBHOOK_URL": "webhook del espacio de Chat",
}


def gsc_credentials():
    """Devuelve un proveedor de token para Search Console, o None si no se puede."""
    token = os.environ.get("GSC_ACCESS_TOKEN")
    if token:
        return lambda: token

    blob = os.environ.get("GSC_CUENTA_SERVICIO_JSON")
    if not blob:
        return None

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ModuleNotFoundError:
        return None

    info = json.loads(blob)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )

    def provider() -> str:
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token

    return provider


def main() -> int:
    missing = [f"{name} ({why})" for name, why in REQUIRED.items() if not os.environ.get(name)]
    if missing:
        print("Faltan variables de entorno; no se probó ninguna conexión:")
        for item in missing:
            print(f"  - {item}")
        return 2

    failures = 0

    print("1/4 LiteLLM")
    try:
        llm = LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ["PDC_MODEL_PRODUCER"],
            max_tokens=8,
            timeout=60,
        )
        answer = llm.complete([{"role": "user", "content": "Responde solo con la palabra: ok"}])
        print(f"    respuesta recibida ({len(answer)} caracteres)")
    except Exception as error:  # noqa: BLE001 - se reporta, no se cae
        failures += 1
        print(f"    FALLÓ: {error}")

    print("2/4 WordPress (solo lectura)")
    try:
        wp = WordPressClient(
            base_url=os.environ["PDC_WP_URL"],
            token=os.environ["PDC_WP_TOKEN"],
            username=os.environ.get("PDC_WP_USER", "leandro"),
        )
        probe = f"smoke-{int(time.time())}"
        found = wp.find_by_run_id(probe)
        print(f"    consulta correcta; coincidencias para {probe}: {0 if found is None else 1}")
    except Exception as error:  # noqa: BLE001
        failures += 1
        print(f"    FALLÓ: {error}")

    print("3/4 Search Console")
    provider = gsc_credentials()
    if provider is None:
        print("    NO VERIFICABLE: falta GSC_CUENTA_SERVICIO_JSON con google-auth instalado,")
        print("    o un GSC_ACCESS_TOKEN ya emitido. No se presenta como correcto.")
    else:
        try:
            client = GscClient(
                os.environ.get("GSC_SITE", "sc-domain:programascontabilidad.com"),
                provider,
            )
            day = date.today() - timedelta(days=3)
            rows = client.query(day, day, dimensions=("query",))
            print(f"    consulta correcta; filas para {day.isoformat()}: {len(rows)}")
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f"    FALLÓ: {error}")

    print("4/4 Google Chat (envía un mensaje de prueba)")
    try:
        status = send(
            os.environ["PDC_CHAT_WEBHOOK_URL"],
            "Prueba de conexión del agente PdC. Si ves esto, el webhook está bien.",
        )
        print(f"    mensaje aceptado ({status})")
    except Exception as error:  # noqa: BLE001
        failures += 1
        print(f"    FALLÓ: {error}")

    print()
    print("Resultado:", "todo responde" if failures == 0 else f"{failures} conexión(es) fallaron")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
