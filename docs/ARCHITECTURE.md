# Arquitectura 2.7

La versión **2.7.0**, basada en el núcleo validado durante el desarrollo 2.0, separa la cámara y la inferencia del hilo gráfico. El selector asigna las muestras a principal y auxiliar; sus motores transforman coordenadas en eventos descriptivos. Solo el adaptador de Windows produce acciones reales. Las pruebas pueden recorrer esos mismos estados sin tocar mouse, teclado o cámara.

```text
Cámara → último cuadro → MediaPipe → asignación de roles
                                     ├→ motor principal: cursor y gestos
                                     └→ motor auxiliar: edición y scroll en L
                                             ↓
                              coordinación y exclusión de conflictos
                                     ├→ acciones de Windows
                                     └→ interfaz de pruebas / radial
```

## Responsabilidades

| Módulo | Responsabilidad |
| --- | --- |
| `settings.py` | Valores tipados, validación y escritura atómica de configuración |
| `models.py` | Contratos de landmarks, muestra de mano, evento y resultado de seguimiento |
| `tracking.py` | Captura e inferencia fuera de Tk; procesamiento del cuadro disponible más reciente |
| `selection.py` | Elección inmediata de principal al observar una sola mano; asignación de auxiliar y recuperación automática de ambos roles |
| `gestures.py` | Geometría de la mano, distancias normalizadas, estados exclusivos, permanencia, histéresis y rearme |
| `auxiliary.py` | Cuatro pinzas de edición y scroll continuo en L con activación de 0.45 s; sin puntero ni entradas directas del sistema |
| `coordinates.py` | Zona de control, suavizado adaptativo y transformación al rectángulo físico de pantalla |
| `windows.py` | Enumeración de monitores, DPI, comandos de Windows y liberación de entradas |
| `desktop.py` | Ventana de pruebas de 550×375, configuración, calibración, bandeja y coordinación segura de ambos roles |
| `rendering.py` | Radial de ocho etiquetas cortas y barra horizontal, sin texto central, arco, porcentaje ni ejecución de comandos |
| `ui.py` | Controles compactos y adaptación de acciones al menú Más |
| `startup.py` | Splash, comprobación del modelo, arranque, registros y control de instancia única |
| `paths.py` | Localización de los recursos incluidos; la carpeta de datos se resuelve en `settings.py` |
| `control.py` | Entrada, selección del intérprete local y relanzamiento sin consola para el arranque normal |

El modelo se incluye localmente con su SHA-256; no se descarga al arrancar. Python lee el archivo y lo entrega como `model_asset_buffer` a MediaPipe, evitando el fallo de su apertura nativa cuando la ruta contiene acentos. Esto solo cambia la carga inicial, no la captura ni los gestos. La ausencia de un dispositivo de audio no debe impedir recuperar la interfaz.

## Tiempo y cancelación

Los tiempos de gestos utilizan reloj monótono. La captura y la detección tienen límites de frecuencia independientes. Los slots de cuadro y resultado conservan el valor más reciente, evitando una cola creciente de acciones antiguas. FPS, tiempo de inferencia, antigüedad del cuadro y recursos del proceso se consultan en **Ajustes → Diagnóstico**, no sobre la cámara permanentemente. El porcentaje de CPU utiliza 100% por núcleo lógico; la memoria muestra el conjunto residente en MiB. Una tasa de inferencia no equivale a latencia física completa.

La pérdida de una mano cancela su gesto pendiente y libera sus entradas retenidas. Los errores de captura, la pausa y el cierre cancelan ambos motores. Menús, volumen, desplazamiento y clics de la principal comparten una máquina de estados con prioridad. La coordinación bloquea las acciones auxiliares durante pinza/clic/arrastre, menú, onda, scroll, volumen, pausa, configuración, calibración o cambio de cámara, para evitar acciones simultáneas incompatibles. La auxiliar ya asignada puede actuar si la principal sale momentáneamente de cámara, con control activo y sin otra operación incompatible. Fix.4 no cambia la elección de roles, la interfaz de control ni los gestos de la principal.

El motor auxiliar devuelve eventos de edición: Copiar, Pegar, Deshacer y Rehacer para las pinzas del pulgar con 8, 12, 16 y 20, respectivamente. Exige 0.45 s continuos de muestras nuevas. Su `reset()` cancela el candidato conservando el bloqueo de ejecución y la marca temporal; `clear()` reinicia explícitamente una sesión. La pérdida de seguimiento o la deshabilitación no rearma una pinza ejecutada. El adaptador utiliza Ctrl+C, Ctrl+V, Ctrl+Z y Ctrl+Y, independientemente del perfil principal. Los recibe la aplicación en primer plano, sin limitarse a VS Code; Ctrl+Y no tiene el mismo significado en todas las aplicaciones. El mapa anterior Guardar/Buscar/Terminal/Paleta se sustituye, no se añade como otro conjunto activo.

