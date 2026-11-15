"""El generador de temas: lo que la corrida diaria necesita para no quedarse en blanco."""

import unittest
from datetime import date

from orchestrator.temas import cubierto, tema_del_dia, temas_nuevos


class TemasTests(unittest.TestCase):
    def test_todas_las_propuestas_son_create_y_del_pais(self):
        propuestas = temas_nuevos("CO", [])

        self.assertTrue(propuestas)
        for propuesta in propuestas:
            self.assertEqual(propuesta.action, "create")
            self.assertEqual(propuesta.country, "CO")

    def test_un_segmento_publicado_no_se_vuelve_a_proponer(self):
        archivo = [
            "https://programascontabilidad.com/comparativas-de-software/"
            "software-contable-para-ferreterias-en-colombia/"
        ]

        palabras = [p.focus_keyword for p in temas_nuevos("CO", archivo)]

        self.assertNotIn("software contable para ferreterías en colombia", palabras)
        self.assertTrue(any("droguerías" in palabra for palabra in palabras))

    def test_un_par_de_marca_cubierto_no_se_propone(self):
        archivo = [
            "https://programascontabilidad.com/comparativas-de-software/alegra-vs-pacioli-2026/"
        ]

        palabras = [p.focus_keyword for p in temas_nuevos("DO", archivo)]

        self.assertNotIn("alegra vs pacioli", palabras)

    def test_los_pares_de_marca_van_primero(self):
        propuestas = temas_nuevos("DO", [])

        self.assertEqual(propuestas[0].intent, "compare")
        self.assertGreaterEqual(propuestas[0].score, 70.0)
        self.assertIn("fichas del país están en el registro", propuestas[0].evidence["reason"])

    def test_un_mercado_fuera_del_portal_se_rechaza(self):
        with self.assertRaises(ValueError):
            temas_nuevos("PE", [])

    def test_nunca_propone_a_alegra_contra_si_misma(self):
        palabras = [p.focus_keyword for p in temas_nuevos("CR", [])]

        self.assertFalse(any("alegra vs alegra" in palabra for palabra in palabras))

    def test_el_tema_del_dia_es_estable_y_rota(self):
        archivo = []

        primero = tema_del_dia("CO", archivo, dia=date(2026, 11, 15))
        segundo = tema_del_dia("CO", archivo, dia=date(2026, 11, 15))
        siguiente = tema_del_dia("CO", archivo, dia=date(2026, 11, 16))

        self.assertIsNotNone(primero)
        self.assertIsNotNone(segundo)
        self.assertIsNotNone(siguiente)
        assert primero and segundo and siguiente
        self.assertEqual(primero.focus_keyword, segundo.focus_keyword)
        self.assertNotEqual(primero.focus_keyword, siguiente.focus_keyword)

    def test_cuando_todo_esta_cubierto_no_hay_temas(self):
        # Es el caso que dispara el respaldo de GSC: sin temas curados, decide el rendimiento.
        from orchestrator.directorio import con_ficha
        from orchestrator.temas import _slug, segmentos

        archivo = [
            f"https://programascontabilidad.com/comparativas-de-software/"
            f"{_slug('software contable para ' + s + ' en colombia')}/"
            for s in segmentos("CO")
        ]
        for marca in con_ficha("CO"):
            if marca != "alegra":
                archivo.append(
                    f"https://programascontabilidad.com/comparativas-de-software/"
                    f"alegra-vs-{_slug(marca)}-colombia/"
                )

        self.assertEqual(temas_nuevos("CO", archivo), [])
        self.assertIsNone(tema_del_dia("CO", archivo))

    def test_cubierto_ignora_acentos_y_plurales(self):
        archivo = ["https://programascontabilidad.com/software-de-facturacion-para-panaderia/"]

        self.assertTrue(cubierto(archivo, "panaderías"))
        self.assertFalse(cubierto(archivo, "ferreterías"))


if __name__ == "__main__":
    unittest.main()
