"""Producción por secciones: una llamada corta por bloque.

Una pieza de 13.000 caracteres no cabe en una sola llamada al gateway (se agota el tiempo o
el presupuesto de tokens). Aquí la estructura de nueve bloques se escribe bloque a bloque,
con el mismo prompt de sistema en todas las llamadas para que la caché del gateway acierte.

Ventaja operativa, además del tiempo: si un bloque falla, se reintenta ese bloque y no la
pieza entera.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from orchestrator.assigner import Brief
from orchestrator.producer import Draft, DraftParseError

# (clave, instrucción, quiere_enlaces)
BLOQUES: tuple[tuple[str, str], ...] = (
    (
        "respuesta",
        "Respuesta directa: dos o tres frases que contesten la pregunta central del lector, "
        "sin rodeos y sin repetir el título. Es el bloque que citan los motores de respuesta.",
    ),
    (
        "definicion",
        "Qué es y qué alcanza: define el tema y sus límites en el país del brief.",
    ),
    (
        "solucion",
        "La solución a la pregunta principal, con la comparativa cuando el formato lo pida. "
        "Incluye aquí el primer enlace a Alegra con UTM y TRES enlaces internos a otras piezas del blog.",
    ),
    (
        "procedimiento",
        "Cómo se hace, paso a paso, si el tema tiene un procedimiento.",
    ),
    (
        "analisis",
        "Análisis software por software. Un H3 por CADA marca del registro de datos, sin excepción "
        "y sin agregar marcas que no estén. Cada H3 lleva, como mínimo: qué es (dos frases), los "
        "planes y precios reales que publica (con su periodicidad), dos ventajas concretas, dos "
        "límites concretos y una frase de veredicto sobre para quién sirve. No resumas una marca "
        "en una línea: si está en el registro, se desarrolla.",
    ),
    (
        "tabla",
        "Tabla comparativa o cálculo diferencial con los precios y planes del registro de datos. "
        "Usa una tabla HTML. Si un competidor no publica precios, la celda dice que no los publica. "
        "Incluye aquí el segundo enlace a Alegra con UTM.",
    ),
    (
        "errores",
        "Errores frecuentes y casos problemáticos, con TRES enlaces internos más a otras piezas del blog.",
    ),
    (
        "preguntas",
        "Tres o cuatro preguntas conversacionales como H2, redactadas como las haría un lector, "
        "cada una con su respuesta breve.",
    ),
    (
        "fuentes",
        "Fuentes oficiales del país, enlazadas y nombradas. Incluye el tercer enlace a Alegra con UTM "
        "solo si el CTA no lo lleva.",
    ),
    (
        "veredicto",
        "Cierre recomendatorio: para cada perfil de negocio (emprendedor, pyme que crece, empresa "
        "con varias sedes) di qué opción conviene y por qué, en dos o tres frases. Sin promesas "
        "que el registro no respalde.",
    ),
    (
        "cta",
        "CTA y recurso descargable coherentes con el problema del lector, no un cierre genérico.",
    ),
)

CABECERA = """Devuelve SOLO este JSON, sin texto antes ni después:
{"title": "título SEO con la keyword foco", "meta_description": "140 a 160 caracteres con la keyword", "alt_text": "texto alternativo descriptivo de la portada", "intro": "primer párrafo en HTML, que contenga la keyword foco"}"""


@dataclass
class SalidaSecciones:
    draft: Draft
    bloques: dict[str, str] = field(default_factory=dict)
    fallidos: list[str] = field(default_factory=list)
    llamadas: int = 0


def _limpiar(texto: str) -> str:
    """Quita cercas de código y devuelve el HTML tal cual."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```[a-zA-Z]*\n", "", limpio)
        limpio = re.sub(r"\n```$", "", limpio)
    return limpio.strip()


def _json(texto: str) -> dict[str, Any]:
    limpio = _limpiar(texto)
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio < 0 or fin < 0:
        raise DraftParseError("la cabecera no trae un objeto JSON")
    try:
        return json.loads(limpio[inicio : fin + 1])
    except json.JSONDecodeError as error:
        raise DraftParseError(f"la cabecera no es JSON válido: {error}") from error


def producir_por_secciones(
    brief: Brief,
    *,
    llm: Any,
    skill: str,
    legal: str,
    registro: str = "",
    max_reintentos: int = 3,
) -> SalidaSecciones:
    """Escribe la cabecera y cada bloque con llamadas separadas, y ensambla la pieza."""
    if brief.opportunity is None:
        raise ValueError("un brief sin oportunidad no se puede producir")

    keyword = brief.opportunity.focus_keyword
    sistema = f"""{skill.strip()}

## Reglas no negociables

- Escribes como Leandro, para programascontabilidad.com, en español neutro de {brief.country}.
- Keyword foco: «{keyword}». No la repitas de forma artificial.
- No inventes precios ni cifras: usa solo las del registro de datos que viene abajo.
- Si un competidor no publica un dato, dilo y sigue. La ausencia declarada es información.
- Escribe «revisé» por defecto; «probé» solo con evidencia documentada.

## Contexto legal del mercado

{legal}

## Registro de datos del mercado (única fuente de cifras)

{registro or "sin fichas de este mercado"}
"""

    salida = SalidaSecciones(draft=None)  # type: ignore[arg-type]

    def llamar(instruccion: str) -> str:
        salida.llamadas += 1
        return llm.complete(
            [
                {"role": "system", "content": sistema},
                {
                    "role": "user",
                    "content": (
                        f"Brief: {brief.format} · {brief.country} · acción {brief.opportunity.action}\n"
                        f"Tema que cubre la URL: {brief.opportunity.url}\n\n{instruccion}"
                    ),
                },
            ]
        )

    cabecera = _json(llamar(f"Escribe la cabecera de la pieza.\n\n{CABECERA}"))
    for campo in ("title", "meta_description", "alt_text", "intro"):
        if not str(cabecera.get(campo, "")).strip():
            raise DraftParseError(f"la cabecera no trae «{campo}»")

    partes: list[str] = [f"<h1>{cabecera['title']}</h1>", str(cabecera["intro"]).strip()]

    for clave, instruccion in BLOQUES:
        fragmento = ""
        for _ in range(max_reintentos):
            try:
                crudo = llamar(
                    "Escribe SOLO este bloque, en HTML, sin encabezado de nivel 1 y sin repetir "
                    f"el título. No expliques nada fuera del HTML.\n\nBloque «{clave}»: {instruccion}"
                )
                fragmento = _limpiar(crudo)
            except Exception:  # noqa: BLE001 - un bloque caído no tumba la pieza
                continue
            if len(fragmento) >= 80:
                break
            fragmento = ""

        if not fragmento:
            salida.fallidos.append(clave)
            continue

        salida.bloques[clave] = fragmento
        partes.append(fragmento)

    html = "\n\n".join(partes)
    salida.draft = Draft(
        title=str(cabecera["title"]).strip(),
        meta_description=str(cabecera["meta_description"]).strip(),
        html=html,
        alt_text=str(cabecera["alt_text"]).strip(),
        slug=_slug(str(cabecera["title"])),
    )
    return salida


def _slug(titulo: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFD", titulo.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:70]
