"""Presentation contracts; drawings never invoke operating-system actions."""

import math
import os
from unittest.mock import Mock, call as mock_call

import pytest

from biogesture.gestures import MENUS
from biogesture.models import EngineOutput
from biogesture.rendering import (
    ACCENT, BACKGROUND, BORDER, CAMERA_HEIGHT, COMMAND_LABELS, FOOTER_HEIGHT, TEXT, TOOLBAR_HEIGHT, WINDOW_HEIGHT,
    WINDOW_WIDTH, RadialGeometry, draw_empty_state, draw_radial_menu, status_text,
)


def test_camera_first_layout_preserves_exact_client_size():
    assert (WINDOW_WIDTH, WINDOW_HEIGHT) == (550, 375)
    assert TOOLBAR_HEIGHT + CAMERA_HEIGHT + FOOTER_HEIGHT == WINDOW_HEIGHT
    assert CAMERA_HEIGHT == 335
    assert set(COMMAND_LABELS) == {command for commands in MENUS.values() for command in commands}
    assert all(1 <= len(label.split()) <= 2 and "\n" not in label for label in COMMAND_LABELS.values())


@pytest.mark.parametrize("level", MENUS)
def test_radial_menu_keeps_all_eight_commands_in_engine_order(level):
    canvas = Mock()
    draw_radial_menu(canvas, EngineOutput(state="MENU", menu_level=level, menu_selected=3, progress=.65))
    assert canvas.create_text.call_count == 8
    labels = [call.kwargs["text"] for call in canvas.create_text.call_args_list]
    assert labels == [COMMAND_LABELS[command] for command in MENUS[level]]
    geometry = RadialGeometry()
    for index, call in enumerate(canvas.create_text.call_args_list):
        assert call.args == geometry.label_position(index)
        assert call.kwargs["fill"] == (ACCENT if index == 3 else TEXT)
        assert call.kwargs["font"][-1] == ("bold" if index == 3 else "normal")
    canvas.create_oval.assert_called_once_with(*geometry.ring_bounds(5), fill=BACKGROUND, outline="", tags="radial")
    canvas.create_polygon.assert_not_called()
    canvas.create_arc.assert_not_called()
    canvas.create_line.assert_not_called()
    track, fill = canvas.create_rectangle.call_args_list
    left, top, right, bottom = geometry.progress_bounds()
    assert track.args == (left, top, right, bottom)
    assert track.kwargs["fill"] == BORDER
    assert fill.args == pytest.approx((left, top, left + (right - left) * .65, bottom))
    assert fill.kwargs["fill"] == ACCENT
    assert right - left > bottom - top


@pytest.mark.parametrize("selected", [-1, 8, 40])
def test_radial_without_selection_has_no_loading_bar(selected):
    canvas = Mock()
    draw_radial_menu(canvas, EngineOutput(state="MENU", menu_selected=selected, progress=.65))
    assert canvas.create_text.call_count == 8
    assert all(call.kwargs["fill"] == TEXT for call in canvas.create_text.call_args_list)
    canvas.create_rectangle.assert_not_called()


@pytest.mark.parametrize("progress,expected", [(-.4, 0), (0, 0), (1, 1), (1.8, 1),
                                               (float("nan"), 0), (float("inf"), 0)])
def test_radial_progress_never_exceeds_horizontal_track(progress, expected):
    canvas = Mock()
    draw_radial_menu(canvas, EngineOutput(state="MENU", menu_selected=0, progress=progress))
    rectangles = canvas.create_rectangle.call_args_list
    assert len(rectangles) == (2 if expected else 1)
    if expected:
        left, top, right, bottom = RadialGeometry().progress_bounds()
        assert rectangles[-1].args == pytest.approx((left, top, left + (right - left) * expected, bottom))


@pytest.mark.parametrize("index", range(8))
def test_sector_label_and_polygon_follow_clockwise_engine_direction(index):
    geometry = RadialGeometry()
    x, y = geometry.label_position(index)
    actual = int(((math.degrees(math.atan2(y - geometry.center_y, x - geometry.center_x)) + 22.5) % 360) // 45)
    assert actual == index
    points = geometry.sector_polygon(index)
    assert all(0 <= x <= WINDOW_WIDTH for x in points[::2])
    assert all(0 <= y <= CAMERA_HEIGHT for y in points[1::2])


@pytest.mark.parametrize("title,detail", [
    ("", ""),
    ("Preparando cámara", "Tu espacio de trabajo, a un gesto."),
    ("Cámara apagada", "Más → Encender cámara"),
    ("Cámara no disponible", "Revisa Ajustes o reiníciala desde Más."),
])
def test_empty_camera_clears_every_overlay_without_drawing_legacy_messages(title, detail):
    canvas = Mock()
    draw_empty_state(canvas, title, detail)
    assert canvas.mock_calls == [mock_call.delete("all")]


def test_status_preserves_paused_tracking_help_and_camera_off():
    assert status_text("PUNTERO", "Global", paused=True) == "En pausa  ·  Global"
    assert "1 de 4" in status_text("ONDA 1/4", "Global", paused=True)
    assert "Muestra una mano" in status_text("MUESTRA UNA MANO", "Global", paused=True)
    assert status_text("CÁMARA APAGADA", "Global", paused=True) == "Cámara apagada  ·  Global"


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_GUI") != "1", reason="Geometría real optativa de Tk")
@pytest.mark.parametrize("scaling", [1.333, 1.666, 2.0, 2.666])
def test_all_menu_text_fits_without_overlaps_at_supported_dpi(scaling):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", scaling)
    canvas = tk.Canvas(root, width=WINDOW_WIDTH, height=CAMERA_HEIGHT)
    try:
        for level in MENUS:
            for selected in range(-1, 8):
                canvas.delete("all")
                draw_radial_menu(canvas, EngineOutput(state="MENU", menu_level=level,
                                                     menu_selected=selected, progress=.65))
                labels = []
                for item in canvas.find_all():
                    if canvas.type(item) != "text":
                        continue
                    bounds = canvas.bbox(item)
                    x1, y1, x2, y2 = bounds
                    assert 0 <= x1 < x2 <= WINDOW_WIDTH, (level, selected, canvas.itemcget(item, "text"), bounds)
                    assert 0 <= y1 < y2 <= CAMERA_HEIGHT, (level, selected, bounds)
                    labels.append((item, bounds))
                for index, (item, (x1, y1, x2, y2)) in enumerate(labels):
                    for other, (a1, b1, a2, b2) in labels[index + 1:]:
                        assert x2 <= a1 or a2 <= x1 or y2 <= b1 or b2 <= y1, (
                            level, selected, canvas.itemcget(item, "text"), canvas.itemcget(other, "text"))
                assert len(labels) == 8
                for bar in canvas.find_withtag("radial-progress-track"):
                    a1, b1, a2, b2 = canvas.bbox(bar)
                    assert 0 <= a1 < a2 <= WINDOW_WIDTH and 0 <= b1 < b2 <= CAMERA_HEIGHT
                    for item, (x1, y1, x2, y2) in labels:
                        assert x2 <= a1 or a2 <= x1 or y2 <= b1 or b2 <= y1, (
                            level, selected, "progress overlaps", canvas.itemcget(item, "text"))
    finally:
        root.destroy()
