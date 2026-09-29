# Modelo de seguimiento

Archivo: `hand_landmarker.task`, modelo Hand Landmarker float16 versión 1 de Google MediaPipe.

- Fuente: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- Guía: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python
- Modelo incluido localmente; la aplicación no descarga modelos durante el arranque.
- Avisos de dependencias y modelos: ver `THIRD_PARTY_NOTICES.md`.

## Modelo ocular experimental 3.0

Archivo: `face_landmarker.task`, Face Landmarker float16 versión 1 de Google MediaPipe.

- Fuente fija: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
- SHA-256: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- Guía: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python
- Se incluye localmente; no se descarga ni se carga al seleccionar cursor con índice.
- Salidas opcionales de expresiones y matrices faciales desactivadas. El modelo conserva sus cálculos internos necesarios.
- Los 478 landmarks NO son coordenadas de mirada en pantalla. La 3.0 añade una estimación calibrada experimental, con validación independiente y rechazo de muestras inválidas.
- No se usa para identificar personas. No hay imágenes ni perfiles biométricos persistentes.

## Modelos de precisión ocular OpenVINO

En `gaze-precision/`: XML y BIN FP32 de `gaze-estimation-adas-0002` y `head-pose-estimation-adas-0001` (cuatro archivos, unos 15.3 MB en total).

- Manifiestos oficiales fijados en Open Model Zoo, revisión `6697dead54ed1cdd664b0313189c2cb52ee6335e`: [mirada](https://github.com/openvinotoolkit/open_model_zoo/blob/6697dead54ed1cdd664b0313189c2cb52ee6335e/models/intel/gaze-estimation-adas-0002/model.yml) y [postura](https://github.com/openvinotoolkit/open_model_zoo/blob/6697dead54ed1cdd664b0313189c2cb52ee6335e/models/intel/head-pose-estimation-adas-0001/model.yml).
- Binarios oficiales de la colección `open_model_zoo/2023.0/models_bin/1` en `storage.openvinotoolkit.org`.
- Licencia declarada en ambos manifiestos: Apache-2.0; texto conservado en [OPENVINO-LICENSE.txt](OPENVINO-LICENSE.txt). Los modelos se incluyen sin modificar; el recorte y la calibración son adaptaciones del programa.
- Los tamaños y SHA-384 oficiales están fijados en `biogesture/gaze_neural.py`. Se comprueban antes de cualquier importación del motor o lectura de modelos.
- Preparación explícita: `scripts/prepare_gaze_models.py`; `--verify-only` no usa red. La aplicación nunca descarga los modelos al abrirse.
- Solo se cargan al elegir el motor ocular personal, no con el cursor de índice ni el motor ocular anterior.
- [Preparación y alcance](../../docs/PRECISION_OCULAR.md). No son un sistema de identificación ni garantizan por sí solos precisión de cursor.
