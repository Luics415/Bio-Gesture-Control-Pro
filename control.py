import cv2
import time
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from pynput.mouse import Button, Controller
from pynput.keyboard import Key, Controller as KeyboardController
from mediapipe.python.solutions import hands as mp_hands
from mediapipe.python.solutions import drawing_utils as mp_draw
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

W_FIJO, H_FIJO = 550, 375
RADIO_MENU_ICONOS = 100       
RADIO_FONDO_NEGRO = 130       
ESCALA_TEXTO_MENU = 0.52 

try:
    device_enumerator = AudioUtilities.GetDeviceEnumerator()
    speakers = device_enumerator.GetDefaultAudioEndpoint(0, 1)
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume_control = cast(interface, POINTER(IAudioEndpointVolume))
except:
    volume_control = None

mouse = Controller()
keyboard = KeyboardController()

hand_detector = mp_hands.Hands(
    max_num_hands=1, 
    model_complexity=1, 
    min_detection_confidence=0.7, 
    min_tracking_confidence=0.7
)

menu_completo = {
    "PRINCIPAL": ["SISTEMA", "EDICION", "WEB", "MEDIA", "MAYUS", "PESTANYA", "INICIO", "ESC"],
    "SISTEMA": ["CONFIG", "ADMIN", "BLOQUEAR", "BUSCAR", "VOL+", "VOL-", "MUTE", "VOLVER"],
    "EDICION": ["COPIAR", "PEGAR", "DESHACER", "REHACER", "CORTAR", "TODO", "DELETE", "VOLVER"],
    "WEB": ["NUEVA T", "CERRAR T", "RECARGAR", "REGRESAR", "AVANCE", "FAVORITOS", "DESCARGA", "VOLVER"],
    "MEDIA": ["PLAY/PAUSE", "SIGUIENTE", "ATRAS 10s", "ADELAN 10s", "MUTE", "FULLSCREEN", "SUBTITULOS", "VOLVER"]
}

