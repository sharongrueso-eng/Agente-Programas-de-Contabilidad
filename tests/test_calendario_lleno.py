"""El calendario no deja días hábiles vacíos: si el mercado del día no tiene señal, entra la mejor
oportunidad del resto del portal."""

from datetime import date

from orchestrator.audit import Opportunity
from orchestrator.diagnostico import calendario


class Diagnostico:
    def __init__(self, oportunidades):
        self.oportunidades = oportunidades
        self.solapamientos = []


def _oportunidad(url: str, score: float, pais: str = "MX"):
    return Opportunity(
        url=url,
        country=pais,
        action="refresh_by_decline",
        focus_keyword="precios de software contable",
        intent="price",
        score=score,
        evidence={"reason": "posición 20 vs 12"},
    )


def test_los_dias_sin_senal_de_su_mercado_se_llenan_con_otro():
    diag = {"MX": Diagnostico([_oportunidad(f"https://x/{i}/", 10 - i) for i in range(6)])}
    plan = calendario(diag, desde=date(2026, 11, 23), dias=5)

    assert len(plan) == 5
    vacios = [s for s in plan if s["accion"] == "sin_slot"]
    assert vacios == []
    objetivos = [s["objetivo"] for s in plan]
    assert len(set(objetivos)) == 5  # no se repite una pieza


def test_sin_ninguna_oportunidad_el_dia_queda_vacio_y_lo_dice():
    plan = calendario({}, desde=date(2026, 11, 23), dias=2)
    assert all(s["accion"] == "sin_slot" for s in plan)
    assert "ningún mercado" in plan[0]["motivo"]
