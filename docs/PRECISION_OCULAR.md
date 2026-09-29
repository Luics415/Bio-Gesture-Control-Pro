# Motor ocular personal · revisión de precisión v2

Prototipo de Bio-Gesture 3.0.0.dev4. Identificador: `precision-openvino-v2`.
No modifica los gestos, roles ni acciones de las manos. Se prepara como portable de pruebas, no como instalador firmado ni publicación estable.

## Uso en esta carpeta

1. Cierra la instancia anterior y abre `INICIAR_CONTROL.vbs`.
2. En **Ajustes → Control**, selecciona **Ojos (experimental)**, modo óptimo y **Motor ocular → Precisión v2 · OpenVINO**. Guarda. Una elección anterior se conserva hasta que la cambies.
3. Abre **Calibrar mirada…**. Sigue los 21 objetivos de aprendizaje y los 13 nuevos de comprobación; los dibujos de ojos no son objetivos. Los puntos adicionales comprueban también zonas cercanas a las esquinas.
4. Si no aprueba, conserva el intento con **E**. **D** muestra el detalle y **P** permite ver la estimación sin controlar la PC. No hace falta repetir a ciegas: comparte el JSON y el mapa del error para investigar.

El entorno `.venv` de esta carpeta y los cuatro archivos de modelo ya están preparados. **Personal · OpenVINO** conserva v1 (13 + 9), y **Anterior · comparación** el motor geométrico (9 + 5); cada motor requiere su propia calibración. La opción de cursor con índice sigue disponible y no carga OpenVINO ni seguimiento facial. El portable dev4 se usa extrayendo su ZIP completo y abriendo `BioGestureControlPro.exe`; debe conservarse `_internal` junto a él.

## Qué cambió

MediaPipe sigue localizando el rostro y la geometría ocular. A partir de la misma imagen, sin duplicar la cámara, se recortan ambos ojos y la cara. Dos redes de Open Model Zoo estiman postura y dirección de mirada. Un ajuste personal aprende la relación con la pantalla, comparando una familia neuronal y otra que también utiliza la geometría del iris.

La selección compara modelos lineales y de núcleo radial, con distintos niveles de regularización. Usa validación cruzada por **objetivo de entrenamiento**, no divide aleatoriamente cuadros correlacionados. Cada objetivo pesa lo mismo; la normalización de cada partición se aprende solo con sus datos de entrenamiento. Los trece objetivos finales son independientes y no reajustan el modelo.

V2 conserva esta familia de ajuste: las comparaciones numéricas retrospectivas no justificaron sustituirla. Añade ocho puntos al perímetro 4–96 %, conservando los trece centrales/intermedios. La comprobación incorpora cuatro esquinas al 7–93 %, separadas de todos los objetivos entrenados. Se recogen 1.2 s útiles por objetivo de aprendizaje (antes 0.8); la validación conserva 0.8 s y evalúa cuadros originales. No se inventan observaciones de los extremos a partir de los informes antiguos.

## Puntero estabilizado y comparación con F

El cursor ocular utiliza un filtro propio, independiente de la configuración del índice: One Euro en coordenadas normalizadas, `min_cutoff=0.22`, `beta=4`, derivada `1.0`. Esta revisión reduce un poco más el temblor residual del último diagnóstico y conserva una respuesta progresiva a los movimientos intencionales. Un salto mayor que `0.16` de distancia normalizada espera como máximo una observación nueva para descartar un pico aislado. Después del suavizado se aplica una fijación de salida de `0.0055` con liberación a `0.010`: el micro-movimiento permanece en el último punto concentrado, pero un desplazamiento deliberado sí progresa. La pérdida de mirada, pausa o hueco mayor de 0.25 s reinicia el historial. Repetir la misma captura no avanza el filtro.

En P, **F** alterna Original/Estabilizado. La opción estabilizada usa la misma implementación que el cursor, sin enviar entradas al escritorio; los números originales permanecen visibles. El filtro no cambia el ajuste ni la aprobación y no atrae el cursor a botones. Las pruebas sintéticas reducen el temblor y limitan la demora en saltos confirmados, pero no demuestran precisión real. Durante la captura, el asistente muestra únicamente el objetivo; su centro alterna dos colores estáticos al cambiar de punto, sin animación continua ni texto que tape los objetivos periféricos.

