"""Producción por secciones: una llamada corta por bloque.

Una pieza de 13.000 caracteres no cabe en una sola llamada al gateway (se agota el tiempo o
el presupuesto de tokens). Aquí la estructura de nueve bloques se escribe bloque a bloque,
con el mismo prompt de sistema en todas las llamadas para que la caché del gateway acierte.

Ventaja operativa, además del tiempo: si un bloque falla, se reintenta ese bloque y no la
pieza entera.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from orchestrator.assigner import Brief
from orchestrator import linea_visual as lv
from orchestrator.producer import Draft, DraftParseError

# (clave, instrucción, quiere_enlaces)
BLOQUES: tuple[tuple[str, str], ...] = (
    (
        "respuesta",
        "Respuesta directa: dos o tres frases que contesten la pregunta central del lector, "
        "sin rodeos y sin repetir el título. Es el bloque que citan los motores de respuesta.",
    ),
    (
        "puntos_clave",
        "Cuatro viñetas con lo que decide la compra o la duda del lector, una por línea, cada "
        "una empezando por «- » y de 12 a 20 palabras. Sin introducción ni cierre: solo la lista.",
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
        "resumen",
        "Una sola frase de cierre, de 25 a 40 palabras, que resuma la respuesta para quien "
        "solo va a leer el final. Sin listas y sin repetir el veredicto.",
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
    marcas: Sequence[str] = (),
    fichas: Sequence[Any] = (),
    carpeta: Path | None = None,
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
- El **primer párrafo** de la pieza contiene la keyword foco completa y literal: «{keyword}».
  No parafraseada, no en el H2, no más adelante. Sin eso la pieza no pasa la validación.
- Si la marca que nombra la keyword **no tiene ficha en el registro**, el título y la meta no
  prometen precios, funciones, límites ni análisis de esa marca: describen el tema y comparan
  solo con lo que el registro sí contiene. Prometer un dato que no tenemos es un bloqueo.
- Si el registro dice que un proveedor no publica precios, se puede prometer eso mismo: que no
  publica, y recomendar pedir cotización.

## Contexto legal del mercado

{legal}

## Plataformas que puedes nombrar

{{marcas_texto}}

Ninguna otra. Si un nombre no está en esa lista, no existe para esta pieza: no se inventa, no se
deforma y no se abrevia. Escribir «Susii» donde va «Siigo» invalida el artículo entero.

## Registro de datos del mercado (única fuente de cifras)

{registro or "sin fichas de este mercado"}
"""

    marcas_texto = ", ".join(marcas) if marcas else "las que aparezcan en el registro"
    sistema = sistema.replace("{marcas_texto}", marcas_texto)

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
        if clave in {"puntos_clave", "resumen"}:
            crudo = ""
            for _ in range(max_reintentos):
                try:
                    crudo = llamar(
                        "Bloque «" + clave + "»: " + instruccion
                        + chr(10) + "Devuelve solo el texto, sin HTML y sin explicaciones."
                    )
                except Exception:  # noqa: BLE001
                    continue
                if len(crudo.strip()) >= 40:
                    break
                crudo = ""
            if clave == "puntos_clave":
                items = [
                    _limpiar(linea).lstrip("-•* ").strip()
                    for linea in crudo.splitlines()
                    if linea.strip().startswith(("-", "•", "*"))
                ]
                construido = lv.puntos_clave(items[:5]) if len(items) >= 2 else ""
            else:
                frase = " ".join(crudo.split())[:400]
                construido = lv.resumen(frase) if len(frase) >= 40 else ""
            if construido:
                salida.bloques[clave] = construido
                partes.append(construido)
            else:
                salida.fallidos.append(clave)
            continue

        # La tabla sale del registro, no del modelo: pedirle cifras dentro de celdas es
        # justo donde inventa precios que el registro sí tiene.
        if clave == "tabla" and fichas:
            construida = _tabla_del_registro(fichas)
            if construida:
                salida.bloques[clave] = construida
                partes.append(construida)
                continue

        # El análisis por marca va marca por marca: una sola llamada con las cuatro no cabe
        # en la ventana del gateway y el bloque se pierde entero.
        if clave == "analisis" and marcas:
            fragmentos: list[str] = []
            for marca in marcas:
                trozo = ""
                for _ in range(max_reintentos):
                    try:
                        trozo = _limpiar(
                            llamar(
                                "Bloque «analisis»: " + instruccion
                                + "\n\nDesarrolla SOLO «" + marca + "»: un H3 con su nombre y "
                                "debajo los planes y precios que el registro publica para esa "
                                "marca, dos ventajas, dos límites y una frase de veredicto. "
                                "Nada más."
                            )
                        )
                    except Exception:  # noqa: BLE001 - una marca caída no tumba el bloque
                        continue
                    if "<h3" in trozo.lower() and len(trozo) >= 300:
                        break
                    # El modelo a veces devuelve markdown o texto sin encabezado: el H3 lo
                    # pone el código, porque la estructura es nuestra y el texto es suyo.
                    if len(trozo) >= 300:
                        trozo = f"<h3>{marca}</h3>" + trozo
                        break
                    trozo = ""
                if trozo:
                    fragmentos.append(trozo)
            if fragmentos:
                unido = "\n".join(fragmentos)
                salida.bloques[clave] = unido
                partes.append(unido)
            else:
                salida.fallidos.append(clave)
            continue

        guardado = (carpeta / f"{clave}.html") if carpeta else None
        if guardado and guardado.exists():
            previo = guardado.read_text(encoding="utf-8").strip()
            if len(previo) >= 80:
                salida.bloques[clave] = previo
                partes.append(previo)
                continue

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
        if guardado:
            guardado.parent.mkdir(parents=True, exist_ok=True)
            guardado.write_text(fragmento, encoding="utf-8")

    html = "\n\n".join(partes)
    salida.draft = Draft(
        title=str(cabecera["title"]).strip(),
        meta_description=str(cabecera["meta_description"]).strip(),
        html=html,
        alt_text=str(cabecera["alt_text"]).strip(),
        slug=_slug(str(cabecera["title"])),
    )
    return salida


def _tabla_del_registro(fichas: Sequence[Any]) -> str:
    """Tabla de precios por marca, con las cifras tal como las publica cada proveedor."""
    filas: list[list[str]] = []
    for ficha in fichas:
        brand = ficha.get("brand", "") if isinstance(ficha, dict) else getattr(ficha, "brand", "")
        planes = ficha.get("plans", []) if isinstance(ficha, dict) else getattr(ficha, "plans", [])
        for plan in planes or []:
            if not isinstance(plan, dict):
                continue
            precio = str(plan.get("price", "")).strip()
            moneda = str(plan.get("currency", "")).strip()
            periodo = str(plan.get("period", "")).strip()
            if not precio:
                celda = "No publicado"
            else:
                celda = (
                    f'<strong style="font-size:17px;color:#002B5B;white-space:nowrap;">'
                    f"{precio} {moneda}</strong>"
                    f'<span style="display:block;font-size:12px;line-height:1.4;color:#4B5563;">'
                    f"{periodo}</span>"
                )
            filas.append([str(plan.get("name", "")), str(brand), celda])
    if not filas:
        return ""
    caption = (
        "Precios tal como los publica cada proveedor en su sitio, consultados el "
        f"{datos_fecha()}; pueden cambiar sin aviso."
    )
    return lv.tabla(caption, ["Plan", "Proveedor", "Precio publicado"], filas)


def datos_fecha() -> str:
    from datetime import date

    meses = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    hoy = date.today()
    return f"{hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"


def _slug(titulo: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFD", titulo.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:70]
