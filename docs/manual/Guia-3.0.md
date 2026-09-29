# Guía de uso · Bio-Gesture 3.0 experimental

⚓ **Desarrollado por Luics415**

Esta guía acompaña al prototipo **3.0.0.dev4 para Windows**, desde código local o su portable de pruebas. No convierte el ejecutable público 2.7 en una versión 3.0. El control ocular necesita pruebas reales antes de recomendarlo para trabajo cotidiano.

## 1. Empieza con un modo cómodo

Abre **INICIAR_CONTROL.vbs** en el proyecto local ya preparado. La aplicación arranca sin una ventana de consola y conserva la opción de mover el cursor con el índice.

Si usas el portable dev4, extrae todo el ZIP y abre **BioGestureControlPro.exe**; no muevas solo el EXE ni elimines `_internal`. Ese paquete no requiere instalar Python por separado. No es un instalador firmado ni una versión ocular estable.

En **Ajustes → Control** puedes elegir:

| Quiero… | Selección |
|---|---|
| Seguir usando el control manual conocido | Dedo índice. |
| Probar la mirada como cursor | Ojos (experimental). |

El rendimiento óptimo es permanente para ambos usos. No hay un modo que reduzca la cámara o desactive los ojos.

## 2. Antes de calibrar los ojos

**Distancia orientativa para empezar: unos 50–70 cm de la cámara.** Es un punto de partida, no una distancia medida ni garantizada. Puedes consultar el mismo texto en Ajustes: no aparecerá sobre el vídeo.

- Coloca la cámara estable y selecciona un monitor concreto.
- Usa luz que permita ver ambos ojos, evitando reflejos directos.
- Lleva los mismos lentes que utilizarás durante la sesión.
- Busca una postura cómoda; no necesitas dejar de parpadear.

La primera revisión no calibra varios monitores como una única superficie. Tampoco garantiza precisión si los ojos quedan demasiado pequeños, ocultos o desenfocados.

## 3. Calibrar la mirada

Selecciona **Ojos (experimental)** y **Motor ocular → Precisión v2 · OpenVINO**, guarda los ajustes y abre **Calibrar mirada…**. Si tenías otro motor guardado, el programa respeta esa elección hasta que la cambies. El control de la computadora queda en pausa mientras se realiza el proceso.

1. **Antes de iniciar**, revisa el recorte ampliado de los ojos: deben verse ambos, con sus puntos de detección. Ampliar la imagen no mejora su resolución ni demuestra que se detecte bien el iris a través de los lentes.
2. El fondo inicial es **gris mate**. Si la luz del monitor se refleja mucho en tus lentes, puedes seleccionar **Fondo: oscuro** antes de comenzar. Usa luz suave frontal que permita ver los ojos. El fondo no se cambia durante la recogida.
3. **Siéntate cómodo y mantén la cabeza relativamente estable.** No debes quedarte rígido, pero tampoco girar la cabeza para apuntar al objetivo ni acercarte y alejarte durante los puntos.
4. Pulsa **Iniciar** y mueve **solo la mirada** al centro de cada objetivo. La vista ampliada se oculta: no sigas el esqueleto, los puntos de detección ni el cursor del ratón.
5. Espera a que cada objetivo cambie. Parpadea normalmente; no necesitas mostrar las manos ni hacer gestos para confirmar.
6. Completa los **21 objetivos** y después los **13 de comprobación**. Hay puntos cercanos al perímetro; el texto y los botones no los cubren. Se recogen 1.2 s útiles por objetivo de aprendizaje y 0.8 s por comprobación. Estos últimos comprueban el resultado sin volver a enseñar al sistema sus respuestas. Los motores históricos conservan sus propias cantidades.
7. Si la validación se aprueba, cierra Ajustes y activa el control con victoria o el botón de la interfaz.

Puedes cancelar con **Esc**. Un parpadeo pausa la recogida: conserva las muestras válidas del mismo punto y continúa tras volver a estabilizar la mirada. No borra los puntos anteriores. Si faltan muestras durante 20 segundos, el asistente indica el motivo y permite **Repetir punto**. Cambiar el fondo exige empezar de nuevo para no mezclar condiciones de iluminación.

Si aparece **precisión insuficiente**, la recogida terminó pero el resultado no superó la comprobación. El aviso muestra el **error medio**, el **máximo** y el punto con mayor desviación; esos porcentajes representan distancia normalizada en pantalla, no aciertos. El cursor sigue bloqueado. Exporta con **E antes de Reintentar todo** para conservar las mediciones. También puedes volver al índice.

La calibración es obligatoria al comenzar una sesión ocular. No se guarda una identidad facial. Una vez terminada, mirar el teclado o parpadear no obliga a calibrar otra vez. Si notas imprecisión, entra voluntariamente a **Calibrar mirada…** en el menú o Ajustes. Mover la cámara puede hacer necesaria esa corrección.

### Herramientas temporales para investigar un fallo

Dev3 añade un mapa de los objetivos y las predicciones medias de comprobación. **D** abre datos técnicos, **P** permite probar la estimación sin controlar la computadora y **E** exporta voluntariamente las mediciones numéricas. Las mismas acciones tienen botones; no necesitas escribir comandos. P o Esc sale del visor de prueba; Esc fuera de ese visor cierra la calibración.

En dev4, dentro de **P**, **F** alterna entre **Original** (sin suavizado) y **Estabilizado** (mismo filtro del puntero ocular real). La estabilización reduce oscilación, no corrige por sí sola un desplazamiento de posición ni aprueba la calibración. E conserva las medidas originales y la identificación del filtro; no graba el recorrido de P.

