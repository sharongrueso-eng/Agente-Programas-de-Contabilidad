"""Runner: la corrida completa de una pieza, con estado y reanudación.

Encadena producción → validación → juez → corrección → publicación. Cada paso escribe su
resultado y su checkpoint antes de pasar al siguiente, así que un fallo de red se retoma
desde donde se quedó y no vuelve a gastar tokens en lo que ya estaba bien.

`dry_run` recorre toda la cadena menos la escritura en el sitio.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from orchestrator.assigner import Brief
from orchestrator.corrector import correct
from orchestrator.judge import judge
from orchestrator.link_pass import corregir_enlaces
from orchestrator.mcp_publish import publicar as publicar_mcp
from orchestrator.preparacion import (
    IMAGE_CAPTION,
    build_image_prompt,
    comprimir_portada,
    generate_image,
)
from orchestrator.producer import Draft, fingerprint, produce, requires_body
from orchestrator.reparacion import (
    agregar_enlaces_internos,
    ajustar_meta,
    completar_captions,
    completar_cta,
    normalizar_slug,
)
from orchestrator.presentacion import presentar
from orchestrator.publisher import PublishConditions, publish
from orchestrator.validator import (
    limpiar_artefactos,
    sanear_afirmaciones,
    BLOQUEADO,
    CORREGIR,
    PASS,
    ValidationRules,
    bloqueantes,
    sanear_cifras,
    validate,
)

ORDER = ("production", "validation", "judge", "publication")
MAX_CYCLES = 3


class LockHeld(RuntimeError):
    """Ya hay una corrida en curso."""


class RunLock:
    """Candado de exclusión: dos corridas no pueden pisarse."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise LockHeld(f"ya hay una corrida en curso ({self.path})") from error
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class RunState:
    root: Path
    task_id: str

    def __post_init__(self) -> None:
        self.dir = Path(self.root) / self.task_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: Any) -> None:
        (self.dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def load(self, name: str, default: Any = None) -> Any:
        path = self.dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def checkpoint(self, last_step: str, resume_from: str = "", **extra: Any) -> None:
        self.save(
            "checkpoint.json",
            {"last_step": last_step, "resume_from": resume_from, **extra},
        )

    @property
    def resume_from(self) -> str:
        data = self.load("checkpoint.json", {}) or {}
        value = data.get("resume_from", "")
        return value if value in ORDER else ""


@dataclass
class Deps:
    producer: Any
    judge: Any
    corrector: Any
    wp: Any
    publisher: Any
    skill: str = ""
    skill_bloques: str = ""
    legal: str = ""
    manual: str = ""
    registry: str = ""
    evidence_of_testing: bool = False
    image: Any = None
    fallback_image: bytes = b""
    author_id: int = 17
    image_max_kb: int = 300
    mcp: Any = None
    mapa: Any = None
    avisar: Any = None
    solo_borrador: bool = False
    urls_internas: Any = None
    post_existente: int | None = None
    subir_media: Any = None
    permitir_vivo: bool = False
    verificar_publicacion: Any = None
    brands_available: int | None = None
    publicar_con_observaciones: bool = False
    dominio: str = "programascontabilidad.com"


def _avisar_publicacion(deps: Deps, brief: Brief, resultado: dict[str, Any]) -> None:
    """El aviso sale en cuanto la pieza queda publicada, no al cierre del día."""
    if deps.avisar is None:
        return
    try:
        deps.avisar(
            "slot_publicado",
            {
                "slot": brief.slot,
                "pais": brief.country,
                "formato": brief.format.capitalize(),
                "keyword": brief.opportunity.focus_keyword if brief.opportunity else "",
                "url": resultado.get("output_url", ""),
            },
        )
    except Exception:  # noqa: BLE001 - un aviso caído no invalida la publicación
        pass


def _draft_to_dict(draft: Draft) -> dict[str, str]:
    return asdict(draft)


def _reconciliar_titulo(
    draft: Draft, brief: Brief, state: RunState, steps: list[dict[str, Any]]
) -> Draft:
    """Que el título anuncie el elenco que el cuerpo trata, por código y sin gastar llamadas.

    Se hace antes de validar y otra vez después de cada corrección: el corrector puede recortar
    o ampliar el elenco, y el título tiene que seguir contando lo mismo que el artículo. El slug
    no se toca, así que en un reencauche la URL del post vivo no cambia.
    """
    from .titulo import reconciliar

    nuevo, motivo = reconciliar(draft, brief)
    if nuevo.title == draft.title:
        return draft
    state.save("borrador.json", _draft_to_dict(nuevo))
    steps.append({"step": "estructura", "status": "DONE", "accion": "titulo", "detalle": motivo})
    return nuevo


def _contract(
    status: str,
    brief: Brief,
    state: RunState,
    steps: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "task_id": brief.task_id,
        "output_url": "",
        "evidence_url": str(state.dir),
        "resume_from": "",
        "block_reason": "",
        "steps": steps,
    }
    payload.update(extra)
    return payload


def _blocking_codes(verdict: Any) -> str:
    codes = [control.code for control in getattr(verdict, "blocking", ())]
    details = [f"{c.code}: {c.detail}" for c in getattr(verdict, "blocking", ()) if c.detail]
    return "; ".join(details) or ", ".join(codes)


def run(
    brief: Brief,
    *,
    deps: Deps,
    state: RunState,
    conditions: PublishConditions,
    dry_run: bool = True,
    max_cycles: int = MAX_CYCLES,
    presentar_pieza: bool = False,
) -> dict[str, Any]:
    """Ejecuta la corrida y devuelve el contrato con los pasos recorridos."""
    steps: list[dict[str, Any]] = []
    resume = state.resume_from
    start = ORDER.index(resume) if resume else 0

    draft_data = state.load("borrador.json")
    draft = Draft(**draft_data) if draft_data else None

    if start <= ORDER.index("production"):
        result = produce(
            brief,
            llm=deps.producer,
            wp=deps.wp,
            skill=deps.skill,
            legal=deps.legal,
            evidence_dir=str(state.dir),
        )
        steps.append({"step": "production", "status": result["status"]})
        if result["status"] != "DONE":
            return _contract(
                result["status"],
                brief,
                state,
                steps,
                resume_from=result.get("resume_from", ""),
                block_reason=result.get("block_reason", ""),
            )
        draft_data = dict(result.get("draft") or {})
        # La pieza se presenta aquí: tarjetas, tabla de criterios, panel de perfiles y firma.
        if presentar_pieza:
            draft_data["html"] = presentar(draft_data.get("html", ""), pais=brief.country)
        state.save("borrador.json", draft_data)
        draft = Draft(**draft_data)
        state.checkpoint("production")

    if draft is None:
        return _contract(
            "BLOCKED",
            brief,
            state,
            steps,
            block_reason="la corrida no tiene borrador en la carpeta de estado",
        )

    if deps.registry and draft.html:
        saneado, retiradas = sanear_cifras(draft.html, deps.registry)
        # Afirmaciones que el registro contradice: se retiran por código.
        saneado, artefactos = limpiar_artefactos(saneado)
        saneado, afirmaciones = sanear_afirmaciones(saneado, deps.registry)
        retiradas = list(retiradas) + artefactos + afirmaciones
        if retiradas:
            draft = replace(draft, html=saneado)
            state.save("borrador.json", asdict(draft))
            steps.append(
                {
                    "step": "sanitize",
                    "status": "DONE",
                    "cifras_retiradas": retiradas,
                }
            )

    # El CTA final es obligatorio y se construye en código: pedírselo al modelo costaba una
    # llamada larga que el gateway devolvía vacía.
    if draft.html:
        con_cta = completar_cta(draft, country=brief.country)
        if con_cta.html != draft.html:
            draft = con_cta
            state.save("borrador.json", asdict(draft))
            steps.append({"step": "estructura", "status": "DONE", "accion": "cta_final"})

        con_pie = completar_captions(draft)
        if con_pie.html != draft.html:
            draft = con_pie
            state.save("borrador.json", asdict(draft))
            steps.append({"step": "estructura", "status": "DONE", "accion": "caption"})

        con_meta = ajustar_meta(draft)
        if con_meta.meta_description != draft.meta_description:
            draft = con_meta
            state.save("borrador.json", asdict(draft))
            steps.append({"step": "estructura", "status": "DONE", "accion": "meta"})

        sin_anio = normalizar_slug(draft)
        if sin_anio.slug != draft.slug:
            draft = sin_anio
            state.save("borrador.json", asdict(draft))
            steps.append({"step": "estructura", "status": "DONE", "accion": "slug"})

        con_enlaces = agregar_enlaces_internos(draft, list(deps.urls_internas or []))
        if con_enlaces.html != draft.html:
            draft = con_enlaces
            state.save("borrador.json", asdict(draft))
            steps.append({"step": "estructura", "status": "DONE", "accion": "enlaces_internos"})

        draft = _reconciliar_titulo(draft, brief, state, steps)

    verdict = None
    if start <= ORDER.index("judge"):
        converged = False
        judge_blocks = 0
        for cycle in range(1, max_cycles + 1):
            verdict = validate(
                draft,
                brief,
                ValidationRules(),
                evidence_of_testing=deps.evidence_of_testing,
                registry_text=deps.registry,
                brands_available=deps.brands_available,
            )
            state.save("veredictos.json", {"validator": [asdict(c) for c in verdict.controls]})
            steps.append({"step": "validation", "status": verdict.status, "cycle": cycle})

            if verdict.status == BLOQUEADO:
                return _contract(
                    "BLOCKED",
                    brief,
                    state,
                    steps,
                    block_reason=_blocking_codes(verdict),
                )

            if verdict.status == CORREGIR:
                codigos = {control.code for control in verdict.to_fix}
                if codigos == {"internal_links"} and deps.urls_internas:
                    enlaces = corregir_enlaces(
                        draft, list(deps.urls_internas), llm=deps.corrector, dominio=deps.dominio
                    )
                    steps.append(
                        {
                            "step": "link_pass",
                            "status": "DONE" if enlaces.secciones_corregidas else "SIN_CAMBIOS",
                            "secciones": enlaces.secciones_corregidas,
                            "rechazadas": enlaces.rechazadas,
                        }
                    )
                    if enlaces.secciones_corregidas:
                        draft = enlaces.draft
                        state.save("borrador.json", _draft_to_dict(draft))
                        continue

                fixed, reason = _fix(draft, verdict.to_fix, deps, state)
                if fixed is None:
                    # Si lo que queda son advertencias, no se detiene la publicación: se
                    # publica y se avisa. Solo un fallo bloqueante justifica parar.
                    if bloqueantes(verdict.to_fix):
                        return _contract("BLOCKED", brief, state, steps, block_reason=reason)
                    advertencias = [
                        {"code": c.code, "detail": c.detail} for c in verdict.to_fix
                    ]
                    state.save("advertencias.json", {"items": advertencias})
                    steps.append(
                        {
                            "step": "validation",
                            "status": "ADVERTENCIA",
                            "items": len(advertencias),
                        }
                    )
                else:
                    draft = fixed
                    draft = _reconciliar_titulo(draft, brief, state, steps)
                    continue

            outcome = _juzgar(draft, brief, verdict, deps, state)
            if outcome.status == "FAILED" and "JSON" in (outcome.detail or ""):
                # Una respuesta vacía del juez es del gateway, no del contenido: un reintento.
                outcome = _juzgar(draft, brief, verdict, deps, state)
            steps.append({"step": "judge", "status": outcome.status, "cycle": cycle})
            state.save(
                "veredictos.json",
                {
                    "validator": [asdict(c) for c in verdict.controls],
                    "judge": [asdict(c) for c in outcome.controls],
                    "suggestions": list(outcome.suggestions),
                    "approved_fingerprint": fingerprint(draft),
                },
            )

            if outcome.status == "FAILED":
                return _contract(
                    "FAILED",
                    brief,
                    state,
                    steps,
                    resume_from="judge",
                    block_reason=outcome.detail,
                )
            if outcome.status == BLOQUEADO:
                # Un bloqueo del juez también se intenta corregir una vez: casi siempre es una
                # frase concreta que el corrector puede reescribir o retirar.
                if judge_blocks < 1 and getattr(outcome, "controls", ()):
                    judge_blocks += 1
                    fixed, reason = _fix(draft, outcome.controls, deps, state)
                    if fixed is not None:
                        draft = fixed
                        continue
                return _contract(
                    "BLOCKED", brief, state, steps, block_reason=outcome.detail
                )
            if outcome.status == CORREGIR:
                graves = [
                    c for c in getattr(outcome, "controls", ())
                    if c.status != PASS and c.code == "intent_depth"
                ]
                if graves:
                    return _contract(
                        "BLOCKED",
                        brief,
                        state,
                        steps,
                        block_reason="el juez encontró la pieza incompleta: "
                        + graves[0].detail[:300],
                    )
                if deps.publicar_con_observaciones:
                    observaciones = [
                        {"code": c.code, "detail": c.detail}
                        for c in getattr(outcome, "controls", ())
                        if c.status != PASS
                    ]
                    state.save(
                        "observaciones.json",
                        {"advisory": True, "items": observaciones},
                    )
                    steps.append(
                        {
                            "step": "judge",
                            "status": "CORREGIR_ANOTADO",
                            "items": len(observaciones),
                        }
                    )
                    state.checkpoint("judge")
                    converged = True
                    break

                fixed, reason = _fix(draft, outcome.controls, deps, state)
                if fixed is None:
                    if bloqueantes(outcome.controls):
                        return _contract("BLOCKED", brief, state, steps, block_reason=reason)
                    advertencias = [
                        {"code": c.code, "detail": c.detail}
                        for c in outcome.controls
                        if c.status != "PASS"
                    ]
                    state.save("advertencias.json", {"items": advertencias})
                    steps.append(
                        {
                            "step": "judge",
                            "status": "ADVERTENCIA",
                            "items": len(advertencias),
                        }
                    )
                else:
                    draft = fixed
                    draft = _reconciliar_titulo(draft, brief, state, steps)
                    continue

            state.checkpoint("judge")
            converged = True
            break

        if not converged:
            pending = "; ".join(
                f"{control.code}: {control.detail}" if control.detail else control.code
                for control in (verdict.to_fix if verdict else ())
            )
            return _contract(
                "BLOCKED",
                brief,
                state,
                steps,
                block_reason=(
                    f"la pieza no convergió tras {max_cycles} ciclos de corrección"
                    + (f" ({pending})" if pending else "")
                ),
            )

    approved = (state.load("veredictos.json", {}) or {}).get("approved_fingerprint", "")
    effective = replace(
        conditions,
        approved_fingerprint=approved or conditions.approved_fingerprint,
        current_fingerprint=fingerprint(draft),
    )

    cover: bytes | None = None
    portada = state.load("portada.json", {}) or {}
    if not dry_run and deps.image is not None and requires_body(brief.opportunity.action):
        try:
            prompt = build_image_prompt(draft, brief)
            original, respaldo = generate_image(
                deps.image, prompt, fallback=deps.fallback_image
            )
            cover, calidad = comprimir_portada(original, max_kb=deps.image_max_kb)
            (state.dir / "portada.webp").write_bytes(cover)
            portada = {
                "caption": IMAGE_CAPTION,
                "alt": draft.alt_text,
                "bytes": len(cover),
                "bytes_original": len(original),
                "calidad_webp": calidad,
                "used_fallback": respaldo,
                "prompt": prompt,
            }
            state.save("portada.json", portada)
            steps.append(
                {"step": "preparation", "status": "FALLBACK" if respaldo else "DONE"}
            )
        except Exception as error:  # noqa: BLE001 - la portada no detiene la publicación
            steps.append(
                {"step": "preparation", "status": "SKIPPED", "detail": str(error)}
            )
            portada = {"caption": IMAGE_CAPTION, "error": str(error)}

    if dry_run:
        steps.append({"step": "publication", "status": "SIMULATED"})
        state.checkpoint("publication")
        return _contract("DONE", brief, state, steps)

    if deps.mcp is not None and deps.mapa is not None:
        result = publicar_mcp(
            draft,
            brief,
            ejecutar=deps.mcp.ejecutar,
            mapa=deps.mapa,
            portada=cover or (state.dir / "portada.webp").read_bytes()
            if (state.dir / "portada.webp").exists()
            else None,
            solo_borrador=deps.solo_borrador,
            post_id=deps.post_existente,
            subir_media=deps.subir_media,
            permitir_vivo=deps.permitir_vivo,
            verificar=deps.verificar_publicacion,
        )
        steps.append({"step": "publication", "status": result["status"], "via": "mcp"})
        state.save("publicacion.json", result)

        if result["status"] != "DONE":
            return _contract(
                result["status"],
                brief,
                state,
                steps,
                output_url=result.get("output_url", ""),
                block_reason=result.get("block_reason", ""),
            )

        # El título que el lector ve en Google tiene que ser el de la pieza. Sin esta
        # comprobación un artículo quedó con el H1 en Colombia y el <title> diciendo «en Perú».
        if result.get("output_url"):
            from .seo import coincide, titulo_renderizado

            visto = titulo_renderizado(result["output_url"])
            if visto and not coincide(visto, draft.title):
                steps.append(
                    {"step": "seo_titulo", "status": "FAILED", "renderizado": visto[:100]}
                )
                return _contract(
                    "FAILED",
                    brief,
                    state,
                    steps,
                    output_url=result.get("output_url", ""),
                    post_id=result.get("post_id"),
                    block_reason=(
                        "el <title> publicado no es el de la pieza: el sitio muestra «"
                        + visto[:90]
                        + "» y la pieza se titula «"
                        + draft.title[:60]
                        + "». El contenido sí quedó escrito."
                    ),
                )
            steps.append(
                {
                    "step": "seo_titulo",
                    "status": "PASS" if visto else "ADVERTENCIA",
                    "renderizado": visto[:100],
                }
            )

        state.checkpoint("publication")
        _avisar_publicacion(deps, brief, result)
        return _contract(
            "DONE", brief, state, steps, output_url=result.get("output_url", "")
        )

    result = publish(
        draft,
        brief,
        client=deps.publisher,
        conditions=effective,
        evidence_dir=str(state.dir),
        cover=cover,
        author_id=deps.author_id,
    )
    steps.append({"step": "publication", "status": result["status"]})
    state.save("publicacion.json", result)

    if result["status"] != "DONE":
        return _contract(
            result["status"],
            brief,
            state,
            steps,
            output_url=result.get("output_url", ""),
            resume_from=result.get("resume_from", ""),
            block_reason=result.get("block_reason", ""),
        )

    state.checkpoint("publication")
    _avisar_publicacion(deps, brief, result)
    return _contract(
        "DONE",
        brief,
        state,
        steps,
        output_url=result.get("output_url", ""),
    )


def _fix(
    draft: Draft,
    issues: Any,
    deps: Deps,
    state: RunState,
) -> tuple[Draft | None, str]:
    outcome = correct(
        draft,
        issues,
        llm=deps.corrector,
        manual=deps.manual,
    )
    if outcome.status != "DONE" or outcome.draft is None:
        return None, outcome.detail or "el corrector no logró un arreglo seguro"

    state.save("borrador.json", _draft_to_dict(outcome.draft))
    state.checkpoint("correction")
    return outcome.draft, ""


def _trozos(html: str, maximo: int = 9_000) -> list[str]:
    """Parte el artículo por sus h2, sin cortar una sección por la mitad."""
    if len(html) <= maximo:
        return [html]
    cortes = [
        i
        for i in range(len(html))
        if html.startswith("<h2", i) or html.startswith("<h3", i)
    ]
    if not cortes:
        return [html[i : i + maximo] for i in range(0, len(html), maximo)]
    limites = [0] + cortes[1:] + [len(html)]
    trozos, actual = [], ""
    for inicio, fin in zip(limites, limites[1:]):
        segmento = html[inicio:fin]
        if actual and len(actual) + len(segmento) > maximo:
            trozos.append(actual)
            actual = segmento
        else:
            actual += segmento
    if actual:
        trozos.append(actual)
    return trozos


def _juzgar(draft, brief, verdict, deps, state=None):
    """Juzga la pieza completa, por partes si es larga, y combina los veredictos.

    Una pieza de 80 000 caracteres no cabe en una llamada: el juez recibía un texto cortado y
    acusaba secciones ausentes que sí existían.
    """
    partes = _trozos(draft.html)
    if len(partes) == 1:
        return judge(draft, brief, verdict, deps.registry, llm=deps.judge)

    controles: list = []
    state_advertencias: list = []
    for indice, parte in enumerate(partes, start=1):
        trozo = replace(draft, html=parte)
        parcial = judge(
            trozo,
            brief,
            verdict,
            deps.registry,
            llm=deps.judge,
            contexto_parte=(
                f"Estás leyendo la PARTE {indice} de {len(partes)} del artículo. Juzga solo lo "
                'que aparece en esta parte: hechos, cifras, atribuciones y tono. No informes '
                'como defecto que falte una sección que podría estar en otra parte.'
            ),
        )
        if parcial.status == "FAILED":
            # Un trozo que el gateway deja en blanco no invalida el juicio de los demás:
            # se anota y se sigue. Si no queda ningún trozo juzgado, la corrida se detiene.
            state_advertencias.append(
                {"code": "juez_incompleto", "detail": f"parte {indice}: {parcial.detail}"[:200]}
            )
            continue
        # La cobertura ("falta la tabla de precios") es un juicio del artículo entero: dentro de
        # una parte siempre parece faltar algo. Se registra como advertencia, no como bloqueo.
        for control in getattr(parcial, "controls", ()):
            if getattr(control, "code", "") == "intent_depth":
                state_advertencias.append(
                    {"code": "intent_depth", "detail": control.detail}
                )
                continue
            controles.append(control)

    if state_advertencias:
        try:
            state.save("advertencias.json", {"items": state_advertencias})
        except Exception:  # noqa: BLE001
            pass

    if not controles and state_advertencias:
        return type(parcial)(status="FAILED", detail="ninguna parte se pudo juzgar")

    # El juez no bloquea: lo que encuentra se corrige.
    suaves = [
        c for c in controles if str(getattr(c, "status", "")) in ("CORREGIR", "BLOQUEADO")
    ]
    if suaves:
        return type(parcial)(status="CORREGIR", detail=suaves[0].detail, controls=controles)
    return type(parcial)(status="PASS", detail="", controls=controles)
