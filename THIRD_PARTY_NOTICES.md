# Dependencias y avisos de terceros

El código propio del proyecto utiliza la licencia [MIT](LICENSE). Las dependencias y el modelo conservan sus licencias y titulares. Este archivo es un índice de procedencia. El generador portable de 2.0 recopila los textos de licencia y avisos disponibles en las distribuciones instaladas y los incluye en `_internal/licenses`, con versiones y rutas en `DEPENDENCIES.json`, además de la licencia del intérprete. El inventario debe revisarse antes de una publicación final y no equivale a una certificación legal.

| Componente directo | Licencia declarada por su proyecto | Referencia |
| --- | --- | --- |
| MediaPipe | Apache-2.0 | [Repositorio oficial](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE) |
| Modelo Hand Landmarker | Consultar registro y procedencia del modelo | [Modelo incluido](assets/models/README.md) |
| NumPy | BSD-3-Clause, con avisos adicionales para bibliotecas incluidas | [Licencias oficiales](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| OpenCV / opencv-contrib-python | Apache-2.0 para OpenCV; licencia MIT del empaquetado y avisos de binarios incluidos | [Empaquetado oficial y licencias](https://github.com/opencv/opencv-python#licensing) |
| Pillow | HPND (licencia de PIL/Pillow), con avisos de bibliotecas incluidas | [Licencia oficial](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| pynput | LGPL-3.0 | [Licencia oficial](https://github.com/moses-palmer/pynput/blob/master/COPYING.LGPL) |
| pycaw | MIT | [Licencia oficial](https://github.com/AndreMiras/pycaw/blob/develop/LICENSE) |
| comtypes | MIT | [Licencia oficial](https://github.com/enthought/comtypes/blob/main/LICENSE.txt) |
| pystray | LGPL-3.0 | [Licencia oficial](https://github.com/moses-palmer/pystray/blob/master/COPYING.LGPL) |
| psutil | BSD-3-Clause | [Licencia oficial](https://github.com/giampaolo/psutil/blob/master/LICENSE) |

Python y Tk/Tcl, las dependencias transitivas de los archivos `requirements*.lock.txt` y las bibliotecas nativas de sus ruedas también aportan sus propios avisos. Los directorios `*.dist-info` del entorno instalado contienen metadatos y licencias que deben inventariarse al preparar un ejecutable. No se distribuye el antiguo `venv`.

Las herramientas de desarrollo (pytest, Ruff y pip-tools) se mantienen en el bloqueo separado de desarrollo. PyInstaller y sus herramientas usan `requirements-build.lock.txt`, respetando las versiones del bloqueo de ejecución. El portable local no se presenta como instalador firmado ni como publicación final; su inventario y comprobaciones figuran en el manifiesto de compilación.
