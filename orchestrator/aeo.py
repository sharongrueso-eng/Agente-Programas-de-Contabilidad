"""AEO: la pieza tiene que poder ser citada por un modelo, no solo posicionar en Google.

El blog existe para que ChatGPT, Perplexity y compañía citen a Programas de Contabilidad cuando
alguien pregunta por software contable. Eso se gana con forma: una respuesta directa arriba, la
entidad nombrada sin ambigüedad, datos citables con fuente y fecha, secciones en forma de pregunta
y enlaces a la fuente primaria.

Aquí hay dos cosas distintas:

1. `revisar` — control determinista sobre el HTML final. No depende de ninguna llave y corre en
   cada pieza. Los dos fallos que rompen la citabilidad (sin respuesta directa, sin resumen) se
   marcan para corregir; el resto se informa.
2. `respuestas_externas` — se le pregunta a ChatGPT y a Perplexity la consulta foco y se guarda
   **qué respondieron**: si citan el blog, qué fuentes usan y si mencionan a Alegra. Es la
   validación que se registra con la corrida; sin llave de esos modelos queda como «sin modelo»,
   no como aprobado.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from orchestrator.validator import _texto_visible

MODELOS_POR_DEFECTO = ("openai/gpt-4o-mini", "perplexity/sonar")
DOMINIO = "programascontabilidad.com"
FUENTES_PRIMARIAS = (
    "dian.gov.co",
    "sat.gob.mx",
    "hacienda.go.cr",
    "dgii.gov.do",
    "siigo.com",
    "alegra.com",
    "loggro.com",
    "siesa.com",
    "worldoffice",
)


@dataclass
class Chequeo:
    codigo: str
    pasa: bool
    detalle: str
    grave: bool = False


def _parrafos(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", " ", p).strip() for p in re.findall(r"<p\b[^>]*>(.*?)</p>", html, re.I | re.S)]


def _sin_acentos(texto: str) -> str:
    import unicodedata

    plano = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in plano if not unicodedata.combining(c)).lower()


def revisar(html: str, keyword: str) -> list[Chequeo]:
    """Los ocho controles de citabilidad. Los graves ameritan corrección antes de publicar."""
    visibles = _texto_visible(html)
    parrafos = [p for p in _parrafos(html) if len(p.split()) >= 5]
    chequeos: list[Chequeo] = []

    # 1. Respuesta directa en el primer párrafo, corta y con la consulta foco.
    primero = parrafos[0] if parrafos else ""
    clave = _sin_acentos(keyword)
    corto = 0 < len(primero.split()) <= 70
    tiene_clave = clave and clave in _sin_acentos(primero)
    chequeos.append(
        Chequeo(
            "aeo_respuesta_directa",
            bool(primero) and corto and bool(tiene_clave),
            f"primer párrafo: {len(primero.split())} palabras; "
            f"menciona la consulta: {'sí' if tiene_clave else 'no'}",
            grave=True,
        )
    )

    # 2. Bloque de resumen: lo que un modelo puede citar sin leer todo.
    tiene_resumen = bool(
        re.search(r"(?i)(respuesta rápida|respuesta rapida|en resumen|en breve|lo esencial)", visibles)
    )
    chequeos.append(
        Chequeo(
            "aeo_resumen",
            tiene_resumen,
            "trae un bloque de respuesta rápida o resumen" if tiene_resumen else "no hay bloque de resumen",
            grave=True,
        )
    )

    # 3. Secciones en forma de pregunta: el formato que citan los motores generativos.
    preguntas = re.findall(r"<h[23][^>]*>\s*([^<]{8,140}\?)\s*</h[23]>", html, re.I)
    chequeos.append(
        Chequeo(
            "aeo_preguntas_visibles",
            len(preguntas) >= 2,
            f"{len(preguntas)} encabezados en forma de pregunta (mínimo 2)",
        )
    )

    # 4. Definición explícita: «X es …», la frase que un modelo copia para explicar.
    definicion = re.search(
        r"(?i)\b(es|son|consiste en|sirve para|se define como)\b", " ".join(parrafos[:6])
    )
    chequeos.append(
        Chequeo(
            "aeo_definicion",
            bool(definicion),
            "hay una definición en los primeros párrafos" if definicion else "no hay definición explícita",
        )
    )

    # 5. Dato citable: tabla o lista con cifras y fuente.
    tablas = len(re.findall(r"<table", html, re.I))
    con_pie = len(re.findall(r"<caption", html, re.I))
    cifras = len(re.findall(r"\b\d{2,3}(?:[.,]\d{3})+\b", visibles))
    chequeos.append(
        Chequeo(
            "aeo_dato_citable",
            (tablas >= 1 and con_pie >= 1) or cifras >= 5,
            f"{tablas} tabla(s), {con_pie} con pie de fuente, {cifras} cifras en el texto",
        )
    )

    # 6. Fuentes primarias enlazadas.
    enlaces = re.findall(r'href="(https?://[^"]+)"', html, re.I)
    primarias = [u for u in enlaces if any(d in u.lower() for d in FUENTES_PRIMARIAS)]
    chequeos.append(
        Chequeo(
            "aeo_fuentes",
            len(primarias) >= 2,
            f"{len(primarias)} enlaces a fuentes primarias (mínimo 2)",
        )
    )

    # 7. Entidad sin ambigüedad: el nombre del producto aparece en el arranque.
    entidad = _sin_acentos(visibles[:1200])
    nombra = any(_sin_acentos(m) in entidad for m in ("alegra", "siigo", "loggro", "world office", "siesa"))
    chequeos.append(
        Chequeo(
            "aeo_entidad",
            nombra,
            "el producto se nombra en el arranque" if nombra else "no se nombra el producto en el arranque",
        )
    )

    # 8. FAQ desplegable (informativo: Sharon decidió que no es obligatoria).
    chequeos.append(
        Chequeo(
            "aeo_faq",
            "<details" in html.lower(),
            "trae FAQ desplegable" if "<details" in html.lower() else "sin FAQ desplegable (opcional)",
        )
    )

    return chequeos


def puntaje(chequeos: Sequence[Chequeo]) -> float:
    """Proporción de controles superados, sin contar la FAQ (opcional)."""
    evaluables = [c for c in chequeos if c.codigo != "aeo_faq"]
    if not evaluables:
        return 0.0
    return round(sum(1 for c in evaluables if c.pasa) / len(evaluables), 3)


def graves(chequeos: Sequence[Chequeo]) -> list[Chequeo]:
    return [c for c in chequeos if c.grave and not c.pasa]


def preguntas_para_modelos(html: str, keyword: str) -> list[str]:
    """Las preguntas con las que se prueba la citabilidad: la consulta foco y las del artículo."""
    salida = [f"¿Cuál es el mejor {keyword}? Responde con fuentes."]
    for texto in re.findall(r"<h[23][^>]*>\s*([^<]{8,140}\?)\s*</h[23]>", html, re.I)[:2]:
        pregunta = re.sub(r"\s+", " ", texto).strip()
        if pregunta not in salida:
            salida.append(pregunta)
    return salida


def respuestas_externas(
    preguntas: Sequence[str],
    consultar: Callable[[str, str], str] | None,
    modelos: Sequence[str] = MODELOS_POR_DEFECTO,
) -> dict[str, Any]:
    """Pregunta a ChatGPT y Perplexity y guarda la respuesta tal cual.

    Sin llave de esos modelos (o sin pasarela que los sirva) el resultado es explícito:
    `sin_modelo`. No se marca como aprobado lo que no se comprobó.
    """
    if consultar is None:
        return {
            "estado": "sin_modelo",
            "detalle": "no hay llave de ChatGPT ni de Perplexity configurada",
            "modelos": list(modelos),
            "respuestas": [],
        }

    respuestas: list[dict[str, Any]] = []
    for modelo in modelos:
        for pregunta in preguntas:
            entrada: dict[str, Any] = {"modelo": modelo, "pregunta": pregunta}
            try:
                texto = consultar(modelo, pregunta)
                entrada["respuesta"] = (texto or "").strip()[:2000]
                entrada["cita_el_blog"] = DOMINIO in (texto or "").lower()
                entrada["menciona_alegra"] = "alegra" in (texto or "").lower()
                entrada["estado"] = "ok"
            except Exception as error:  # noqa: BLE001 - se registra el fallo, no se inventa
                entrada["estado"] = "error"
                entrada["detalle"] = str(error)[:300]
            respuestas.append(entrada)

    estados = {r["estado"] for r in respuestas}
    return {
        "estado": "ok" if "ok" in estados else "sin_respuesta",
        "modelos": list(modelos),
        "citado": any(r.get("cita_el_blog") for r in respuestas),
        "respuestas": respuestas,
    }


def guardar(informe: dict[str, Any], carpeta: Path) -> Path:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "aeo.json"
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def informe(html: str, keyword: str, externas: dict[str, Any] | None = None) -> dict[str, Any]:
    chequeos = revisar(html, keyword)
    return {
        "puntaje": puntaje(chequeos),
        "chequeos": [asdict(c) for c in chequeos],
        "graves_fallidos": [c.codigo for c in graves(chequeos)],
        "preguntas": preguntas_para_modelos(html, keyword),
        "respuestas_externas": externas or {"estado": "no_ejecutada"},
    }
