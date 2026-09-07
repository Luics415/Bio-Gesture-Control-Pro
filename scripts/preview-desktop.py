"""Export a synthetic SVG preview using the application's actual canvas drawing.

No Tk window, webcam, screenshot, model or desktop input is opened. The approved
anchor PNG is embedded byte-for-byte; only its display dimensions are specified.
"""

import argparse
import base64
from html import escape
import math
from pathlib import Path
import sys


def number(value):
    return f"{float(value):.3f}".rstrip("0").rstrip(".") or "0"


class SvgCanvas:
    """Small adapter for the Canvas methods used by biogesture.rendering."""

    def __init__(self):
        self.items = []

    def delete(self, target):
        if target != "all":
            raise ValueError("The preview adapter only supports deleting all canvas items")
        self.items.clear()

    @staticmethod
    def _style(options):
        fill = options.get("fill") or "none"
        outline = options.get("outline") or "none"
        return (f'fill="{escape(str(fill), quote=True)}" stroke="{escape(str(outline), quote=True)}" '
                f'stroke-width="{number(options.get("width", 1))}"')

    def create_rectangle(self, x1, y1, x2, y2, **options):
        self.items.append(f'<rect x="{number(x1)}" y="{number(y1)}" width="{number(x2 - x1)}" '
                          f'height="{number(y2 - y1)}" {self._style(options)}/>')

    def create_oval(self, x1, y1, x2, y2, **options):
        self.items.append(f'<ellipse cx="{number((x1 + x2) / 2)}" cy="{number((y1 + y2) / 2)}" '
                          f'rx="{number((x2 - x1) / 2)}" ry="{number((y2 - y1) / 2)}" {self._style(options)}/>')

    def create_polygon(self, *coordinates, **options):
        points = " ".join(f"{number(x)},{number(y)}" for x, y in zip(coordinates[::2], coordinates[1::2]))
        self.items.append(f'<polygon points="{points}" {self._style(options)} stroke-linejoin="round"/>')

    def create_text(self, x, y, **options):
        font = options.get("font", ("Segoe UI", -11))
        size = abs(font[1]) if font[1] < 0 else font[1] * 96 / 72
        weight = "bold" if "bold" in font[2:] else "normal"
        anchor = options.get("anchor", "center")
        alignment = "start" if "w" in anchor else "end" if "e" in anchor and anchor != "center" else "middle"
        lines = str(options.get("text", "")).split("\n")
        line_height = size * 1.2
        initial_y = y - (len(lines) - 1) * line_height / 2
        spans = "".join(f'<tspan x="{number(x)}" y="{number(initial_y + index * line_height)}">'
                        f'{escape(line)}</tspan>' for index, line in enumerate(lines))
        self.items.append(f'<text font-family="Segoe UI, sans-serif" font-size="{number(size)}" '
                          f'font-weight="{weight}" fill="{escape(options.get("fill", "#000"), quote=True)}" '
                          f'text-anchor="{alignment}" dominant-baseline="central">{spans}</text>')

    def create_arc(self, x1, y1, x2, y2, **options):
        if options.get("style", "arc") != "arc":
            raise ValueError("Only stroked arcs are required by the application preview")
        start, extent = float(options["start"]), float(options["extent"])
        if not extent:
            return
        rx, ry = (x2 - x1) / 2, (y2 - y1) / 2
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

        def point(degrees):
            radians = math.radians(degrees)
            return cx + rx * math.cos(radians), cy - ry * math.sin(radians)

        ax, ay = point(start)
        bx, by = point(start + extent)
        path = (f'M {number(ax)} {number(ay)} A {number(rx)} {number(ry)} 0 '
                f'{int(abs(extent) > 180)} {int(extent < 0)} {number(bx)} {number(by)}')
        self.items.append(f'<path d="{path}" fill="none" '
                          f'stroke="{escape(options.get("outline", "#000"), quote=True)}" '
                          f'stroke-width="{number(options.get("width", 1))}"/>')

    def svg(self):
        return "\n".join(self.items)