La auxiliar también genera eventos de rueda desde una L de pulgar e índice abiertos aproximadamente a 90°, con los otros tres dedos doblados. Dev.6 evalúa el ángulo visible (55–125°) y tolera flexión ligera del índice y pulgar mediante guardas exclusivas de la auxiliar. Tras 0.45 s compara el centro normalizado de la palma (media Y de 0, 5, 9, 13 y 17) con y=0.50 de la imagen. La banda neutra inclusiva 0.45–0.55 detiene el desplazamiento. Fuera de ella, arriba produce rueda positiva y abajo negativa: empieza al 25 % de `Settings.scroll_rate` y aumenta linealmente hasta el 100 % en los extremos, saturada. El mínimo evita una velocidad prácticamente nula junto al borde neutro. Este ajuste se comparte con el scroll preexistente de la principal, sin reconfigurarlo ni cambiar su gesto. El motor no mueve el cursor.

Perder la L o la muestra, deshabilitarla, pausar, bloquearla por prioridad o llamar a `reset()` descarta temporización y fracciones pendientes del scroll auxiliar. La vuelta a la zona muerta o un cambio de dirección no conserva restos que puedan producir un paso retrasado en el sentido anterior. La siguiente activación espera 0.45 s y aplica el centro fijo de la imagen, sin pedir volver a él ni acumular movimiento. La pose L sigue pendiente de validar físicamente, no es una garantía de precisión o comodidad. Mantener Ctrl/Mayús mediante gestos y otras ampliaciones quedan fuera de esta revisión.

La pausa de acciones conserva seguimiento para reconocer victoria y la onda lateral: esta última solo cambia el modo de ventana, sin reanudar ni enviar entradas. La onda acepta una mano relajada con al menos tres dedos largos abiertos; exige cuatro recorridos y tres inversiones dentro de 2.2 s, con amplitud inicial de 0.50 palmas. Los huecos de hasta 0.15 s no suman movimiento. Después de cambiar la ventana espera 0.30 s antes de contar una secuencia nueva, sin exigir cerrar o soltar la mano. El seguimiento normal del índice y la semántica de pinza se conservan.

Ocultar la ventana conserva el trabajo en segundo plano, pero omite crear imágenes y dibujar video mientras no sea visible. **Más → Apagar cámara** libera el dispositivo; salir cierra el seguimiento. La distribución de pruebas es barra de 28 píxeles, cámara de 335 y estado de 12. La barra muestra Activar/Pausar, Ajustes y Más; el modo fijo conserva el tamaño, elimina bordes y usa opacidad inicial de 85%.

Desde dev.7 la zona de cámara no crea instrucciones, contadores, mensajes de espera/error ni barras auxiliares, tampoco con `--diagnostics`. Solo contiene la imagen, puntos/conexiones opcionales y el menú radial cuando se utiliza. **Dibujar puntos de mano** decide siempre si se dibujan ambas manos; se respeta una preferencia guardada. Fuente, VBS y EXE comienzan sin diagnóstico visual. `--diagnostics` permite consultar el pie externo de desarrollo, nunca reintroduce textos en la cámara. Ajustes, registros, controles y diálogos de fallos de arranque siguen disponibles. El splash conserva el diseño aprobado con la actualización de número a 2.7 solicitada por el autor.

## Coordenadas

Los landmarks se interpretan teniendo en cuenta la proporción del cuadro; la vista se adapta mediante escalado proporcional. Las distancias de pinza se expresan con respecto al tamaño de palma. La zona activa calibrada se transforma al monitor elegido o al escritorio virtual, incluidos orígenes negativos. El espejo de cámara y las inversiones del usuario se aplican de manera explícita.

Las propiedades del monitor pueden cambiar durante la sesión. La calibración define la zona de trabajo de la mano principal elegida, que puede ser cualquiera. Se detectan hasta dos manos sin confiar en su orden. Al iniciar o reelegir, basta una observación válida de una sola mano para asignar la principal; no hay tiempo de permanencia ni obligación de retirar ambas un segundo. Si inicialmente aparecen dos, se espera un cuadro con una sola.

El selector conserva los roles y usa posición, escala, movimiento y lateralidad observada para recuperarlos automáticamente tras perder detección. Una observación muy solapada puede omitirse sin crear un bloqueo permanente. **Más → Reelegir mano principal** es una decisión manual, no una recuperación obligatoria tras cada fallo. La auxiliar está habilitada por defecto y puede deshabilitarse desde Ajustes o Más. Este seguimiento de sesión no es identificación biométrica.

## Configuración y privacidad

Los valores predeterminados inician pausados, con el rol auxiliar habilitado, a 640×480 y hasta 30 cuadros por segundo solicitados. El controlador de cámara puede negociar otros valores. La escritura de ajustes sustituye el archivo de forma atómica después de validar todo el contenido. Un archivo ilegible o inválido utiliza valores predeterminados sin destruir el contenido anterior. La migración conserva los ajustes personalizados y actualiza el antiguo par predeterminado de onda (0.65 palmas y 1.6 s) a 0.50 y 2.2.

La carpeta de datos habitual es `%LOCALAPPDATA%\BioGestureControlPro`. La variable `BIOGESTURE_DATA_DIR` permite aislar pruebas. No existe backend, cuenta, nube ni grabación de imágenes para realizar el seguimiento. El arranque recomendado es `INICIAR_CONTROL.vbs`, que utiliza `.venv\Scripts\pythonw.exe`; los registros de bibliotecas nativas se redirigen al diagnóstico sin abrir una consola del programa.
