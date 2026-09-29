"""Local legal-information window for the desktop application.

The application has no web view, account system, analytics SDK or cookie jar.
Keeping the notices in code makes the same information available offline in a
portable build.  The Markdown copies under ``docs/legal`` are the public,
reviewable versions.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


EFFECTIVE_DATE = "28 de septiembre de 2026"

LEGAL_SECTIONS = {
    "Privacidad": f"""AVISO DE PRIVACIDAD · Bio-Gesture Control Pro
Vigente desde: {EFFECTIVE_DATE}

Responsable y alcance
Bio-Gesture Control Pro es un proyecto de Luics415. Este aviso describe la
aplicación de escritorio y su portable. No sustituye asesoría jurídica. El
repositorio y GitHub son servicios separados y tienen sus propios avisos.

Qué procesa
La cámara se procesa localmente para detectar manos, rostro e iris. Los
fotogramas se mantienen en memoria para la inferencia y no se envían ni se
guardan como fotografías o vídeo. La aplicación no identifica al propietario.

Qué puede guardarse
• Ajustes locales (modo, monitor y preferencias) en la carpeta de datos de la
  aplicación.
• Solo si el usuario pulsa Exportar diagnóstico: un JSON numérico de la prueba
  ocular (geometría, tiempos, errores y configuración), sin imágenes ni vídeo.
El usuario puede borrar esa carpeta desde el explorador. No se crean cuentas ni
perfiles publicitarios.

Red, analítica y terceros
El uso normal no hace solicitudes de red, no contiene analítica, publicidad,
SDK de seguimiento ni cookies. El script opcional de preparación de modelos
descarga archivos de Open Model Zoo desde los dominios documentados; no forma
parte del arranque. Las librerías de MediaPipe, OpenCV, OpenVINO, pynput,
pystray y otras se ejecutan para la función indicada y conservan sus propios
avisos de licencia en THIRD_PARTY_NOTICES.md.

Base y control
La cámara y los datos de mirada pueden ser datos personales o sensibles si se
relacionan con una persona. El tratamiento local se limita a la función que el
usuario activa. El usuario decide cuándo mostrar la cámara, exportar un
diagnóstico, calibrar o borrar datos. Para una solicitud de acceso,
rectificación, cancelación u oposición, usa un canal privado que el responsable
publique junto con la versión; no compartas datos personales en issues públicos.
Referencia pública: github.com/Luics415/Bio-Gesture-Control-Pro.

Si en el futuro se añade una cuenta, nube, analítica o envío de imágenes, este
aviso y el consentimiento se revisarán antes de activarlo.
""",
    "Términos": f"""TÉRMINOS Y CONDICIONES · Bio-Gesture Control Pro
Vigentes desde: {EFFECTIVE_DATE}

1. Licencia y alcance
El código propio se distribuye bajo MIT; las dependencias, modelos y avisos
de terceros conservan sus licencias. La versión que se entrega puede ser de
desarrollo y debe consultarse junto a su manifiesto de compilación.

2. Uso responsable
La herramienta envía entradas al sistema a partir de gestos y mirada. Es un
instrumento experimental de accesibilidad y productividad, no un dispositivo
médico, de seguridad, autenticación, vigilancia o control de maquinaria. No la
uses para acciones críticas, conducción, emergencias o decisiones sobre otras
personas. Detén o pausa el programa si el cursor o una acción no es la esperada.

3. Sin garantía de precisión
La cámara, iluminación, lentes, postura, distancia y pantalla cambian el
resultado. La calibración y los diagnósticos no garantizan precisión en cada
equipo ni compatibilidad con todas las aplicaciones. El usuario conserva la
responsabilidad de revisar el resultado antes de hacer clic, arrastrar o
ejecutar un comando.

4. Cambios y contenido
Luics415 puede corregir, retirar o actualizar funciones, avisos y modelos. No
se incorporan reseñas, testimonios o resultados que no tengan evidencia. Las
imágenes de identidad del ancla y la firma se usan con autorización del autor;
los modelos y librerías tienen la procedencia indicada en el repositorio.

