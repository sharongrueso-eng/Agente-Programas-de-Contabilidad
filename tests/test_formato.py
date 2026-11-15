"""El presupuesto de forma: tablas por tipo de pieza y elenco que fija el título."""

import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.formato import (
    contar_tablas,
    elenco_cerrado,
    marcas_ajenas,
    presupuesto,
    tablas_sin_pie,
)
from orchestrator.producer import Draft
from orchestrator.validator import ValidationRules, validate

TABLA = (
    "<table><caption>Consultado el 13-nov-2026</caption><tr><th>A</th></tr>"
    "<tr><td>1</td></tr></table>"
)
SIN_PIE = "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"


def draft(html: str, titulo: str = "Plan Siigo vs Alegra: comparativa") -> Draft:
    return Draft(
        title=titulo,
        meta_description="Comparativa de planes y precios para elegir en Colombia con datos publicados.",
        html=html,
        alt_text="",
        slug="plan-siigo-vs-alegra",
    )


def brief(formato: str = "comparativa", pais: str = "CO") -> Brief:
    oportunidad = Opportunity(
        url="https://programascontabilidad.com/comparativas-de-software/siigo/",
        country=pais,
        action="refresh_structure",
        focus_keyword="comparativa",
        intent="compare",
        score=50.0,
        evidence={},
    )
    return Brief(
        task_id="t-1",
        date=date(2026, 11, 13),
        slot="A",
        format=formato,
        country=pais,
        opportunity=oportunidad,
    )


class PresupuestoTest(unittest.TestCase):
    def test_cada_formato_tiene_su_cupo(self):
        self.assertEqual(presupuesto("comparativa").tablas_max, 3)
        self.assertEqual(presupuesto("resena").tablas_max, 3)
        self.assertEqual(presupuesto("guia").tablas_max, 2)
        self.assertEqual(presupuesto("desconocido").tablas_max, 3)

    def test_contar_tablas(self):
        self.assertEqual(contar_tablas(TABLA * 5), 5)
        self.assertEqual(contar_tablas(""), 0)

    def test_tabla_sin_pie(self):
        self.assertEqual(tablas_sin_pie(TABLA + SIN_PIE), 1)


class ElencoTest(unittest.TestCase):
    def test_dos_marcas_en_el_titulo_cierran_el_elenco(self):
        self.assertTrue(elenco_cerrado("Siigo vs Alegra en Colombia", "CO", "comparativa"))

    def test_una_lista_no_cierra_el_elenco(self):
        self.assertFalse(elenco_cerrado("Los 5 mejores ERP de Colombia", "CO", "mejores"))

    def test_una_resena_de_una_marca_lo_cierra(self):
        self.assertTrue(elenco_cerrado("Adm Cloud reseña: precios y funciones", "DO", "resena"))

    def test_marca_fuera_del_elenco_se_detecta(self):
        html = "<p>Siigo y Alegra compiten con Loggro en el mismo segmento.</p>"
        ajenas = marcas_ajenas(html, "Siigo vs Alegra: comparativa", "CO")
        self.assertIn("Loggro", [m.title() for m in ajenas])


class ControlTest(unittest.TestCase):
    def codes(self, veredicto):
        return {control.code: control for control in veredicto.controls}

    def test_cinco_tablas_bloquean(self):
        veredicto = validate(draft(TABLA * 5), brief("comparativa"), ValidationRules())
        control = self.codes(veredicto)["presupuesto_tablas"]
        self.assertEqual(control.status, "BLOQUEADO")
        self.assertIn("admite 3", control.detail)

    def test_tres_tablas_pasan(self):
        veredicto = validate(draft(TABLA * 3), brief("comparativa"), ValidationRules())
        self.assertEqual(self.codes(veredicto)["presupuesto_tablas"].status, "PASS")

    def test_el_cupo_del_formato_se_corrige_y_no_bloquea(self):
        # Seis marcas del mercado en una comparativa: el cupo es 5, así que se pide corregir,
        # pero la pieza no muere — antes este control bloqueaba la corrida entera.
        html = TABLA + "<p>Siigo, Alegra, Loggro, Helisa, World Office, ContaPyme y Aliaddo.</p>"
        veredicto = validate(draft(html), brief("comparativa"), ValidationRules())
        control = self.codes(veredicto)["elenco_del_formato"]
        self.assertEqual(control.status, "CORREGIR")
        self.assertIn("admite 5", control.detail)
        self.assertNotEqual(veredicto.status, "BLOQUEADO")

    def test_competidor_fuera_del_titulo_dentro_del_cupo_no_bloquea(self):
        html = TABLA + "<p>Siigo y Alegra, frente a Loggro, que tiene comandas.</p>" * 3
        veredicto = validate(draft(html), brief("comparativa"), ValidationRules())
        self.assertEqual(self.codes(veredicto)["elenco_del_formato"].status, "PASS")
        self.assertNotEqual(veredicto.status, "BLOQUEADO")

    def test_cupo_por_formato(self):
        html = TABLA + "<p>Siigo, Loggro y Helisa.</p>"
        veredicto = validate(draft(html), brief("resena"), ValidationRules())
        control = self.codes(veredicto)["elenco_del_formato"]
        self.assertEqual(control.status, "CORREGIR")
        self.assertIn("admite 2", control.detail)

    def test_una_faq_en_encabezados_sueltos_se_marca(self):
        html = TABLA + (
            "<h2>¿Cuánto cuesta el software?</h2><p>x</p>"
            "<h2>¿Sirve para una ferretería?</h2><p>y</p>"
            "<h2>¿Se puede migrar?</h2><p>z</p>"
        )
        veredicto = validate(draft(html), brief("comparativa"), ValidationRules())
        control = self.codes(veredicto)["faq_sin_details"]
        self.assertEqual(control.status, "CORREGIR")

    def test_una_faq_con_details_pasa(self):
        html = TABLA + (
            '<details class="pdc-faq"><summary><h3><em>¿Cuánto cuesta?</em></h3></summary>'
            "<div><p>x</p></div></details>"
            "<h2>¿Sirve para una ferretería?</h2><h2>¿Se puede migrar?</h2>"
        )
        veredicto = validate(draft(html), brief("comparativa"), ValidationRules())
        self.assertNotIn("faq_sin_details", self.codes(veredicto))

    def test_resena_de_otro_producto_no_exige_enlaces_de_alegra(self):
        html = TABLA + "<p>Adm Cloud es un ERP en la nube para República Dominicana.</p>"
        veredicto = validate(
            draft(html, titulo="Adm Cloud reseña: precios y funciones"),
            brief("resena", "DO"),
            ValidationRules(),
        )
        self.assertEqual(self.codes(veredicto)["alegra_links"].status, "PASS")

    def test_comparativa_con_alegra_en_el_titulo_si_exige(self):
        html = TABLA + "<p>Siigo y Alegra, sin enlaces.</p>"
        veredicto = validate(
            draft(html, titulo="Siigo vs Alegra: comparativa"),
            brief("comparativa", "CO"),
            ValidationRules(),
        )
        self.assertEqual(self.codes(veredicto)["alegra_links"].status, "CORREGIR")


if __name__ == "__main__":
    unittest.main()
