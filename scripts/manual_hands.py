"""Editable, original Bezier hand illustrations for the user manual.

Palm-facing explanatory drawings, not MediaPipe measurements. All shapes are
PDF vectors; this module has no image, application, camera or input dependency.
Coordinates retain the manual's approximately (-15, 0)..(105, 145) hand box.
"""

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics


TEAL = colors.HexColor("#087d85")
SKIN = colors.HexColor("#dcefee")
POSES = ("open", "index", "l", "victory", "thumb", "scroll",
         "pinch8", "pinch12", "pinch16", "pinch20")


def _path(c, commands, *, fill=False, stroke=True, width=1.35):
    path = c.beginPath()
    for command in commands:
        kind, *values = command
        if kind == "M":
            path.moveTo(*values)
        elif kind == "L":
            path.lineTo(*values)
        elif kind == "C":
            path.curveTo(*values)
        elif kind == "Z":
            path.close()
    c.setLineWidth(width)
    c.drawPath(path, fill=int(fill), stroke=int(stroke))


def _crease(c, points, *, width=.7):
    _path(c, points, width=width)


def _long_finger(c, x, base, length, *, lean=0, width=14):
    """Tapered phalanges, asymmetric pad and soft interphalangeal folds."""
    c.saveState()
    c.translate(x, base)
    c.rotate(lean)
    r = width / 2
    c.setFillColor(SKIN)
    _path(c, [
        ("M", -r-1, -7), ("C", -r-2, 5, -r-.5, 16, -r+.4, 25),
        ("C", -r+.7, 34, -r+.8, length-13, -r+1.7, length-7),
        ("C", -r+2.7, length-.4, r-1.7, length+2, r-.2, length-5),
        ("C", r+1.2, length-12, r-.5, 35, r-.2, 25),
        ("C", r+.4, 16, r+2, 4, r+1.5, -7), ("Z",),
    ], fill=True)
    for yy in (length * .42, length * .72):
        _crease(c, [("M", -r+2.3, yy), ("C", -1.8, yy-1.7, 2, yy-1.6, r-1.8, yy-.2)])
    _crease(c, [("M", -r+3, length-9), ("C", -.6, length-7.2, 2.7, length-7.5, r-2, length-9)], width=.55)
    c.restoreState()


def _folded_finger(c, x, y, *, width=16, height=28, tilt=0):
    """A flexed finger seen as a knuckle arch and a tucked fingertip pad."""
    c.saveState()
    c.translate(x, y)
    c.rotate(tilt)
    r = width / 2
    c.setFillColor(SKIN)
    _path(c, [
        ("M", -r+2, -8), ("C", -r-3, 0, -r-2.8, 12, -r+1, height-5),
        ("C", -r+4, height+1.8, r-1, height+1, r+2, height-5),
        ("C", r+4.2, height-11, r+3.5, 6, r+1, 2),
        ("C", r-2, -4, -2, -7, -r+2, -8), ("Z",),
    ], fill=True)
    _crease(c, [("M", -r+.8, height-6), ("C", -2, height-9, 2, height-9, r+1.5, height-6)])
    _crease(c, [("M", -r+1.2, 12), ("C", -r+1, 3, -1, 0, r, 5)], width=.65)
    c.restoreState()


def _palm(c):
    """Thenar/hypothenar silhouette with a narrowing wrist; no box at the MCPs."""
    c.setFillColor(SKIN)
    _path(c, [
        ("M", 32, 0), ("C", 34, 13, 29, 21, 24, 29),
        ("C", 18, 40, 20, 54, 25, 67),
        ("C", 39, 81, 73, 83, 92, 70),
        ("C", 98, 62, 98, 49, 95, 39),
        ("C", 91, 28, 84, 23, 79, 14), ("C", 77, 9, 79, 4, 79, 0), ("Z",),
    ], fill=True, stroke=False)
    _path(c, [("M", 32, 0), ("C", 34, 13, 29, 21, 24, 29),
              ("C", 18, 40, 20, 54, 25, 67)])
    _path(c, [("M", 92, 70), ("C", 98, 62, 98, 49, 95, 39),
              ("C", 91, 28, 84, 23, 79, 14), ("C", 77, 9, 79, 4, 79, 0)])
    _crease(c, [("M", 35, 11), ("C", 46, 8, 64, 9, 76, 12)], width=.8)
    _crease(c, [("M", 36, 15), ("C", 45, 13, 54, 13, 61, 14)], width=.5)