5. Responsabilidad
En la medida permitida por la ley aplicable, el software se entrega “tal cual”
y el usuario asume copias de seguridad, permisos de cámara, riesgos del sistema
y comprobación de cada acción. Nada aquí limita derechos irrenunciables del
consumidor ni las obligaciones que la ley no permita excluir.

Contacto y versión pública: github.com/Luics415/Bio-Gesture-Control-Pro.
""",
    "Cookies": f"""POLÍTICA DE COOKIES · Bio-Gesture Control Pro
Vigente desde: {EFFECTIVE_DATE}

La aplicación de escritorio no es un sitio web: no crea, lee ni almacena
cookies, identificadores publicitarios, píxeles ni tecnologías equivalentes.
Por ese motivo no muestra un banner de consentimiento para el funcionamiento
local actual.

El repositorio en GitHub y cualquier página que GitHub aloje son servicios
independientes. GitHub puede usar cookies técnicas y otras tecnologías según
su propia política y configuración. Si el proyecto incorpora una web propia,
analítica, publicidad o cookies no esenciales, se documentarán por separado y
se solicitará consentimiento previo cuando la ley aplicable lo exija, con una
opción real de rechazar y cambiar la elección.

No desactives las cookies técnicas de GitHub si impiden iniciar sesión o
proteger el repositorio. Para revisar o borrar datos del navegador, utiliza
los controles del navegador y la política del proveedor correspondiente.
""",
}


def open_legal_window(parent):
    """Open one keyboard-navigable, offline legal notice window."""
    existing = getattr(parent, "_legal_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return existing

    window = tk.Toplevel(parent)
    parent._legal_window = window
    window.title("Privacidad, términos y cookies · Bio-Gesture")
    window.geometry("700x540")
    window.minsize(500, 360)
    window.configure(background="#11171d")
    window.transient(parent)

    style = ttk.Style(window)
    try:
        style.configure("Legal.TNotebook", background="#11171d")
        style.configure("Legal.TFrame", background="#11171d")
    except tk.TclError:
        pass

    heading = tk.Label(window, text="⚓ Privacidad y condiciones de uso", bg="#11171d",
                       fg="#79d8dc", font=("Segoe UI", -14, "bold"), anchor="w")
    heading.pack(fill="x", padx=16, pady=(14, 4))
    hint = tk.Label(window, text="Información disponible sin conexión. Usa Tab para recorrer controles y Esc para cerrar.",
                    bg="#11171d", fg="#eef2f5", font=("Segoe UI", -10), anchor="w")
    hint.pack(fill="x", padx=16, pady=(0, 10))

    notebook = ttk.Notebook(window, style="Legal.TNotebook")
    notebook.pack(fill="both", expand=True, padx=16, pady=(0, 10))
    for title, content in LEGAL_SECTIONS.items():
        frame = ttk.Frame(notebook, style="Legal.TFrame", padding=8)
        notebook.add(frame, text=title)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(frame, wrap="word", background="#1a232c", foreground="#eef2f5",
                       insertbackground="#eef2f5", selectbackground="#2e6970",
                       relief="flat", borderwidth=0, padx=12, pady=10,
                       font=("Segoe UI", -10), takefocus=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        text.insert("1.0", content)
        text.configure(state="disabled")

    buttons = ttk.Frame(window, style="Legal.TFrame")
    buttons.pack(fill="x", padx=16, pady=(0, 14))
    close = ttk.Button(buttons, text="Cerrar", command=window.destroy, takefocus=True)
    close.pack(side="right")
    window.bind("<Escape>", lambda event: window.destroy())

    def clear_reference(event=None):
        if getattr(parent, "_legal_window", None) is window:
            parent._legal_window = None

    window.protocol("WM_DELETE_WINDOW", lambda: (clear_reference(), window.destroy()))
    window.bind("<Destroy>", clear_reference, add="+")
    window.after_idle(close.focus_set)
    return window

