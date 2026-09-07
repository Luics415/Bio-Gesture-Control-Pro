# Desarrollo de 2.0

El usuario del portable no necesita estos pasos. Son para modificar el código en Windows x64 con Python 3.12 x64 y Tcl/Tk.

1. Ejecuta `PREPARAR_DESARROLLO.bat`: verifica el modelo local y prepara `.venv` con dependencias fijadas y hashes.
2. Abre `INICIAR_CONTROL.vbs` para arrancar sin consola. El antiguo `venv` no se utiliza.
3. Para una ventana de prueba sin cámara, atajos globales ni entradas reales: `wscript.exe INICIAR_CONTROL.vbs --smoke`.

Desde la raíz del proyecto, para revisar código y dependencias:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
```

Las pruebas adicionales del modelo se habilitan con `BIOGESTURE_TEST_MEDIAPIPE=1`; las de geometría Tk, con `BIOGESTURE_TEST_GUI=1`. No activan una cámara ni generan entradas reales. Necesitan una sesión gráfica para Tk.

```powershell
.\.venv\Scripts\python.exe control.py --smoke --clean-ui --smoke-seconds 3
.\.venv\Scripts\python.exe scripts\benchmark.py --detector --detector-iterations 100
```

La medición de cuadros negros sintéticos comprueba inferencia, no precisión con manos reales. En pruebas, usa `BIOGESTURE_DATA_DIR` para aislar datos. `--console` conserva la consola solo cuando se solicita expresamente.

La versión 1.20.36 permanece en `legacy/v1.20.36`. No se altera el README original; el documento de la distribución nueva es `README-2.0.md`.

Consulta [Distribución](DISTRIBUTION.md) para generar el paquete portable y comprobarlo.