class AplicacionGestos:
    def __init__(self, root):
        self.root = root
        self.root.title("Bio-Gesture Control Pro Luics415 v1.20.36")
        self.modo_fijo = False 
        self.root.geometry(f"{W_FIJO}x{H_FIJO}")
        self.root.resizable(False, False)
        
        self.label_video = tk.Label(root)
        self.label_video.pack(fill="both", expand=True)
        
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        self.SUAVIZADO = 5
        self.prev_x, self.prev_y = 0, 0
        self.ultimo_clic = 0
        self.arrastrando = False
        self.inicio_pinza = 0
        
        self.estado_pausado = False
        self.inicio_gesto_pausa = 0
        
        self.nivel_actual = "PRINCIPAL"
        self.opciones_actuales = menu_completo["PRINCIPAL"]
        self.centro_menu = None
        self.inicio_pulgar = 0
        self.inicio_seleccion = 0
        self.opcion_actual = -1

        self.inicio_scroll_timer = 0
        self.modo_scroll_activo = False 

        self.gesto_volumen_activo = False
        self.y_ancla_volumen = 0        
        self.ultimo_update_vol = 0      
        self.PASO_VOLUMEN = 0.02

        self.cont_agitado = 0
        self.dir_anterior = 0 
        self.t_ultima_direccion = 0

        self.actualizar_frame()

    def toggle_modo_ventana(self):
        self.modo_fijo = not self.modo_fijo
        self.root.overrideredirect(self.modo_fijo)
        self.root.attributes('-topmost', self.modo_fijo)
        self.root.attributes('-alpha', 0.85 if self.modo_fijo else 1.0)

    def ejecutar_comando_pro(self, opcion):
        if opcion in menu_completo and opcion != "PRINCIPAL":
            self.nivel_actual = opcion
            self.opciones_actuales = menu_completo[opcion]
            return True 
        if opcion == "VOLVER":
            self.nivel_actual = "PRINCIPAL"
            self.opciones_actuales = menu_completo["PRINCIPAL"]
            return True

        comandos_simples = {
            "PLAY/PAUSE": 'k', "ATRAS 10s": 'j', "ADELAN 10s": 'l', "FULLSCREEN": 'f',
            "SUBTITULOS": 'c', "MUTE": 'm', "MAYUS": Key.caps_lock, 
            "DELETE": Key.delete, 
            "INICIO": Key.cmd, "ESC": Key.esc
        }
        
        if opcion in comandos_simples:
            keyboard.press(comandos_simples[opcion]); keyboard.release(comandos_simples[opcion])
            return False

        if opcion == "NUEVA T": 
            with keyboard.pressed(Key.ctrl): keyboard.press('t'); keyboard.release('t')
        elif opcion == "CERRAR T": 
            with keyboard.pressed(Key.ctrl): keyboard.press('w'); keyboard.release('w')
        elif opcion == "RECARGAR": 
            keyboard.press(Key.f5); keyboard.release(Key.f5)
        elif opcion == "REGRESAR": 
            with keyboard.pressed(Key.alt): keyboard.press(Key.left); keyboard.release(Key.left)
        elif opcion == "AVANCE": 
            with keyboard.pressed(Key.alt): keyboard.press(Key.right); keyboard.release(Key.right)
        elif opcion == "FAVORITOS": 
            with keyboard.pressed(Key.ctrl): keyboard.press('d'); keyboard.release('d')
        elif opcion == "DESCARGA": 
            with keyboard.pressed(Key.ctrl): keyboard.press('j'); keyboard.release('j')
            
        elif opcion == "PESTANYA": 
            with keyboard.pressed(Key.alt): keyboard.press(Key.tab); keyboard.release(Key.tab)
        elif opcion == "COPIAR":
            with keyboard.pressed(Key.ctrl): keyboard.press('c'); keyboard.release('c')
        elif opcion == "PEGAR":
            with keyboard.pressed(Key.ctrl): keyboard.press('v'); keyboard.release('v')
        elif opcion == "DESHACER":
            with keyboard.pressed(Key.ctrl): keyboard.press('z'); keyboard.release('z')
        elif opcion == "TODO": 
            with keyboard.pressed(Key.ctrl): keyboard.press('a'); keyboard.release('a')
        elif opcion == "SIGUIENTE":
            with keyboard.pressed(Key.shift): keyboard.press('n'); keyboard.release('n')
        elif opcion == "CORTAR":
            with keyboard.pressed(Key.ctrl): keyboard.press('x'); keyboard.release('x')
        elif opcion == "REHACER":
            with keyboard.pressed(Key.ctrl): keyboard.press('y'); keyboard.release('y')
            
        return False

    def actualizar_frame(self):
        ret, frame_raw = self.cap.read()
        if ret:
            frame = cv2.flip(cv2.resize(frame_raw, (W_FIJO, H_FIJO)), 1)
            h, w, _ = frame.shape
            t_actual = time.time()
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hand_detector.process(rgb)

            if results.multi_hand_landmarks:
                for landmarks in results.multi_hand_landmarks:
                    p = landmarks.landmark
                    pulgar, indice, corazon, anular, menique = p[4], p[8], p[12], p[16], p[20]
                    
                    dist_izq = ((indice.x - pulgar.x)**2 + (indice.y - pulgar.y)**2)**0.5
                    dist_dedos_juntos = ((indice.x - corazon.x)**2 + (indice.y - corazon.y)**2)**0.5
                    
                    es_pulgar_arriba = (pulgar.y < p[2].y - 0.1)
                    
                    dedos_doblados = (indice.y > p[6].y and corazon.y > p[10].y)
                    dedos_estirados = (indice.y < p[6].y and corazon.y < p[10].y)

                    v_victoria = (dedos_estirados and anular.y > p[14].y and menique.y > p[18].y)
                    if v_victoria and dist_dedos_juntos > 0.07 and dist_izq > 0.15:
                        if self.inicio_gesto_pausa == 0: self.inicio_gesto_pausa = t_actual
                        progreso = t_actual - self.inicio_gesto_pausa
                        
                        ancho_barra = 200
                        x_ini = (w // 2) - (ancho_barra // 2)
                        y_ini = 10
                        
                        cv2.rectangle(frame, (x_ini, y_ini), (x_ini + ancho_barra, y_ini + 6), (50, 50, 50), -1)
                        fill_w = int(min(progreso/3.0, 1) * ancho_barra)
                        cv2.rectangle(frame, (x_ini, y_ini), (x_ini + fill_w, y_ini + 6), (0, 0, 255), -1)
                        
                        if progreso >= 3.0:
                            self.estado_pausado = not self.estado_pausado
                            self.inicio_gesto_pausa = 0
                            time.sleep(0.5)
                    else:
                        self.inicio_gesto_pausa = 0

                    if self.estado_pausado:
                        cv2.putText(frame, "MODO REPOSO", (w//2-100, h//2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        continue 

                    if indice.y < p[6].y and menique.y < p[18].y:
                        curr_x = indice.x
                        if abs(curr_x - self.dir_anterior) > 0.15:
                            self.cont_agitado += 1
                            self.dir_anterior = curr_x
                            self.t_ultima_direccion = t_actual
                        if self.cont_agitado >= 4:
                            self.toggle_modo_ventana()
                            self.cont_agitado = 0
                    if t_actual - self.t_ultima_direccion > 0.4: self.cont_agitado = 0
                    
                    if es_pulgar_arriba and dedos_doblados:
                        self.inicio_scroll_timer = 0
                        self.modo_scroll_activo = False
                        
                        if self.inicio_pulgar == 0: self.inicio_pulgar = t_actual
                        if t_actual - self.inicio_pulgar >= 0.8:
                            if self.centro_menu is None: self.centro_menu = (int(pulgar.x*w), int(pulgar.y*h))
                            cx, cy = self.centro_menu
                            overlay = frame.copy()
                            cv2.circle(overlay, (cx, cy), RADIO_FONDO_NEGRO, (20, 20, 20), -1)
                            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                            
                            ang_p = np.arctan2(int(pulgar.y*h)-cy, int(pulgar.x*w)-cx)
                            if ang_p < 0: ang_p += 2*np.pi
                            dist_p = np.hypot(int(pulgar.x*w)-cx, int(pulgar.y*h)-cy)

                            for i in range(8):
                                rad = np.deg2rad(i * 45)
                                tx, ty = int(cx + RADIO_MENU_ICONOS*np.cos(rad)), int(cy + RADIO_MENU_ICONOS*np.sin(rad))
                                label = self.opciones_actuales[i]
                                col = (255, 255, 255)
                                if dist_p > 40 and np.deg2rad(i*45-22.5) < ang_p < np.deg2rad(i*45+22.5):
                                    if self.opcion_actual != i: self.opcion_actual = i; self.inicio_seleccion = t_actual
                                    col = (0, 255, 0)
                                    prog = t_actual - self.inicio_seleccion
                                    cv2.ellipse(frame, (cx, cy), (RADIO_MENU_ICONOS+15, RADIO_MENU_ICONOS+15), 0, i*45-22, i*45-22 + int(min(prog/1.2, 1)*44), (0, 255, 0), 4)
                                    if prog >= 1.2:
                                        self.ejecutar_comando_pro(label)
                                        self.inicio_seleccion = t_actual + 1
                                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                                cv2.putText(frame, label, (tx-tw//2, ty+th//2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
                        continue 

                    else:
                        self.inicio_pulgar, self.centro_menu = 0, None

                    pose_scroll_potencial = (dist_dedos_juntos < 0.03) and (not es_pulgar_arriba)
                    
                    if pose_scroll_potencial:
                        scroll_arriba = dedos_estirados
                        scroll_abajo = dedos_doblados 
                        
                        if scroll_arriba or scroll_abajo:
                            if self.inicio_scroll_timer == 0: 
                                self.inicio_scroll_timer = t_actual
                            
                            tiempo_hold = t_actual - self.inicio_scroll_timer
                            cx_f, cy_f = int(indice.x*w), int(indice.y*h)
                            
                            if tiempo_hold >= 1.5:
                                self.modo_scroll_activo = True
                                vel = 0.5
                                if scroll_arriba: mouse.scroll(0, vel)
                                if scroll_abajo: mouse.scroll(0, -vel)
                        else:
                            self.inicio_scroll_timer = 0
                            self.modo_scroll_activo = False
                    else:
                        self.inicio_scroll_timer = 0
                        self.modo_scroll_activo = False

                    if not self.modo_scroll_activo:
                        mx = np.interp(indice.x, [0.1, 0.9], [0, 1920])
                        my = np.interp(indice.y, [0.1, 0.9], [0, 1080])
                        self.prev_x += (mx - self.prev_x) / self.SUAVIZADO
                        self.prev_y += (my - self.prev_y) / self.SUAVIZADO
                        mouse.position = (self.prev_x, self.prev_y)

                        if dist_izq < 0.035:
                            if self.inicio_pinza == 0: self.inicio_pinza = t_actual
                            if (t_actual - self.inicio_pinza) > 0.3 and not self.arrastrando:
                                mouse.press(Button.left); self.arrastrando = True
                        else:
                            if self.arrastrando: mouse.release(Button.left); self.arrastrando = False
                            if 0 < (t_actual - self.inicio_pinza) < 0.3: mouse.click(Button.left, 1)
                            self.inicio_pinza = 0

                        if ((corazon.x - pulgar.x)**2 + (corazon.y - pulgar.y)**2)**0.5 < 0.035:
                            if t_actual - self.ultimo_clic > 0.6:
                                mouse.click(Button.right, 1); self.ultimo_clic = t_actual

                    if ((anular.x - pulgar.x)**2 + (anular.y - pulgar.y)**2)**0.5 < 0.04 and volume_control and not self.modo_scroll_activo:
                        vol = volume_control.GetMasterVolumeLevelScalar()
                        if not self.gesto_volumen_activo:
                            self.gesto_volumen_activo, self.y_ancla_volumen = True, anular.y
                        else:
                            if t_actual - self.ultimo_update_vol > 0.05:
                                diff = self.y_ancla_volumen - anular.y
                                if abs(diff) > 0.02:
                                    nv = max(0.0, min(1.0, vol + (self.PASO_VOLUMEN if diff > 0 else -self.PASO_VOLUMEN)))
                                    volume_control.SetMasterVolumeLevelScalar(nv, None)
                                    self.ultimo_update_vol = t_actual
                        
                        pad_x = 10
                        pad_y = h - 20
                        ancho_vol = 120
                        alto_barra = 8
                        
                        cv2.rectangle(frame, (pad_x, pad_y), (pad_x + ancho_vol, pad_y + alto_barra), (50, 50, 50), -1)
                        cv2.rectangle(frame, (pad_x, pad_y), (pad_x + int(vol*ancho_vol), pad_y + alto_barra), (0, 255, 255), -1)
                        cv2.putText(frame, f"{int(vol*100)}%", (pad_x + ancho_vol + 10, pad_y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                    else: self.gesto_volumen_activo = False

                    mp_draw.draw_landmarks(frame, landmarks, mp_hands.HAND_CONNECTIONS)

            img = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            self.label_video.imgtk = img
            self.label_video.configure(image=img)
        
        self.root.after(1, self.actualizar_frame)

if __name__ == "__main__":
    root = tk.Tk(); app = AplicacionGestos(root); root.mainloop()