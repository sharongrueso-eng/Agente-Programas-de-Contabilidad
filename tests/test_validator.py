"""Deterministic controls that run before the judge sees a piece."""

import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import Draft
from orchestrator.validator import ValidationRules, validate

KEYWORD = "opiniones de siigo"

ALEGRA = (
    'https://www.alegra.com/co/contabilidad/?utm_source=programascontabilidad'
    '&utm_medium=referencia&utm_campaign=co'
)
INTERNAL = "https://programascontabilidad.com"


def html_body(
    *,
    h1: str = "Opiniones de Siigo en Colombia",
    intro: str = "Las opiniones de Siigo entre contadores colombianos cambian según el tamaño del negocio.",
    alegra_links: int = 3,
    internal_links: int = 5,
    sources: int = 2,
    extra: str = "",
) -> str:
    parts = [f"<h1>{h1}</h1>", f"<p>{intro}</p>"]
    parts += [f'<a href="{ALEGRA}">Alegra</a>' for _ in range(alegra_links)]
    parts += [f'<a href="{INTERNAL}/guia-{i}/">interna</a>' for i in range(internal_links)]
    parts += [f'<a href="https://fuente{i}.gov.co/">fuente</a>' for i in range(sources)]
    parts.append(extra)
    return "".join(parts)


def draft(**overrides) -> Draft:
    base = dict(
        title="Opiniones de Siigo: lo que dicen los contadores",
        meta_description=(
            "Opiniones de Siigo en Colombia: qué dicen los contadores que la usan a diario, "
            "sus límites reales y qué revisar antes de decidir."
        ),
        html=html_body(),
        alt_text="Contadora revisando facturas electrónicas",
        slug="opiniones-de-siigo",
    )
    base.update(overrides)
    return Draft(**base)


def brief(action: str = "refresh_structure", country: str = "CO") -> Brief:
    opportunity = Opportunity(
        url=f"{INTERNAL}/opiniones-siigo-colombia/",
        country=country,
        action=action,
        focus_keyword=KEYWORD,
        intent="review",
        score=50.0,
        evidence={},
    )
    return Brief(
        task_id="2026-11-06-A",
        date=date(2026, 11, 6),
        slot="A",
        format="resena",
        country=country,
        opportunity=opportunity,
    )


def status_of(verdict, code: str) -> str:
    for control in verdict.controls:
        if control.code == code:
            return control.status
    raise AssertionError(f"control no evaluado: {code}")


class BaselineTests(unittest.TestCase):
    def test_a_clean_draft_passes_every_control(self) -> None:
        verdict = validate(draft(), brief(), ValidationRules())

        self.assertEqual(verdict.status, "PASS", [c for c in verdict.controls if c.status != "PASS"])
        self.assertTrue(verdict.controls)


class SlugAndMetadataTests(unittest.TestCase):
    def test_slug_must_contain_the_keyword(self) -> None:
        verdict = validate(draft(slug="siigo-opiniones-2024"), brief(action="create"), ValidationRules())

        self.assertEqual(status_of(verdict, "slug_keyword"), "PASS")

    def test_slug_without_keyword_blocks(self) -> None:
        verdict = validate(draft(slug="siigo-analisis"), brief(action="create"), ValidationRules())

        self.assertEqual(status_of(verdict, "slug_keyword"), "BLOQUEADO")
        self.assertEqual(verdict.status, "BLOQUEADO")

    def test_new_urls_may_not_carry_a_year(self) -> None:
        verdict = validate(
            draft(slug="opiniones-de-siigo-2026"),
            brief(action="create"),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "slug_year"), "CORREGIR")

    def test_existing_urls_keep_their_year(self) -> None:
        verdict = validate(
            draft(slug="opiniones-de-siigo-2026"), brief(action="refresh_structure"), ValidationRules()
        )

        self.assertEqual(status_of(verdict, "slug_year"), "PASS")

    def test_title_must_carry_the_exact_keyword(self) -> None:
        verdict = validate(draft(title="Lo que dicen los contadores"), brief(), ValidationRules())

        self.assertEqual(status_of(verdict, "title_keyword"), "CORREGIR")

    def test_h1_must_carry_the_keyword(self) -> None:
        verdict = validate(draft(html=html_body(h1="Siigo visto por contadores")), brief(), ValidationRules())

        self.assertEqual(status_of(verdict, "h1_keyword"), "CORREGIR")

    def test_first_paragraph_must_carry_the_keyword(self) -> None:
        verdict = validate(
            draft(html=html_body(intro="Un repaso por la herramienta y su soporte.")),
            brief(),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "intro_keyword"), "CORREGIR")

    def test_meta_description_length_is_bounded(self) -> None:
        verdict = validate(draft(meta_description="Opiniones de siigo."), brief(), ValidationRules())

        self.assertEqual(status_of(verdict, "meta_keyword"), "PASS")
        self.assertEqual(status_of(verdict, "meta_length"), "CORREGIR")


