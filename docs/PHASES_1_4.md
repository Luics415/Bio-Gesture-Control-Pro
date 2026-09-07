# Estado del proyecto 2.0 · fases 1–7

Versión: **2.0.0-dev.7**. Las fases 1–5 tienen implementación local. Esta revisión elimina definitivamente los textos de la zona de cámara, mejora las manos ilustradas del manual y añade la firma aprobada al final. Mantiene las correcciones dev.6 de puntos opcionales y L. La publicación del código/manual/portable de pruebas no sustituye la sesión física ni Windows limpio. La identidad de ancla se conserva sin rediseñar los recursos aprobados; el texto del splash es exactamente **Desarrollado por Luics415**. No se presenta como un rediseño completo de ventana aprobado.

## Alcance

| Fase | Trabajo de esta entrega | Evidencia verificable |
| --- | --- | --- |
| 1. Base reproducible | Entorno `.venv` nuevo; dependencias y hashes; copia del código 1.20.36; diagnóstico; licencia y avisos | `setup-dev.ps1`, `diagnose.py`, archivos de bloqueo y carpeta `legacy` |
| 2. Núcleo | Captura e inferencia separadas de la interfaz; slots de último cuadro; errores visibles; cierre seguro | Módulos de seguimiento, acciones, pruebas sin dispositivos |
| 3. Precisión | Escala de palma, geometría de dedos, histéresis, tiempos, suavizado y mapeo de pantalla | Motor y pruebas de secuencias, pantalla y configuración |
| 4. Escritorio | Vista de pruebas 550×375 con cámara de 550×335, radial simplificado, modo fijo transparente, bandeja, perfiles, calibración, selección de cámara y splash | Interfaz y pruebas locales; ejecutable limpio por defecto, diagnóstico explícito; revisión física pendiente |
| 5. Dos manos, primera implementación | Principal y auxiliar recuperables, reelección manual, auxiliar habilitada por defecto con opción de apagarla, cuatro comandos de edición y scroll en L | Selector y motor auxiliar; validación física y refinamiento pendientes |

El código y las pruebas automatizadas son comprobables localmente. No implican que todos los gestos, dispositivos o monitores hayan pasado una sesión física de uso. Los resultados concretos de ejecución deben leerse en los informes generados y en el registro de trabajo de la entrega, no inferirse de esta tabla.

Fix.4 conserva el cursor continuo del índice, las pinzas de clic/arrastre y los demás gestos de la principal de fix.3. La onda acepta al menos tres dedos largos abiertos de manera relajada y cuenta **cuatro recorridos con tres inversiones**, inicialmente de 0.50 palmas dentro de 2.2 s. También cambia el modo con el control pausado, sin habilitar otras acciones. Se rearma después de 0.30 s, sin exigir cerrar o soltar la mano.

La principal se elige con el primer cuadro válido de una sola mano, sin sostenerla ni esperar un segundo. Si aparecen dos al arrancar, basta retirar una. Los roles recuperan la detección automáticamente y **Más → Reelegir mano principal** permite una nueva elección manual. Estos roles y sus controles de interfaz se conservan respecto a fix.3.

La auxiliar usa pinzas de 0.45 s para **Copiar, Pegar, Deshacer y Rehacer**, mediante pulgar con índice, corazón, anular y meñique, respectivamente. Sustituyen Guardar/Buscar/Terminal/Paleta por Ctrl+C/V/Z/Y, independientes del perfil principal y destinados a la aplicación en primer plano, no solo a VS Code. Rehacer mediante Ctrl+Y depende de que la aplicación reconozca ese atajo. Cada pinza exige abrir antes de repetir.

Se incorpora además la **L auxiliar** —pulgar e índice abiertos aproximadamente a 90°, otros tres dedos doblados— para desplazar sin tomar el cursor. Tras 0.45 s compara la palma con el centro fijo de la imagen. Arriba del 45 % desplaza arriba; debajo del 55 %, abajo. La banda 45–55 % detiene el scroll. Desde dev.6 se tolera un ángulo visible 55–125° y una flexión ligera de índice/pulgar; fuera de la banda la velocidad va del 25 % al 100 % de `scroll_rate`, inicialmente de 1.5 a 6 pasos por segundo. Se reutiliza ese ajuste sin cambiar ni reconfigurar el scroll de la principal. Perder la L/mano, pausar o bloquearse descarta temporizadores y fracciones pendientes, sin ráfaga al volver. La comodidad y precisión de esta pose están pendientes de validación física.

Pinzas/clics, arrastre, menú, onda, scroll y volumen de la principal tienen prioridad; pausa, configuración, calibración y cambio de cámara también bloquean las acciones auxiliares. La auxiliar asignada puede actuar cuando la principal sale momentáneamente de cámara, sin una operación incompatible. Modificadores Ctrl/Mayús sostenidos mediante gestos y otras ampliaciones quedan pospuestos.

La ventana mantiene 550×375: barra de 28 píxeles con **Activar/Pausar**, **Ajustes** y **Más**, cámara de 335 y franja inferior de 12; las métricas se consultan en Diagnóstico. El radial muestra ocho etiquetas cortas y una barra horizontal. En dev.7 se elimina el dibujo de todas las instrucciones, contadores de onda y avisos dentro de cámara, en fuente, VBS y EXE, incluso con diagnóstico explícito. **Dibujar puntos de mano** sigue siendo opcional y respeta la preferencia guardada. El inicio habitual no muestra estado de desarrollo; `--diagnostics` habilita solo el pie externo. Controles, Ajustes y diálogos de fallo siguen disponibles; el ancla y splash permanecen intactos.