El archivo se guarda en la carpeta de datos del programa, dentro de `diagnostics/gaze`; puedes llegar desde **Ajustes → Diagnóstico → Abrir carpeta de diagnóstico**. El asistente muestra la ruta al exportar. No se guardan fotografías ni vídeo, pero el informe sí contiene mediciones oculares: compártelo solo si deseas que se analice. No se usa como perfil ni se carga automáticamente.

No hace falta repetir numerosos intentos: una sesión completa exportada permite analizar el fallo. Lee el [procedimiento de diagnóstico](../DIAGNOSTICO_OCULAR.md). Estos controles de prueba no representan el diseño final.

## 4. Apuntar, hacer clic y arrastrar

En modo ojos, la mirada coloca el cursor y las manos ejecutan los gestos. Para clic izquierdo, junta índice y pulgar de la principal y vuelve a separarlos. Para arrastrar, mantén esa pinza, mira hacia el destino y abre para soltar.

En modo índice se conserva el desplazamiento del cursor mediante ese dedo. Elige este modo cuando necesites una alternativa inmediata al prototipo ocular.

Si se pierde la mirada, el cursor deja de avanzar y no se permiten acciones nuevas. Si ya estabas arrastrando, se conserva brevemente el botón, **hasta 0.32 segundos**, con el cursor quieto, para tolerar un parpadeo corto. Abrir la pinza lo libera inmediatamente; si la mirada no se recupera de forma estable dentro de ese plazo, también se libera.

**Un arrastre aún puede interrumpirse por un parpadeo largo o una pérdida de seguimiento.** La tolerancia es experimental y debe evaluarse durante las pruebas físicas; no deja el botón presionado indefinidamente.

## 5. Ausencia y reposo

Tras **1 minuto y 10 segundos sin mirada válida**, el modo ocular entra en reposo y reduce el seguimiento. Vuelve a colocarte ante la cámara, espera a tener los ojos visibles y realiza **victoria con la mano principal** para reanudar.

Mostrar una mano permite recuperar la frecuencia normal de detección mientras vuelves; las acciones siguen bloqueadas hasta reconocer victoria y una mirada estable.

La calibración no se borra por entrar en reposo. Si cambiaste la cámara de sitio o la posición resulta muy diferente, puedes recalibrar por tu cuenta.

El reposo **no bloquea Windows ni distingue personas**. Cualquier persona que conozca el gesto podría reanudar. No utilices esta función como sustituto del bloqueo de sesión del equipo. En modo índice no se espera detectar ojos.

## 6. Scroll con la L de la auxiliar

Forma una **L con índice y pulgar extendidos** y los otros dedos recogidos. Mantenla aproximadamente medio segundo: ese lugar se convierte en el punto inicial.

| Posición de la L | Resultado |
|---|---|
| Por encima del punto inicial | Scroll continuo hacia arriba. |
| Cerca del punto inicial | Se detiene en una zona neutra. |
| Por debajo del punto inicial | Scroll continuo hacia abajo. |
| Mano abierta o L deshecha | Se detiene y borra la referencia. |

Alejarte más del punto inicial aumenta la velocidad hasta un límite. No es necesario regresar al centro de la cámara. Cada nueva L puede comenzar donde te resulte cómodo. La zona neutra y la sensibilidad se ajustan en el programa.

Perder la detección también detiene el desplazamiento; al recuperar y activar nuevamente la L se establece otra referencia. Los antiguos gestos de scroll de la principal ya no se utilizan en el perfil 3.0.

## 7. Vista de tareas y edición

Con la auxiliar, extiende **índice y corazón juntos**, dejando los otros dedos recogidos. Sostén aproximadamente **0.65 segundos** para abrir **Vista de tareas de Windows (Windows + Tab)**. Deshaz el gesto antes de volver a ejecutarlo. Mantener los dedos juntos ayuda a distinguirlo de la victoria abierta de la principal.

Las pinzas de copiar, pegar, deshacer y rehacer se conservan. El menú radial sigue disponible y los roles no obligan a que una mano concreta sea izquierda o derecha.

## 8. Si algo no responde bien

- **No acepta un punto:** mira su centro, comprueba luz/reflejos y repite el punto. Si necesitas cambiar la posición o el fondo, reinicia la calibración para que todos los puntos compartan condiciones.
- **Falla la precisión al terminar:** no sigas el punto con la cabeza. Mantén una postura cómoda y estable, mueve solo la mirada y revisa el error medio/máximo. No se habilita el control saltándose esta comprobación.
- **Se ve oscuro o hay reflejos:** comprueba la vista ocular antes de iniciar. Prueba gris mate con luz frontal suave; el fondo oscuro puede ayudar si el propio monitor se refleja. Ninguna opción garantiza eliminar reflejos de los lentes.
- **El cursor se siente impreciso:** repite la calibración desde el menú o vuelve al índice.
- **No reanuda tras ausencia:** primero recupera una mirada visible y estable; después haz victoria.
- **La L no desplaza:** espera su activación y sepárala verticalmente de su propio punto inicial; no del centro de la imagen.
- **Hay lentitud o demasiado consumo:** el programa mantiene el modo óptimo; ajusta la cámara o cierra aplicaciones externas antes de reducir la calidad del control.
- **Necesitas detener todo:** utiliza la pausa del programa; el atajo de emergencia existente es **Ctrl + Alt + F12**.

El vídeo habitual permanece limpio, con dibujos opcionales de manos y el menú radial. Las indicaciones de calibración se muestran solo en su ventana dedicada. El procesamiento es local; no se envían las imágenes a servicios externos.

---

⚓ **Desarrollado por Luics415**

La precisión ocular, los lentes y el comportamiento térmico siguen pendientes de validación física. Linux y macOS se abordarán en versiones futuras.
