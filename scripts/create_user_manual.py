"""Build the illustrated local user manual; no webcam, screenshot or OS input.

Diagrams are explanatory vector drawings, not detections or recreated photos.
Run with the bundled document runtime (ReportLab), not the app dependencies.
"""

import math
from pathlib import Path
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biogesture import AUTHOR, __version__  # noqa: E402 - standalone document entry point

VERSION_LABEL = ".".join(__version__.split(".")[:2])
OUT = ROOT / f"output/pdf/Bio-Gesture-Control-Pro-{VERSION_LABEL}-Manual-de-usuario.pdf"
W, H = A4
PAGE_COUNT = 17
M = 43
CW = W - 2 * M
INK = colors.HexColor("#182a35")
MUTED = colors.HexColor("#506877")
TEAL = colors.HexColor("#087d85")
PALE = colors.HexColor("#eaf6f5")
LINE = colors.HexColor("#d6e3e7")
NAVY = colors.HexColor("#071527")
PURPLE = colors.HexColor("#7550a4")
SKIN = colors.HexColor("#dcefee")
STYLE = {}
BOTTOMS = []
C = None


def init_fonts():
    for name, file in (("UI", "segoeui.ttf"), ("UI-Bold", "segoeuib.ttf"), ("UI-Italic", "segoeuii.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / file)))
    pdfmetrics.registerFontFamily("UI", normal="UI", bold="UI-Bold", italic="UI-Italic", boldItalic="UI-Bold")
    STYLE["body"] = ParagraphStyle("body", fontName="UI", fontSize=11, leading=16, textColor=INK, spaceAfter=7)
    STYLE["small"] = ParagraphStyle("small", parent=STYLE["body"], fontSize=9, leading=13, textColor=MUTED)
    STYLE["h2"] = ParagraphStyle("h2", parent=STYLE["body"], fontName="UI-Bold", fontSize=16, leading=21, textColor=TEAL)
    STYLE["cell"] = ParagraphStyle("cell", parent=STYLE["body"], fontSize=10, leading=14)
    STYLE["white"] = ParagraphStyle("white", parent=STYLE["body"], textColor=colors.white)
    STYLE["center"] = ParagraphStyle("center", parent=STYLE["body"], alignment=TA_CENTER)


def paragraph(text, x, y, width=CW, style="body"):
    p = Paragraph(text, STYLE[style])
    _, height = p.wrap(width, H)
    if y - height < 44:
        raise ValueError(f"Text below safe area: {text[:70]}")
    p.drawOn(C, x, y - height)
    BOTTOMS.append(y - height)
    return y - height - 9


def heading(text, y):
    return paragraph(text, M, y, style="h2")


def label(text, x, y, size=10, color=INK, bold=False):
    C.setFillColor(color)
    C.setFont("UI-Bold" if bold else "UI", size)
    C.drawString(x, y, text)


def arrow(x1, y1, x2, y2, color=TEAL, width=2):
    C.setStrokeColor(color)
    C.setFillColor(color)
    C.setLineWidth(width)
    C.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    p = C.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - 8 * math.cos(angle - .45), y2 - 8 * math.sin(angle - .45))
    p.lineTo(x2 - 8 * math.cos(angle + .45), y2 - 8 * math.sin(angle + .45))
    p.close()
    C.drawPath(p, fill=1, stroke=0)


def note(title, text, y, color=TEAL):
    title_p = Paragraph(f"<b>{title}</b>", STYLE["body"])
    text_p = Paragraph(text, STYLE["body"])
    th = title_p.wrap(CW - 30, H)[1]
    bh = text_p.wrap(CW - 30, H)[1]
    total = th + bh + 31
    if y - total < 44:
        raise ValueError("Note extends beyond page")
    C.setFillColor(PALE)
    C.roundRect(M, y - total, CW, total, 9, fill=1, stroke=0)
    C.setFillColor(color)
    C.rect(M, y - total + 8, 3, total - 16, fill=1, stroke=0)
    title_p.drawOn(C, M + 15, y - 12 - th)
    text_p.drawOn(C, M + 15, y - 18 - th - bh)
    BOTTOMS.append(y - total)
    return y - total - 18


def table(headers, rows, y, fractions=None):
    widths = [CW * a for a in (fractions or [1 / len(headers)] * len(headers))]
    data = [[Paragraph(f"<b>{v}</b>", STYLE["cell"]) for v in headers]]
    data += [[Paragraph(str(v), STYLE["cell"]) for v in row] for row in rows]
    t = Table(data, colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f9fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEAL),
        ("LINEBELOW", (0, 1), (-1, -1), .35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    height = t.wrap(CW, H)[1]
    if y - height < 48:
        raise ValueError(f"Table too tall on page: {headers}")
    t.drawOn(C, M, y - height)
    BOTTOMS.append(y - height)
    return y - height - 18


def hand(x, y, scale=1, pose="open", marks=False, color=TEAL):
    """Draw the pose-specific anatomical vector illustration."""
    from scripts.manual_hands import draw_hand
    draw_hand(C, x, y, scale=scale, pose=pose, marks=marks, color=color)


def page(number, title, section):
    C.setFillColor(colors.white)
    C.rect(0, 0, W, H, fill=1, stroke=0)
    C.bookmarkPage(f"p{number}")
    C.addOutlineEntry(title, f"p{number}", level=0)
    label("BIO-GESTURE / MANUAL DE USUARIO", M, H - 30, 8, TEAL, True)
    C.setFillColor(INK)
    C.setFont("UI-Bold", 26)
    C.drawString(M, H - 77, title)
    label(section.upper(), M, H - 101, 9, MUTED)
    C.setStrokeColor(LINE)
    C.line(M, 36, W - M, 36)
    label(AUTHOR, M, 22, 8, MUTED)
    C.setFont("UI", 8)
    C.drawRightString(W - M, 22, f"{number:02d} / {PAGE_COUNT}  |  {__version__}")
    return H - 128


def cover():
    C.setFillColor(NAVY)
    C.rect(0, 0, W, H, fill=1, stroke=0)
    C.bookmarkPage("p1")
    C.addOutlineEntry("Manual de usuario", "p1", level=0)
    C.drawImage(str(ROOT / "assets/brand/anchor-approved.png"), W / 2 - 90, H - 275,
                180, 180, preserveAspectRatio=True, anchor="c", mask="auto")
    C.setFillColor(colors.white)
    C.setFont("UI-Bold", 30)
    C.drawCentredString(W / 2, H - 335, "Bio-Gesture Control Pro")
    C.setFont("UI", 25)
    C.drawCentredString(W / 2, H - 375, f"Manual de usuario · {VERSION_LABEL}")
    C.setFillColor(colors.HexColor("#79d8dc"))
    C.setFont("UI", 13)
    C.drawCentredString(W / 2, H - 420, "Tu escritorio, con una mano principal y una auxiliar")
    C.setFillColor(colors.white)
    C.setFont("UI-Bold", 13)
    C.drawCentredString(W / 2, 296, AUTHOR)
    paragraph("Guía visual para Windows. Instalación portable, gestos, ajustes, menú radial y recuperación.",
              M + 24, 258, CW - 48, "white")
    paragraph(f"Edición de pruebas {__version__}. Los dibujos son esquemas explicativos; no son capturas ni resultados de detección.",
              M + 24, 197, CW - 48, "white")
    C.setFillColor(colors.HexColor("#15323d"))
    C.roundRect(M, 65, CW, 68, 10, fill=1, stroke=0)
    paragraph("<b>Tu salida rápida: Ctrl+Alt+F12</b><br/>Pausa las acciones y recupera la ventana del programa.", M + 17, 120, CW - 34, "white")


def start():
    y = page(2, "Empieza sin complicaciones", "De la carpeta al primer movimiento")
    y = note("1. Extrae todo el ZIP", "Haz clic derecho en el ZIP y elige Extraer todo. Abre la carpeta extraída: BioGestureControlPro.exe debe quedar junto a _internal. No ejecutes el EXE dentro del ZIP.", y)
    y = note("2. Abre y prepara", "Abre BioGestureControlPro.exe. Verás el ancla y la firma al cargar. El inicio predeterminado está pausado. En Ajustes elige cámara y monitor; al Guardar permanece pausado.", y)
    y = note("3. Elige tu principal y activa", "Muestra solo la mano que moverá el cursor. Si ves ambas al comenzar, retira una momentáneamente. Luego puedes usar las dos. Pulsa Activar y prueba primero índice, clic y pausa.", y)
    y = paragraph("No necesitas instalar Python, Git ni ejecutar comandos. El portable no añade servicios ni inicio automático. En equipos nuevos puede ser necesario habilitar tú mismo el permiso de cámara en Windows.", M, y)
    y = heading("Encuentra lo que necesitas", y - 6)
    sections = [("Ventana, roles y puntos", 3), ("Cursor y gestos principales", 5), ("Mano auxiliar y L", 7),
                ("Menú radial y sus funciones", 9), ("Ajustes y calibración", 13), ("Problemas y mantenimiento", 15)]
    for text, dest in sections:
        label(text, M + 8, y - 12, 11)
        label(str(dest), W - M - 19, y - 12, 11, TEAL, True)
        C.linkAbsolute(text, f"p{dest}", Rect=(M, y - 21, W - M, y + 2), thickness=0)
        y -= 27


def desktop():
    y = page(3, "Reconoce tu ventana", "Una vista de 550 x 375, controles accesibles")
    x, top, width, height = M + 28, y - 5, CW - 56, 270
    C.setFillColor(NAVY)
    C.roundRect(x, top - height, width, height, 10, fill=1, stroke=0)
    label("Bio-Gesture", x + 16, top - 24, 11, colors.white, True)
    label("Activar    Ajustes    Más", x + width - 166, top - 24, 10, colors.HexColor("#79d8dc"))
    C.setFillColor(colors.HexColor("#f0f5f6"))
    C.rect(x + 11, top - height + 13, width - 22, height - 51, fill=1, stroke=0)
    hand(x + 83, top - height + 40, 1.02, "index")
    hand(x + 250, top - height + 40, 1.02, "l", color=PURPLE)
    label("Ilustración de orientación, no captura", x + 72, top - height - 13, 8, MUTED)
    y = top - height - 25
    y = table(["Control", "Qué hace"], [
        ("Activar / Pausar", "Habilita o suspende las acciones. Pausar conserva la cámara para reconocer victoria y onda."),
        ("Ajustes", "Configura cámara, precisión, pantalla, puntos y mano auxiliar. Abrirlos pausa el control."),
        ("Más", "Fijar ventana, cámara, ocultar, salir, reelegir principal y activar/desactivar auxiliar."),
        ("Ancla en la bandeja", "Permite mostrar la ventana, pausar, cambiar modo y salir. Está junto al reloj; puede estar entre los iconos ocultos."),
    ], y, [.29, .71])
    note("Ocultar no es apagar", "Ocultar mantiene el seguimiento y las acciones si el control está activo. Apagar cámara detiene el dispositivo. Salir cierra el programa.", y)


def roles():
    y = page(4, "Dos manos, dos funciones", "No hay izquierda o derecha obligatoria")
    hand(M + 20, y - 157, 1.04, "open", marks=True)
    y2 = paragraph("<b>Principal</b><br/>Controla el cursor, clics, arrastre, volumen, menú y gestos de ventana/pausa.", M + 200, y - 10, CW - 205)
    paragraph("<b>Auxiliar</b><br/>Copia, pega, deshace, rehace y desplaza con la L. Nunca toma el cursor.", M + 200, y2 - 4, CW - 205)
    y -= 190
    y = table(["Número", "Dedo"], [("4", "Pulgar"), ("8", "Índice"), ("12", "Corazón / medio"),
                                     ("16", "Anular"), ("20", "Meñique")], y, [.2, .8])
    y = paragraph("Los números son referencias de detección, no botones. La elección inicial se hace con una sola mano visible; la otra recibe el rol auxiliar. Tras una pérdida de detección se recuperan los roles automáticamente: no hace falta retirar ambas manos un segundo.", M, y)
    y = note("¿Quieres intercambiar los roles?", "Más > Reelegir mano principal. El programa pausa las acciones: muestra solo la elegida, deja que se detecte y vuelve a Activar. Una imagen fija no basta para saber qué rol tenía cada mano en esa sesión.", y)
    note("Ver los puntos es opcional", "Ajustes > Escritorio > Dibujar puntos de mano > Guardar. La casilla manda también en el EXE limpio. No activa textos de ayuda; desmárcala para volver a una imagen sin puntos.", y)


def clicks():
    y = page(5, "Cursor, clic y arrastre", "La mano principal conserva su comportamiento")
    for pose, title, text in [
        ("index", "Mover el cursor", "Desplaza el dedo índice (punto 8). No necesitas cerrar rígidamente los demás dedos. Un gesto exclusivo reconocido, como el menú o volumen, tiene prioridad."),
        ("pinch8", "Clic izquierdo: 8 con 4", "Junta índice y pulgar para presionar. Sepáralos para soltar: ese ciclo es el clic. Para arrastrar, mantén la pinza mientras mueves el índice; abrirla termina el arrastre sin añadir otro clic."),
        ("pinch12", "Clic derecho: 12 con 4", "Junta corazón y pulgar. Se ejecuta una vez; abre la pinza antes de repetir. El clic se realiza en la posición del cursor que guía el índice."),
    ]:
        hand(M + 17, y - 120, .77, pose)
        paragraph(f"<b>{title}</b><br/>{text}", M + 147, y - 8, CW - 147)
        y -= 155
    y = note("Para practicar sin riesgo", "Abre una carpeta o un documento de prueba. Primero mueve, luego haz un clic, después arrastra un elemento prescindible. No pruebes sobre archivos importantes ni acciones destructivas.", y)
    paragraph("Al perder la mano, se suelta cualquier botón retenido. Si se interrumpió una pinza, ábrela antes de iniciar otra; esto evita que el botón vuelva a quedar presionado por accidente.", M, y)


def main_other():
    y = page(6, "Más gestos de la principal", "Pausa, volumen, scroll y modo de ventana")
    for i, (pose, title) in enumerate((("victory", "Victoria"), ("pinch16", "Volumen"),
                                     ("scroll", "Scroll arriba"), ("thumb", "Menú"))):
        xx = M + i * 128
        hand(xx + 22, y - 74, .5, pose)
        label(title, xx + 22, y - 86, 10, TEAL, True)
    y -= 103
    y = table(["Gesto", "Uso"], [
        ("Victoria mantenida", "Índice y corazón extendidos y separados; anular y meñique doblados. Pulgar lejos del índice, sin tocar corazón/anular. Mantén 2 s para alternar pausa; suelta antes de repetir."),
        ("Pulgar + anular", "Junta 4 y 16 y mueve la mano verticalmente: arriba sube volumen, abajo lo baja. Abre para terminar. No controla el cursor durante este gesto."),
        ("Índice y corazón juntos", "Con pulgar recogido y demás dedos doblados, mantén la postura 0.7 s: pareja extendida desplaza arriba; pareja doblada y separada del anular, abajo."),
        ("Pulgar levantado", "Con los otros dedos doblados, mantén 0.8 s para abrir el radial. No se exige que apunte perfectamente hacia arriba."),
    ], y, [.32, .68])
    y = heading("Ventana normal / fija transparente", y)
    y = paragraph("Abre la mano de forma relajada y haz cuatro recorridos laterales alternados, empezando hacia cualquier lado. Completa el gesto dentro de unos 2.2 s. Tres recorridos no bastan.", M, y)
    for i, (a, b) in enumerate(((0, 1), (1, 0), (0, 1), (1, 0))):
        xx = M + 14 + i * 126
        arrow(xx + a * 81, y - 33, xx + b * 81, y - 33)
        label(str(i + 1), xx + 36, y - 55, 10, TEAL, True)
    y -= 88
    y = note("No cierres la mano para continuar", "Después del cambio puedes mantenerla abierta. Una espera antirrepetición de 0.30 s separa las secuencias; cada nuevo cambio requiere otros cuatro recorridos. También funciona en pausa, sin reactivar el mouse.", y)
    paragraph("La vista fija no tiene bordes, queda encima de otras ventanas y usa la opacidad elegida. También puedes alternarla desde Más o la bandeja y arrastrarla por la zona libre de su barra superior.", M, y)


def auxiliary():
    y = page(7, "Tu mano auxiliar", "Edición cotidiana en la aplicación activa")
    y = paragraph("Mantén cada pinza 0.45 s. El comando se ejecuta una vez; abre antes de repetir. No se limita a Visual Studio Code.", M, y)
    items = [(8, "Copiar", "Ctrl+C", "Índice"), (12, "Pegar", "Ctrl+V", "Corazón"),
             (16, "Deshacer", "Ctrl+Z", "Anular"), (20, "Rehacer", "Ctrl+Y", "Meñique")]
    for i, (tip, title, key, finger) in enumerate(items):
        col, row = i % 2, i // 2
        x = M + col * (CW / 2 + 8)
        top = y - row * 180
        C.setFillColor(PALE)
        C.roundRect(x, top - 165, CW / 2 - 8, 160, 9, fill=1, stroke=0)
        hand(x + 15, top - 135, .63, f"pinch{tip}", color=PURPLE)
        paragraph(f"<b>{title}</b><br/>{key}<br/>{finger} + pulgar", x + 115, top - 35, CW / 2 - 137)
    y -= 376
    y = note("Primero elige el destino", "Los atajos llegan a la ventana en primer plano. Copiar necesita una selección; Deshacer/Rehacer dependen del historial de esa aplicación. Algunas aplicaciones no usan Ctrl+Y para Rehacer.", y)
    y = note("La principal tiene prioridad", "Clic, arrastre, menú, onda, volumen y scroll de la principal bloquean la auxiliar. Pausa, Ajustes y calibración también la bloquean. La auxiliar puede actuar si la principal sale momentáneamente de cámara y no hay una operación incompatible.", y)
    paragraph("Puedes deshabilitar los comandos auxiliares desde Más o Ajustes > Escritorio. Esto no cambia el movimiento del índice principal.", M, y)


def l_scroll():
    y = page(8, "La L y el centro de imagen", "Arriba desplaza arriba; abajo desplaza abajo")
    hand(M + 26, y - 140, .95, "l", color=PURPLE)
    paragraph("<b>Pulgar e índice abiertos</b><br/>Forma una L natural; corazón, anular y meñique doblados. Usa la mano auxiliar y mantén la pose 0.45 s.", M + 178, y - 7, CW - 178)
    y -= 177
    box_x, box_top, box_w, box_h = M + 5, y, 220, 238
    C.setFillColor(PALE)
    C.roundRect(box_x, box_top - box_h, box_w, box_h, 8, fill=1, stroke=0)
    C.setFillColor(colors.HexColor("#cde5e4"))
    C.rect(box_x, box_top - box_h * .55, box_w, box_h * .1, fill=1, stroke=0)
    C.setDash(3, 3)
    C.setStrokeColor(TEAL)
    C.line(box_x, box_top - box_h * .5, box_x + 25, box_top - box_h * .5)
    C.line(box_x + 165, box_top - box_h * .5, box_x + box_w, box_top - box_h * .5)
    C.setDash()
    arrow(box_x + 40, box_top - 82, box_x + 40, box_top - 29)
    arrow(box_x + 40, box_top - 158, box_x + 40, box_top - 211)
    label("ARRIBA", box_x + 76, box_top - 60, 13, TEAL, True)
    label("CENTRO = PARAR", box_x + 33, box_top - 123, 11, INK, True)
    label("ABAJO", box_x + 80, box_top - 187, 13, TEAL, True)
    yy = paragraph("<b>Qué punto importa</b><br/>El centro de la palma, no la punta del índice. Una L con el dedo muy alto puede tener la palma todavía en el centro.", M + 252, y - 2, CW - 252)
    yy = paragraph("<b>Banda neutra: 45-55 %</b><br/>Dentro se detiene. Fuera comienza el desplazamiento y aumenta gradualmente al alejarte.", M + 252, yy - 7, CW - 252)
    paragraph("<b>El centro nunca se mueve</b><br/>No se toma donde empezaste el gesto. Puedes iniciar directamente arriba o abajo.", M + 252, yy - 7, CW - 252)
    y -= 260
    y = note("Prueba en tres posiciones", "Mantén la L y mueve toda la palma claramente arriba, luego al centro y después abajo. Espera a confirmar la pose; no uses una posición pegada al límite central para tu primera prueba.", y)
    paragraph("Soltar la L, perder la mano o pausar detiene el scroll. Al recuperarla se confirma otra vez, sin pedir retirar ambas manos ni volver al centro. Velocidad de desplazamiento se ajusta en Precisión; también afecta al scroll de la principal.", M, y)


def radial():
    y = page(9, "Usa el menú radial", "Ocho posiciones y una barra de carga")
    cx, cy, radius = M + 167, y - 160, 150
    C.setFillColor(NAVY)
    C.circle(cx, cy, radius, fill=1, stroke=0)
    names = ["Sistema", "Edición", "Web", "Multimedia", "Mayúsculas", "Ventanas", "Inicio", "Escape"]
    for i, text in enumerate(names):
        angle = i * math.pi / 4
        xx, yy = cx + 107 * math.cos(angle), cy - 107 * math.sin(angle)
        C.setFont("UI-Bold" if i == 0 else "UI", 10)
        C.setFillColor(colors.HexColor("#79d8dc") if i == 0 else colors.white)
        C.drawCentredString(xx, yy - 3, text)
    C.setFillColor(colors.HexColor("#35424c"))
    C.rect(cx - 40, cy, 80, 4, fill=1, stroke=0)
    C.setFillColor(colors.HexColor("#79d8dc"))
    C.rect(cx - 40, cy, 48, 4, fill=1, stroke=0)
    paragraph("<b>1. Abre</b><br/>Pulgar levantado, otros dedos doblados; 0.8 s.", M + 340, y - 35, CW - 340)
    paragraph("<b>2. Elige</b><br/>Mueve el pulgar desde donde abriste hacia un sector.", M + 340, y - 127, CW - 340)
    paragraph("<b>3. Confirma</b><br/>Mantén la dirección 1 s hasta completar la barra.", M + 340, y - 219, CW - 340)
    y -= 344
    y = note("Vuelve al centro entre selecciones", "Regresa el pulgar cerca de la posición donde abriste para preparar otra selección, también al entrar a un submenú o elegir Volver. Cambiar de sector reinicia la barra.", y)
    y = paragraph("Deja la pose de pulgar para cerrar el radial. Al abrirlo otra vez comienza en el menú principal. No es un menú que se maneje haciendo clic sobre los rótulos; responde al gesto.", M, y)
    note("El dibujo es simple", "La barra es la confirmación. No necesitas leer un porcentaje ni esperar una animación circular. Los siguientes apartados explican todas sus funciones.", y)


def menu_system():
    y = page(10, "Menú principal y Sistema", "Navegación y funciones del escritorio")
    y = table(["Principal", "Acción"], [
        ("Sistema / Edición / Web / Multimedia", "Abren los cuatro submenús descritos en estas páginas."),
        ("Mayúsculas", "Alterna Bloq Mayús."), ("Ventanas", "Alt+Tab: cambia de ventana, no de pestaña."),
        ("Inicio", "Abre Inicio con la tecla Windows."), ("Escape", "Envía Escape a la aplicación activa."),
    ], y, [.39, .61])
    y = heading("Sistema", y)
    y = table(["Opción", "Acción"], [
        ("Ajustes", "Abre la configuración y pausa las acciones."),
        ("Tareas", "Abre el Administrador de tareas de Windows. El nombre interno ADMIN no es el rol de una mano."),
        ("Bloquear", "Bloquea la sesión de Windows al completar la selección. No pide una segunda confirmación."),
        ("Buscar", "Global/Multimedia: búsqueda de Windows. Navegador/VS Code: Ctrl+F."),
        ("Volumen + / Volumen -", "Envía las teclas de volumen del sistema."),
        ("Silenciar", "Alterna el silencio del volumen del sistema."),
        ("Volver", "Regresa al menú principal."),
    ], y, [.29, .71])
    note("No selecciones Bloquear durante una prueba casual", "Reserva esa función para cuando realmente quieras cerrar el acceso a tu sesión. El programa no controla la pantalla segura ni se eleva automáticamente como administrador.", y)


def menu_edit_web():
    y = page(11, "Edición y Web", "Atajos para la ventana en primer plano")
    y = heading("Edición", y)
    y = table(["Opción", "Atajo y resultado"], [
        ("Copiar / Pegar", "Ctrl+C / Ctrl+V."), ("Deshacer / Rehacer", "Ctrl+Z / Ctrl+Y; depende del historial y atajos de la aplicación."),
        ("Cortar", "Ctrl+X: corta la selección."), ("Seleccionar todo", "Ctrl+A."),
        ("Eliminar", "Suprimir: puede borrar contenido o archivos seleccionados."), ("Volver", "Regresa al menú principal."),
    ], y, [.38, .62])
    y = heading("Web", y)
    y = table(["Opción", "Atajo y resultado"], [
        ("Nueva pestaña", "Ctrl+T."), ("Cerrar pestaña", "Ctrl+W: cierra la pestaña/elemento activo según la aplicación."),
        ("Recargar", "F5."), ("Atrás / Adelante", "Alt+Izquierda / Alt+Derecha."),
        ("Favoritos", "Ctrl+D."), ("Descargas", "Ctrl+J."), ("Volver", "Regresa al menú principal."),
    ], y, [.38, .62])
    note("Comprueba el foco", "Bio-Gesture no adivina en qué documento quieres trabajar. Selecciona antes la ventana destino con el cursor principal. Practica Cortar, Eliminar y Cerrar pestaña con contenido prescindible.", y)


def media():
    y = page(12, "Multimedia y perfiles", "Mismo menú; compatibilidad según la aplicación")
    y = table(["Multimedia", "Acción"], [
        ("Play/pausa", "Tecla multimedia del sistema."), ("Siguiente", "Siguiente pista mediante tecla multimedia."),
        ("-10 s / +10 s", "Teclas j / l de YouTube; solo habilitadas con perfil Multimedia y reproductor adecuado en primer plano."),
        ("Silenciar", "Silencio global del sistema, no la letra m del reproductor."),
        ("Pantalla completa", "Multimedia: f. Navegador/VS Code: F11. En Global no está habilitada."),
        ("Subtítulos", "Tecla c de YouTube; perfil Multimedia y reproductor con ese atajo."),
        ("Volver", "Regresa al menú principal."),
    ], y, [.34, .66])
    y = heading("Elige el perfil en Ajustes > Escritorio", y)
    y = table(["Perfil", "Cuándo usarlo"], [
        ("Global", "Uso general; Buscar abre búsqueda de Windows."),
        ("Navegador", "Buscar dentro de la página y pantalla completa con F11."),
        ("VS Code", "Buscar en el editor y pantalla completa con F11. No añade por sí solo nuevas opciones al radial."),
        ("Multimedia", "Activa los atajos específicos de reproductor descritos arriba."),
    ], y, [.27, .73])
    note("Un perfil no cambia la mano auxiliar", "Las pinzas auxiliares siempre envían Ctrl+C/V/Z/Y. Los perfiles se eligen manualmente: no detectan automáticamente la aplicación. Una acción incompatible puede pausar el control; consulta Diagnóstico.", y)


def settings():
    y = page(13, "Ajustes sin adivinar", "Cambia una cosa y comprueba su efecto")
    y = table(["Pestaña", "Controles y significado"], [
        ("Cámara", "Índice 0-16 elige el dispositivo. Ancho/alto y FPS son valores solicitados, no garantizados. FPS de detección limita el análisis. Vista espejo refleja horizontalmente la imagen."),
        ("Precisión: pinzas", "Cierre/apertura se miden respecto a la palma; apertura debe superar cierre. El indicador de arrastre cambia la etiqueta, no retrasa el clic izquierdo."),
        ("Precisión: movimiento", "Suavizado en reposo y respuesta al movimiento ajustan el equilibrio entre estabilidad y respuesta. No cambies ambos a la vez si estás probando."),
        ("Precisión: otras acciones", "Velocidad de desplazamiento afecta a ambos scrolls. Sensibilidad de volumen ajusta su cambio vertical. Invertir horizontal/vertical afecta al cursor, no al sentido del scroll L."),
        ("Escritorio", "Monitor primary: principal de Windows; virtual: escritorio completo; también puedes elegir una pantalla concreta. Incluye perfil, opacidad fija, inicio pausado, puntos y auxiliar."),
        ("Diagnóstico", "Versión, estado, FPS, tiempo de detección, CPU/memoria y carpeta de registros. Los avisos se consultan aquí; la zona de cámara no muestra instrucciones ni contadores de gestos."),
    ], y, [.30, .70])
    y = note("Guardar y reanudar son pasos distintos", "Guardar valida y aplica los ajustes; la cámara puede reiniciarse y el control permanece pausado. Espera la imagen y pulsa Activar. Cancelar descarta los cambios no guardados, pero no revierte una calibración ya capturada.", y)
    note("La casilla de puntos sí decide", "Marcada: dibuja los puntos de las manos detectadas. Desmarcada: no los dibuja. Funciona en la vista limpia; no añade mensajes ni cambia los gestos. Una instalación nueva empieza sin puntos, pero conserva tu preferencia guardada al actualizar.", y)


def calibration():
    y = page(14, "Calibra tu zona cómoda", "Menos esfuerzo para llegar a los bordes")
    y = paragraph("Selecciona antes cámara, espejo y monitor; guarda esos ajustes. Muestra la principal y abre Ajustes > Escritorio > Calibrar zona de trabajo. La calibración pausa las acciones.", M, y)
    bx, by, bw, bh = M + 58, y - 215, CW - 116, 185
    C.setFillColor(PALE)
    C.roundRect(bx, by, bw, bh, 10, fill=1, stroke=0)
    C.setStrokeColor(TEAL)
    C.setDash(5, 3)
    C.rect(bx + 38, by + 28, bw - 76, bh - 56, fill=0, stroke=1)
    C.setDash()
    for xx, yy, n in ((bx + 38, by + bh - 28, "1"), (bx + bw - 38, by + 28, "2")):
        C.setFillColor(TEAL)
        C.circle(xx, yy, 13, fill=1, stroke=0)
        C.setFillColor(colors.white)
        C.setFont("UI-Bold", 12)
        C.drawCentredString(xx, yy - 4, n)
    arrow(bx + 59, by + bh - 45, bx + bw - 59, by + 45)
    y = by - 24
    y = note("1. Extremo superior izquierdo", "Lleva el índice a la esquina superior izquierda de la zona que alcanzas cómodamente en la imagen. Mantén la posición un segundo y pulsa Capturar.", y)
    y = note("2. Extremo inferior derecho", "Repite en la esquina inferior derecha y vuelve a Capturar. No elijas una zona diminuta: necesita al menos 20 % de ancho y alto. Si tiembla o no hay muestras suficientes, repite con la mano quieta.", y)
    y = paragraph("La segunda captura guarda la zona automáticamente. Cierra Ajustes y pulsa Activar antes de comprobar los bordes. La referencia es la imagen con tu espejo actual: comprueba que llegas a las esquinas cómodamente, sin girar la pantalla ni invertir el sentido por intuición.", M, y)
    note("Esta calibración no mueve el centro de la L", "La zona de trabajo se aplica al cursor principal. La auxiliar sigue comparando la palma con la mitad fija de la imagen.", y)


def troubleshooting():
    y = page(15, "Si algo no responde", "Comprobaciones sencillas antes de tocar umbrales")
    y = table(["Qué notas", "Qué revisar"], [
        ("No aparece la imagen", "Comprueba cámara, índice elegido y permisos de Windows. Cierra otra aplicación que la esté usando. Apaga/enciende cámara desde Más."),
        ("Se ve la mano, pero no hay control", "¿Está pausado? ¿Hay Ajustes/calibración abiertos? Al iniciar deja una sola mano visible para elegir la principal; luego pulsa Activar."),
        ("No aparecen los puntos", "Marca Dibujar puntos de mano y pulsa Guardar. Debe haber detección válida. La vista limpia no anula esa casilla."),
        ("La L no desplaza", "Usa la auxiliar; confirma sus comandos habilitados. Dobla los otros tres dedos. Mueve el centro de la palma claramente fuera de la banda central, mantén la pose y comprueba que la principal no esté haciendo otro gesto."),
        ("La L parece cambiar de sentido", "La dirección depende de la palma respecto a la imagen, no del índice ni de la pantalla. En el centro se detiene. Prueba arriba y abajo con una separación clara."),
        ("Copiar/Pegar va al lugar equivocado", "Selecciona antes la ventana destino. Comprueba selección, portapapeles y atajos de esa aplicación."),
        ("El puntero salta o no llega", "Mejora luz y encuadre, calibra, revisa monitor/espejo y evita ocluir o cruzar manos. Cambia un ajuste de suavizado a la vez."),
        ("La onda no cambia la ventana", "Cuatro recorridos, tres cambios de dirección. Mano abierta relajada y desplazamiento lateral suficiente. También puedes usar Más."),
        ("El EXE no abre tras moverlo", "Extrae toda la carpeta; no separes _internal. Usa una carpeta accesible. No desactives las protecciones de Windows para forzar la prueba."),
    ], y, [.32, .68])
    note("Ante una acción inesperada", "Ctrl+Alt+F12 pausa y recupera la ventana. Revisa el estado en Diagnóstico. No cierres tareas del sistema ni cambies permisos para intentar arreglar un gesto.", y)


def care():
    y = page(16, "Uso seguro y mantenimiento", "Cierra bien, conserva tus ajustes")
    y = heading("Actualiza sin mezclar carpetas", y)
    y = paragraph("Sal del programa desde Más o la bandeja. Extrae el ZIP nuevo en una carpeta distinta y ábrelo desde allí. No sobrescribas archivos de una versión abierta ni mezcles su _internal con otra entrega. La configuración se carga desde tu perfil de Windows.", M, y)
    y = heading("Dónde se guardan tus datos", y)
    y = paragraph("Ajustes y registros: <b>%LOCALAPPDATA%\\BioGestureControlPro</b>. Puedes abrir esa carpeta desde Diagnóstico. El seguimiento es local y no graba fotos o video de manera predeterminada. Las capturas que entregaste para esta revisión se conservan aparte; no se incorporan a este manual.", M, y)
    y = heading("Retirar el portable", y)
    y = paragraph("Cierra el programa y elimina su carpeta extraída cuando ya no la necesites. Los ajustes permanecen por separado. Borrarlos es una decisión distinta: perderías la calibración y preferencias guardadas. El portable no instala un servicio ni incluye desinstalador formal.", M, y)
    y = note("Versión de pruebas, no instalador firmado", "La firma visual de Luics415 no es una firma digital de Windows. El funcionamiento en un equipo con herramientas de desarrollo no confirma todavía una computadora recién instalada. Publicar el código o un portable de pruebas no convierte esta edición en una versión final certificada.", y)
    y = heading("Comprueba tu sesión", y)
    for item in ["Imagen estable y manos completas, con luz uniforme.", "Principal elegida; cursor, clics y pausa comprobados.",
                 "Auxiliar: una ejecución por pinza; L arriba, centro y abajo.", "Onda de cuatro recorridos, bandeja y salida correcta."]:
        y = paragraph("<b>□</b> " + item, M + 5, y, CW - 5)
    y = paragraph("Referencia: código y README de esta revisión, además de tus dos capturas para analizar la L. Los esquemas orientan; no prometen precisión universal. Descansa si notas tensión en brazos o manos y alterna con teclado/mouse.", M, y - 4, style="small")
    label("Gracias por usar Bio-Gesture. El ancla permanece.", M, y - 5, 11, TEAL, True)


def author_signature():
    C.setFillColor(NAVY)
    C.rect(0, 0, W, H, fill=1, stroke=0)
    C.bookmarkPage("p17")
    C.addOutlineEntry("Firma de autor", "p17", level=0)
    C.setFillColor(colors.HexColor("#79d8dc"))
    C.setFont("UI", 12)
    C.drawCentredString(W / 2, H - 122, "BIO-GESTURE CONTROL PRO")
    C.setFillColor(colors.white)
    C.setFont("UI-Bold", 26)
    C.drawCentredString(W / 2, H - 163, "El ancla es nuestra identidad")
    # Place the author-approved 2.7 version edit, uncropped.
    signature_width = W - 40
    signature_height = signature_width * 2 / 3
    C.drawImage(str(ROOT / "assets/brand/splash-author.png"), 20, H / 2 - signature_height / 2 - 10,
                signature_width, signature_height, preserveAspectRatio=True, anchor="c", mask="auto")
    C.setFillColor(colors.white)
    C.setFont("UI-Bold", 15)
    C.drawCentredString(W / 2, 151, AUTHOR)
    C.setFillColor(colors.HexColor("#79d8dc"))
    C.setFont("UI", 10)
    C.drawCentredString(W / 2, 118, "Gracias por formar parte del proyecto.")
    C.setFont("UI", 8)
    C.drawCentredString(W / 2, 30, f"17 / {PAGE_COUNT}  |  {__version__}")


def main():
    global C
    init_fonts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    C = canvas.Canvas(str(OUT), pagesize=A4, pageCompression=1)
    C.setTitle(f"Bio-Gesture Control Pro {VERSION_LABEL} - Manual de usuario")
    C.setAuthor("Luics415")
    C.setCreator("Bio-Gesture Control Pro - Documentación")
    C.setSubject(f"Guía visual de uso, {__version__}; esquemas originales, sin capturas personales")
    C.setKeywords("Bio-Gesture, Luics415, manual, gestos, Windows, accesibilidad")
    for render in (cover, start, desktop, roles, clicks, main_other, auxiliary, l_scroll,
                   radial, menu_system, menu_edit_web, media, settings, calibration, troubleshooting, care, author_signature):
        render()
        C.showPage()
    C.save()
    print(f"Manual generado: {OUT}; {PAGE_COUNT} páginas; margen mínimo de contenido: {min(BOTTOMS):.1f} pt")


if __name__ == "__main__":
    main()
