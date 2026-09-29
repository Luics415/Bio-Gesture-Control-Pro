from pathlib import Path

from biogesture.legal import EFFECTIVE_DATE, LEGAL_SECTIONS


def test_legal_notices_are_offline_and_consistent_with_public_documents():
    root = Path(__file__).parents[1]
    public = {name: (root / "docs" / "legal" / name).read_text(encoding="utf-8")
              for name in ("PRIVACIDAD.md", "TERMINOS.md", "COOKIES.md")}
    assert EFFECTIVE_DATE in LEGAL_SECTIONS["Privacidad"]
    assert "no se envían" in LEGAL_SECTIONS["Privacidad"]
    assert "no crea, lee ni almacena" in LEGAL_SECTIONS["Cookies"]
    assert "no hace solicitudes de red" in public["PRIVACIDAD.md"]
    assert "consentimiento previo" in public["COOKIES.md"]
    assert "tal cual" in public["TERMINOS.md"]


def test_public_legal_documents_have_no_tracking_snippets():
    root = Path(__file__).parents[1]
    content = "\n".join((root / "docs" / "legal" / name).read_text(encoding="utf-8")
                          for name in ("PRIVACIDAD.md", "TERMINOS.md", "COOKIES.md"))
    assert "Google Analytics" not in content
    assert "facebook pixel" not in content.lower()


def test_security_and_assets_rights_are_public_package_inputs():
    root = Path(__file__).parents[1]
    assert (root / "SECURITY.md").is_file()
    rights = (root / "docs" / "ASSETS_RIGHTS.md").read_text(encoding="utf-8")
    assert "capturas aportadas por el usuario" in rights
    assert "THIRD_PARTY_NOTICES.md" in rights

