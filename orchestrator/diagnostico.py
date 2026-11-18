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

Ahrefs no decide: aporta volumen, SERP, competidores y citaciones en respuestas de IA, pero GSC
decide. Con `AHREFS_API_KEY` (ver `orchestrator/ahrefs.py`) se suma a la evidencia de las
primeras oportunidades del ranking sin cambiar acción, intención ni puntaje.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
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


INTENCIONES = ("compare", "best", "review", "price", "learn")


def pregunta_de_intencion(query: str) -> str:
    """El prompt del modelo: una palabra, sin explicación, para que no haya nada que interpretar."""
    return (
        "Clasifica la intención de esta búsqueda de Google hecha por una pyme o un contador que "
        "busca software contable, de facturación electrónica, POS, ERP o nómina en "
        "Latinoamérica. Responde solo una palabra:\n"
        "compare = quiere comparar dos o más programas o ver alternativas\n"
        "best = quiere una lista de los mejores programas para un caso\n"
        "review = quiere saber cómo es un programa concreto (opiniones, funciones, qué es)\n"
        "price = quiere precios o planes\n"
        "learn = quiere aprender a hacer algo o entender un tema, o va a la web de una marca\n\n"
        f"Búsqueda: {query}"
    )


class LimiteDelDia(RuntimeError):
    """Se alcanzó el máximo de consultas nuevas al modelo en esta corrida."""


class ModeloConMemoria:
    """Envuelve `consultar_modelo`: lo que el modelo ya decidió no se le vuelve a preguntar.

    La memoria es un JSON {consulta normalizada: intención} en el volumen de estado. Se carga
    también una semilla del repositorio (`datos/referencia/intenciones-semilla.json`), así la
    primera corrida no hace cientos de llamadas. Solo se guardan respuestas válidas, y hay un
    máximo de consultas nuevas por corrida para no comerse el tiempo de la tarea: lo que queda
    sin preguntar se resuelve con las reglas hoy y con el modelo otro día.
    """

    def __init__(
        self,
        consultar: Callable[[str], str],
        ruta: Path,
        *,
        semilla: Path | None = None,
        maximo_nuevas: int = 40,
    ) -> None:
        self.consultar = consultar
        self.ruta = Path(ruta)
        self.maximo_nuevas = maximo_nuevas
        self.nuevas = 0
        self.memoria: dict[str, str] = {}
        for archivo in (semilla, self.ruta):
            if archivo and Path(archivo).exists():
                try:
                    datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                self.memoria.update(
                    {self.clave(k): v for k, v in datos.items() if v in INTENCIONES}
                )

    @staticmethod
    def clave(query: str) -> str:
        return " ".join(query.lower().split())

    def __call__(self, query: str) -> str:
        clave = self.clave(query)
        if clave in self.memoria:
            return self.memoria[clave]
        if self.nuevas >= self.maximo_nuevas:
            raise LimiteDelDia(f"máximo de {self.maximo_nuevas} consultas nuevas por corrida")
        self.nuevas += 1
        crudo = (self.consultar(query) or "").strip().lower()
        respuesta = next((t for t in re.findall(r"[a-z]+", crudo) if t in INTENCIONES), "")
        if respuesta:
            self.memoria[clave] = respuesta
        return respuesta

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(dict(sorted(self.memoria.items())), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        temporal.replace(self.ruta)


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
        "impresiones_previas": page.prev_impressions,
        "historico_16m_por_28_dias": (
            {"clics": page.hist_clicks_28d, "impresiones": page.hist_impressions_28d}
            if page.hist_impressions_28d is not None
            else None
        ),
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
    ahrefs: Any = None,
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

    # Lo que el modelo decidió para una consulta ambigua también vale para la oportunidad de esa
    # URL, pero solo si las reglas la dejaron en «learn» y es la misma consulta: el modelo
    # desempata, no corrige a las reglas.
    por_modelo = {
        f["url"]: f["intencion"]
        for f in fichas
        if f.get("intencion_decidida_por") == "modelo"
    }
    fichas_por_url = {f["url"]: f for f in fichas}
    propias = [
        replace(o, intent=por_modelo[o.url])
        if o.intent == "learn"
        and o.url in por_modelo
        and fichas_por_url[o.url]["consulta_dominante"].lower() == (o.focus_keyword or "").lower()
        else o
        for o in propias
    ]
    ranking = sorted(propias, key=lambda o: (PRIORIDAD.get(o.action, 9), -o.score))

    estado_ahrefs = "sin llave: no se usa"
    if ahrefs is not None:
        try:
            ranking, estado_ahrefs = ahrefs.enriquecer(pais, ranking)
        except Exception as error:  # noqa: BLE001 - Ahrefs complementa; nunca tumba el diagnóstico
            estado_ahrefs = f"error: {str(error)[:160]}"

    return Diagnostico(
        pais=pais,
        generado=hoy,
        datos_de=capturado,
        edad_dias=edad_de_los_datos(capturado, hoy),
        umbral_impresiones=umbral(pais),
        paginas=sorted(fichas, key=lambda f: f["clics"], reverse=True),
        oportunidades=ranking,
        solapamientos=[s for s in solapamientos(pages) if s["pais"] == pais],
        ahrefs=estado_ahrefs,
    )


def en_descanso(
    oportunidades: Sequence[Opportunity], journal: Any, dia: date | None = None
) -> tuple[list[Opportunity], list[Opportunity]]:
    """Separa lo que se puede tocar hoy de lo que está en descanso de 30 días.

    La regla es del proyecto y vive en `RefreshJournal`; el registro estaba conectado al comando
    `plan` pero no a la corrida diaria, así que la misma URL volvía a salir cada vez que le tocaba
    al país. Aquí se aplica a lo que la corrida va a elegir.
    """
    if journal is None:
        return list(oportunidades), []
    hoy = dia or date.today()
    libres: list[Opportunity] = []
    descansando: list[Opportunity] = []
    for oportunidad in oportunidades:
        if oportunidad.url and not journal.can_refresh(oportunidad.url, hoy):
            descansando.append(oportunidad)
        else:
            libres.append(oportunidad)
    return libres, descansando


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
