"""Distribution assets must be usable without changing the approved anchor."""

import hashlib

from PIL import Image

from biogesture import AUTHOR
from biogesture.paths import resource_path


def test_approved_anchor_is_preserved_byte_for_byte():
    path = resource_path("assets/brand/anchor-approved.png")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "e161ac64b91082980778f32260967e35e45d1e542dac8ed09fbb5ee34a5b77e4"


def test_windows_icon_includes_small_and_high_resolution_sizes():
    with Image.open(resource_path("assets/brand/app.ico")) as icon:
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= icon.ico.sizes()


def test_splash_is_available_and_author_text_is_exact():
    assert AUTHOR == "Desarrollado por Luics415"
    with Image.open(resource_path("assets/brand/splash-author.png")) as splash:
        splash.verify()