class LinkTests(unittest.TestCase):
    # La excepción de elenco cerrado libera del mínimo a la reseña de un producto ajeno; estas
    # pruebas se hacen sobre una pieza cuyo título sí incluye Alegra, donde el mínimo aplica.
    TITULO_CON_ALEGRA = "Siigo vs Alegra: precios y planes en Colombia"

    def test_three_alegra_links_with_utm_are_required(self) -> None:
        verdict = validate(
            draft(html=html_body(alegra_links=2), title=self.TITULO_CON_ALEGRA),
            brief(),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "alegra_links"), "CORREGIR")

    def test_alegra_links_without_utm_do_not_count(self) -> None:
        bare = '<a href="https://www.alegra.com/co/">Alegra</a>' * 3

        verdict = validate(
            draft(html=html_body(alegra_links=0, extra=bare), title=self.TITULO_CON_ALEGRA),
            brief(),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "alegra_links"), "CORREGIR")

    def test_five_internal_links_are_required(self) -> None:
        verdict = validate(draft(html=html_body(internal_links=4)), brief(), ValidationRules())

        self.assertEqual(status_of(verdict, "internal_links"), "CORREGIR")

    def test_two_external_sources_are_required(self) -> None:
        verdict = validate(draft(html=html_body(sources=1)), brief(), ValidationRules())

        self.assertEqual(status_of(verdict, "sources"), "CORREGIR")

    def test_alegra_links_do_not_count_as_sources(self) -> None:
        verdict = validate(
            draft(html=html_body(alegra_links=6, sources=0)), brief(), ValidationRules()
        )

        self.assertEqual(status_of(verdict, "sources"), "CORREGIR")


class CountryTests(unittest.TestCase):
    def test_foreign_authority_blocks_the_piece(self) -> None:
        verdict = validate(
            draft(html=html_body(extra="<p>El SAT exige CFDI 4.0.</p>")),
            brief(country="CO"),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "country_norms"), "BLOQUEADO")

    def test_dominican_republic_never_uses_the_short_form(self) -> None:
        verdict = validate(
            draft(html=html_body(extra="<p>Las empresas de RD migran al e-CF.</p>")),
            brief(country="DO"),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "country_norms"), "BLOQUEADO")


class HonestyTests(unittest.TestCase):
    def test_first_person_testing_without_evidence_is_flagged(self) -> None:
        verdict = validate(
            draft(html=html_body(extra="<p>Probé Siigo durante dos semanas.</p>")),
            brief(),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "testing_claims"), "CORREGIR")

    def test_testing_claim_is_allowed_with_evidence(self) -> None:
        verdict = validate(
            draft(html=html_body(extra="<p>Probé Siigo durante dos semanas.</p>")),
            brief(),
            ValidationRules(),
            evidence_of_testing=True,
        )

        self.assertEqual(status_of(verdict, "testing_claims"), "PASS")

    def test_revisé_is_the_default_verb(self) -> None:
        verdict = validate(
            draft(html=html_body(extra="<p>Revisé la documentación oficial en noviembre de 2026.</p>")),
            brief(),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "testing_claims"), "PASS")


class JargonTests(unittest.TestCase):
    def test_pipeline_language_is_flagged(self) -> None:
        verdict = validate(
            draft(html=html_body(extra="<p>La compuerta 0 mostró 1400 impresiones en GSC.</p>")),
            brief(),
            ValidationRules(),
        )

        self.assertEqual(status_of(verdict, "internal_jargon"), "CORREGIR")


class SnippetModeTests(unittest.TestCase):
    def test_snippet_mode_passes_with_only_title_and_meta(self) -> None:
        snippet = Draft(
            title="Opiniones de Siigo: lo que dicen los contadores",
            meta_description=(
                "Opiniones de Siigo en Colombia: qué dicen los contadores que la usan a diario, "
                "sus límites reales y qué revisar antes de decidir."
            ),
            slug="opiniones-de-siigo",
        )

        verdict = validate(snippet, brief(action="refresh_snippet"), ValidationRules())

        self.assertEqual(verdict.status, "PASS")

    def test_snippet_mode_blocks_when_the_body_is_rewritten(self) -> None:
        verdict = validate(draft(), brief(action="refresh_snippet"), ValidationRules())

        self.assertEqual(status_of(verdict, "snippet_body"), "BLOQUEADO")


if __name__ == "__main__":
    unittest.main()


class ClaimTests(unittest.TestCase):
    """Lo que la pieza promete tiene que poder demostrarse."""

    def test_the_platform_count_cannot_exceed_the_registry(self) -> None:
        pieza = draft(title="Análisis de 8 plataformas de software contable")
        verdict = validate(pieza, brief(), ValidationRules(), brands_available=4)

        self.assertEqual(status_of(verdict, "brand_count"), "CORREGIR")

    def test_the_platform_count_passes_when_it_matches(self) -> None:
        pieza = draft(title="Análisis de 4 plataformas de software contable")
        verdict = validate(pieza, brief(), ValidationRules(), brands_available=4)

        self.assertEqual(status_of(verdict, "brand_count"), "PASS")

    def test_a_savings_claim_without_evidence_is_flagged(self) -> None:
        pieza = draft(html=html_body() + "<p>Ahorra 8 horas al mes en la facturación.</p>")
        verdict = validate(pieza, brief(), ValidationRules(), registry_text="Siigo cobra 49.900 COP")

        self.assertEqual(status_of(verdict, "improvement_claims"), "CORREGIR")

    def test_a_savings_claim_is_allowed_when_the_registry_holds_it(self) -> None:
        frase = "Ahorra 8 horas al mes en la facturación."
        pieza = draft(html=html_body() + f"<p>{frase}</p>")
        verdict = validate(pieza, brief(), ValidationRules(), registry_text=frase)

        self.assertEqual(status_of(verdict, "improvement_claims"), "PASS")
