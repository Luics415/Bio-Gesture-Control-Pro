"""Replace only the centered version number in the approved author splash."""

from pathlib import Path
import shutil

import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "assets/brand/splash-author.png"
ARCHIVE = ROOT / "assets/brand/splash-author-2.7.png"


def main():
    if not ARCHIVE.exists():
        shutil.copy2(SPLASH, ARCHIVE)
    original = Image.open(SPLASH).convert("RGBA")
    rgb = np.asarray(original.convert("RGB"))

    # The approved artwork has a uniform dark panel behind the number. Inpaint
    # only that number's bounding band; every other pixel remains untouched.
    mask = np.zeros(rgb.shape[:2], dtype=np.uint8)
    region = rgb[720:800, 690:860]
    colored = ((region.max(axis=2) > 70) & ((region.max(axis=2) - region.min(axis=2)) > 18)).astype(np.uint8)
    colored = cv2.dilate(colored, np.ones((3, 3), dtype=np.uint8), iterations=1) * 255
    mask[720:800, 690:860] = colored
    restored = cv2.inpaint(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), mask, 3, cv2.INPAINT_TELEA)
    canvas = Image.fromarray(cv2.cvtColor(restored, cv2.COLOR_BGR2RGB)).convert("RGBA")

    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 70)
    text_mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(text_mask).text((768, 758), "3.5", font=font, fill=255, anchor="mm")

    glow = text_mask.filter(ImageFilter.GaussianBlur(6))
    glow_layer = Image.new("RGBA", canvas.size, (0, 225, 255, 0))
    glow_layer.putalpha(glow.point(lambda value: int(value * 0.55)))
    canvas = Image.alpha_composite(canvas, glow_layer)

    gradient = np.zeros((canvas.height, canvas.width, 4), dtype=np.uint8)
    gradient[:, :, 0] = np.linspace(0, 150, canvas.width, dtype=np.uint8)[None, :]
    gradient[:, :, 1] = np.linspace(220, 130, canvas.width, dtype=np.uint8)[None, :]
    gradient[:, :, 2] = 255
    gradient[:, :, 3] = np.asarray(text_mask)
    canvas = Image.alpha_composite(canvas, Image.fromarray(gradient, "RGBA"))
    canvas.save(SPLASH, format="PNG", optimize=False)


if __name__ == "__main__":
    main()
