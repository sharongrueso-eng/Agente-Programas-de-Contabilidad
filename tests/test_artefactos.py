"""Lo que nunca debe llegar al post: andamiaje de la producción, viñetas fuera del marco,
enlaces muertos y una firma sin la foto del autor.

Todo salió de la revisión del borrador 5685 (ferreterías CO, 15-nov-2026), que se publicó con
«## Bloque «Alegra» — fragmento listo para pegar», cercas de markdown, siete enlaces a 404 y la
inicial «L» en lugar de la ficha del autor.
"""

import unittest

from orchestrator import enlaces, linea_visual, presentacion
from orchestrator.validator import limpiar_artefactos


class AndamiajeTests(unittest.TestCase):
    def test_se_quita_el_encabezado_de_bloque_y_la_cerca(self):
        html = (
            "<p>Texto del artículo.</p>"
            "<p>## Bloque «Alegra» — fragmento listo para pegar «`html</p>"
            "<p>```html</p><p>Más texto.</p><p>```</p>"
        )

        limpio, retirados = limpiar_artefactos(html)

        self.assertNotIn("## Bloque", limpio)
        self.assertNotIn("```", limpio)
        self.assertNotIn("fragmento listo para pegar", limpio)
        self.assertIn("Texto del artículo.", limpio)
        self.assertIn("Más texto.", limpio)
        self.assertTrue(any("andamiaje" in r for r in retirados))

    def test_se_quita_la_nota_de_proceso_entera(self):
        html = (
            "<p>Un párrafo normal.</p>"
            "<p>Para cerrar el bloque antes de publicar (tres datos, ninguna cifra inventada):</p>"
            "<ul><li>Tabla de planes de World Office Cloud leída del sitio del fabricante.</li>"
            "<li>Confirmar si el precio se publica por plan cerrado.</li></ul>"
        )

        limpio, _ = limpiar_artefactos(html)

        self.assertNotIn("Para cerrar el bloque", limpio)
        self.assertNotIn("Confirmar si el precio", limpio)
        self.assertIn("Un párrafo normal.", limpio)

    def test_se_quita_el_marcador_pendiente(self):
        limpio, retirados = limpiar_artefactos("<p>Precio [PENDIENTE: tabla WP] del plan.</p>")

        self.assertNotIn("PENDIENTE", limpio)
        self.assertIn("Precio  del plan.", limpio)
        self.assertTrue(any("pendientes" in r for r in retirados))

    def test_se_quitan_los_comentarios_de_gutenberg(self):
        limpio, _ = limpiar_artefactos(
            "<!-- wp:paragraph --><p>Texto.</p><!-- /wp:paragraph -->"
        )

        self.assertNotIn("wp:paragraph", limpio)
        self.assertIn("<p>Texto.</p>", limpio)


class ListasTests(unittest.TestCase):
    def test_toda_lista_lleva_sangria_con_important(self):
        html = linea_visual.normalizar_listas("<p>x</p><ul><li>uno</li></ul><ol><li>dos</li></ol>")

        self.assertEqual(html.count("padding-left:22px !important"), 2)
        self.assertIn('style="margin:0 0 16px 0;padding-left:22px !important;"', html)

    def test_no_toca_una_lista_que_ya_la_tiene(self):
        original = '<ul style="padding-left:20px !important;"><li>uno</li></ul>'

        self.assertEqual(linea_visual.normalizar_listas(original), original)

    def test_corrige_el_padding_left_sin_important(self):
        html = linea_visual.normalizar_listas('<ul style="padding-left:0;"><li>uno</li></ul>')

        self.assertIn("padding-left:22px !important", html)
        self.assertNotIn("padding-left:0", html)


class EnlacesTests(unittest.TestCase):
    def test_un_enlace_roto_pierde_el_ancla_y_conserva_el_texto(self):
        html = '<p>Ver <a href="https://www.siigo.com/precios/">precios de Siigo</a> y nada más.</p>'

        limpio, retirados = enlaces.revisar(html, permitidas=[], comprobar=lambda _u: 404)

        self.assertNotIn("<a ", limpio)
        self.assertIn("precios de Siigo", limpio)
        self.assertEqual(len(retirados), 1)

    def test_un_enlace_interno_fuera_del_sitemap_se_retira(self):
        html = '<p><a href="https://programascontabilidad.com/software-pos-colombia/">POS</a></p>'

        limpio, retirados = enlaces.revisar(
            html,
            permitidas=["https://programascontabilidad.com/mejores-software-contable-colombia/"],
            comprobar=lambda _u: 200,
        )

        self.assertNotIn("<a ", limpio)
        self.assertIn("POS", limpio)
        self.assertEqual(retirados, ["https://programascontabilidad.com/software-pos-colombia/"])

    def test_un_enlace_interno_del_sitemap_se_queda(self):
        url = "https://programascontabilidad.com/mejores-software-contable-colombia/"
        html = f'<p><a href="{url}">mejores</a></p>'

        limpio, retirados = enlaces.revisar(html, permitidas=[url], comprobar=lambda _u: 200)

        self.assertEqual(limpio, html)
        self.assertEqual(retirados, [])

    def test_un_403_no_se_toma_por_roto(self):
        html = '<p><a href="https://www.dian.gov.co/">DIAN</a></p>'

        limpio, retirados = enlaces.revisar(html, permitidas=[], comprobar=lambda _u: 403)

        self.assertEqual(limpio, html)
        self.assertEqual(retirados, [])


class FirmaTests(unittest.TestCase):
    def test_la_firma_lleva_la_foto_del_autor_y_no_una_inicial(self):
        firma = presentacion.firma()

        self.assertIn(linea_visual.AVATAR_LEANDRO, firma)
        self.assertIn("Leandro", firma)
        self.assertNotIn(">L<", firma)


if __name__ == "__main__":
    unittest.main()
