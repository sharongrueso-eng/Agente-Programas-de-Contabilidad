"""Paso de enlaces internos: corrige solo la sección que los necesita.

El corrector general reescribe la pieza entera y con 20.000 caracteres el gateway se cae por
tiempo. Aquí el trabajo se reduce a lo mínimo: se parte el HTML por secciones, se detectan
las que no tienen enlaces internos y se pide una sola cosa por sección —agregar entre dos y
tres enlaces, con URLs que ya existen en el sitio—.

La respuesta se valida antes de aceptarla: si el fragmento no contiene ninguna de las URLs
ofrecidas, se descarta. Un modelo que inventa una URL interna rompe el sitio, así que no se
le cree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from orchestrator.producer import Draft

_SECCION = re.compile(r"(<h2[^>]*>.*?</h2>.*?)(?=<h2|$)", re.IGNORECASE | re.DOTALL)


def secciones(html: str) -> list[str]:
    return [m.group(1) for m in _SECCION.finditer(html)]


def sin_enlaces_internos(html: str, dominio: str) -> list[str]:
    """Secciones sin ningún enlace al propio sitio."""
    return [
        seccion
        for seccion in secciones(html)
        if f'href="https://{dominio}' not in seccion and 'href="/' not in seccion
    ]


@dataclass
class ResultadoEnlaces:
    draft: Draft
    secciones_corregidas: int = 0
    rechazadas: int = 0
    llamadas: int = 0
    detalle: list[str] = field(default_factory=list)


def corregir_enlaces(
    draft: Draft,
    urls: list[str],
    *,
    llm: Any,
    dominio: str,
    max_secciones: int = 3,
) -> ResultadoEnlaces:
    """Agrega enlaces internos a las secciones que no los tienen, una por llamada."""
    pendientes = sin_enlaces_internos(draft.html, dominio)
    resultado = ResultadoEnlaces(draft=draft)
    if not pendientes or not urls:
        return resultado

    disponibles = "\n".join(f"- {u}" for u in urls[:12])
    html = draft.html

    for seccion in pendientes[:max_secciones]:
        instruccion = (
            "Reescribe SOLO esta sección del artículo agregando entre dos y tres enlaces "
            "internos usando EXCLUSIVAMENTE estas URLs, sin inventar ninguna otra:\n"
            f"{disponibles}\n\n"
            "Devuelve el HTML de la sección completo y nada más. Conserva el texto: solo "
            "agrega los enlaces dentro de frases existentes.\n\n"
            f"{seccion}"
        )
        resultado.llamadas += 1

        try:
            crudo = llm.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "Eres un editor que solo agrega enlaces internos. No cambias cifras, "
                            "no agregas párrafos nuevos y no usas URLs que no estén en la lista."
                        ),
                    },
                    {"role": "user", "content": instruccion},
                ]
            )
        except Exception:  # noqa: BLE001 - un fallo de red no rompe la pieza
            resultado.rechazadas += 1
            continue

        nueva = crudo.strip()
        if nueva.startswith("```"):
            nueva = re.sub(r"^```[a-zA-Z]*\n", "", nueva)
            nueva = re.sub(r"\n```$", "", nueva)

        # Guardia de evidencia: al menos una URL de la lista tiene que estar dentro.
        if not any(u in nueva for u in urls):
            resultado.rechazadas += 1
            resultado.detalle.append("fragmento descartado: no usa ninguna URL ofrecida")
            continue

        if len(nueva) < len(seccion) * 0.6 or len(nueva) > len(seccion) * 2.5:
            resultado.rechazadas += 1
            resultado.detalle.append("fragmento descartado: cambió de tamaño fuera de rango")
            continue

        html = html.replace(seccion, nueva, 1)
        resultado.secciones_corregidas += 1

    resultado.draft = Draft(
        title=draft.title,
        meta_description=draft.meta_description,
        html=html,
        alt_text=draft.alt_text,
        slug=draft.slug,
    )
    return resultado