def _palm_creases(c, *, covered=False):
    _crease(c, [("M", 29, 58), ("C", 38, 52, 39, 39, 43, 28)])
    _crease(c, [("M", 44, 26), ("C", 51, 19, 67, 19, 74, 24)], width=.55)
    if not covered:
        _crease(c, [("M", 34, 63), ("C", 45, 55, 63, 58, 77, 65)])
        _crease(c, [("M", 42, 49), ("C", 56, 43, 72, 42, 83, 48)])
        _crease(c, [("M", 82, 56), ("C", 88, 52, 90, 46, 89, 41)], width=.5)


def _spread_thumb(c, *, horizontal=False):
    c.setFillColor(SKIN)
    if horizontal:
        commands = [
            ("M", 35, 24), ("C", 25, 23, 20, 30, 12, 36),
            ("C", 5, 41, -3, 43, -9, 44),
            ("C", -16, 46, -15, 53, -10, 56),
            ("C", -5, 59, 2, 57, 9, 55),
            ("C", 17, 52, 24, 51, 28, 55), ("C", 31, 58, 32, 63, 32, 69),
            ("L", 41, 53), ("L", 43, 35), ("Z",),
        ]
        crease = [("M", 10, 42), ("C", 9, 46, 9, 50, 11, 53)]
        tip = (-8, 50)
    else:
        commands = [
            ("M", 36, 24), ("C", 24, 23, 18, 34, 10, 43),
            ("C", 2, 52, -6, 64, -10, 70),
            ("C", -13, 75, -10, 81, -5, 80),
            ("C", 0, 79, 4, 72, 9, 67),
            ("C", 17, 59, 24, 54, 29, 58), ("C", 32, 61, 32, 65, 32, 70),
            ("L", 41, 54), ("L", 43, 35), ("Z",),
        ]
        crease = [("M", 6, 52), ("C", 10, 50, 13, 49, 16, 49)]
        tip = (-5, 74)
    # Only the exposed contour is stroked; the attachment merges into the palm.
    _path(c, commands, fill=True, stroke=False)
    _path(c, commands[:-3])
    _crease(c, crease)
    return tip


def _tucked_thumb(c):
    """Rest across the lower palm, clear of every tucked fingertip."""
    c.setFillColor(SKIN)
    _path(c, [
        ("M", 29, 24), ("C", 19, 28, 17, 35, 21, 41),
        ("C", 25, 46, 31, 46, 37, 44),
        ("C", 44, 42, 49, 44, 55, 43),
        ("C", 62, 42, 63, 37, 58, 34),
        ("C", 54, 31, 48, 33, 43, 34),
        ("C", 38, 35, 33, 33, 32, 29),
    ], fill=True)
    _crease(c, [("M", 41, 35), ("C", 40, 38, 40, 41, 41, 43)])
    _crease(c, [("M", 52, 38), ("C", 54, 40, 57, 40, 58, 38)], width=.5)
    return (56, 38)


def _raised_thumb(c):
    c.setFillColor(SKIN)
    _path(c, [
        ("M", 31, 25), ("C", 17, 31, 15, 48, 17, 66),
        ("C", 20, 79, 16, 93, 15, 107),
        ("C", 14, 116, 15, 124, 21, 125),
        ("C", 28, 126, 30, 119, 30, 111),
        ("C", 31, 98, 32, 88, 36, 81),
        ("C", 41, 73, 43, 63, 42, 51),
    ], fill=True)
    _crease(c, [("M", 19, 91), ("C", 23, 89, 27, 89, 31, 90)])
    _crease(c, [("M", 19, 111), ("C", 22, 113, 25, 113, 27, 110)], width=.55)
    return (23, 118)


def _pinching_finger(c, x, base, peak, tip):
    """A bent finger with continuous dorsal arc and a rounded pad at contact."""
    tx, ty = tip
    c.setFillColor(SKIN)
    contour = [
        ("M", x+7, base-4), ("C", x+12, base+12, x+13, peak-7, x+1, peak),
        ("C", x-10, peak+6, x-22, peak-4, x-21, peak-18),
        ("C", x-21, peak-28, tx-8, ty+9, tx-4, ty+3),
        ("C", tx-1, ty-.6, tx+4, ty, tx+5, ty+4),
        ("C", tx+7, ty+11, x-10, peak-18, x-8, peak-13),
        ("C", x-5, peak-7, x+2, peak-11, x+2, peak-20),
        ("C", x+2, base+13, x-2, base+3, x-8, base-7),
    ]
    # The hidden MCP attachment has no closing stroke or extra fingertip curl:
    # at small manual scale those marks can look like a second contact or a 6.
    _path(c, contour + [("Z",)], fill=True, stroke=False)
    _path(c, contour)
    _crease(c, [("M", x+4, peak-4), ("C", x, peak-6, x-6, peak-6, x-10, peak-4)])


