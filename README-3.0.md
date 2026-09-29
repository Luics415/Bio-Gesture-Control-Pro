# Bio-Gesture Control Pro 3.0 · Desarrollo

**Prototipo `3.0.0.dev4` para Windows.** La mirada es una opción experimental; el cursor con índice sigue disponible y es la opción predeterminada. Esta revisión prepara un portable de pruebas, no una distribución 3.0 validada para uso cotidiano.

Desarrollado por Luics415 · ⚓

[Guía de pruebas en PDF](docs/manual/Guia-de-pruebas-3.0.pdf) · [Manual 3.0 en texto](docs/manual/Guia-3.0.md) · [Estado de fases y validación](docs/V3_DEVELOPMENT.md) · [Entrega dev.7](docs/DELIVERY_DEV7.md) · [Corrección ocular y splash 3.5](docs/DELIVERY_DEV8.md) · [Privacidad, términos y cookies](docs/legal/README.md)

## Lo que cambia

| Función | En esta revisión |
|---|---|
| Cursor | Elección explícita entre **Dedo índice** y **Ojos (experimental)**. |
| Calibración ocular | Precisión v2 OpenVINO: 21 puntos de aprendizaje y 13 de comprobación, incluidos bordes. Obligatoria en cada sesión ocular. |
| Estabilización ocular | Filtro propio del puntero, independiente del índice. P/F permite comparar estimación original y estabilizada sin controlar la PC. |
| Rendimiento | Óptimo y fijo para ojos y manos; conserva la calidad solicitada. |
| Scroll auxiliar con L | Referencia tomada donde activas la L, no en el centro de la cámara. |
| Vista de tareas | Índice y corazón juntos de la auxiliar, sostenidos durante aproximadamente 0.65 s, ejecutan Windows + Tab. |
| Cámara | Se conserva limpia: dibujos opcionales de manos y menú radial, sin instrucciones oculares superpuestas. |

## Probar el código local

Este prototipo se inicia con **INICIAR_CONTROL.vbs**, que utiliza el entorno **.venv** del proyecto y no abre una consola. La preparación de desarrollo sigue requiriendo Windows x64, Python 3.12 y `PREPARAR_DESARROLLO.bat`; no es el procedimiento de instalación para un usuario final.

