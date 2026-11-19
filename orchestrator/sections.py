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
        "y sin agregar marcas que no estén. Cada H3 lleva, como mínimo: qué es (dos frases), sus "
        "funciones y beneficios concretos, dos límites concretos y una frase de veredicto sobre "
        "para quién sirve. Desarrolla CADA marca por separado y no nombres a Alegra dentro de la "
        "ficha de otra marca: Alegra tiene su propio H3 y ahí se cuenta lo suyo. No resumas una "
        "marca en una línea: si está en el registro, se desarrolla.",
    ),
    (
        "tabla",
        "Tabla comparativa SOLO si aporta: funciones lado a lado, o el costo de un mismo escenario "
        "(por ejemplo, llevar 10 clientes o 3 usuarios). Si el tema se decide por funcionalidades, "
        "no hay tabla de precios y esta sección puede ser una lista de criterios. Si hay precios, "
        "se comparan los planes equivalentes (POS con POS, ERP con ERP), todos en la moneda del "
        "país y en el mismo periodo; nunca una tabla con todos los planes de todos. "
        "Incluye aquí el segundo enlace a Alegra con UTM.",
    ),
    (
        "errores",
        "Errores frecuentes y casos problemáticos, con TRES enlaces internos más a otras piezas del blog.",
    ),
    (
        "preguntas",
        "Tres o cuatro preguntas que haría un lector, cada una con su respuesta breve (dos o "
        "tres frases, con el dato del registro cuando aplique). Sin HTML. Formato exacto, una "
        "línea por pregunta y otra por respuesta:\nP: ¿…?\nR: …\n"
        "El componente de la FAQ lo arma el código.",
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
    """Quita cercas de código y la etiqueta del bloque si el modelo la pegó al texto."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```[a-zA-Z]*\n", "", limpio)
        limpio = re.sub(r"\n```$", "", limpio)
    # «Respuesta directa.com: …» salía a la calle como si fuera una frase: el modelo pega el
    # nombre del bloque a la primera oración y el lector lo lee como un dominio inventado.
    limpio = re.sub(
        r"^(?:<p>\s*)?(?:respuesta\s+(?:directa|breve|inmediata)|puntos\s+clave)\s*[.:\-–]\s*(?:com\b)?\s*[:.]?\s*",
        "",
        limpio,
        flags=re.IGNORECASE,
    )
    return limpio.strip()


def cortado(fragmento: str) -> bool:
    """Un bloque que no termina en una etiqueta de cierre ni en un signo de fin de frase se cortó.

    Pasaba con el texto a mitad de palabra («integración con Rap», «exig»): el bloque superaba
    el mínimo de 80 caracteres y entraba a la pieza roto.
    """
    final = (fragmento or "").rstrip()
    if not final:
        return True
    if final.endswith(">"):
        # Termina en etiqueta: tiene que ser un cierre, no una etiqueta de apertura suelta.
        return bool(re.search(r"<(?!/)[a-zA-Z][^>]*>\s*$", final)) and not re.search(
            r"<(br|hr|img)[^>]*>\s*$", final, re.I
        )
    visible = re.sub(r"<[^>]+>", " ", final).rstrip()
    return not re.search(r"[.!?…»”\")]\s*$", visible)


_PAR_FAQ = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:P|Pregunta)\s*[:.\-–]\s*(?P<p>.+?)\s*$\s*"
    r"^\s*(?:R|Respuesta)\s*[:.\-–]\s*(?P<r>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def pares_de_faq(texto: str) -> list[tuple[str, str]]:
    """Pares pregunta-respuesta del formato «P: … / R: …», sin etiquetas de bloque."""
    pares = []
    for m in _PAR_FAQ.finditer(_limpiar(texto)):
        pregunta = re.sub(r"<[^>]+>", "", m.group("p")).strip().strip("*").strip()
        respuesta = re.sub(r"</?(p|div|h\d)[^>]*>", "", m.group("r")).strip().strip("*").strip()
        if len(pregunta) >= 8 and len(respuesta) >= 20 and not cortado(respuesta):
            if not pregunta.endswith("?"):
                pregunta = pregunta.rstrip(".") + "?"
            if not pregunta.startswith("¿"):
                pregunta = "¿" + pregunta
            pares.append((pregunta, respuesta))
    return pares


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


def _marcar_progreso(carpeta: Path | None, terminados: list[str], fallidos: list[str]) -> None:
    """Deja en la carpeta de la corrida cuántos bloques van.

    Es la única evidencia que sobrevive si la tarea se agota a mitad: sin esto, una corrida
    cortada deja una carpeta «bloques» con archivos sueltos y ninguna forma de saber qué faltó.
    """
    if carpeta is None:
        return
    try:
        (carpeta.parent / "progreso.json").write_text(
            json.dumps(
                {
                    "total": len(BLOQUES),
                    "terminados": terminados,
                    "en_disco": len(list(carpeta.glob("*.html"))),
                    "faltan": [clave for clave, _ in BLOQUES if clave not in terminados],
                    "fallidos": fallidos,
                },
                ensure_ascii=False,
                indent=2,
            )
            + chr(10),
            encoding="utf-8",
        )
    except OSError:
        pass


def producir_por_secciones(
    brief: Brief,
    *,
    llm: Any,
    skill: str,
    skill_bloques: str = "",
    legal: str = "",
    registro: str = "",
    marcas: Sequence[str] = (),
    fichas: Sequence[Any] = (),
    carpeta: Path | None = None,
    max_reintentos: int = 3,
    contexto: str = "",
    html_vivo: str = "",
    maximo_secciones_vivas: int = 4,
) -> SalidaSecciones:
    """Escribe la cabecera y cada bloque con llamadas separadas, y ensambla la pieza.

    En un reencauche (`html_vivo`), los bloques fijos no tienen dónde poner las secciones propias
    de la página publicada («Cloud o instalación local», «Según tu caso de uso»…). Al terminar,
    cada sección de la viva que la pieza no cubre se escribe como bloque propio, a partir de lo
    que dice hoy, y se inserta antes de las preguntas y el cierre.
    """
    if brief.opportunity is None:
        raise ValueError("un brief sin oportunidad no se puede producir")

    keyword = brief.opportunity.focus_keyword
    from orchestrator.formato import presupuesto as _presupuesto

    tablas_max = _presupuesto(brief.format).tablas_max
    from orchestrator.registry import fecha_de_consulta

    fecha_consulta = fecha_de_consulta(
        [f for f in fichas if isinstance(f, dict)]
    ) or f"el {datos_fecha()}"
    sistema = f"""{skill.strip()}

{contexto.strip()}

## Reglas no negociables

- Escribes para programascontabilidad.com con voz editorial propia, en español neutro de {brief.country}. No firmas como una persona.
- Keyword foco: «{keyword}». No la repitas de forma artificial.
- No inventes precios ni cifras: usa solo las del registro de datos que viene abajo.
- **Los precios no son obligatorios.** Muchos temas se deciden por funciones, integraciones o
  facilidad de uso: ahí no va tabla de precios ni comparación de tarifas. Si hay precios, que
  permitan comparar: planes equivalentes (POS con POS, ERP con ERP), todos en la moneda del país
  (convierte si vienen en dólares y el país no usa dólares) y todos en el mismo periodo (mensual o
  anual, no los dos). Nunca una tabla con todos los planes de todos los competidores.
- La pieza admite **{tablas_max} tablas como máximo** y, si no hacen falta, no lleva ninguna.
  Cuando necesites comparar sin tabla, usa listas o párrafos.
- **Sin fechas de consulta.** No escribas «consultada el 18 de noviembre de 2026» ni «a fecha de…»:
  los precios los mantiene al día el vigía y una fecha en el texto envejece el artículo. La fuente
  se cita por su nombre y su enlace, nada más.
- **Alegra no abre la pieza.** El artículo empieza por el problema del país y el mercado; Alegra
  entra como una alternativa más, en su propio apartado, y solo al final —en el veredicto— se
  presenta como la opción que más encaja según el perfil. Nada de «Alegra es la mejor» al principio.
- **Cada sistema se describe solo.** En la ficha de un competidor no se nombra a Alegra ni se
  compara con ella: sus funciones, sus límites y para quién sirve. Los beneficios de Alegra
  (facturación, contabilidad, Alegra BOT) se cuentan en su apartado, una vez y sin repetirlos.
- **No repitas subtítulos.** Dos H2 que preguntan lo mismo con otras palabras («¿Qué sistema
  conviene?» y «Veredicto: qué sistema conviene») son un defecto: cada sección tiene su pregunta.
- Si un competidor no publica un dato, dilo y sigue. La ausencia declarada es información.
- En una comparativa bastan **dos o tres competidores**: el registro es un techo, no una lista que
  haya que cubrir entera. Los dos o tres que el lector compararía de verdad valen más que todos.
- **Intención de producto**: el tema se apoya en algo donde Alegra es fuerte —facturación
  electrónica, contabilidad, punto de venta, nómina electrónica, inventario y costos, cartera o
  automatización con IA—. Si el ángulo no se sostiene en ninguno de esos frentes, replantéalo:
  no se escribe una pieza donde Alegra no tiene nada que ofrecer.
- **Alegra BOT** (el asistente con IA que responde por WhatsApp y registra facturas y gastos) se
  resalta como beneficio cuando el ángulo lo permita: es el diferenciador que el lector no
  encuentra en el competidor. Con nombre propio, «Alegra BOT», y una frase que diga qué resuelve.
- **AEO: escribe para que un modelo te pueda citar.** La respuesta va en la primera o segunda
  frase del arranque, la consulta foco en el primer párrafo, al menos dos secciones con el H2 en
  forma de pregunta, y cada cifra con su fuente (sin fecha: la mantiene al día el vigía). Un
  párrafo que empiece definiendo («El software contable es…») vale más que tres que den rodeos.
- Devuelves **solo el HTML de la pieza**: sin cercas de markdown (```), sin encabezados tipo
  «## Bloque «X» — fragmento listo para pegar», sin marcadores `[PENDIENTE…]` y sin notas de
  proceso para el editor. Eso no es texto para el lector y se publica tal cual.
- No escribas en primera persona que revisaste o probaste algo («revisé», «probé», «comprobamos»):
  atribuye cada dato a su fuente por su nombre («según la página de precios de X»), sin fecha.
- **Ninguna fecha de consulta en el cuerpo.** Ni «consultada el…», ni «a fecha de…», ni un H2
  «Fuentes y fecha de consulta». La sección de fuentes se titula «Fuentes».
- En un tema de segmento (veterinarias, ferreterías, restaurantes…) no afirmes nada sobre el
  sector, su regulación, sus autoridades o su mercado que no esté en el registro o en el contexto
  legal: habla de lo que el software resuelve para ese negocio. Sin estadísticas del sector.
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

## Lo que el registro ya prueba

{{prueba_texto}}

## Registro de datos del mercado (única fuente de cifras)

{registro or "sin fichas de este mercado"}
"""

    marcas_texto = ", ".join(marcas) if marcas else "las que aparezcan en el registro"
    sistema = sistema.replace("{marcas_texto}", marcas_texto)
    sistema = sistema.replace("{prueba_texto}", _prueba_del_registro(fichas))

    salida = SalidaSecciones(draft=None)  # type: ignore[arg-type]

    # Las referencias completas se pagan una vez, en la cabecera. Los bloques reciben la skill
    # sola: reenviar cuarenta mil caracteres de referencias en cada bloque multiplica el costo
    # sin mejorar el texto, porque las reglas que importan ya están en la skill.
    sistema_bloques = sistema
    if skill_bloques:
        sistema_bloques = sistema.replace(skill.strip(), skill_bloques.strip(), 1)

    def llamar(instruccion: str, compacto: bool = False) -> str:
        salida.llamadas += 1
        return llm.complete(
            [
                {"role": "system", "content": sistema_bloques if compacto else sistema},
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
            for intento in range(max_reintentos):
                try:
                    crudo = llamar(
                        "Bloque «" + clave + "»: " + instruccion
                        + chr(10) + "Devuelve solo el texto, sin HTML y sin explicaciones.",
                        compacto=True,
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

        # La FAQ es un componente (`<details>`), no encabezados sueltos: el validador lo exige y
        # la instrucción anterior pedía preguntas en H2, así que se marcaba en casi todas las
        # corridas. El modelo escribe los pares; el código arma el componente.
        if clave == "preguntas":
            pares: list[tuple[str, str]] = []
            for intento in range(max_reintentos):
                try:
                    pares = pares_de_faq(
                        llamar("Bloque «preguntas»: " + instruccion, compacto=True)
                    )
                except Exception:  # noqa: BLE001
                    continue
                if len(pares) >= 2:
                    break
            if len(pares) >= 2:
                construido = "<h2>Preguntas frecuentes</h2>\n" + lv.faq(pares[:5])
                salida.bloques[clave] = construido
                partes.append(construido)
            else:
                salida.fallidos.append(clave)
            continue

        # La tabla sale del registro, no del modelo: pedirle cifras dentro de celdas es
        # justo donde inventa precios que el registro sí tiene. Y solo entran las marcas que la
        # pieza ya nombra: una tabla no puede presentar competidores que el artículo no trata.
        if clave == "tabla" and fichas:
            dicho = " ".join(partes).lower()
            nombradas = [
                ficha
                for ficha in fichas
                if str(
                    ficha.get("brand", "") if isinstance(ficha, dict) else getattr(ficha, "brand", "")
                ).lower()
                in dicho
            ]
            construida = _tabla_del_registro(nombradas or fichas)
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
                for intento in range(max_reintentos):
                    try:
                        trozo = _limpiar(
                            llamar(
                                "Bloque «analisis»: " + instruccion
                                + "\n\nDesarrolla SOLO «" + marca + "»: un H3 con su nombre y "
                                "debajo qué es, sus funciones y beneficios concretos, dos "
                                "límites y una frase de veredicto. No nombres a Alegra en esta "
                                "ficha. Nada más."
                            )
                        )
                    except Exception:  # noqa: BLE001 - una marca caída no tumba el bloque
                        continue
                    if cortado(trozo):
                        trozo = ""
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
            previo = _limpiar(guardado.read_text(encoding="utf-8"))
            # Un bloque en caché que nombra una plataforma inventada no se reutiliza:
            # arrastraría el error a todas las corridas siguientes.
            try:
                from orchestrator.directorio import extranas
                from orchestrator.sujeto import permitidas as del_tema

                ajenas = extranas(previo, brief.country, permitidas=del_tema(brief))
            except Exception:  # noqa: BLE001
                ajenas = []
            if ajenas:
                print(f"   bloque «{clave}» descartado: nombra {', '.join(ajenas[:3])}")
                guardado.unlink(missing_ok=True)
                previo = ""
            if len(previo) >= 80:
                salida.bloques[clave] = previo
                partes.append(previo)
                continue

        fragmento = ""
        for intento in range(max_reintentos):
            try:
                crudo = llamar(
                    "Escribe SOLO este bloque, en HTML, sin encabezado de nivel 1 y sin repetir "
                    f"el título. No expliques nada fuera del HTML.\n\nBloque «{clave}»: {instruccion}"
                )
                fragmento = _limpiar(crudo)
            except Exception:  # noqa: BLE001 - un bloque caído no tumba la pieza
                continue
            if len(fragmento) >= 80 and not cortado(fragmento):
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
            _marcar_progreso(carpeta, list(salida.bloques), salida.fallidos)

    if html_vivo:
        _completar_secciones_vivas(
            partes,
            salida,
            html_vivo=html_vivo,
            llamar=llamar,
            carpeta=carpeta,
            maximo=maximo_secciones_vivas,
            max_reintentos=max_reintentos,
        )

    html = "\n\n".join(partes)
    salida.draft = Draft(
        title=str(cabecera["title"]).strip(),
        meta_description=str(cabecera["meta_description"]).strip(),
        html=html,
        alt_text=str(cabecera["alt_text"]).strip(),
        slug=_slug(str(cabecera["title"])),
    )
    return salida


# Bloques de cierre: las secciones recuperadas de la viva van antes de estos.
_CIERRE = ("preguntas", "fuentes", "resumen", "veredicto", "cta")


def _completar_secciones_vivas(
    partes: list[str],
    salida: "SalidaSecciones",
    *,
    html_vivo: str,
    llamar: Any,
    carpeta: Path | None,
    maximo: int,
    max_reintentos: int,
) -> None:
    """Escribe, una por una, las secciones de la viva que la pieza nueva dejó por fuera."""
    from orchestrator.reencauche import _visible, anclas_internas, secciones_perdidas

    perdidas = secciones_perdidas("\n\n".join(partes), html_vivo)[:maximo]
    if not perdidas:
        return
    nuevas: list[str] = []
    for numero, seccion in enumerate(perdidas, start=1):
        clave = f"viva_{numero}"
        guardado = (carpeta / f"{clave}.html") if carpeta else None
        if guardado and guardado.exists():
            previo = _limpiar(guardado.read_text(encoding="utf-8"))
            if len(previo) >= 80:
                salida.bloques[clave] = previo
                nuevas.append(previo)
                continue
        enlaces = [href for href, _ in anclas_internas(seccion.html).values()]
        instruccion = (
            f"Bloque «{clave}»: la página publicada tiene la sección «{seccion.titulo}» y la "
            "versión nueva no la cubre. Escríbela mejorada en HTML: un <h2> con ese mismo tema "
            "(puedes ajustar el título sin cambiar de qué habla) y su desarrollo. Parte de lo "
            "que dice hoy, actualiza lo que haya cambiado y no repitas lo que ya cubren otras "
            "secciones. Las cifras salen solo del registro de datos: si la sección trae un precio "
            "que el registro no tiene, se quita."
            + (
                " Conserva estos enlaces internos con la misma URL: " + ", ".join(enlaces)
                if enlaces
                else ""
            )
            + "\n\nLo que dice hoy la sección:\n"
            + _visible(seccion.html)[:2500]
        )
        fragmento = ""
        for _ in range(max_reintentos):
            try:
                fragmento = _limpiar(
                    llamar(
                        "Escribe SOLO este bloque, en HTML, sin encabezado de nivel 1. No "
                        f"expliques nada fuera del HTML.\n\n{instruccion}"
                    )
                )
            except Exception:  # noqa: BLE001 - una sección caída no tumba la pieza
                continue
            if len(fragmento) >= 80 and not cortado(fragmento):
                break
            fragmento = ""
        if not fragmento:
            salida.fallidos.append(clave)
            continue
        if "<h2" not in fragmento.lower():
            fragmento = f"<h2>{seccion.titulo}</h2>\n{fragmento}"
        salida.bloques[clave] = fragmento
        nuevas.append(fragmento)
        if guardado:
            guardado.parent.mkdir(parents=True, exist_ok=True)
            guardado.write_text(fragmento, encoding="utf-8")

    if not nuevas:
        return
    # partes = [h1, intro, *bloques en el orden en que se escribieron]
    escritas = [c for c in salida.bloques if not c.startswith("viva_")]
    cierre = next((i for i, c in enumerate(escritas) if c in _CIERRE), len(escritas))
    posicion = 2 + cierre
    partes[posicion:posicion] = nuevas


def _prueba_del_registro(fichas: Sequence[Any]) -> str:
    """Qué marcas tienen precios en el registro y cuáles no, para que el redactor no rellene."""
    from orchestrator.registry import tiene_precios

    con = [str(f.get("brand", "")) for f in fichas if isinstance(f, dict) and tiene_precios(f)]
    sin = [str(f.get("brand", "")) for f in fichas if isinstance(f, dict) and not tiene_precios(f)]
    lineas = []
    if con:
        lineas.append(
            "Tienen precios publicados en el registro de abajo: " + ", ".join(con) + ". Nunca "
            "escribas que una de ellas «no tiene ficha» o «no está documentada». Si un dato "
            "concreto no aparece, dilo de ese dato —«no publica el precio de ese módulo»—, "
            "nunca de la plataforma entera."
        )
    if sin:
        lineas.append(
            "No tienen precios en el registro: " + ", ".join(sin) + ". De ellas escribe "
            "exactamente «El proveedor no publica ese precio en su sitio web.» y no describas su "
            "modelo de cobro, sus planes ni qué incluye cada plan."
        )
    if not lineas:
        lineas.append("Cita solo lo que trae el registro de abajo.")
    lineas.append(
        "Lo que una ficha lista como funciones del producto no se reparte por planes: «incluido "
        "desde X al mes» solo si el registro lo dice de ese plan."
    )
    return "\n\n".join(lineas)


def _precio_numero(valor: Any) -> float:
    """Convierte «1.751.920» o «18» en número comparable; lo ilegible vale infinito."""
    texto = re.sub(r"[^0-9,.]", "", str(valor or "")).replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return float("inf")


def _tabla_del_registro(fichas: Sequence[Any]) -> str:
    """Punto de entrada de cada marca: su plan publicado más económico, con la cifra exacta.

    Antes se escribía una fila por plan de cada ficha. Con las seis fichas colombianas eso daba
    95 filas y una tabla de 68.000 caracteres: rompía el presupuesto de tablas del formato,
    duplicaba lo que ya dice el análisis marca por marca y no lo leía nadie. El lector necesita
    con qué entra cada proveedor, no su catálogo completo.
    """
    filas: list[list[str]] = []
    for ficha in fichas:
        brand = ficha.get("brand", "") if isinstance(ficha, dict) else getattr(ficha, "brand", "")
        planes = ficha.get("plans", []) if isinstance(ficha, dict) else getattr(ficha, "plans", [])
        publicados = [
            plan
            for plan in (planes or [])
            if isinstance(plan, dict)
            and str(plan.get("price", "")).strip()
            and plan.get("publicado", True) is not False
        ]
        # Un «usuario adicional» es más barato que cualquier plan y no es una puerta de entrada:
        # ponerlo como «desde» engaña al lector, que compara lo que cuesta empezar.
        sin_adicionales = [
            plan
            for plan in publicados
            if not re.search(r"adicion|add-?on|extra|complemento", str(plan.get("name", "")), re.I)
        ]
        publicados = sin_adicionales or publicados
        if not publicados:
            filas.append(
                [
                    f'<strong style="color:#002B5B;">{brand}</strong>',
                    "—",
                    '<span style="color:#4B5563;">No publicado</span>',
                ]
            )
            continue
        elegido = min(publicados, key=lambda plan: _precio_numero(plan.get("price")))
        precio = str(elegido.get("price", "")).strip()
        moneda = str(elegido.get("currency", "")).strip()
        periodo = str(elegido.get("period", "")).strip()
        celda = (
            f'<strong style="font-size:17px;color:#002B5B;white-space:nowrap;">'
            f"{precio} {moneda}</strong>"
            f'<span style="display:block;font-size:12px;line-height:1.4;color:#4B5563;">'
            f"{periodo}</span>"
        )
        filas.append(
            [f'<strong style="color:#002B5B;">{brand}</strong>', str(elegido.get("name", "")), celda]
        )
    if not filas:
        return ""
    from orchestrator.registry import fecha_de_consulta

    consulta = fecha_de_consulta([f for f in fichas if isinstance(f, dict)]) or f"el {datos_fecha()}"
    caption = (
        "Plan publicado más económico de cada proveedor en su sitio, consultados "
        f"{consulta}; pueden cambiar sin aviso."
    )
    return lv.tabla(caption, ["Proveedor", "Plan de entrada", "Precio publicado"], filas)


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