El inicio de desarrollo es **INICIAR_CONTROL.vbs** después de preparar `.venv`. La distribución portable utiliza directamente **BioGestureControlPro.exe** con toda su carpeta. El estado verificable del paquete figura en [Distribución](DISTRIBUTION.md) y [Validación](VALIDATION.md); no equivale a un instalador firmado.

## Conservación del original

El directorio `venv` antiguo no se borra ni se publica. Su intérprete dependía de una ruta ajena a esta instalación. La copia fuente `legacy/v1.20.36/control.py` sirve para comparar funciones y parámetros. No se ejecuta automáticamente porque el original inicia cámara y control del escritorio sin una fase de configuración.

No existe una medición histórica comparable del rendimiento de 1.20.36. El benchmark de esta entrega separa tiempo del motor y, opcionalmente, inferencia con cuadros negros. Ninguno demuestra un porcentaje de mejora de uso real.

## Pruebas de aceptación físicas pendientes

1. Iniciar, abrir configuración, seleccionar cámara y recuperar un fallo o desconexión.
2. Calibrar ambas lateralidades por separado; comprobar espejo, extremos y dirección vertical.
3. Mover cursor, hacer clic izquierdo/derecho, arrastrar y retirar la mano durante el arrastre.
4. Mantener y soltar poses: verificar una ejecución discreta por gesto y continuidad deliberada de scroll/volumen.
5. Mover la mano abierta relajada a derecha e izquierda: completar cuatro recorridos y alternar ventana normal/fija una vez. Repetir una secuencia completa tras 0.30 s, sin cerrar la mano. Comprobarlo activo y pausado, sin acciones de mouse durante la pausa, y recuperar la vista desde bandeja.
6. Validar perfiles con el editor, navegador y reproductor correspondientes en primer plano.
7. Probar Ctrl+Alt+F12, cierre completo y recuperación después de errores.
8. Comprobar 100%, 125%, 150% y 200% de escala, pantallas con distinto DPI y escritorio con coordenadas negativas.
9. Medir latencia de extremo a extremo, falsos positivos, CPU y memoria en sesiones prolongadas, distintas luces y distancias.
10. Probar elección inicial con una o dos manos, reelección manual, desaparición y cruces; verificar recuperación automática sin intercambiar comandos entre roles.
11. Probar Copiar/Pegar/Deshacer/Rehacer en las aplicaciones cotidianas sobre contenido de prueba: una ejecución por pinza, apertura antes de repetir y compatibilidad de Ctrl+Y. Comprobar bloqueo durante pinza/clic/arrastre, menú, onda, scroll, volumen, pausa y calibración de la principal.
12. Evaluar la comodidad de la L auxiliar y su activación de 0.45 s; verificar arriba/abajo, zona muerta, velocidad limitada y parada al centro. Interrumpir pose, seguimiento o autorización y comprobar que conserva el centro de la imagen y retoma según la zona actual tras confirmar la L, sin exigir volver al centro ni producir una ráfaga.

La frecuencia real depende del equipo y la cámara; no se promete 30 o 60 FPS por configurar ese objetivo. El consumo y la comodidad con dos manos requieren mediciones físicas; disponer de ambos motores no demuestra esos resultados.

## Criterios de cierre de fases

- **Fase 5, implementación local:** dos roles, cuatro pinzas de edición cotidiana y desplazamiento auxiliar en L; completar refinamiento y validación. Ambos roles pueden corresponder a cualquiera de las manos del mismo usuario. La auxiliar está inicialmente habilitada y se controla desde Ajustes o Más; no se afirma implementado un gesto adicional de autorización. Ctrl/Mayús sostenidos y otros gestos quedan pospuestos.
- **Fase 6, automatización avanzada:** pruebas unitarias e integradas, geometría Tk, modelo real sobre cuadros sintéticos y pruebas sin entradas. Queda la aceptación física de esta revisión, incluidas oclusiones y cruces de dos manos; no se marca completa con pruebas sintéticas.
- **Fase 7, empaquetado en curso:** portable sin Python externo, verificación del modelo incluido y SHA-256. Quedan pruebas en Windows limpio, instalador con accesos/desinstalador, firma digital y publicación verificable; requieren evidencias y, para firma/publicación, las decisiones correspondientes.

La firma visual de autor del splash ya es parte del diseño. La firma digital de Windows es un proceso diferente y corresponde a fase 7; esta versión de desarrollo no se presenta como un ejecutable firmado ni como una Release publicada.

## Documentación y limpieza

El README publicado de 1.0 se conserva byte por byte, sin añadirle enlaces. La extensión es `README-2.0.md`, también utilizada como descripción del paquete. Una prueba fija el hash del original y otra protege el splash aprobado.

Se elimina el BAT de compatibilidad redundante de la raíz; se mantienen VBS, herramientas de desarrollo y el respaldo histórico. El portable debe excluir entornos virtuales, pruebas, cachés y registros personales. No se borra `venv` antiguo ni la configuración del usuario durante esta limpieza.

Las capturas reales se registran en [capturas](captures/README.md). El capturador falló en este Windows; no hay imágenes nuevas que se puedan presentar como capturas válidas.
