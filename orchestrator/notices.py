"""Avisos para el espacio de Chat.

Los textos son plantillas fijas del código: no los redacta un modelo. Un aviso que
cambia de redacción cada día no se puede auditar, y el equipo deja de leerlo.
"""

from __future__ import annotations

import json
from typing import Any

from orchestrator.adapters import HttpTransport, UrllibTransport

TEMPLATES: dict[str, str] = {
    "chequeo_fallido": (
        "⚠️ El chequeo de las 5:40 no pasó: {detalle}.\n"
        "El día no arranca y ningún slot se produce."
    ),
    "corrida_fallida": (
        "⚠️ Corrida {task_id} · {estado}\n"
        "Motivo: {motivo}\n"
        "Paso donde se detuvo: {paso}\n"
        "No se publicó nada. La evidencia queda en {carpeta}"
    ),
    "borrador_listo": (
        "📝 Borrador listo · {pais} · {formato}\n"
        "Keyword: {keyword}\n"
        "Post ID: {post_id}\n"
        "Firma: Leandro · pendiente de revisión antes de publicar"
    ),
    "slot_publicado": (
        "✅ Slot {slot} · {pais} · {formato} · PUBLICADA\n"
        "Keyword: {keyword}\n"
        "URL: {url}"
    ),
    "bloqueo": (
        "🚫 Bloqueo · regla {regla}\n"
        "Motivo: {motivo}\n"
        "La pieza queda como borrador y el sistema sigue con el siguiente slot."
    ),
    "reporte_diario": (
        "📊 Reporte del día\n"
        "Publicadas: {publicadas} · Bloqueadas: {bloqueadas}\n"
        "Acumulado de la semana: {semana}"
    ),
    "registro_vencido": (
        "📋 El registro de datos de {marca} lleva {dias} días sin revisar.\n"
        "Hasta actualizarlo, el juez no tiene contra qué contrastar sus cifras."
    ),
    "sin_reporte": (
        "🔕 El agente de PdC no reportó el {fecha}.\n"
        "Revisar Coolify y el estado de la instancia."
    ),
}


def render(kind: str, **fields: Any) -> str:
    """Devuelve el aviso con sus datos. Falla si falta un campo o el tipo no existe."""
    template = TEMPLATES[kind]
    return template.format(**fields)


def send(
    webhook_url: str,
    text: str,
    *,
    transport: HttpTransport | None = None,
    timeout: float = 30.0,
) -> int:
    """Publica el aviso como la app «Agente PdC» y devuelve el estado HTTP."""
    client = transport or UrllibTransport(timeout=timeout)
    status, raw = client.request(
        "POST",
        webhook_url,
        headers={"Content-Type": "application/json"},
        body=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
    )

    if status >= 400:
        preview = raw.decode("utf-8", "replace")[:300]
        raise RuntimeError(f"el webhook de Chat respondió {status}: {preview}")

    return status