El ejecutable y el ZIP públicos de la [versión 2.7](https://github.com/Luics415/Bio-Gesture-Control-Pro/releases/tag/v2.7.0) siguen correspondiendo a 2.7: abrirlos no prueba estos cambios. La compilación local dev4 genera un **ZIP portable de pruebas**: se extrae completo y se abre `BioGestureControlPro.exe`, conservando `_internal` junto a él. No es un instalador firmado ni una publicación en GitHub; consulta su `BUILD-MANIFEST.json` para conocer las verificaciones del paquete concreto.

### Elegir el control

En **Ajustes → Control**, selecciona **Mover cursor con**. El rendimiento óptimo es fijo; guarda los cambios antes de calibrar.

- **Índice:** conserva el control manual existente y no carga el modelo facial.
- **Ojos:** necesita cámara activa y un monitor concreto; todavía no calibra el escritorio virtual de varios monitores.
- **Rendimiento óptimo fijo:** ojos y manos utilizan siempre la calidad solicitada; ya no existe un selector que reduzca cámara o desactive el seguimiento facial.

**Motor ocular → Precisión v2 · OpenVINO** selecciona esta revisión. **Personal · OpenVINO** conserva v1 (13 + 9 objetivos) y **Anterior · comparación** conserva el estimador solo geométrico. Una configuración existente mantiene su elección: selecciona v2 expresamente para probar la nueva calibración. Cambiar de motor descarta la calibración anterior. La elección no modifica gestos, roles, clics, arrastre ni comandos auxiliares.

### Motor personal de precisión

Esta revisión de desarrollo incorpora dos redes locales de OpenVINO: una estima la postura de la cabeza y otra analiza las imágenes de ambos ojos para estimar una dirección de mirada. Una calibración personal convierte esa dirección en coordenadas de pantalla. No es simplemente aumentar los puntos de MediaPipe ni instalar EyeTrax.

El ajuste compara modelos lineales y no lineales, usando únicamente los objetivos de aprendizaje. Cada objetivo pesa lo mismo; los trece de comprobación **no se usan para elegir o corregir el modelo**. V2 conserva el estimador de v1 y añade ocho objetivos al 4–96 % de pantalla, manteniendo los centrales/intermedios. Recoge 1.2 s útiles por objetivo de aprendizaje; la comprobación conserva 0.8 s y evalúa muestras sin suavizar. Se conservan los límites de aprobación y la protección ante pérdida de mirada. Los modelos se cargan solo en modo ocular y se ejecutan en su trabajador independiente, en CPU con dos hilos.

El entorno local de esta carpeta ya está preparado. Para reproducirlo en otra carpeta de desarrollo, consulta [preparación, procedencia y límites del motor](docs/PRECISION_OCULAR.md). El motor anterior sigue disponible; los nuevos diagnósticos identifican cuál se utilizó. **La integración y las pruebas sintéticas no demuestran todavía una mejora de precisión con una persona.**

### Privacidad, seguridad y accesibilidad

La aplicación funciona localmente: no tiene cuentas, publicidad, analítica, cookies ni servidor propio. La cámara no se guarda como imagen o vídeo; un diagnóstico ocular numérico solo se escribe cuando el usuario pulsa **Exportar diagnóstico**. El menú **Más → Privacidad, términos y cookies** abre los tres avisos sin conexión, y sus copias públicas están en [`docs/legal`](docs/legal/README.md). El portable incluye únicamente la documentación y licencias declaradas en su manifiesto; no incluye entornos virtuales ni credenciales. El reporte privado de vulnerabilidades se describe en [`SECURITY.md`](SECURITY.md).

La procedencia visual está auditada en [`docs/ASSETS_RIGHTS.md`](docs/ASSETS_RIGHTS.md): el ancla, el splash y la firma son identidad aprobada del autor; el manual usa dibujos; las capturas privadas no se distribuyen.

Los controles principales tienen etiquetas explícitas, foco de teclado y activación con Enter; la ventana legal permite Tab y Esc. Esto es una revisión básica de accesibilidad, no una certificación WCAG. Antes de publicar una web propia o una versión comercial, revisa consentimiento, derechos de imagen, licencias de modelos y las leyes de cada jurisdicción con asesoría profesional.

### Primer uso ocular

Antes de pulsar **Iniciar**, comprueba ambos ojos en la vista ampliada. Los puntos dibujados muestran la detección: **no son objetivos que debas seguir**. El fondo gris mate evita empezar con una pantalla casi negra; puedes elegir **Fondo: oscuro** antes de iniciar si el monitor se refleja en tus lentes. La ampliación no añade detalle a la captura ni garantiza una detección correcta.

Siéntate cómodo, con la cámara quieta y la cabeza relativamente estable. **Mueve solo la mirada al centro de cada objetivo**, sin girar la cabeza para apuntarle. No necesitas mostrar las manos ni dejar de parpadear. La vista de los ojos se oculta al comenzar los objetivos para no distraerte.

Con v2 se recogen 21 puntos y se comprueba la precisión en 13 objetivos nuevos. V1 conserva trece y nueve; el motor geométrico, nueve y cinco. Los parpadeos interrumpen la recogida, pero conservan las muestras válidas del mismo punto; al volver a mirar, espera a que continúe. Si un punto no se completa en 20 segundos, puedes repetir ese punto. Si falla la **comprobación de precisión**, el cursor ocular permanece bloqueado: exporta el diagnóstico antes de iniciar otro intento.

**Distancia orientativa para empezar: unos 50–70 cm de la cámara.** No es una medición ni una garantía de funcionamiento. Ajusta tu posición hasta que los ojos se vean con suficiente detalle y calibra con los lentes que usarás. La recomendación aparece también como texto en Ajustes, nunca sobre el vídeo.

Una vez validada la calibración, el control permanece en pausa hasta que lo actives. Parpadear o mirar el teclado no borra la calibración. **Calibrar mirada…**, disponible en el menú y Ajustes, permite repetirla voluntariamente cuando el cursor se sienta impreciso.

### Diagnóstico de pruebas en dev3

Las herramientas añadidas inicialmente en dev3 se conservan para ambos motores. El nuevo motor sí cambia la estimación, pero **no rebaja los límites de aprobación**. Las pruebas físicas anteriores no aprobaron la calibración y todavía hay que evaluar esta nueva alternativa.

Después de un fallo aparece un mapa: círculos para los objetivos, cruces para la mirada media estimada y líneas que muestran la desviación. En la ventana de calibración:

- **D — Detalle:** motor utilizado, observaciones nuevas por segundo, edad de la captura, coste neuronal, dirección estimada, tamaño de los ojos, iris, postura y muestras/rechazos por punto.
- **P — Probar sin controlar PC:** tras completar el ajuste, muestra una cruz dentro del asistente, aunque haya fallado la comprobación. **F** alterna original/estabilizada; esta última usa el mismo filtro del cursor ocular. Los números permiten comparar ambas. **No mueve el ratón, no habilita clics y no aprueba la calibración.** P o Esc vuelve al resultado.
- **E — Exportar diagnóstico:** guarda voluntariamente un JSON local con mediciones numéricas de calibración/comprobación. No incluye fotografías ni vídeo y no se envía automáticamente.

Las predicciones se ocultan mientras se recogen los objetivos, para no influir en dónde miras. Los diagnósticos no alteran la zona habitual de cámara ni los gestos de las manos. Consulta [cómo realizar y compartir una prueba útil](docs/DIAGNOSTICO_OCULAR.md), incluido el comando de reproducción sin cámara.

### Corrección anterior en dev2

Se corrigió un sobreajuste reproducible: pequeñas variaciones de postura podían influir demasiado durante el aprendizaje y hacer fallar la comprobación posterior. Ahora cada objetivo tiene el mismo peso y las variables de postura tienen una regularización mayor. **No se han rebajado los límites de aprobación** ni se utilizan las respuestas de comprobación para reajustar el modelo.

El antiguo aviso genérico de precisión insuficiente muestra ahora el error medio, el máximo y el punto de comprobación con mayor desviación. Son distancias normalizadas en pantalla, no porcentajes de aciertos. La corrección está comprobada con pruebas sintéticas; todavía falta confirmar que permita completar tu calibración real, especialmente con reflejos en los lentes.

### Pérdidas de mirada y reposo

Una observación inválida o demasiado antigua bloquea el movimiento del cursor y las acciones nuevas dependientes de él. Si ya había un arrastre válido, el botón puede conservarse **hasta 0.32 s**, con el cursor quieto, para tolerar un parpadeo breve; abrir la pinza libera inmediatamente y superar ese plazo también libera. Cuando los ojos vuelven, se comprueba su estabilidad sin recalibrar automáticamente. Esta tolerancia inicial todavía requiere pruebas físicas.

Tras **70 segundos sin mirada válida**, el modo ocular entra en reposo. Para reanudar requiere **victoria de la mano principal y mirada válida estable**. Mostrar otra vez un rostro no reanuda por sí solo. El modo índice no depende de detectar ojos.

Al volver a detectar una mano se recupera temporalmente la frecuencia normal de seguimiento para comprobar la mirada; esto no desbloquea las acciones ni sustituye el gesto de victoria.

Esto **no es identificación del propietario ni un bloqueo de Windows**. Otra persona puede realizar el mismo gesto; la responsabilidad de dejar el equipo accesible sigue siendo del usuario.

### Scroll en L

Forma la L con la auxiliar y mantenla aproximadamente **0.45 s** para fijar el punto inicial. Por encima continúa hacia arriba; por debajo continúa hacia abajo. Cuanto más te alejas, mayor velocidad, con un límite. Cerca del punto inicial hay una zona neutra que puedes ajustar.

**Abre la mano o deshaz la L para detener y borrar la referencia.** La pérdida de detección también detiene el scroll. La siguiente activación registra un punto nuevo. Se han retirado los antiguos gestos de scroll de la principal; copiar, pegar, deshacer y rehacer permanecen en la auxiliar.

## Alcance real del prototipo

MediaPipe localiza puntos faciales y del iris; **no proporciona directamente el punto de pantalla que mira una persona**. Esta revisión añade una estimación local calibrada con límites conservadores de postura, tamaño del rostro y geometría ocular. No demuestra todavía precisión suficiente para editar texto, seleccionar controles pequeños o trabajar durante horas. [Explicación de Google Research](https://research.google/blog/mediapipe-iris-real-time-iris-tracking-depth-estimation/) y [Face Landmarker oficial](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

Las salidas faciales opcionales de expresiones y matrices están desactivadas; permanecen los cálculos internos necesarios del modelo. No se envían imágenes a un servicio externo ni se persiste una identidad facial. Los modelos se incluyen localmente y no se descargan al abrir el programa.

**Pendiente:** pruebas físicas con lentes, reflejos, parpadeos, cambios de postura y distancia; mediciones térmicas y de latencia prolongadas; empaquetado y distribución 3.0. Linux y macOS se posponen a versiones futuras.

Consulta la [guía de uso 3.0](docs/manual/Guia-3.0.md) y el [estado técnico de desarrollo](docs/V3_DEVELOPMENT.md). El PDF y su generador de dev3 se conservan como material histórico y no se regeneraron en dev4: para esta revisión prevalecen la guía en texto, este README y [Precisión ocular](docs/PRECISION_OCULAR.md). El manual visual de 2.7 también se conserva como referencia histórica.
