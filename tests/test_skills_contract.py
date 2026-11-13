"""Contract tests for the editorial skills.

These encode decisions the team made on 6 November 2026, so a later edit cannot
quietly reintroduce a rule we retired. They check text, not behaviour: the skills
are prompts, and the only way to assert a prompt is by its invariants.
"""

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
PORTAL = SKILLS / "prog-cont-blog"
LEGAL = SKILLS / "marco-legal" / "legal-context.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FrontmatterTests(unittest.TestCase):
    def test_every_skill_declares_matching_name(self) -> None:
        for skill_dir in (SKILLS / "prog-cont-blog", SKILLS / "pdc-locale-signals"):
            content = read(skill_dir / "SKILL.md")
            self.assertTrue(content.startswith("---"), f"{skill_dir.name} sin frontmatter")
            name = re.search(r"^name:\s*(\S+)", content, re.MULTILINE)
            self.assertIsNotNone(name, f"{skill_dir.name} sin campo name")
            self.assertEqual(name.group(1), skill_dir.name)


class TerminologyTests(unittest.TestCase):
    def test_no_file_uses_pyme(self) -> None:
        # Las referencias importadas son material de origen ajeno: no se reescriben.
        offenders = []
        for path in SKILLS.rglob("*.md"):
            # El material importado del portal conserva su redacción original.
            if "prog-cont-blog" in path.as_posix():
                continue
            if re.search(r"\bpymes?\b", read(path), re.IGNORECASE):
                offenders.append(path.name)
        self.assertEqual(offenders, [], "el estándar es 'negocios y empresas'")


class MarketScopeTests(unittest.TestCase):
    def test_legal_context_covers_four_markets_and_excludes_panama(self) -> None:
        content = read(LEGAL)

        for flag in ("🇲🇽", "🇨🇴", "🇨🇷", "🇩🇴"):
            self.assertIn(flag, content, f"falta el mercado {flag}")
        self.assertNotIn("🇵🇦", content)
        self.assertNotIn("SFEP", content)

    def test_audio_and_authority_naming_are_absent(self) -> None:
        content = read(LEGAL)

        self.assertNotIn("Administración Tributaria Virtual", content)
        self.assertNotIn("DGT-R-48-2016", content)


class LegalCurrencyTests(unittest.TestCase):
    def test_colombia_cites_the_current_resolution(self) -> None:
        content = read(LEGAL)

        self.assertIn("Resolución DIAN 000165", content)
        self.assertIn("000227 de 2025", content)

    def test_costa_rica_uses_tribu_cr_framework(self) -> None:
        content = read(LEGAL)

        self.assertIn("TRIBU-CR", content)
        self.assertIn("MH-DGT-RES-0027-2024", content)
        self.assertIn("D-150", content)

    def test_dominican_republic_cites_law_and_decree(self) -> None:
        content = read(LEGAL)

        self.assertIn("Ley 32-23", content)
        self.assertIn("Decreto 587-24", content)


if __name__ == "__main__":
    unittest.main()
