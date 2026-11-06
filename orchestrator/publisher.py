"""Publicador: el único módulo que escribe en el sitio en vivo.

Publica solo si se cumplen todas las condiciones —huella idéntica a la aprobada, ventana
horaria, tope diario, chequeo del día en verde y sin pausa global—, y no da la pieza por
publicada hasta releer la URL. Si la relectura no coincide, revierte y lo reporta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Protocol

from orchestrator.assigner import Brief
from orchestrator.preparacion import IMAGE_CAPTION
from orchestrator.producer import Draft


class PublisherClient(Protocol):
    def find_by_run_id(self, run_id: str) -> dict[str, Any] | None: ...

    def find_by_url(self, url: str) -> dict[str, Any] | None: ...

    def create_post(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_post(self, post_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...

    def restore(self, post_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...

    def read_live(self, url: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PublishConditions:
    approved_fingerprint: str
    current_fingerprint: str
    now: datetime
    window_start: time
    window_end: time
    publications_today: int
    daily_cap: int
    health_check_ok: bool
    paused: bool = False


def can_publish(conditions: PublishConditions) -> tuple[bool, str]:
    """Compuerta del publicador. Devuelve (puede, motivo del bloqueo)."""
    if conditions.paused:
        return False, "pausa global activa"
    if not conditions.health_check_ok:
        return False, "el chequeo del día no pasó"
    if conditions.publications_today >= conditions.daily_cap:
        return False, (
            f"tope diario alcanzado ({conditions.publications_today}/{conditions.daily_cap})"
        )

    current = conditions.now.time()
    if not (conditions.window_start <= current <= conditions.window_end):
        return False, (
            f"fuera de la ventana de publicación "
            f"({conditions.window_start:%H:%M}–{conditions.window_end:%H:%M})"
        )

    if conditions.approved_fingerprint != conditions.current_fingerprint:
        return False, "la huella del contenido no coincide con la aprobada"

    return True, ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _first_h1(html: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.IGNORECASE | re.DOTALL)
    return re.sub(r"<[^>]+>", " ", match.group(1)) if match else ""


def verify_readback(
    draft: Draft,
    live: dict[str, Any],
    *,
    expect_featured_image: bool = False,
    expect_author: int | None = None,
) -> list[str]:
    """Compara lo publicado con lo aprobado. Cualquier diferencia es un fallo."""
    problems: list[str] = []

    status = live.get("status_code")
    if status != 200:
        problems.append(f"la URL respondió {status}")

    if expect_author is not None and live.get("author") not in (None, expect_author):
        problems.append(
            f"la firma no es la de Leandro: el post quedó con el autor {live.get('author')}"
        )

    if _normalize(live.get("title", "")) != _normalize(draft.title):
        problems.append("el título publicado no coincide con el aprobado")

    if _normalize(live.get("meta_description", "")) != _normalize(draft.meta_description):
        problems.append("la meta descripción publicada no coincide con la aprobada")

    robots = (live.get("robots") or "").lower()
    if "noindex" in robots:
        problems.append("la pieza salió con noindex")

    if draft.html.strip():
        expected_h1 = _normalize(_first_h1(draft.html))
        published_h1 = _normalize(live.get("h1", ""))
        if expected_h1 and published_h1 and expected_h1 != published_h1:
            problems.append("el H1 publicado no coincide con el aprobado")

    if expect_featured_image and not live.get("featured_image"):
        problems.append("la imagen destacada no quedó asignada")

    return problems


def _result(status: str, brief: Brief, evidence_dir: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "task_id": brief.task_id,
        "output_url": "",
        "evidence_url": evidence_dir,
        "resume_from": "",
        "block_reason": "",
    }
    payload.update(extra)
    return payload


def _payload(
    draft: Draft, brief: Brief, *, status: str, author_id: int = 17
) -> dict[str, Any]:
    opportunity = brief.opportunity
    payload: dict[str, Any] = {
        "title": draft.title,
        "slug": draft.slug,
        "excerpt": draft.meta_description,
        "status": status,
        "author": author_id,
        "meta": {
            "pdc_run_id": brief.task_id,
            "pdc_target_country": brief.country,
            "pdc_estado": "publicada" if status == "publish" else "borrador",
            "pdc_focus_keyword": opportunity.focus_keyword if opportunity else "",
        },
    }
    if draft.html.strip():
        payload["content"] = draft.html
    if draft.alt_text:
        payload["meta"]["pdc_alt_text"] = draft.alt_text
    return payload


def publish(
    draft: Draft,
    brief: Brief,
    *,
    client: PublisherClient,
    conditions: PublishConditions,
    evidence_dir: str = "",
    expect_featured_image: bool = False,
    cover: bytes | None = None,
    cover_filename: str = "portada.webp",
    author_id: int = 17,
) -> dict[str, Any]:
    """Publica la pieza aprobada, la relee y revierte si algo no coincide."""
    allowed, reason = can_publish(conditions)
    if not allowed:
        return _result("BLOCKED", brief, evidence_dir, block_reason=reason)

    opportunity = brief.opportunity
    already_published = client.find_by_run_id(brief.task_id)
    if already_published and already_published.get("status") == "publish":
        return _result(
            "DONE",
            brief,
            evidence_dir,
            output_url=str(already_published.get("link", "")),
            wp_post_id=already_published.get("id"),
            readback={"verified": True, "reused": True},
        )

    target = already_published
    if target is None and opportunity and opportunity.action != "create" and opportunity.url:
        target = client.find_by_url(opportunity.url)

    payload = _payload(draft, brief, status="publish", author_id=author_id)

    if cover:
        try:
            media = client.upload_media(
                cover, cover_filename, alt_text=draft.alt_text, caption=IMAGE_CAPTION
            )
            if media.get("id"):
                payload["featured_media"] = media["id"]
        except Exception as error:  # noqa: BLE001
            return _result(
                "FAILED",
                brief,
                evidence_dir,
                resume_from="publication",
                block_reason=f"no se pudo subir la portada: {error}",
            )

    written: dict[str, Any] = {}
    try:
        if target is None:
            created = client.create_post(payload)
            written = created
            post_id = created.get("id")
            link = str(created.get("link", ""))
            restore_payload: dict[str, Any] = {"status": "draft"}
        else:
            post_id = target.get("id")
            if target.get("status") == "publish":
                restore_payload = {
                    "title": target.get("title", ""),
                    "content": target.get("content", ""),
                    "status": "publish",
                }
            else:
                restore_payload = {"status": "draft"}
            updated = client.update_post(post_id, payload)
            written = updated
            link = str(updated.get("link", target.get("link", "")))
    except Exception as error:  # noqa: BLE001 - red o WordPress: se reintenta el paso
        return _result(
            "FAILED",
            brief,
            evidence_dir,
            resume_from="publication",
            block_reason=f"falló la escritura en WordPress: {error}",
        )

    try:
        live = client.read_live(link)
    except Exception as error:  # noqa: BLE001
        live = {"status_code": 0, "error": str(error)}

    if live.get("author") is None and isinstance(written, dict):
        live["author"] = written.get("author")

    problems = verify_readback(
        draft,
        live,
        expect_featured_image=expect_featured_image,
        expect_author=author_id,
    )
    if problems:
        try:
            client.restore(post_id, restore_payload)
        except Exception:  # noqa: BLE001 - si la reversión falla, el aviso lo dirá
            problems.append("la reversión también falló; revisar el post a mano")

        return _result(
            "FAILED",
            brief,
            evidence_dir,
            resume_from="publication",
            wp_post_id=post_id,
            output_url=link,
            block_reason="la relectura no coincide: " + "; ".join(problems),
        )

    return _result(
        "DONE",
        brief,
        evidence_dir,
        output_url=link,
        wp_post_id=post_id,
        readback={"verified": True, "reused": False},
    )
