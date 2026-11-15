"""El tema del artículo puede nombrarse aunque el directorio no lo tenga."""

import unittest

from orchestrator.directorio import extranas
from orchestrator.sujeto import permitidas


class _Oportunidad:
    def __init__(self, action: str, keyword: str) -> None:
        self.action = action
        self.focus_keyword = keyword


class _Brief:
    def __init__(self, action: str, keyword: str) -> None:
        self.opportunity = _Oportunidad(action, keyword)


class SujetoTests(unittest.TestCase):
    def test_un_reencauche_permite_nombrar_su_tema(self) -> None:
        self.assertIn("susii", permitidas(_Brief("refresh_structure", "susii")))

    def test_un_articulo_nuevo_no_abre_la_puerta(self) -> None:
        self.assertEqual(permitidas(_Brief("create", "software contable para restaurantes")), ())

    def test_la_regla_de_marca_desconocida_respeta_lo_permitido(self) -> None:
        texto = "<p>susii vs Siigo: precios, facturación y soporte.</p>"

        sin_permiso = extranas(texto, "CO")
        con_permiso = extranas(texto, "CO", permitidas=("susii",))

        self.assertIn("susii", [m.lower() for m in sin_permiso])
        self.assertEqual(con_permiso, [])


if __name__ == "__main__":
    unittest.main()