def make_preview(project_root):
    sys.path.insert(0, str(project_root))
    from biogesture.models import EngineOutput
    from biogesture.rendering import (
        ACCENT, BACKGROUND, BORDER, CAMERA_HEIGHT, FOOTER_HEIGHT, MUTED, TEXT,
        TOOLBAR_HEIGHT, WINDOW_HEIGHT, WINDOW_WIDTH, draw_empty_state,
        draw_radial_menu, status_text,
    )

    margin, gap, client_top = 32, 28, 112
    sheet_width = margin * 2 + WINDOW_WIDTH * 2 + gap
    sheet_height = client_top + WINDOW_HEIGHT + 56
    sheet = SvgCanvas()
    sheet.create_rectangle(0, 0, sheet_width, sheet_height, fill="#080d12")
    sheet.create_text(margin, 34, text="Vista previa · sin cámara", fill=TEXT,
                      font=("Segoe UI", -25), anchor="w")
    sheet.create_text(margin, 65, text="Bio-Gesture Control Pro · Dos estados de la interfaz", fill=MUTED,
                      font=("Segoe UI", -13), anchor="w")

    asset = project_root / "assets/brand/anchor-approved.png"
    original_png = base64.b64encode(asset.read_bytes()).decode("ascii")
    definitions = (f'<defs><image id="approved-anchor" width="20" height="20" '
                   f'href="data:image/png;base64,{original_png}"/></defs>')
    windows = []
    for index, radial in enumerate((False, True)):
        left = margin + index * (WINDOW_WIDTH + gap)
        sheet.create_text(left, 94, text="Cámara · sin mano" if not radial else "Menú radial · Sistema",
                          fill=TEXT, font=("Segoe UI", -13), anchor="w")
        chrome = SvgCanvas()
        chrome.create_rectangle(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, fill=BACKGROUND, outline=BORDER)
        chrome.create_rectangle(0, TOOLBAR_HEIGHT, WINDOW_WIDTH, TOOLBAR_HEIGHT + CAMERA_HEIGHT, fill="#080d12")
        chrome.create_text(33, TOOLBAR_HEIGHT / 2, text="Bio-Gesture", fill="#ccd6dc",
                           font=("Segoe UI", -11), anchor="w")
        right = WINDOW_WIDTH - 6
        for label, width, color in (("Más  ⋯", 58, TEXT), ("Ajustes", 60, TEXT),
                                     ("Pausar" if radial else "Activar", 58, ACCENT)):
            chrome.create_text(right - width / 2, TOOLBAR_HEIGHT / 2, text=label,
                               fill=color, font=("Segoe UI", -11))
            right -= width + 2
        footer_y = TOOLBAR_HEIGHT + CAMERA_HEIGHT + FOOTER_HEIGHT / 2
        chrome.create_text(8, footer_y, text=status_text("MENU" if radial else "PAUSADO", "Global", paused=not radial),
                           fill=MUTED, font=("Segoe UI", -9), anchor="w")
        camera = SvgCanvas()
        if radial:
            draw_radial_menu(camera, EngineOutput(state="MENU", menu_level="SISTEMA", menu_selected=1, progress=0.65))
        else:
            draw_empty_state(camera, "")
        windows.append(f'<g transform="translate({left} {client_top})" data-client-size="550x375">\n'
                       f'{chrome.svg()}\n<use href="#approved-anchor" x="8" y="4"/>\n'
                       f'<g transform="translate(0 {TOOLBAR_HEIGHT})">{camera.svg()}</g>\n</g>')
    sheet.create_text(margin, sheet_height - 24,
                      text=f"Cada ventana: {WINDOW_WIDTH} × {WINDOW_HEIGHT} px · Contenido sintético; ninguna cámara está activa.",
                      fill=MUTED, font=("Segoe UI", -12), anchor="w")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet_width}" height="{sheet_height}" '
            f'viewBox="0 0 {sheet_width} {sheet_height}" role="img" data-preview="synthetic">\n'
            '<title>Vista previa sin cámara de Bio-Gesture Control Pro</title>\n'
            '<desc>Dos ventanas de 550 por 375 píxeles. Estado sin mano y menú Sistema con '
            'Tareas seleccionado y una barra horizontal de carga. El ancla es el archivo aprobado original.</desc>\n'
            f'{definitions}\n{sheet.svg()}\n' + "\n".join(windows) + '\n</svg>\n')


def main():
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=project_root / "output/desktop-preview.svg")
    options = parser.parse_args()
    target = options.output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(make_preview(project_root), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
