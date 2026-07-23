# Bio-Gesture Control Pro

Sistema de control de la computadora mediante gestos de la mano frente a una cámara web. El proyecto utiliza visión artificial para localizar los puntos principales de una mano y convertir distintas posiciones de los dedos en movimientos del mouse, clics, desplazamiento, control de volumen y atajos de teclado.

> Estado actual: el programa está diseñado para Windows y utiliza una cámara compatible con OpenCV. La interfaz y los comandos están en español.

## Índice

- [Descripción general](#descripción-general)
- [Características](#características)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tecnologías y dependencias](#tecnologías-y-dependencias)
- [Cómo funciona internamente](#cómo-funciona-internamente)
- [Controles mediante gestos](#controles-mediante-gestos)
- [Menú radial](#menú-radial)
- [Instalación desde cero](#instalación-desde-cero)
- [Ejecución](#ejecución)
- [Diagnóstico](#diagnóstico)
- [Solución de problemas](#solución-de-problemas)
- [Limitaciones y consideraciones](#limitaciones-y-consideraciones)
- [Flujo de uso recomendado](#flujo-de-uso-recomendado)

## Descripción general

Bio-Gesture Control Pro transforma una cámara web en una interfaz de control sin contacto. La aplicación muestra la imagen de la cámara en una ventana de Tkinter y analiza cada cuadro en tiempo real.

El procesamiento principal sigue este flujo:

1. OpenCV obtiene un cuadro de la cámara.
2. El cuadro se redimensiona a `550 x 375` píxeles y se refleja horizontalmente para que la imagen se comporte como un espejo.
3. MediaPipe Hands identifica una mano y sus 21 puntos de referencia, llamados landmarks.
4. El programa calcula distancias y posiciones relativas entre pulgar, índice, corazón, anular y meñique.
5. Las condiciones geométricas resultantes se interpretan como gestos.
6. `pynput` mueve el cursor, hace clics, desplaza la pantalla o envía teclas.
7. Tkinter actualiza la ventana y vuelve a procesar el siguiente cuadro.

El objetivo es permitir acciones comunes de navegación, edición, reproducción multimedia y control del sistema sin tocar directamente el mouse o el teclado.

## Características

- Control del cursor con el dedo índice.
- Suavizado del movimiento para evitar vibraciones.
- Clic izquierdo con pinza entre pulgar e índice.
- Arrastre manteniendo la pinza durante más tiempo.
- Clic derecho con pinza entre pulgar y dedo corazón.
- Desplazamiento vertical con una postura específica de los dedos.
- Control del volumen del sistema mediante el dedo anular.
- Menú radial activado manteniendo el pulgar levantado.
- Submenús de sistema, edición, web y multimedia.
- Atajos de teclado para controlar aplicaciones activas.
- Modo de reposo activado manteniendo el gesto de victoria durante tres segundos.
- Cambio entre ventana normal y ventana fija mediante un movimiento rápido de la mano.
- Dibujo visual de los landmarks y de los indicadores de estado sobre la imagen.

## Estructura del proyecto

```text
Bio-Gesture Control Pro/
|
|-- control.py          Programa principal de control por gestos.
|-- import sys.py       Diagnóstico de la versión e intérprete de Python.
|-- INICIAR_CONTROL.vbs Lanzador silencioso que intenta ejecutar un archivo BAT.
|-- .gitignore          Evita subir venv, cachés y archivos sensibles.
|-- README.md           Documentación del proyecto.
|-- venv/               Entorno virtual local; no debe subirse a GitHub.
```

### `control.py`

Es el archivo principal. Contiene la interfaz, la captura de cámara, el detector de manos, el menú radial, la detección de gestos y la ejecución de comandos.

### `import sys.py`

Es una herramienta de comprobación. Muestra:

- La versión de Python activa.
- La ruta exacta del ejecutable usado.
- Si MediaPipe puede importarse correctamente.

El nombre contiene espacios, por lo que debe ejecutarse entre comillas desde PowerShell.

### `INICIAR_CONTROL.vbs`

Este script intenta abrir de forma oculta el comando:

```text
ACTIVAR_CAMARA.bat
```

Ese archivo BAT no se encuentra en la estructura actual del proyecto. Por ello, la forma funcional y recomendada de iniciar la aplicación en el estado actual es ejecutar directamente `python control.py`. El VBS solo funcionará cuando exista un `ACTIVAR_CAMARA.bat` válido en la carpeta esperada.

### `venv/`

Es el entorno virtual local de Python. Contiene paquetes instalados y archivos binarios de gran tamaño, como OpenCV, MediaPipe y JAX. No es código fuente y no debe subirse al repositorio. Cada equipo debe crear su propio entorno virtual.

## Tecnologías y dependencias

El proyecto usa las siguientes tecnologías:

- **Python**: lenguaje principal.
- **OpenCV (`cv2`)**: captura, transformación y dibujo sobre imágenes de la cámara.
- **MediaPipe Hands**: detección de una mano y sus 21 landmarks.
- **NumPy**: cálculos de distancias, interpolación, ángulos y coordenadas.
- **Tkinter**: ventana gráfica y ciclo de actualización.
- **Pillow (`PIL`)**: conversión de cuadros de OpenCV para mostrarlos en Tkinter.
- **pynput**: control programático del mouse y el teclado.
- **pycaw**: lectura y modificación del volumen maestro de Windows.
- **comtypes**: acceso COM requerido por pycaw.
- **ctypes**: conversión de interfaces de audio de Windows.

Tkinter normalmente viene incluido con la instalación oficial de Python para Windows. Si no está disponible, debe instalarse una distribución de Python que incluya Tcl/Tk.

<img width="1543" height="538" alt="image" src="https://github.com/user-attachments/assets/ddab2102-0228-40f3-9045-3b7fb0e8da79" />


## Cómo funciona internamente

### Captura y presentación de video

La clase `AplicacionGestos` crea una ventana fija de `550 x 375` píxeles. OpenCV intenta abrir la cámara con `cv2.CAP_DSHOW` y solicita una captura de `1920 x 1080` a 60 FPS usando MJPG. Antes de mostrar cada cuadro, la imagen se reduce a la resolución de la ventana y se voltea horizontalmente.

La cámara debe estar conectada y disponible para que `VideoCapture(0)` pueda obtener imágenes. El índice `0` representa normalmente la cámara principal del equipo.

### Detección de la mano

MediaPipe se configura para detectar una sola mano con:

- Complejidad de modelo `1`.
- Confianza mínima de detección `0.7`.
- Confianza mínima de seguimiento `0.7`.

Los puntos usados con mayor frecuencia son:

- `4`: punta del pulgar.
- `8`: punta del índice.
- `12`: punta del dedo corazón.
- `16`: punta del anular.
- `20`: punta del meñique.

También se consultan los puntos intermedios de cada dedo para decidir si está doblado o extendido.

### Movimiento del mouse

La posición normalizada del índice se convierte al espacio de una pantalla de `1920 x 1080`. El rango útil de la cámara se limita aproximadamente entre `0.1` y `0.9` en los ejes horizontal y vertical.

El movimiento se suaviza con un factor de `5` para que pequeños cambios de los landmarks no produzcan un cursor inestable.

### Clic izquierdo y arrastre

El programa calcula la distancia entre pulgar e índice:

- Una pinza breve produce un clic izquierdo.
- Una pinza mantenida durante más de `0.3` segundos inicia un arrastre.
- Al separar los dedos se libera el botón izquierdo.

### Clic derecho

Cuando la distancia entre el pulgar y el dedo corazón es menor que el umbral definido, se produce un clic derecho. Existe una espera mínima de `0.6` segundos entre clics derechos para evitar repeticiones involuntarias.

### Desplazamiento

Cuando índice y corazón están muy juntos, el programa evalúa una postura de desplazamiento. Después de mantenerla durante `1.5` segundos:

- Dedos extendidos: desplaza hacia arriba.
- Dedos doblados: desplaza hacia abajo.

Mientras el modo de desplazamiento está activo, el índice deja de controlar la posición del cursor.

### Control de volumen

La aplicación intenta localizar el dispositivo de audio predeterminado de Windows al iniciar. Si pycaw no puede acceder al dispositivo, el resto del programa continúa, pero el gesto de volumen no estará disponible.

El gesto se activa al acercar el pulgar y el anular. Después se compara la posición vertical del anular con su posición inicial:

- Moverlo hacia arriba aumenta el volumen.
- Moverlo hacia abajo reduce el volumen.

El volumen se limita entre `0%` y `100%` y se dibuja una barra de nivel en la esquina inferior izquierda.

### Modo de reposo

El gesto de victoria, con índice y corazón extendidos y los otros dedos doblados, inicia una barra de progreso. Si se mantiene durante `3` segundos, cambia el estado de reposo.

En modo de reposo se muestra `MODO REPOSO` y se suspenden las acciones de control mientras se mantiene la aplicación abierta.

### Cambio de ventana

Un movimiento rápido de la mano detectado mediante cambios repetidos de posición horizontal activa o desactiva el modo de ventana fija. En ese modo la ventana:

- No muestra los bordes normales.
- Se mantiene encima de otras ventanas.
- Usa una transparencia aproximada de `85%`.

## Controles mediante gestos

| Gesto | Acción |
|---|---|
| Índice apuntando | Mover el cursor |
| Pulgar + índice, separación rápida | Clic izquierdo |
| Pulgar + índice, mantener más de 0.3 s | Arrastrar |
| Pulgar + corazón juntos | Clic derecho |
| Índice y corazón juntos, mantener postura | Activar desplazamiento |
| Desplazamiento con dedos extendidos | Desplazar hacia arriba |
| Desplazamiento con dedos doblados | Desplazar hacia abajo |
| Pulgar + anular | Activar control de volumen |
| Anular hacia arriba | Aumentar volumen |
| Anular hacia abajo | Disminuir volumen |
| Pulgar levantado durante 0.8 s | Abrir menú radial |
| Gesto de victoria durante 3 s | Activar o desactivar reposo |
| Movimiento rápido lateral repetido | Alternar ventana fija |

Los gestos dependen de la iluminación, la distancia a la cámara, el ángulo de la mano y la posición de los dedos. Los tiempos y distancias son umbrales internos del programa y no son configurables desde una interfaz.

## Menú radial

El menú radial aparece al mantener el pulgar levantado durante aproximadamente `0.8` segundos. Tiene ocho posiciones. Para seleccionar una opción:

1. Mantén el pulgar levantado para abrir el menú.
2. Dirige el pulgar hacia una de las ocho opciones.
3. Mantén la dirección durante aproximadamente `1.2` segundos.
4. La opción se ejecutará cuando termine el indicador circular.

Algunas opciones abren un submenú y otras envían directamente un comando al sistema.

### Menú principal

| Opción | Función |
|---|---|
| SISTEMA | Abrir controles del sistema |
| EDICION | Abrir controles de edición |
| WEB | Abrir controles del navegador |
| MEDIA | Abrir controles multimedia |
| MAYUS | Activar o desactivar Caps Lock |
| PESTANYA | Cambiar de ventana con Alt+Tab |
| INICIO | Presionar la tecla Windows |
| ESC | Presionar Escape |

### Sistema

| Opción | Comando o intención |
|---|---|
| CONFIG | Reservado para configuración |
| ADMIN | Reservado para administración |
| BLOQUEAR | Reservado para bloqueo |
| BUSCAR | Reservado para búsqueda |
| VOL+ | Reservado para subir volumen |
| VOL- | Reservado para bajar volumen |
| MUTE | Silenciar mediante la tecla `m` |
| VOLVER | Regresar al menú principal |

Las opciones marcadas como reservadas aparecen en el menú, pero no tienen una implementación específica en `ejecutar_comando_pro` en la versión actual.

### Edición

| Opción | Atajo |
|---|---|
| COPIAR | Ctrl+C |
| PEGAR | Ctrl+V |
| DESHACER | Ctrl+Z |
| REHACER | Ctrl+Y |
| CORTAR | Ctrl+X |
| TODO | Ctrl+A |
| DELETE | Delete |
| VOLVER | Regresar al menú principal |

### Web

| Opción | Atajo |
|---|---|
| NUEVA T | Ctrl+T |
| CERRAR T | Ctrl+W |
| RECARGAR | F5 |
| REGRESAR | Alt+Flecha izquierda |
| AVANCE | Alt+Flecha derecha |
| FAVORITOS | Ctrl+D |
| DESCARGA | Ctrl+J |
| VOLVER | Regresar al menú principal |

### Multimedia

| Opción | Atajo |
|---|---|
| PLAY/PAUSE | `k` |
| SIGUIENTE | Shift+N |
| ATRAS 10s | `j` |
| ADELAN 10s | `l` |
| MUTE | `m` |
| FULLSCREEN | `f` |
| SUBTITULOS | `c` |
| VOLVER | Regresar al menú principal |

Los comandos multimedia basados en letras funcionan especialmente bien en aplicaciones como reproductores web que interpretan esas teclas, pero su resultado depende de la ventana que esté activa.

## Instalación desde cero

Los siguientes pasos están pensados para un equipo Windows sin el entorno virtual de este proyecto.

### 1. Instalar Python

1. Descarga Python desde la página oficial:
   [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
2. Ejecuta el instalador.
3. En la primera pantalla activa la casilla **Add Python.exe to PATH**.
4. Selecciona **Install Now**.
5. Cierra y vuelve a abrir PowerShell o VS Code.
6. Comprueba la instalación:

```powershell
python --version
```

También puedes probar el lanzador de Windows:

```powershell
py --version
```

Se recomienda Python de 64 bits. Si `python` no se reconoce, usa `py` en los comandos siguientes o reinstala Python activando la opción para agregarlo al PATH.

### 2. Instalar Git y descargar el proyecto

Instala Git para Windows desde:

[https://git-scm.com/download/win](https://git-scm.com/download/win)

Después clona el repositorio:

```powershell
git clone https://github.com/Luics415/Bio-Gesture-Control-Pro.git
cd Bio-Gesture-Control-Pro
```

Si ya tienes la carpeta descargada, entra directamente en ella:

```powershell
cd "E:\Respaldo Luis\Bio-Gesture Control Pro"
```

### 3. Crear un entorno virtual nuevo

Dentro de la carpeta del proyecto ejecuta:

```powershell
python -m venv venv
```

Si usas el lanzador `py`:

```powershell
py -m venv venv
```

Esto crea una carpeta `venv` local. No la subas a GitHub.

### 4. Activar el entorno virtual

En PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Cuando se active correctamente, la terminal mostrará algo parecido a:

```text
(venv) PS C:\ruta\al\proyecto>
```

Si PowerShell bloquea la activación por la política de ejecución, abre PowerShell como usuario normal y ejecuta:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Confirma con `Y` y vuelve a activar:

```powershell
.\venv\Scripts\Activate.ps1
```

No es necesario ejecutar PowerShell como administrador para esta configuración de usuario.

### 5. Actualizar herramientas de instalación

Con `venv` activado:

```powershell
python -m pip install --upgrade pip setuptools wheel
```

### 6. Instalar las dependencias

Instala los paquetes usados por `control.py`:

```powershell
python -m pip install opencv-python numpy Pillow pynput mediapipe comtypes pycaw
```

La instalación puede tardar porque OpenCV y MediaPipe incluyen componentes binarios.

### 7. Comprobar el intérprete y MediaPipe

Ejecuta el diagnóstico incluido:

```powershell
python "import sys.py"
```

La salida esperada incluye una versión de Python, la ruta dentro de `venv` y un mensaje de que MediaPipe fue detectado correctamente.

Comprueba que los paquetes principales pueden importarse:

```powershell
python -c "import cv2, numpy, PIL, pynput, mediapipe, comtypes, pycaw; print('Dependencias correctas')"
```

### 8. Conectar y comprobar la cámara

Antes de iniciar:

- Conecta una cámara web.
- Cierra aplicaciones que puedan estar usando la cámara.
- Permite el acceso de Python a la cámara si Windows muestra un aviso.
- Coloca la mano frente a la cámara con iluminación suficiente.

### 9. Iniciar el programa

Con el entorno virtual activado, ejecuta:

```powershell
python control.py
```

Para detenerlo, cierra la ventana de la aplicación o interrumpe el proceso desde la terminal con `Ctrl+C`.

## Ejecución

Cada vez que abras una nueva terminal:

```powershell
cd "E:\Respaldo Luis\Bio-Gesture Control Pro"
.\venv\Scripts\Activate.ps1
python control.py
```

Si el proyecto está en otra ubicación, sustituye la ruta del primer comando.

Para salir del entorno virtual cuando termines:

```powershell
deactivate
```

## Diagnóstico

Si quieres verificar qué Python está usando VS Code o PowerShell:

```powershell
python "import sys.py"
```

También puedes consultar la ruta directamente:

```powershell
python -c "import sys; print(sys.executable)"
```

Debe apuntar a una ruta parecida a:

```text
...\Bio-Gesture Control Pro\venv\Scripts\python.exe
```

En VS Code, selecciona el intérprete con `Ctrl+Shift+P`, busca **Python: Select Interpreter** y elige el que esté dentro de `venv`.

## Solución de problemas

### `python` no se reconoce

Python no está en el PATH o la terminal se abrió antes de instalarlo. Cierra y abre PowerShell. Si sigue ocurriendo, prueba:

```powershell
py --version
```

Si `py` funciona, usa `py` para crear el entorno y después ejecuta el Python de `venv`.

### `No module named cv2`, `mediapipe` u otro paquete

Activa el entorno correcto y reinstala las dependencias:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install opencv-python numpy Pillow pynput mediapipe comtypes pycaw
```

### MediaPipe no se instala o no se puede importar

Comprueba la versión activa:

```powershell
python --version
```

Después actualiza pip e intenta de nuevo:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install mediapipe
```

La disponibilidad de MediaPipe puede variar según la versión de Python y la arquitectura de Windows. Se recomienda utilizar Python de 64 bits y una versión estable compatible con la versión actual de MediaPipe.

### La cámara no abre

El programa usa el índice `0`:

```python
cv2.VideoCapture(0, cv2.CAP_DSHOW)
```

Comprueba los permisos de cámara en **Configuración de Windows > Privacidad y seguridad > Cámara**. Cierra Zoom, Teams, OBS u otra aplicación que la esté usando. Si tienes varias cámaras, el índice podría necesitar cambiarse a `1` o `2`.

### La ventana aparece, pero la imagen está negra

Verifica que la cámara funcione en la aplicación Cámara de Windows. También prueba conectar la cámara antes de ejecutar el programa y reiniciar la aplicación.

### El volumen no cambia

El control depende de pycaw y del dispositivo de audio predeterminado de Windows. Si la inicialización de audio falla, el programa continúa sin control de volumen. Comprueba que haya un dispositivo de salida activo y que pycaw y comtypes estén instalados dentro de `venv`.

### Los gestos se activan solos

Mejora la iluminación, aleja o acerca la mano hasta que se vea completa y evita fondos con mucho movimiento. El sistema usa umbrales geométricos y puede confundirse cuando los dedos se ocultan entre sí.

### Los atajos se envían a la ventana equivocada

`pynput` envía las teclas a la ventana que tenga el foco de Windows. Antes de seleccionar un comando del menú radial, asegúrate de que la aplicación destino sea la ventana activa.

### `INICIAR_CONTROL.vbs` no inicia el programa

El VBS actual intenta ejecutar `ACTIVAR_CAMARA.bat`, pero ese archivo no está presente en el proyecto. Usa el método directo:

```powershell
.\venv\Scripts\Activate.ps1
python control.py
```

Si deseas automatizar el arranque, el archivo BAT debe crearse y configurarse para activar `venv` y ejecutar `control.py` desde la carpeta correcta.

## Limitaciones y consideraciones

- El sistema está orientado a Windows por el uso de `pycaw`, COM y teclas de Windows.
- Solo se procesa una mano a la vez.
- No existe una pantalla de configuración para cambiar umbrales, resolución o cámara.
- El código asume una pantalla de referencia de `1920 x 1080` para transformar la posición del índice.
- El control depende de una cámara con buena iluminación y una vista clara de la mano.
- Algunos comandos del menú están reservados y todavía no tienen una acción implementada.
- El control de teclas puede afectar cualquier aplicación que tenga el foco.
- No se debe ejecutar el proyecto con privilegios elevados salvo que una necesidad concreta del sistema lo requiera.
- `venv` no forma parte del código fuente y debe reconstruirse en cada equipo.

## Flujo de uso recomendado

1. Conecta la cámara.
2. Abre PowerShell en la carpeta del proyecto.
3. Activa `venv`.
4. Ejecuta el diagnóstico si es la primera instalación.
5. Inicia `control.py`.
6. Espera a que la cámara muestre la mano.
7. Prueba primero el movimiento del índice.
8. Prueba clic izquierdo y derecho.
9. Mantén el pulgar levantado para abrir el menú.
10. Selecciona las opciones manteniendo el pulgar en la dirección deseada.
11. Usa el gesto de victoria durante tres segundos para pausar el control.
12. Cierra la ventana al finalizar y ejecuta `deactivate`.

## Licencia

No se ha definido una licencia en el repositorio. Si el proyecto se distribuirá públicamente, añade un archivo de licencia y especifica las condiciones de uso, modificación y distribución.
