"""El diagnóstico diario: qué dice GSC de cada URL y qué se hace con ella.

Esta es la regla de negocio del agente, en código:

- Una señal solo cuenta con **100 impresiones o más en 28 días en CO y MX**, y **30 o más en
  CR y DO**. Por debajo, la URL no entra en el ranking.
- Sin datos de GSC de **máximo 7 días** no hay slot: falla cerrada, no se escribe ni se reencaucha.
- La intención se clasifica con reglas de palabras (`vs`, `alternativas`, `mejores`, `opiniones`,
  `precio`); si queda ambigua, la decide un modelo y el resultado queda escrito en el diagnóstico.
- Cada URL recibe **una** decisión, tomada en este orden: caída → estructura → snippet →
  consolidar → no tocar. Las consultas con impresiones y sin URL dedicada se convierten en
  `create`; sin señal de GSC, solo con evidencia alternativa y la marca «revisar país».
- El ranking y el calendario quincenal se guardan con la corrida: el equipo ve el mismo número que
  vio el agente.

Ahrefs no entra aquí: aporta volumen, SERP, competidores y citaciones en respuestas de IA, pero
GSC decide. Cuando haya llave de Ahrefs, se suma a la evidencia de cada oportunidad sin cambiar
las decisiones.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from orchestrator.audit import (
    AuditRules,
    Opportunity,
    PageMetrics,
    classify_intent,
    expected_ctr,
)
from orchestrator.mercado import PAISES

UMBRALES: Mapping[str, int] = {"CO": 100, "MX": 100, "CR": 30, "DO": 30}
EDAD_MAXIMA_DIAS = 7
DIAS_CALENDARIO = 14
# Prioridad del día: primero lo que mejora lo que ya posiciona, después lo nuevo.
PRIORIDAD = {
    "refresh_by_decline": 0,
    "refresh_structure": 1,
    "refresh_snippet": 2,
    "consolidate": 3,
    "create": 4,
    "create_with_alternative_evidence": 5,
}
HABILES = (0, 1, 2, 3, 4)  # lunes a viernes


class SinDatos(ValueError):
    """No hay diagnóstico posible: datos viejos o de otro mercado. Falla cerrada."""


def umbral(pais: str) -> int:
    return UMBRALES[pais]


def edad_de_los_datos(capturado: date, hoy: date | None = None) -> int:
    return ((hoy or date.today()) - capturado).days


def vigente(capturado: date, hoy: date | None = None, maximo: int = EDAD_MAXIMA_DIAS) -> bool:
    """Los datos sirven si tienen 7 días o menos."""
    return edad_de_los_datos(capturado, hoy) <= maximo


# --- intención ------------------------------------------------------------------------------


def intencion_de(query: str, consultar_modelo: Callable[[str], str] | None = None) -> tuple[str, str]:
    """Devuelve (intención, cómo se decidió).

    Las reglas cubren los cinco casos de la especificación. Si la consulta no trae ninguna marca
    —ni `vs`, ni `mejores`, ni `opiniones`, ni `precio`— y hay modelo disponible, se le pregunta;
    lo que responda queda en el diagnóstico, no se vuelve a decidir cada día.
    """
    reglas = classify_intent(query)
    if reglas != "learn" or consultar_modelo is None:
        return reglas, "reglas"
    try:
        respuesta = (consultar_modelo(query) or "").strip().lower()
    except Exception:  # noqa: BLE001 - sin modelo se queda la regla
        return reglas, "reglas"
    if respuesta in {"compare", "best", "review", "price", "learn"}:
        return respuesta, "modelo"
    return reglas, "reglas"


# --- solapamiento ---------------------------------------------------------------------------


def solapamientos(
    pages: Sequence[PageMetrics], min_compartidas: int = 2, umbral: float = 0.3
) -> list[dict[str, Any]]:
    """Pares de URLs del mismo país que compiten por las mismas consultas.

    Se exige un solapamiento real (Jaccard >= 0.3 sobre las consultas principales, con al menos
    dos consultas en común): compartir una consulta genérica no es canibalización. La dueña es la
    que tiene más clics; la otra se sugiere para 301 en el reporte. El agente **no** aplica
    redirecciones: son una decisión de quien conoce el archivo.
    """
    por_pais: dict[str, list[PageMetrics]] = {}
    for page in pages:
        por_pais.setdefault(page.country, []).append(page)

    pares: list[dict[str, Any]] = []
    for pais, lista in por_pais.items():
        for i, una in enumerate(lista):
            consultas_una = {q.query.lower() for q in una.top_queries}
            if len(consultas_una) < min_compartidas:
                continue
            for otra in lista[i + 1 :]:
                consultas_otra = {q.query.lower() for q in otra.top_queries}
                compartidas = consultas_una & consultas_otra
                if len(compartidas) < min_compartidas:
                    continue
                union = consultas_una | consultas_otra
                jaccard = len(compartidas) / len(union) if union else 0.0
                if jaccard < umbral:
                    continue
                duena, perdedora = (una, otra) if una.clicks >= otra.clicks else (otra, una)
                pares.append(
                    {
                        "pais": pais,
                        "duena": duena.url,
                        "sugerida_para_301": perdedora.url,
                        "consultas_compartidas": sorted(compartidas)[:10],
                        "solapamiento": round(jaccard, 3),
                        "clics_duena": duena.clicks,
                        "clics_perdedora": perdedora.clicks,
                    }
                )

    # Una URL perdedora se sugiere una sola vez: el par con más solapamiento.
    mejores: dict[str, dict[str, Any]] = {}
    for par in pares:
        actual = mejores.get(par["sugerida_para_301"])
        if actual is None or par["solapamiento"] > actual["solapamiento"]:
            mejores[par["sugerida_para_301"]] = par
    return sorted(mejores.values(), key=lambda p: p["solapamiento"], reverse=True)


# --- diagnóstico ----------------------------------------------------------------------------


@dataclass
class Diagnostico:
    pais: str
    generado: date
    datos_de: date
    edad_dias: int
    umbral_impresiones: int
    paginas: list[dict[str, Any]] = field(default_factory=list)
    oportunidades: list[Opportunity] = field(default_factory=list)
    solapamientos: list[dict[str, Any]] = field(default_factory=list)
    ahrefs: str = "sin llave: no se usa"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pais": self.pais,
            "generado": self.generado.isoformat(),
            "datos_de": self.datos_de.isoformat(),
            "edad_dias": self.edad_dias,
            "umbral_impresiones": self.umbral_impresiones,
            "paginas": self.paginas,
            "oportunidades": [asdict(o) for o in self.oportunidades],
            "solapamientos": self.solapamientos,
            "ahrefs": self.ahrefs,
        }


def _ficha_de_pagina(page: PageMetrics) -> dict[str, Any]:
    consultas = sorted(page.top_queries, key=lambda q: (q.clicks, q.impressions), reverse=True)
    dominante = consultas[0].query if consultas else ""
    intencion = classify_intent(dominante) if dominante else "learn"
    real = page.clicks / page.impressions if page.impressions else 0.0
    return {
        "url": page.url,
        "clics": page.clicks,
        "clics_previos": page.prev_clicks,
        "impresiones": page.impressions,
        "ctr": round(real, 4),
        "ctr_esperado": expected_ctr(page.position),
        "posicion": page.position,
        "posicion_previa": page.prev_position,
        "consulta_dominante": dominante,
        "intencion": intencion,
        "formato_publicado": page.format,
        "actualizada_hace_dias": page.updated_days_ago,
        "consultas_principales": [
            {"query": q.query, "clics": q.clicks, "impresiones": q.impressions, "posicion": q.position}
            for q in consultas[:25]
        ],
    }


def diagnosticar(
    pages: Sequence[PageMetrics],
    pais: str,
    *,
    capturado: date,
    rules: AuditRules | None = None,
    hoy: date | None = None,
    consultar_modelo: Callable[[str], str] | None = None,
    oportunidades: Sequence[Opportunity] | None = None,
) -> Diagnostico:
    """Arma el diagnóstico del país. Sin datos frescos lanza `SinDatos`."""
    if pais not in PAISES:
        raise SinDatos(f"el mercado «{pais}» no está en el portal: solo CO, MX, CR, DO")
    hoy = hoy or date.today()
    if not vigente(capturado, hoy):
        raise SinDatos(
            f"GSC de {capturado.isoformat()} tiene {edad_de_los_datos(capturado, hoy)} días; "
            f"el máximo es {EDAD_MAXIMA_DIAS}. Sin dato fresco no hay slot."
        )

    reglas = rules or AuditRules.from_file()
    del_pais = [p for p in pages if (p.country or "").upper() == pais]
    fichas = [_ficha_de_pagina(p) for p in del_pais]

    if consultar_modelo is not None:
        for ficha in fichas:
            if ficha["consulta_dominante"]:
                ficha["intencion"], ficha["intencion_decidida_por"] = intencion_de(
                    ficha["consulta_dominante"], consultar_modelo
                )

    if oportunidades is None:
        from orchestrator.audit import find_opportunities

        oportunidades = find_opportunities(pages, reglas)

    propias = [o for o in oportunidades if (o.country or "").upper() == pais]
    ranking = sorted(propias, key=lambda o: (PRIORIDAD.get(o.action, 9), -o.score))

    return Diagnostico(
        pais=pais,
        generado=hoy,
        datos_de=capturado,
        edad_dias=edad_de_los_datos(capturado, hoy),
        umbral_impresiones=umbral(pais),
        paginas=sorted(fichas, key=lambda f: f["clics"], reverse=True),
        oportunidades=ranking,
        solapamientos=[s for s in solapamientos(pages) if s["pais"] == pais],
    )


# --- calendario quincenal -------------------------------------------------------------------


def dias_habiles(desde: date, cuantos: int) -> list[date]:
    salida: list[date] = []
    dia = desde
    while len(salida) < cuantos:
        if dia.weekday() in HABILES:
            salida.append(dia)
        dia += timedelta(days=1)
    return salida


def calendario(
    diagnosticos: Mapping[str, Diagnostico],
    *,
    desde: date,
    temas: Mapping[str, Sequence[Opportunity]] | None = None,
    dias: int = DIAS_CALENDARIO,
) -> list[dict[str, Any]]:
    """Calendario de los próximos días hábiles, rotando los cuatro mercados.

    Cada día toma la siguiente oportunidad del mercado que le toca: primero reencauches (lo que ya
    posiciona), y cuando se acaban, los temas nuevos. Es el plan que se revisa, no una promesa.
    """
    colas: dict[str, list[dict[str, Any]]] = {}
    for pais in PAISES:
        cola: list[dict[str, Any]] = []
        diagnostico = diagnosticos.get(pais)
        if diagnostico:
            for o in diagnostico.oportunidades:
                if o.action == "consolidate":
                    continue
                cola.append(
                    {
                        "pais": pais,
                        "accion": o.action,
                        "objetivo": o.url,
                        "keyword": o.focus_keyword,
                        "motivo": str(o.evidence.get("reason", "")),
                        "puntaje": o.score,
                    }
                )
            for solape in diagnostico.solapamientos:
                cola.append(
                    {
                        "pais": pais,
                        "accion": "consolidate",
                        "objetivo": solape["duena"],
                        "keyword": "",
                        "motivo": f"301 sugerida: {solape['sugerida_para_301']}",
                        "puntaje": 0.0,
                    }
                )
        if not cola:
            for propuesta in (temas or {}).get(pais, ()):
                cola.append(
                    {
                        "pais": pais,
                        "accion": propuesta.action,
                        "objetivo": propuesta.url,
                        "keyword": propuesta.focus_keyword,
                        "motivo": str(propuesta.evidence.get("reason", "")),
                        "puntaje": propuesta.score,
                    }
                )
        colas[pais] = cola

    plan: list[dict[str, Any]] = []
    for indice, dia in enumerate(dias_habiles(desde, dias)):
        pais = PAISES[indice % len(PAISES)]
        cola = colas.get(pais) or []
        if not cola:
            plan.append(
                {
                    "fecha": dia.isoformat(),
                    "pais": pais,
                    "accion": "sin_slot",
                    "objetivo": "",
                    "keyword": "",
                    "motivo": "sin oportunidades con señal vigente",
                }
            )
            continue
        elegida = cola.pop(0)
        plan.append({"fecha": dia.isoformat(), **elegida})
    return plan


def guardar(diagnostico: Diagnostico | Iterable[Diagnostico], carpeta: Path) -> Path:
    """Guarda el diagnóstico completo con la corrida, como pide la especificación."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    if isinstance(diagnostico, Diagnostico):
        datos: Any = diagnostico.to_dict()
    else:
        datos = [d.to_dict() for d in diagnostico]
    ruta = carpeta / "diagnostico.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def guardar_calendario(plan: Sequence[dict[str, Any]], carpeta: Path) -> Path:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "calendario.json"
    ruta.write_text(json.dumps(list(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta
