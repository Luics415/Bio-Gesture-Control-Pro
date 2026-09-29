# Estado de desarrollo 3.0

Revisión actual: **3.0.0.dev4**. Plataforma de implementación: **Windows**. Este documento describe el código y sus límites; no certifica una publicación remota ni rendimiento físico comprobado. La validación del portable concreto consta en su manifiesto.

## Fases y condición de entrega

| Fase | Implementado en la base local | Pendiente de aceptación |
|---|---|---|
| 1. Base 3.0 | Selector índice/ojos y preservación de ajustes anteriores; el rendimiento óptimo queda fijo. | Comprobar actualizaciones con configuraciones reales y equipos objetivo. |
| 2. Prototipo ocular | Worker facial opcional, redes OpenVINO de postura/mirada y ajuste personal; motor anterior disponible. | Precisión física con usuarios, cámaras, lentes y posturas diferentes. |
| 3. Calibración y recuperación | Precisión v2: 21 puntos más 13 de validación; v1: 13 + 9; geométrico: 9 + 5. Control bloqueado hasta aprobar, reposo de 70 s. | Comodidad real, márgenes de postura y recuperación en sesiones prolongadas. |
| 4. Integración | Cursor ocular independiente del índice y liberación segura al perder observaciones válidas. | Clics pequeños, selección de texto, arrastre y fatiga frente a 2.7. |
| 5. Auxiliar | L anclada, zona neutra/sensibilidad y vista de tareas; scroll antiguo de la principal retirado. | Ajuste físico de umbrales y análisis de confusiones gestuales. |
| 6. Pulido Windows | Pruebas automáticas, documentación y portable experimental dev4. | Rendimiento térmico, revisión visual completa, instalador/firma y prueba en equipo limpio. |

Linux y macOS quedan expresamente fuera de esta entrega inicial. No se atribuye compatibilidad a una plataforma por compartir Python.

## Precisión v2 y estabilización · dev4 · 8 de septiembre de 2026

Los tres intentos OpenVINO aportados por el usuario reprodujeron errores medios 3.97/5.52/4.52 % y máximos 8.60/13.42/11.49 %. Ninguno aprobó la comprobación. El primero ya cumple el límite medio pero no el máximo. Hay ruido temporal y desvío vertical, también cerca del centro; esto no justifica aumentar globalmente la sensibilidad.

- `precision-openvino-v2`: se conserva OpenVINO y la selección de ajuste de v1. Se mantienen sus trece puntos de entrenamiento y se añaden ocho al perímetro 4–96 %; trece objetivos finales, incluidas cuatro esquinas 7–93 %, comprueban zonas diferentes. El protocolo se versiona para no reinterpretar informes v1.
- Entrenamiento v2: 1.2 s útiles por objetivo. La espera inicial y la captura de validación no cambian. La estabilidad temporal no equivale a demostrar que el usuario fija el punto; no se descartan muestras porque su predicción esté lejos del objetivo.
- `gaze_pointer.py`: estabilizador ocular independiente del índice y en coordenadas normalizadas. Filtro adaptativo y contención de un salto aislado durante máximo una observación. No altera el aprendizaje ni los límites 4/8 %, que siguen calculándose sin suavizado.
- P/F: comparación entre original y estabilizado usando la misma implementación que el cursor; no mueve el ratón ni recoge una nueva calibración. El JSON conserva muestras originales y metadatos del filtro de salida, no una grabación de P.
- Objetivos perimetrales sin botones/textos superpuestos; instrucciones en el borde opuesto y Esc siempre disponible. D/E y los informes antiguos se conservan.
- Coste neuronal medido con `perf_counter`, manteniendo `monotonic` para edad de captura: evita confundir un tick de 0/16 ms con inferencia gratuita.
- Empaquetado CPU local con modelos, hashes y licencias; prueba adicional `--gaze-smoke` sin cámara, red ni entradas al escritorio. El ZIP es prerelease, no instalador firmado; Windows limpio y precisión ocular humana siguen pendientes.

Se conserva la selección ocular de configuraciones existentes. Para probar v2, elegir expresamente **Ajustes → Control → Motor ocular → Precisión v2 · OpenVINO**. No se han cambiado gestos ni ajustes de manos. El PDF/generador dev3 permanecen históricos; README-3.0 y la guía en texto describen dev4.

Validación local previa al empaquetado, repetida el 12 de septiembre: **1590 pruebas aprobadas, sin fallos ni omisiones** (Tk, MediaPipe y OpenVINO nativos habilitados; imágenes sintéticas, sin cámara ni entradas al escritorio). Ruff y comprobación de dependencias correctos. Permanecen dos avisos de deprecación de `google._upb`. Evidencia regenerable: `output/tests-dev4-resume.xml`. La ejecución completa tomó 40.56 s en esta PC; no representa un benchmark de uso del programa. Los controles congelados y su resultado se registran adicionalmente en el manifiesto de cada portable.

La revisión del constructor también bloquea `openvino.tools` y `openvino_telemetry` durante el análisis de DLL de PyInstaller. La protección se limita a los procesos de compilación y se comprueba en un proceso aislado real antes de analizar; no altera paquetes instalados ni consentimiento global y no se distribuye en el EXE. Los resultados anteriores del 8 de septiembre permanecen en `output/tests-dev4-final.xml` como evidencia histórica.

## Motor personal de precisión v1 · 8 de septiembre de 2026

Revisión del motor dentro de `3.0.0.dev3`, identificada como `precision-openvino-v1`. La configuración permite elegirla o conservar `legacy-ridge-v1` para comparar; el índice sigue siendo la opción inicial. No se han cambiado las manos ni sus acciones en esta revisión.

- Dos modelos Open Model Zoo FP32 (postura y mirada), con licencia Apache-2.0, revisión y hashes fijos; carga de cuatro archivos mediante bytes. Runtime OpenVINO 2024.6.0 instalado en `.venv`, CPU de dos hilos y un stream. Sin descargas al iniciar.
- Modelo personal de núcleo lineal/radial, selección por objetivo de entrenamiento y normalización independiente en cada partición. No utiliza los nueve objetivos finales para seleccionar ni corregir el ajuste.
- Geometría y límites de aprobación conservados. La dirección frontal respeta la convención operativa del demo oficial de OpenVINO: Z negativa; la conversión a pantalla se aprende, sin imponer las coordenadas del índice.
- D/P/E conservados. El JSON esquema 2 añade seis variables numéricas y la selección del modelo; el replay no necesita OpenVINO ni imágenes. Los dos JSON reales previos reproducen sin cambios errores de 9.1264 % / 24.8172 % y 9.0281 % / 19.3747 % (media/máximo). No se usan para afirmar precisión del motor nuevo.
- Importación del conversor OVC impedida para evitar inicializar su telemetría. Prueba de carga e inferencia real en un proceso nuevo con envíos/conexiones bloqueados: sin intentos de red ni telemetría. No modifica el consentimiento global del usuario.
- **1499 pruebas aprobadas, sin fallos ni omisiones**, incluidas Tk, MediaPipe y OpenVINO nativos con imágenes sintéticas, rutas con acentos, cierre de recursos, pérdida ocular y persistencia/cambio del selector. Dos avisos de deprecación de `google._upb`. Ruff y dependencias sin problemas.
- Medición de ingeniería sobre píxeles sintéticos en esta CPU Ryzen 7 5700G: carga de redes 301 ms; primera inferencia 45.77 ms; después de diez calentamientos, mediana 2.30 ms y p95 2.67 ms. Solo recortes + redes de postura/mirada: excluye cámara, MediaPipe e interfaz y **no mide precisión ocular**.

Preparación y límites: [Precisión ocular](PRECISION_OCULAR.md). Falta aceptación física y medición térmica prolongada. No se ha generado EXE ni publicado esta revisión. Los apartados dev1/dev2/dev3 iniciales siguientes conservan el historial del motor anterior.

## Diagnóstico experimental de dev3 · 8 de septiembre de 2026

La corrección de dev2 no bastó en las pruebas físicas. Cinco intentos registrados completaron los cinco objetivos de comprobación con 68–70 muestras, error medio 7.11–21.40 %, máximo 10.98–31.14 % y dispersión intrapunto 1.27–3.29 %. Esto señala un desfase mayor que la dispersión, pero **no identifica por sí solo la causa**. La inspección no encontró evidencia de doble espejo, coordenadas de monitor incorrectas o índices oculares intercambiados.

Dev3 conserva el ajuste, los controles de geometría, los límites de 4 %/8 % y los gestos de dev2. Añade:

- `gaze_diagnostics.py`: diagnóstico de solo lectura, métricas y sesgo X/Y por objetivo, entrenamiento frente a validación, rangos de características y sensibilidad de los coeficientes en sus unidades originales. Las métricas sobre cuadros calculables muestran también los rechazos y nunca sustituyen la aprobación real.
- `gaze_ui.py`: mapa tras el fallo, D para detalle, P para probar la estimación solo sobre el lienzo, E para exportación explícita. No aparecen predicciones durante los objetivos; el visor P no recoge ni modifica muestras y no habilita entradas del escritorio.
- Telemetría facial numérica acotada: resolución observada, tamaño/apertura de ojos, inferencia, latencia de captura a resultado y frecuencia efectiva de resultados. No hay un segundo detector ni cámara adicional. La cifra de FPS del detector no se confunde con los FPS solicitados.
- `gaze_export.py`: JSON voluntario en la carpeta de datos, subcarpeta `diagnostics/gaze`, con nombres únicos y sin sobreescribir intentos anteriores. No exporta imágenes ni carga perfiles. Las características oculares y tiempos relativos permiten analizar una sesión sin imágenes; no se transmiten automáticamente.
- `gaze_replay.py`: reproducción local de entrenamiento/comprobación desde JSON, sin cámara, interfaz o entradas del escritorio. Rechaza tamaños excesivos, tiempos desordenados y datos malformados; no ejecuta contenido del archivo ni modifica el original.
- El contexto conserva el fondo usado al adquirir los datos, aunque se cambie el fondo después del fallo antes de exportar.

Una reproducción sintética con señal vertical pequeña demuestra que un desplazamiento diminuto del iris puede amplificarse y producir un error estable elevado. **No se utiliza como diagnóstico definitivo del usuario**, ni para cambiar umbrales automáticamente. El siguiente paso requiere una exportación numérica real del nuevo asistente. Procedimiento: [Diagnóstico ocular](DIAGNOSTICO_OCULAR.md).

### Validación local de dev3

- **1388 pruebas aprobadas, sin fallos ni omisiones**, con Tk real y modelos nativos sobre imágenes sintéticas. Los avisos de excepciones ignoradas se trataron como errores en la ejecución final; permanecen solo dos avisos de deprecación de `google._upb`.
- Se verifican reproducción del informe, lectura sin cambios de estado, rechazo de datos malformados, límites de tamaño, exportación explícita sin red, copia de métricas y ausencia de entrada al escritorio durante el visor.
- Geometría del asistente verificada en 800 × 600 y 1920 × 1080 con dos escalas, incluyendo detalle, mapa y botones.
- Se reprodujo y corrigió una retención de variables de Ajustes por su callback de cambio de rendimiento. La ventana elimina el callback y libera las variables en el hilo de interfaz, evitando que el cargador de modelos intente finalizarlas después desde otro hilo. La prueba de interfaz también elimina su callback simulado circular.
- Ruff, comprobación de dependencias y arranque/cierre `--smoke` correctos. La guía PDF tiene cinco páginas renderizadas y revisadas, con el ancla y la firma conservadas.
- Evidencia local: `output/validation-v3-dev3/tests-final.xml`. No se abrió la cámara ni se emitieron entradas reales al escritorio durante estas comprobaciones. Sin EXE ni publicación remota.

## Corrección de calibración en dev2 · 8 de septiembre de 2026

La prueba física del usuario confirmó el cambio entre índice/ojos y el rechazo de intentos incorrectos, pero también el fallo «precisión insuficiente» al intentar calibrar correctamente. No se considera validado todavía el control ocular real.

- Se reprodujo un sobreajuste del entrenamiento: las variables de postura podían absorber demasiado de la señal ocular. El ajuste utiliza ahora la mediana por objetivo, igual peso entre objetivos y regularización diferenciada para iris (0.01) y postura (1.0).
- En una reproducción **sintética, no una medición del usuario**, con mirada válida y pequeñas variaciones correlacionadas de postura, el error medio/máximo pasó de 37.51 % / 57.80 % a 2.03 % / 4.51 %.
- La comprobación sigue evaluando **cada cuadro** contra los mismos límites de 4 % medio y 8 % máximo. No se reajusta con los objetivos de comprobación ni se ignoran cuadros erróneos mediante medianas de validación.
- El asistente comienza con gris mate y permite elegir fondo oscuro antes de iniciar. Explica postura estable, seguimiento con los ojos, parpadeo normal y ausencia de gestos de confirmación.
- La vista previa ocular solo se calcula durante la preparación o el diagnóstico, no junto a los objetivos ni sobre el vídeo habitual. Usa un recorte efímero de la imagen existente, sin abrir otra cámara, guardar imágenes o iniciar conexiones de red. Se invalida al desactivarse, perder rostro o detenerse el detector.
- Los parpadeos conservan segmentos válidos del mismo objetivo. La espera inicial es 0.7 s y la recuperación 0.25 s; solo cuenta el tiempo útil entre muestras nuevas del mismo segmento. Un punto incompleto vence a los 20 s y puede repetirse; una precisión insuficiente exige repetir todo.
- Los fallos muestran métricas y punto problemático. Los registros incluyen cifras del resultado, no imágenes ni características oculares.

Los reflejos de lentes no están resueltos por estas mejoras: el filtro de detalle/desenfoque no es un detector de reflejos. Sigue pendiente repetir la calibración con cámara real y evaluar el cursor, los clics y el arrastre. Esta revisión continúa **solo en la carpeta fuente**, sin EXE ni publicación.

### Validación local de dev2

- **1277 pruebas aprobadas, sin fallos ni omisiones**, habilitando Tk real y los modelos nativos con imágenes sintéticas. No se abrió la cámara ni se enviaron entradas al escritorio.
- Se incluyen regresiones de ruido/postura, independencia de la validación, parpadeos, repetición de puntos, recortes y limpieza ocular. Una carrera de arranque que podía reactivar una vista previa ya cerrada quedó reproducida y corregida.
- La interfaz se comprobó a 800 × 600 y 1920 × 1080, con dos escalas, incluyendo instrucciones y diagnósticos largos.
- Ruff, dependencias y arranque/cierre de comprobación correctos. Permanecen dos avisos de deprecación de `google._upb`, sin ocultarlos.
- Evidencia: `output/validation-v3-dev2/tests-final.xml`. La guía PDF actual tiene **cuatro páginas**, renderizadas y revisadas; se conserva el ancla y la firma de autor. El manual histórico 2.7 no se modificó.

## Validación local de dev1 · 8 de septiembre de 2026

- Batería conjunta: **1190 pruebas aprobadas, sin fallos ni omisiones**. Se habilitaron las pruebas reales de Tk y los modelos nativos sobre imágenes sintéticas; no se abrió la cámara ni se enviaron entradas al escritorio.
- Dos avisos de deprecación proceden de `google._upb`; no son fallos de pruebas ni se han ocultado.
- Ruff, comprobación de dependencias y arranque/cierre `--smoke` correctos.
- Evidencia regenerable local: `output/validation-v3-dev1/tests-final.xml`.
- Guía PDF de pruebas de aquella revisión: tres páginas renderizadas y revisadas; la [guía actual](manual/Guia-de-pruebas-3.0.pdf) se amplió en dev2. El manual público 2.7 se conserva sin sustituirlo.
- El aviso de distancia solo aparece en Ajustes y documentación. Un ajuste visual no reinicia la cámara ni borra la calibración; cambiar de monitor sí invalida el mapeo ocular.
- Falta medir precisión, consumo y comodidad con cámara real. No se ha compilado ni publicado un EXE 3.0. El splash aprobado 2.7 se conserva temporalmente; su actualización gráfica y el paquete final quedan para la fase de distribución.

## Base geométrica y motor anterior

`biogesture/face_tracking.py` consume la imagen de cámara ya disponible; no abre una segunda cámara. El modelo Face Landmarker está incluido localmente y solo se carga en modo ojos. Las salidas opcionales de expresiones y matrices faciales están desactivadas. La implementación evita trasladar inferencia facial al hilo de interfaz.

`biogesture/gaze.py` extrae diez características de una malla con iris: posición de ambos iris respecto a sus ojos, desplazamiento de la nariz como aproximación bidimensional de postura, separación de ojos, inclinación y posición en el cuadro. Esto **no es un modelo completo de mirada 3D ni compensación física de distancia**.

La geometría comprueba apertura ocular, tamaño mínimo de los ojos, coordenadas finitas, iris plausible y margen de orientación. El worker incorpora un filtro inicial de detalle/desenfoque de las regiones oculares; su umbral es experimental. Ninguna de estas comprobaciones garantiza reconocer todos los reflejos de lentes o los errores de landmarks.

La regresión regularizada se aprende en la sesión con una mediana por objetivo y penalización mayor para las variables de postura. No se autorizan coordenadas hasta superar la validación con objetivos y capturas distintos a los utilizados para aprender. La validación evalúa todos los cuadros, no solo sus centros. Los límites iniciales son **error euclídeo normalizado medio ≤ 0.04 y máximo ≤ 0.08**. Son un filtro exploratorio, no una promesa de precisión en píxeles ni un criterio suficiente para declarar una versión estable.

Una comprobación binocular adicional rechaza discrepancias excesivas respecto a la geometría aprendida. Así, errores opuestos de ambos iris no pueden cancelarse fácilmente y producir un falso centro de pantalla. No impone que los ojos sean idénticos ni sustituye un modelo de vergencia.

Se rechazan extrapolaciones fuera del margen calibrado. La recomendación de **50–70 cm** es una orientación inicial visible en Ajustes y el manual: no proviene de una medición de profundidad y no define por sí sola un rango garantizado.

La documentación oficial distingue iris de mirada en pantalla: [Google Research: MediaPipe Iris](https://research.google/blog/mediapipe-iris-real-time-iris-tracking-depth-estimation/). El contrato de puntos faciales y opciones del detector está en [Face Landmarker para Python](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

## Calibración original sin filtración entre aprendizaje y comprobación

Esta lista describe el motor anterior. El personal conserva las reglas temporales y de bloqueo, con trece objetivos de aprendizaje y nueve de comprobación.

- Nueve objetivos de entrenamiento distribuidos en ambos ejes.
- Cinco objetivos de validación diferentes; sus capturas deben ser posteriores y no repetidas.
- Espera inicial de 0.7 s por objetivo y recogida de al menos 0.8 s con ocho muestras nuevas como mínimo.
- Los cuadros antiguos, inválidos o repetidos no cuentan como nuevas muestras.
- Un parpadeo conserva los segmentos válidos del punto actual y exige 0.25 s de estabilización antes de continuar. Los huecos de detección no cuentan como tiempo de recogida.
- Un punto tiene un límite de 20 s. Repetir un punto incompleto no permite saltarse objetivos ni una validación fallida.
- Variación ocular degenerada, objetivos sin cobertura o error excesivo impiden activar el cursor.
- Las calibraciones no se guardan como perfiles biométricos ni se reutilizan automáticamente al comenzar una nueva sesión ocular.

Las pruebas sintéticas verifican estas reglas. No reemplazan un ensayo con ojos reales ni pueden demostrar que los landmarks sigan correctamente el iris a través de un lente.

## Contrato de seguridad temporal

Los tiempos de captura y del supervisor comparten un reloj monotónico. Una muestra con más de 0.25 s de antigüedad no autoriza entradas. La interfaz puede mantener la última coordenada dentro de ese límite entre capturas, pero repetir un paquete no renueva la presencia ni establece estabilidad por sí solo.

Ante pérdida ocular se bloquean movimientos y acciones nuevas. Un arrastre que ya estaba activo puede conservar el botón durante una gracia máxima de **0.32 s**, sin mover el cursor; abrir la pinza o agotar el plazo libera. La recuperación estable dentro del plazo permite continuar sin convertir cada parpadeo breve en una suelta, pero sigue siendo una tolerancia experimental por validar físicamente.

Recuperar observaciones requiere estabilidad; un parpadeo no borra la calibración. Tras 70 s sin mirada válida, el reposo queda retenido incluso si aparece un rostro nuevo. La reanudación exige victoria y seguimiento estable. No es autenticación ni identifica al propietario. El reposo reduce inferencia; detectar una mano reciente reactiva la frecuencia normal para evitar que una captura reducida impida validar la mirada en equipos lentos. Este cambio de frecuencia no autoriza acciones ni libera el reposo.

El seguimiento facial permanece desactivado en modo índice. Desde dev4 el rendimiento óptimo es fijo: no hay un perfil ahorrativo ni una reducción automática de captura/detección. Las preferencias antiguas de ahorro se normalizan al cargar para evitar que una configuración histórica degrade el seguimiento actual.

## Gestos auxiliares

La L toma su referencia tras aproximadamente 0.45 s. El desplazamiento vertical respecto a esa posición controla dirección y velocidad continua, normalizado por tamaño de mano; la referencia no se arrastra detrás del movimiento. Abrir la mano, deshacer la L o perder detección detiene el scroll. La banda neutra ya no es el 45–55 % de la imagen.

La vista de tareas utiliza índice y corazón extendidos y juntos en la auxiliar durante aproximadamente 0.65 s. Emite una sola vez hasta liberar el gesto; se distingue de una victoria abierta. Se conservan las cuatro pinzas auxiliares de edición. Los roles continúan sin fijarse a izquierda o derecha.

## Pruebas para desarrollo

Desde la raíz del proyecto, en el entorno `.venv` ya preparado:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
```

`INICIAR_CONTROL.vbs` inicia el código local sin consola. El portable público 2.7 conserva su versión; no se actualiza solo porque cambie este árbol de fuentes.

## Antes de distribuir 3.0

1. Medir selección de objetivos pequeños, error de clic, arrastre, tiempo de tarea y fatiga frente al modo índice.
2. Ensayar ojos/lentes/reflejos, iluminación, teclado, giros, posturas, cámaras movidas y pérdida de seguimiento.
3. Medir al menos sesiones prolongadas de CPU, memoria, latencia y calentamiento en los equipos objetivo, en ambos perfiles.
4. Verificar pausa/reanudación también bajo carga y con frecuencia facial reducida en reposo.
5. Revisar asistente y ajustes a diferentes escalas de pantalla, sin mensajes sobre la cámara.
6. Generar un paquete 3.0 identificado de forma inequívoca, verificar su contenido y probarlo en una computadora limpia.

Hasta superar estos puntos, **el modo ocular debe seguir etiquetado como experimental** y el índice debe permanecer disponible.
