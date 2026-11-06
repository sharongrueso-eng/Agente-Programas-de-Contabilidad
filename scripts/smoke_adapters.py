#!/usr/bin/env python
"""Read-only smoke test for the LiteLLM and WordPress adapters.

Run it once IT hands over the credentials, before the first real production run:

    python scripts/smoke_adapters.py

It reads these environment variables and never prints or logs their values:

    OPENAI_BASE_URL        LiteLLM gateway base URL (…/v1)
    PDC_LLM_KEY            virtual key for the producer
    PDC_MODEL_PRODUCER     model name for the producer
    PDC_WP_URL             https://programascontabilidad.com
    PDC_WP_TOKEN           WordPress application password or API token
    PDC_WP_USER            WordPress user (default: leandro)

Without every variable it exits 2 and names what is missing, without touching the
network. The WordPress check is a read-only lookup; the model check asks for a single
short word so it costs a handful of tokens.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.adapters import LiteLlmClient, WordPressClient  # noqa: E402

REQUIRED = {
    "OPENAI_BASE_URL": "URL del LiteLLM de Alegra",
    "PDC_LLM_KEY": "llave virtual del productor",
    "PDC_MODEL_PRODUCER": "modelo del productor",
    "PDC_WP_URL": "URL de WordPress",
    "PDC_WP_TOKEN": "token de API de WordPress",
}


def main() -> int:
    missing = [f"{name} ({why})" for name, why in REQUIRED.items() if not os.environ.get(name)]
    if missing:
        print("Faltan variables de entorno; no se probó ninguna conexión:")
        for item in missing:
            print(f"  - {item}")
        return 2

    failures = 0

    print("1/2 LiteLLM")
    try:
        llm = LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ["PDC_MODEL_PRODUCER"],
            max_tokens=8,
            timeout=60,
        )
        answer = llm.complete(
            [{"role": "user", "content": "Responde solo con la palabra: ok"}]
        )
        print(f"    respuesta recibida ({len(answer)} caracteres)")
    except Exception as error:  # noqa: BLE001 - the point is to report, not to crash
        failures += 1
        print(f"    FALLÓ: {error}")

    print("2/2 WordPress (solo lectura)")
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

    print()
    print("Resultado:", "todo responde" if failures == 0 else f"{failures} conexión(es) fallaron")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