def _opposed_thumb(c, target, color):
    """The thumb crosses the palm and its soft pad meets the selected tip."""
    tx, ty = target
    c.setFillColor(SKIN)
    _path(c, [
        ("M", 32, 25), ("C", 18, 29, 13, 39, 17, 50),
        ("C", 20, 60, tx-10, ty-14, tx-5, ty-3),
        ("C", tx-4, ty+1, tx+2, ty+1, tx+5, ty-3),
        ("C", tx+8, ty-9, tx+3, ty-14, tx, ty-17),
        ("C", .6*tx+16, ty-23, 37, 45, 40, 34),
    ], fill=True)
    c.setFillColor(color)
    c.circle(tx, ty, 1.8, fill=1, stroke=0)


def draw_hand(canvas, x, y, scale=1, pose="open", marks=False, color=TEAL):
    """Draw one vector hand without changing the caller's canvas state.

    Pinches use an extended remainder of the hand to identify which finger is
    bent into contact; L, victory, thumb and scroll use their required folded
    fingers. Open-hand number markers identify tips 4/8/12/16/20.
    """
    if pose not in POSES:
        raise ValueError(f"Unknown illustrated hand pose: {pose}")
    c = canvas
    c.saveState()
    c.translate(x, y)
    c.scale(scale, scale)
    c.setStrokeColor(color)
    c.setLineCap(1)
    c.setLineJoin(1)
    c.setFillColor(SKIN)
    extended = {
        "open": (8, 12, 16, 20), "index": (8,), "l": (8,),
        "victory": (8, 12), "thumb": (), "scroll": (8, 12),
    }
    pinch_tip = int(pose[5:]) if pose.startswith("pinch") else None
    active = tuple(tip for tip in (8, 12, 16, 20) if tip != pinch_tip) if pinch_tip else extended[pose]
    specs = {8: (32, 65, 65, 4, 14), 12: (53, 74, 70, 0, 15),
             16: (74, 71, 63, -3, 14), 20: (91, 65, 46, -8, 12)}
    if pose == "victory":
        specs[8], specs[12] = (31, 64, 70, 17, 14), (56, 73, 70, -10, 15)
    elif pose == "scroll":
        specs[8], specs[12] = (36, 65, 65, 0, 14), (51, 70, 66, 0, 15)
    elif pose == "thumb":
        specs[8], specs[12] = (45, 68, 65, 0, 14), (62, 70, 70, 0, 15)
        specs[16], specs[20] = (79, 68, 63, 0, 14), (96, 63, 46, 0, 12)
    for tip in active:
        fx, base, length, lean, fw = specs[tip]
        _long_finger(c, fx, base, length, lean=lean, width=fw)
    _palm(c)
    _palm_creases(c, covered=pose != "open")
    for tip in (8, 12, 16, 20):
        if tip not in active and tip != pinch_tip:
            fx, base, _, _, fw = specs[tip]
            _folded_finger(c, fx, base-14, width=fw+1, height=26 if tip != 20 else 23,
                           tilt=-4 if tip == 20 else 0)
    if pinch_tip:
        targets = {8: (15, 78), 12: (36, 82), 16: (57, 75), 20: (74, 65)}
        peaks = {8: 111, 12: 117, 16: 110, 20: 99}
        fx, base, _, _, _ = specs[pinch_tip]
        _pinching_finger(c, fx, base, peaks[pinch_tip], targets[pinch_tip])
        _opposed_thumb(c, targets[pinch_tip], color)
    elif pose in ("open", "l", "victory"):
        _spread_thumb(c, horizontal=pose in ("l", "victory"))
    elif pose == "thumb":
        _raised_thumb(c)
    else:
        _tucked_thumb(c)
    if marks:
        # Markers are tip references, not additional anatomy or interactive UI.
        tips = {4: (-5, 74), 8: (28, 123), 12: (53, 138), 16: (77, 128), 20: (96, 105)}
        font = "UI-Bold" if "UI-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
        for number, (tx, ty) in tips.items():
            c.setFillColor(color)
            c.circle(tx, ty, 6.9, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont(font, 7.3)
            c.drawCentredString(tx, ty-2.5, str(number))
    c.restoreState()
