"""Build the development guide separately from the preserved 2.7 visual manual."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/Bio-Gesture-Control-Pro-3.0-Guia-de-pruebas.pdf"


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for name, filename in (("Guide", "segoeui.ttf"), ("GuideBold", "segoeuib.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / filename)))
    pdfmetrics.registerFontFamily("Guide", normal="Guide", bold="GuideBold", italic="Guide", boldItalic="GuideBold")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("GuideBody", fontName="Guide", fontSize=10.5, leading=15,
                          textColor=colors.HexColor("#233c49"), spaceAfter=8)
    title = ParagraphStyle("GuideTitle", parent=body, fontName="GuideBold", fontSize=25, leading=31,
                           textColor=colors.HexColor("#087d85"), spaceAfter=12)
    heading = ParagraphStyle("GuideHeading", parent=body, fontName="GuideBold", fontSize=15, leading=20,
                             spaceBefore=12, spaceAfter=7)
    small = ParagraphStyle("GuideSmall", parent=body, fontSize=9, leading=12)
    del styles
    story = []

    def p(text, style=body):
        story.append(Paragraph(text, style))

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#d6e3e7"))
        canvas.line(44, 42, A4[0] - 44, 42)
        canvas.setFont("Guide", 8)
        canvas.setFillColor(colors.HexColor("#506877"))
        canvas.drawString(44, 28, "Bio-Gesture 3.0 | Prototipo local de desarrollo")
        canvas.drawRightString(A4[0] - 44, 28, str(doc.page))

    p("Bio-Gesture Control Pro 3.0", title)
    p("Guía de pruebas · 3.0.0.dev3", heading)
    p("<b>Elige cómo apuntar: ojos o dedo índice.</b> La edición 2.7 permanece disponible aparte. "
      "Este prototipo ocular necesita pruebas reales antes de convertirse en una versión final.")
    p("1. Elige tu control", heading)
    p("Abre <b>Ajustes → Control</b>. Dedo índice mantiene el cursor clásico; "
      "Ojos (experimental) utiliza una estimación calibrada de mirada. Guarda los cambios: "
      "la cámara se reinicia y el control permanece pausado.")
    data = [[Paragraph("Óptimo", body), Paragraph("Conserva tu calidad configurada. Permite índice u ojos.", body)],
            [Paragraph("Ahorrativo", body), Paragraph("Solo manos; desactiva el modelo facial. Solicita 480 × 360 y hasta 15 FPS, sin borrar tus valores de calidad.", body)]]
    table = Table(data, colWidths=[110, A4[0] - 198])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eaf6f5")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 11),
                               ("TOPPADDING", (0, 0), (-1, -1), 9)]))
    story.append(table)
    p("2. Prepara la cámara", heading)
    p("<b>Distancia orientativa para empezar: unos 50-70 cm de la cámara.</b> No es una medición "
      "ni un rango garantizado. Depende de la cámara, la iluminación y los lentes. Usa tus lentes "
      "habituales, evita reflejos directos y mantén ambos ojos dentro de la imagen.")
    p("Antes de iniciar", heading)
    p("El asistente muestra un recorte ampliado de ambos ojos con sus puntos de detección. "
      "Comprueba la visibilidad y los reflejos. <b>No debes seguir esos dibujos con la mirada.</b> "
      "La ampliación ayuda a observar, pero no añade resolución ni garantiza una detección correcta.")
    p("El fondo inicial es <b>gris mate</b>, para no empezar con una pantalla casi negra. Si el monitor "
      "se refleja demasiado en tus lentes, puedes elegir <b>Fondo: oscuro</b> antes de iniciar. "
      "Usa luz suave frontal y evita cambiar la iluminación durante los puntos.")
    p("La primera implementación utiliza un monitor. No selecciones Escritorio completo para los ojos.", small)
    story.append(PageBreak())
    p("Calibrar: sigue el objetivo", title)
    p("Cabeza estable · Solo la mirada · Parpadeo normal", heading)
    p("<b>1. Acomódate.</b> Cámara quieta, lentes habituales y cabeza relativamente estable. "
      "No necesitas quedarte rígido, pero no gires la cabeza para apuntar ni te acerques y alejes durante los puntos.")
    p("<b>2. Pulsa Iniciar.</b> El recorte de los ojos se oculta. Mira el centro del objetivo "
      "y espera a que cambie. Mueve solo los ojos: no sigas el cursor del ratón ni los puntos de detección.")
    p("<b>3. Parpadea normalmente.</b> No necesitas mostrar las manos ni confirmar con gestos. "
      "Los parpadeos pausan la recogida; las muestras válidas del mismo punto se conservan. "
      "Al volver a mirar, espera a que continúe.")
    p("<b>4. Completa nueve puntos y cinco de comprobación.</b> Los cinco finales comprueban el "
      "resultado sin volver a enseñar al sistema sus respuestas. El cursor permanece bloqueado durante el proceso.")
    p("<b>5. Si se aprueba, activa el control.</b> Cierra Ajustes y utiliza victoria o el botón "
      "de la interfaz. Aprobar la calibración no reanuda el control automáticamente.")
    p("Si aparece un error", heading)
    p("<b>Un punto no termina:</b> tras 20 segundos, el asistente indica qué ha impedido recoger "
      "muestras suficientes y permite <b>Repetir punto</b>. Si cambias la postura, la cámara o el fondo, "
      "conviene comenzar de nuevo. Cambiar el fondo exige repetir la calibración completa.")
    p("<b>Precisión insuficiente al terminar:</b> se muestran el error medio, el máximo y el punto "
      "con mayor desviación. Son distancias normalizadas en pantalla, no porcentajes de aciertos. "
      "Usa <b>Reintentar todo</b> o vuelve al índice. Conserva el texto del diagnóstico si necesitas informar del fallo.")
    p("Puedes cancelar con <b>Esc</b>. La calibración es obligatoria por sesión ocular; después "
      "se conserva durante parpadeos y pérdidas breves. Si el cursor se siente extraño, usa "
      "<b>Más → Calibrar mirada</b> o Ajustes → Control. Mover la cámara puede requerir recalibrar.")
    story.append(PageBreak())
    p("Investigar una calibración fallida", title)
    p("Dev3: herramientas temporales de diagnóstico", heading)
    p("Las pruebas reales siguen sin aprobar la calibración. Esta revisión añade instrumentos "
      "para averiguar por qué: <b>no cambia el ajuste ni rebaja los límites de aprobación.</b> "
      "Una sesión completa exportada permite investigar; no necesitas repetir muchos intentos.")
    p("El mapa del resultado", heading)
    p("Los <b>círculos</b> indican dónde estaban los objetivos; las <b>cruces</b>, dónde calculó "
      "la mirada media. Las líneas muestran el desvío. La tabla separa el error de cada punto. "
      "Una media dibujada no sustituye la comprobación de todos los cuadros.")
    p("D · Detalle técnico", heading)
    p("Muestra capturas nuevas por segundo, edad de la muestra, tiempo del detector, tamaño de los ojos "
      "en píxeles, apertura, iris, postura y recogida por punto. Las cifras son medidas; pedir 60 FPS "
      "a la cámara no garantiza 60 estimaciones por segundo.")
    p("P · Probar sin controlar PC", heading)
    p("Después del ajuste puedes ver una cruz seguir la estimación dentro del asistente, incluso "
      "si la comprobación falló. <b>No mueve el ratón, no ejecuta clics y no aprueba la calibración.</b> "
      "P o Esc vuelve al resultado. No se recogen nuevas muestras mientras usas este visor.")
    p("E · Exportar diagnóstico", heading)
    p("Antes de reintentar, pulsa E o su botón. Guarda un JSON local con las mediciones numéricas "
      "del intento, no una grabación del visor. La ruta aparece en pantalla. Después de cerrar el "
      "asistente: <b>Ajustes → Diagnóstico → Abrir carpeta de diagnóstico</b>; entra a "
      "<b>diagnostics/gaze</b> y comparte el archivo mirada-fecha-identificador.json si deseas que se analice.")
    p("El archivo contiene características oculares, objetivos, tiempos relativos y configuración "
      "técnica. <b>No incluye fotos ni vídeo y no se envía automáticamente.</b> "
      "No se usa como perfil ni modifica tus ajustes. Los informes exportados permanecen hasta que los borres.")
    p("Durante los puntos se oculta la predicción para no influir en dónde miras. "
      "La zona habitual de cámara y los gestos de manos permanecen sin cambios.", small)
    story.append(PageBreak())
    p("Acciones y recuperación", title)
    p("Mano principal", heading)
    p("Pinza índice-pulgar: clic izquierdo; mantenerla permite arrastrar y abrirla libera el botón. "
      "En modo ojos, mira hacia el destino; en modo índice, desplaza el dedo como en la 2.7. "
      "Se conservan clic derecho, volumen, pausa, cambio de ventana y menú radial. "
      "Los dos antiguos gestos de scroll de la principal están retirados.")
    p("Scroll con L: tú eliges el punto de inicio", heading)
    p("1. Forma la L con la auxiliar y mantenla 0.45 segundos para fijar el inicio.<br/>"
      "2. Sube respecto a ese punto: scroll continuo hacia arriba, incluso con la mano quieta.<br/>"
      "3. Baja respecto a ese punto: scroll continuo hacia abajo.<br/>"
      "4. Regresa cerca del inicio para detenerlo sin deshacer la L.<br/>"
      "5. Abre la mano o deshaz la L para terminar. La próxima L fijará un inicio nuevo.")
    p("Alejarse más del inicio aumenta la velocidad, hasta un límite. La zona neutra y sensibilidad "
      "se ajustan en Precisión. Perder la mano detiene el scroll y exige confirmar otra L en el lugar actual.")
    p("Auxiliar: edición y Vista de tareas", heading)
    p("Las pinzas con el pulgar conservan: índice = copiar, corazón = pegar, anular = deshacer, "
      "meñique = rehacer. Mantén 0.45 segundos.<br/>"
      "<b>Vista de tareas (Windows + Tab):</b> extiende índice y corazón juntos, recoge pulgar, anular "
      "y meñique; mantén 0.65 segundos. Deshaz la pose antes de repetir. No es la V de victoria.")
    p("Parpadear, mirar el teclado o salir de cámara", heading)
    p("Al perder una mirada válida se congela el cursor y se bloquean acciones nuevas. Un arrastre ya "
      "activo dispone de 0.32 segundos para recuperar seguimiento: abrir la pinza lo libera antes. "
      "Si la pérdida continúa, se libera por seguridad. "
      "Al recuperar seguimiento estable puedes continuar sin recalibrar. Tras <b>70 segundos</b> "
      "sin mirada válida, entra en reposo y reduce el trabajo. Recupera una mirada válida y mantén "
      "el gesto normal de victoria para reanudar. No identifica al propietario: úsalo bajo tu responsabilidad.")
    p("Salida rápida: <b>Ctrl + Alt + F12</b>. Pausa y recupera la ventana. "
      "En modo índice no existe temporizador de ausencia de ojos.", small)
    story.append(PageBreak())
    p("Qué está probado y qué falta", title)
    p("Esta guía describe un prototipo, no una garantía de precisión ocular universal. "
      "MediaPipe entrega landmarks del rostro y del iris; el proyecto aprende una relación con "
      "la pantalla durante la calibración. Las pruebas sintéticas no sustituyen tu experiencia real.")
    p("En dev2 se corrigió un sobreajuste del aprendizaje sin rebajar el criterio de aprobación. "
      "Todavía falta confirmar una calibración real satisfactoria y probar su cursor. "
      "Los reflejos de lentes pueden seguir impidiendo una estimación válida.")
    p("Antes de utilizarlo en tareas importantes", heading)
    p("Prueba primero sobre una ventana sin información importante. Comprueba clics, arrastre, "
      "L, Vista de tareas, parpadeos y reposo. Usa el índice si la mirada no resulta cómoda. "
      "Ten a mano un ratón o teclado físico para pausar y corregir ajustes.")
    p("Pendientes para finalizar 3.0", heading)
    p("Precisión con objetivos pequeños; comodidad y fatiga; lentes y reflejos; cambios de postura "
      "y distancia; cámaras de distintas laptops; consumo y temperatura durante sesiones prolongadas. "
      "No se ha validado una computadora limpia ni se distribuye aquí un instalador 3.0 firmado. "
      "Linux y macOS se reservan para versiones posteriores.")
    p("Privacidad y presentación", heading)
    p("El procesamiento es local. No se guardan fotografías ni video, ni se suben muestras oculares. "
      "La calibración de esta primera implementación vive solo durante la sesión. La zona de cámara "
      "no muestra instrucciones: únicamente imagen, dibujos opcionales de manos y menú radial.")
    p("Base técnica", heading)
    p('<link href="https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python">'
      'Guía oficial de MediaPipe Face Landmarker</link><br/>'
      '<link href="https://research.google/blog/mediapipe-iris-real-time-iris-tracking-depth-estimation/">'
      'Google Research: alcance y límites de MediaPipe Iris</link>', small)
    story.append(Spacer(1, 22))
    story.append(Image(str(ROOT / "assets/brand/anchor-approved.png"), width=80, height=80))
    center = ParagraphStyle("GuideAuthor", parent=heading, alignment=1)
    p("Desarrollado por Luics415", center)
    SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=44, leftMargin=44, topMargin=44,
                      bottomMargin=58, title="Bio-Gesture 3.0 - Guía de pruebas", author="Luics415").build(
                          story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
