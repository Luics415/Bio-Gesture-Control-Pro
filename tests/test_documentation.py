"""Keep the published 1.0 README and the approved author artwork untouched."""

import hashlib
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_readme_1_matches_published_a216201_without_even_a_link_added():
    assert hashlib.sha256((ROOT / "README.md").read_bytes()).hexdigest() == (
        "312dc0df773810135751006f42d42e819ad3b75df8063f1a5719f8a7c13a66da"
    )


def test_package_metadata_uses_separate_v2_documentation():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["readme"] == "README-2.0.md"
    assert (ROOT / project["readme"]).is_file()


def test_splash_keeps_approved_artwork_byte_for_byte():
    assert hashlib.sha256((ROOT / "assets/brand/splash-author.png").read_bytes()).hexdigest() == (
        "8a499e2225eadfd0cbc7df5be9a706878c7f3af882935bd00e20ecf06be02020"
    )
