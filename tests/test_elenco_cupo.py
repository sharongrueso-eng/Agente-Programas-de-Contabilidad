"""El cupo del formato se cuenta; el título se corrige en vez de bloquear.

La regla vieja bloqueaba la pieza cuando el cuerpo nombraba marcas que el título no anunciaba,
y la bloqueaba al final de la cadena, con la producción ya pagada. Ahora hay dos piezas: un cupo
por formato que se corrige, y un paso de título que anuncia el elenco que el artículo trata.
"""

import unittest

from orchestrator.formato import marcas_nombradas, presupuesto
from orchestrator.mercado import PAISES, validar_pais
from orchestrator.producer import Draft
from orchestrator.titulo import reconciliar


def _draft(titulo: str, cuerpo: str) -> Draft:
    return Draft(title=titulo, meta_description="", html=cuerpo, alt_text="", slug="slug")


class _Brief:
    def __init__(self, formato: str, pais: str = "CO") -> None:
        self.format = formato
        self.country = pais


class CupoDelFormatoTests(unittest.TestCase):
    def test_los_cupos_son_los_acordados(self) -> None:
        self.assertEqual(presupuesto("resena").elenco_max, 2)
        self.assertEqual(presupuesto("comparativa").elenco_max, 5)
        self.assertEqual(presupuesto("mejores").elenco_max, 8)
        self.assertEqual(presupuesto("guia").elenco_max, 1)
        self.assertEqual(presupuesto("desconocido").elenco_max, 5)

    def test_las_marcas_se_cuentan_en_titulo_y_cuerpo(self) -> None:
        cuerpo = "<p>Siigo y Loggro; también World Office y Helisa.</p>"

        nombradas = marcas_nombradas(cuerpo, "Siigo: precios", "CO")

        self.assertEqual(len(nombradas), 4)
        self.assertIn("helisa", [m.lower() for m in nombradas])

    def test_alegra_no_gasta_cupo(self) -> None:
        cuerpo = "<p>Alegra, Siigo y Loggro.</p>"

        self.assertEqual(marcas_nombradas(cuerpo, "", "CO"), ["Loggro", "Siigo"])


class ReconciliarTituloTests(unittest.TestCase):
    def test_una_comparativa_anuncia_el_elenco_del_cuerpo(self) -> None:
        draft = _draft(
            "Susii: opiniones y precios",
            "<p>Frente a Siigo, Loggro y Helisa, susii se queda corto.</p>",
        )

        nuevo, motivo = reconciliar(draft, _Brief("comparativa"))

        self.assertNotEqual(nuevo.title, draft.title)
        self.assertIn("Siigo", nuevo.title)
        self.assertIn("título anuncia", motivo)
        self.assertEqual(nuevo.slug, draft.slug)
        self.assertEqual(nuevo.html, draft.html)

    def test_no_toca_el_titulo_si_ya_anuncia_dos_marcas(self) -> None:
        draft = _draft("Alegra vs Siigo: precios", "<p>Siigo, Loggro y World Office.</p>")

        nuevo, motivo = reconciliar(draft, _Brief("comparativa"))

        self.assertEqual(nuevo.title, draft.title)
        self.assertEqual(motivo, "")

    def test_no_toca_una_resena(self) -> None:
        draft = _draft("Susii: opiniones", "<p>Frente a Siigo y Loggro.</p>")

        nuevo, motivo = reconciliar(draft, _Brief("resena"))

        self.assertEqual(nuevo.title, draft.title)
        self.assertEqual(motivo, "")

    def test_un_titulo_que_ya_dice_comparativa_no_la_repite(self) -> None:
        draft = _draft("Susii: comparativa de software contable", "<p>Siigo y Loggro.</p>")

        nuevo, _ = reconciliar(draft, _Brief("comparativa"))

        self.assertEqual(nuevo.title.lower().count("comparativa"), 1)
        self.assertIn(" · con ", nuevo.title)
        self.assertIn("Siigo", nuevo.title)
        self.assertIn("Loggro", nuevo.title)


class MercadosTests(unittest.TestCase):
    def test_los_cuatro_mercados_del_portal(self) -> None:
        self.assertEqual(PAISES, ("CO", "MX", "CR", "DO"))
        for pais in PAISES:
            self.assertEqual(validar_pais(pais.lower()), pais)

    def test_un_quinto_mercado_se_rechaza(self) -> None:
        with self.assertRaises(ValueError):
            validar_pais("PE")


if __name__ == "__main__":
    unittest.main()
