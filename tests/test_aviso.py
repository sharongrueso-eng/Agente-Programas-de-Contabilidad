"""El aviso cuenta qué se tocó, por qué y dónde se revisa."""

import unittest

from orchestrator.notices import aviso_de_pieza, semaforo


class AvisoTests(unittest.TestCase):
    def _aviso(self, **cambios):
        datos = dict(
            titulo="Mejores software contable en Colombia",
            slug="mejores-software-contable-colombia",
            pais="CO",
            nuevo=False,
            url_edicion="https://programascontabilidad.com/wp-admin/post.php?post=5297&action=edit",
            impresiones=10309,
            ctr=0.0092,
            posicion=2.9,
            clics_potenciales=730,
            criticos_ok=20,
            criticos_total=20,
            importantes_ok=12,
            importantes_total=12,
        )
        datos.update(cambios)
        return aviso_de_pieza(**datos)

    def test_it_carries_the_identity_of_the_piece(self) -> None:
        texto = self._aviso()

        self.assertIn("Mejores software contable en Colombia", texto)
        self.assertIn("Slug: mejores-software-contable-colombia", texto)
        self.assertIn("wp-admin/post.php?post=5297", texto)

    def test_it_says_why_this_article_with_the_numbers(self) -> None:
        texto = self._aviso()

        self.assertIn("10.309 impresiones", texto)
        self.assertIn("0.92%", texto)
        self.assertIn("730", texto)

    def test_an_update_says_the_url_did_not_change(self) -> None:
        self.assertIn("URL de siempre", self._aviso())

    def test_a_new_article_says_so(self) -> None:
        self.assertIn("URL nueva", self._aviso(nuevo=True))

    def test_the_traffic_light_reflects_the_judge(self) -> None:
        self.assertEqual(semaforo(criticos_fallidos=0, importantes_fallidos=0, observaciones=1), "amarillo")
        self.assertEqual(semaforo(criticos_fallidos=1, importantes_fallidos=0), "rojo")
        self.assertEqual(semaforo(criticos_fallidos=0, importantes_fallidos=0), "verde")


if __name__ == "__main__":
    unittest.main()