No se han cambiado los límites de error normalizado medio 4 % y máximo 8 %. Se evalúan sin el suavizado del puntero. Ajustar un modelo o mostrarlo con P no habilita el ratón. Se mantienen las restricciones ante muestras antiguas, parpadeos, postura fuera del rango, pausa y arrastre. Cambiar motor revoca la calibración anterior.

El cálculo neuronal se hace en el trabajador ocular, con CPU, precisión FP32, dos hilos y una solicitud por vez. No se ejecuta en el hilo de interfaz ni en el detector de manos. La frecuencia continúa respetando la configuración existente; no se reduce silenciosamente la calidad del modo óptimo.

## Reproducir el entorno de desarrollo

Windows x64 y Python 3.12. Primero prepara las dependencias base mediante el procedimiento de desarrollo del proyecto. Después, desde su raíz:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps --require-hashes -r requirements-gaze.lock.txt
.\.venv\Scripts\python.exe scripts/prepare_gaze_models.py
.\.venv\Scripts\python.exe scripts/prepare_gaze_models.py --verify-only
```

El bloqueo adicional fija OpenVINO 2024.6.0 y su dependencia de empaquetado `openvino-telemetry` 2025.2.0, sin cambiar NumPy ni MediaPipe. Está dirigido a CPython 3.12 / Windows x64: no es un bloqueo universal.

La descarga es una acción explícita del script, nunca del arranque. Se verifican tamaños y SHA-384 de los cuatro archivos antes de cargarlos. Un archivo inválido no se reemplaza silenciosamente. La lectura mediante bytes admite rutas con acentos. Si faltan dependencias o modelos, se bloquea el seguimiento ocular; no se sustituye por una estimación antigua sin avisar.

## Privacidad y diagnóstico

El procesamiento es local. No se guardan imágenes de ojos/cara ni vídeos. La exportación E es voluntaria y numérica: geometría, dirección estimada, postura, objetivos, tiempos, errores y elección del ajuste. Se impide cargar el conversor opcional OVC de OpenVINO durante la inicialización: su importación iniciaría telemetría que no necesitamos. Esto no modifica la instalación del proveedor, las preferencias globales de consentimiento ni variables del sistema. Una prueba en un proceso nuevo bloquea conexiones y llamadas de telemetría y comprueba carga e inferencia reales sin intentos de envío.

Ambas revisiones personales utilizan el esquema de observaciones `openvino-gaze6-v1` y el informe esquema 2, distinguidas por su identificador de motor. La reproducción del JSON funciona sin cámara ni redes neuronales, reconstruyendo el ajuste personal a partir de las medidas guardadas. No reconstruye las imágenes ni evalúa retrospectivamente la CNN. Los informes v1 siguen reproduciéndose con v1, no se recalculan silenciosamente con v2. El contexto identifica el filtro de salida; E no graba el recorrido del visor P. Los costes del worker se miden con un reloj de alta resolución para evitar cifras artificiales de 0/16 ms.

Consulta [Diagnóstico ocular](DIAGNOSTICO_OCULAR.md) para exportar y reproducir una prueba.

## Procedencia y límites reales

Modelos FP32: [gaze-estimation-adas-0002](https://docs.openvino.ai/2023.3/omz_models_model_gaze_estimation_adas_0002.html) y [head-pose-estimation-adas-0001](https://docs.openvino.ai/2023.3/omz_models_model_head_pose_estimation_adas_0001.html). Procedencia, revisión fija y licencia Apache-2.0 en [assets/models](../assets/models/README.md). No se ha incorporado código de EyeTrax ni EyeTheia.

Estos modelos no garantizan coordenadas exactas de pantalla. Intel publica un error angular medio de 6.95° para el estimador de mirada en su conjunto interno: **no es el error de nuestro cursor ni un resultado en esta PC**. El recorte facial a partir de MediaPipe y la calibración personal son adaptaciones que necesitan validación física.

La ejecución real sobre imágenes sintéticas confirma contratos, archivos, inferencia y tiempos; no demuestra que una persona pueda aprobar ni seleccionar botones pequeños. Siguen pendientes pruebas con/sin lentes, recuperación tras parpadeos, postura y distancia, precisión en bordes, sesiones prolongadas y coste térmico. Más procesamiento puede ayudar a interpretar la imagen, pero no recupera información que una cámara desenfocada o un reflejo han ocultado.

⚓ Desarrollado por Luics415
