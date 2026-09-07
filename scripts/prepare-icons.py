"""Format conversion only: preserve the approved anchor artwork."""

from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
source = root / "assets/brand/anchor-approved.png"
with Image.open(source) as original:
    rgba = original.convert("RGBA")
    rgba.save(root / "assets/brand/app.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    rgba.resize((64, 64), Image.Resampling.LANCZOS).save(root / "assets/brand/tray.png")
