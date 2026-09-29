"""Promote 2.7 while preserving historical documentation and author identity."""

import hashlib
from pathlib import Path
import tomllib

from biogesture import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_readme_1_matches_published_a216201_without_even_a_link_added():
    assert hashlib.sha256((ROOT / "legacy/v1.20.36/README.md").read_bytes()).hexdigest() == (
        "312dc0df773810135751006f42d42e819ad3b75df8063f1a5719f8a7c13a66da"
    )


def test_package_metadata_and_program_use_current_version_and_front_page():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["readme"] == "README.md"
    assert project["version"] == __version__ == "3.0.0.dev4"
    assert (ROOT / project["readme"]).is_file()


def test_splash_original_is_archived_and_current_has_requested_version_edit():
    assert hashlib.sha256((ROOT / "assets/brand/splash-author-2.0.png").read_bytes()).hexdigest() == (
        "8a499e2225eadfd0cbc7df5be9a706878c7f3af882935bd00e20ecf06be02020"
    )
    assert hashlib.sha256((ROOT / "assets/brand/splash-author.png").read_bytes()).hexdigest() == (
        "cc4b90b98228a07cb54fb95231bd7de65e0ad40c8817d7c5ab216049bfd996d9"
    )
    assert hashlib.sha256((ROOT / "assets/brand/splash-author-2.7.png").read_bytes()).hexdigest() == (
        "6f6d427ad02b1cb11f0c09195c92a0a38c095b78427b87e4fead4e2adcc45924"
    )


def test_front_page_offers_portable_manual_source_and_history_separately():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Bio-Gesture Control Pro 2.7" in readme
    assert "releases/download/v2.7.0/BioGestureControlPro-2.7.0-windows-x64.zip" in readme
    assert "archive/refs/tags/v2.7.0.zip" in readme
    assert "docs/manual/Manual-de-usuario.pdf" in readme
    assert "legacy/v1.20.36/README.md" in readme
    assert "computadora limpia" in readme and "firma digital" in readme


def test_previous_documentation_entry_redirects_without_duplicating_the_guide():
    previous = (ROOT / "README-2.0.md").read_text(encoding="utf-8")
    assert "[README.md](README.md)" in previous
    assert "blob/v2.0.0-dev.7/README-2.0.md" in previous
    assert len(previous.splitlines()) < 20


def test_current_prototype_guides_explain_calibration_without_promising_glasses_accuracy():
    for relative in ("README-3.0.md", "docs/manual/Guia-3.0.md"):
        guide = (ROOT / relative).read_text(encoding="utf-8")
        assert __version__ in guide
        assert "gris mate" in guide and "Fondo: oscuro" in guide
        assert "cabeza relativamente estable" in guide
        assert "solo la mirada" in guide
        assert "20 segundos" in guide
        assert "error medio" in guide and "máximo" in guide
        assert "reflejos" in guide and "lentes" in guide


def test_v3_pdf_builder_is_explicitly_historical_until_pdf_is_revised():
    source = (ROOT / "scripts/create_v3_guide.py").read_text(encoding="utf-8")
    assert "Guía de pruebas · 3.0.0.dev3" in source
    readme = (ROOT / "README-3.0.md").read_text(encoding="utf-8")
    assert "PDF y su generador de dev3" in readme
    assert "no se regeneraron en dev4" in readme
