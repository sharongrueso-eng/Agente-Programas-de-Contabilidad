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


SEMAFORO = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}
BANDERA = {"CO": "🇨🇴", "MX": "🇲🇽", "CR": "🇨🇷", "DO": "🇩🇴"}


def semaforo(*, criticos_fallidos: int, importantes_fallidos: int, observaciones: int = 0) -> str:
    """Un crítico fallido es rojo; una observación del juez, amarillo."""
    if criticos_fallidos:
        return "rojo"
    if importantes_fallidos or observaciones:
        return "amarillo"
    return "verde"


def aviso_de_pieza(
    *,
    titulo: str,
    slug: str,
    pais: str,
    nuevo: bool,
    url_edicion: str,
    impresiones: int = 0,
    ctr: float = 0.0,
    posicion: float = 0.0,
    clics_potenciales: int = 0,
    criticos_ok: int = 0,
    criticos_total: int = 0,
    importantes_ok: int = 0,
    importantes_total: int = 0,
    estado: str = "amarillo",
    observaciones: int = 0,
    titulo_seo: str = "",
    meta: str = "",
    keyword: str = "",
    schema: str = "BlogPosting",
    motivo: str = "",
    advertencias: tuple[str, ...] = (),
) -> str:
    """El aviso que se quiere leer: qué se tocó, por qué y dónde se revisa.

    Se compone aquí y no lo redacta el modelo, para que las cifras sean las de GSC y el formato
    sea el mismo en todas las corridas.
    """
    if nuevo:
        cabecera = f"{SEMAFORO[estado]} {BANDERA.get(pais, pais)} {pais} · Artículo nuevo publicado"
        linea_estado = "Estado: PUBLICADO — contenido nuevo, URL nueva"
        cierre = (
            f"✅ Artículo nuevo en el blog. Es la primera pieza sobre {keyword or 'el tema'} "
            f"en este mercado, así que no sustituye a nada."
        )
    else:
        cabecera = f"{SEMAFORO[estado]} {BANDERA.get(pais, pais)} {pais} · Artículo actualizado en vivo"
        linea_estado = "Estado: PUBLICADO — el contenido nuevo ya está en la URL de siempre"
        cierre = (
            f"✅ Actualización aplicada al artículo vivo, sin URL nueva. El slug {slug} se "
            "conserva y la versión anterior queda en el historial de revisiones de WordPress, "
            "restaurable desde ahí."
        )

    por_que = motivo or (
        f"· GSC: {impresiones:,} impresiones · CTR {ctr:.2%} · pos {posicion:.1f} · "
        f"potencial ≈ {clics_potenciales:,} clics/mes"
    ).replace(",", ".")

    lineas = [
        cabecera,
        "",
        titulo,
        f"Slug: {slug}",
        linea_estado,
        f"Semáforo QA: {SEMAFORO[estado]} {estado.upper()} — "
        + (
            "sin observaciones"
            if estado == "verde"
            else f"{observaciones} observación(es) del juez"
            if observaciones
            else "hay que revisar puntos importantes"
        ),
        "",
        "Por qué este artículo y no otro:",
        por_que,
        "",
        f"Control de calidad: {criticos_ok}/{criticos_total} críticos · "
        f"{importantes_ok}/{importantes_total} importantes",
        "",
        cierre,
        "",
        f"Editar: {url_edicion}",
    ]
    if advertencias:
        lineas += ["", "Advertencias (no impiden publicar):"]
        lineas += [f"· {aviso[:120]}" for aviso in advertencias[:5]]

    if titulo_seo or meta:
        lineas += [
            "",
            "",
            "SEO escrito en la API de WordPress (automático, nada que pegar a mano):",
            f"Título SEO: {titulo_seo}" if titulo_seo else "",
            f"Meta descripción: {meta}" if meta else "",
            f"Focus keyword: {keyword}" if keyword else "",
            f"Schema: {schema}",
        ]
    return "\n".join(linea for linea in lineas if linea != "" or True)
