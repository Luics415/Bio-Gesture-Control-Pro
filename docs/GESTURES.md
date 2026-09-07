# Gestos y perfiles

La versión de desarrollo **2.0.0-dev.7** utiliza **una mano principal y una auxiliar**. `ADMIN/INVITADO` son roles de control, no personas diferentes ni lateralidades fijas. La primera detección válida de una sola mano elige la principal, sin mantener una pose ni esperar un segundo. Si aparecen ambas al iniciar, basta retirar una y recibir un cuadro válido con la elegida. La otra queda asignada como auxiliar. **Más → Reelegir mano principal** permite cambiar la elección manualmente.

Los roles se conservan y recuperan el seguimiento automáticamente después de perder detección. Una observación solapada puede omitirse, pero ya no deja un bloqueo permanente de identidad ni exige retirar ambas manos. La principal conserva cursor, clics y gestos existentes; la auxiliar tiene comandos propios y no toma el cursor.

## Controles principales

| Pose o movimiento | Uso | Valor inicial |
| --- | --- | --- |
| Posición del índice, punto 8, sin exigir otros dedos doblados | Cursor; un gesto exclusivo de menú/pausa/onda/scroll/volumen tiene prioridad | Zona activa 12%–88% en ambos ejes |
| Pulgar + índice, puntos 4–8 | Cerrar presiona; abrir suelta: clic normal. Mantener y mover: arrastre | Sin espera artificial de pulsación; 0.35 s solo cambia el indicador visual de arrastre |
| Pulgar + corazón, puntos 4–12 | Clic derecho en la posición del índice | Una ejecución hasta abrir |
| Pulgar + anular y movimiento vertical | Subir la mano aumenta volumen; bajarla lo reduce; quieta no repite | Sensibilidad 1.5; zona muerta de movimiento 0.025 palmas |
| Índice y corazón juntos; pulgar recogido, anular y meñique doblados | Pareja extendida: desplazar arriba; pareja doblada y separada del anular: abajo | Espera inicial 0.7 s; 6 pasos de rueda por segundo |
| Victoria: índice y corazón extendidos y separados; anular y meñique doblados, pulgar separado del índice y sin tocar corazón/anular | Alternar pausa de acciones; apoyar el pulgar en el anular impide reanudar | Mantener 2 s y soltar antes de repetir |
| Pulgar extendido y los otros cuatro dedos doblados, sin pinza | Abrir menú radial; no exige apuntar verticalmente hacia arriba | Mantener 0.8 s |
| Mantener la pose de pulgar y moverlo desde el punto donde se abrió el menú | Elegir sector; regresar al centro para rearmar | Mantener selección 1 s |
| **Mano abierta relajada, desplazamiento alternado izquierda-derecha** | **Ventana normal ⇄ fija transparente; también con el control pausado** | 4 recorridos y 3 inversiones de dirección; al menos 0.50 palmas por recorrido dentro de 2.2 s |

Las cifras son valores iniciales de `Settings`, no una calibración universal. La pinza cierra por debajo de **0.25 palmas** y abre desde **0.36 palmas**; entre ambos valores conserva el estado. Si varias pinzas nuevas resultan cercanas, se elige la más próxima. Una pinza izquierda o de volumen ya iniciada conserva su control hasta abrir o hasta que la interrumpa un gesto de mayor prioridad.

El clic izquierdo usa el mismo ciclo que un mouse: pulsación al cerrar la pinza y liberación al abrirla, sin exigir una pose especial de apertura. No existe un clic sintético adicional tras soltar. Mientras se mantiene la pinza, mover el índice arrastra desde la posición actual del cursor. Un cambio de pose, pausa o pérdida de seguimiento siempre libera el botón; esa liberación puede ser interpretada por la aplicación destino como el final del clic o arrastre. El desplazamiento es continuo mientras se mantiene su pose; cambiar entre arriba y abajo vuelve a exigir la espera inicial. La cantidad de líneas desplazadas por un paso de rueda depende de Windows y de la aplicación.

Solo muestras válidas, recientes y asignadas a su rol pueden producir acciones. La onda de la principal se evalúa antes de sus demás gestos, pero una pinza la cancela y conserva su comportamiento de mouse o volumen. Una mano abierta quieta, su primer recorrido o un pulgar momentáneamente dudoso no bloquean el cursor. La onda consume el movimiento al confirmar dos recorridos con una inversión real de dirección, hasta completar la secuencia; un barrido en una sola dirección no congela el cursor. Victoria, menú, pinzas y scroll conservan estados exclusivos. La pinza 8–4 mantiene el seguimiento del índice y no se descarta por tener otros dedos extendidos; el clic derecho tampoco debe confundirse con victoria.

Al perder seguimiento, se liberan los botones retenidos y se cancela el gesto pendiente; la onda puede conservar su intento durante un hueco máximo de 0.15 s, sin contar movimiento no observado. Si se interrumpió una pinza izquierda, debe abrirse antes de iniciar otra. La pérdida de cámara no demuestra que se soltó la pose: clic derecho, victoria y los comandos auxiliares conservan sus bloqueos hasta una liberación reconocida. La onda, en cambio, usa una espera antirrepetición de 0.30 s y no exige soltar la mano. Un menú interrumpido exige soltar el pulgar antes de abrir otro. La pausa mantiene la detección para reconocer victoria y reanudar, y para cambiar únicamente el modo de ventana con la onda. **Más → Apagar cámara** apaga el dispositivo por separado.

## Comandos de la mano auxiliar

La auxiliar está **habilitada por defecto**, con opción de deshabilitarla en Ajustes o Más. Cada pinza debe mantenerse **0.45 s**; emite un único comando y exige abrir antes de repetir. Comparte los umbrales de cierre/apertura de pinza de los ajustes, pero nunca genera puntero, clic ni arrastre.

| Pinza | Comando | Atajo enviado |
| --- | --- | --- |
| Pulgar–índice, 4–8 | Copiar | Ctrl+C |
| Pulgar–corazón, 4–12 | Pegar | Ctrl+V |
| Pulgar–anular, 4–16 | Deshacer | Ctrl+Z |
| Pulgar–meñique, 4–20 | Rehacer | Ctrl+Y |

Este mapa de edición cotidiana sustituye Guardar, Buscar, Terminal y Paleta de la revisión anterior. No depende del perfil de la principal, no abre un editor ni detecta automáticamente la aplicación: los atajos llegan a la **ventana en primer plano**. Funcionan en las aplicaciones que los reconozcan, no solo en VS Code. **Rehacer envía Ctrl+Y**, aunque algunas aplicaciones requieren otra combinación o usan Ctrl+Y para una acción diferente.

Se bloquean las acciones auxiliares durante pinza/clic/arrastre, menú, onda, scroll, volumen o pausa de la principal, así como al configurar, calibrar, cambiar cámara o cerrar. Una pinza que todavía no se ejecutó necesita un nuevo periodo continuo de 0.45 s después de ese bloqueo. Una ya ejecutada conserva su bloqueo hasta una apertura observada: perder la mano o deshabilitarla no autoriza repetirla. La auxiliar ya asignada puede actuar sola si la principal sale momentáneamente de cámara, siempre con control activo y sin una operación incompatible. No se añaden gestos para mantener Ctrl o Mayús presionados; estos modificadores sostenidos y otros gestos quedan pospuestos.

### Desplazamiento continuo con L

La pose de la auxiliar es **pulgar e índice claramente abiertos, con corazón, anular y meñique doblados**. Dev.6 admite un ángulo visible de **55–125°**, evaluado en el plano de la imagen, y leve curvatura natural. La profundidad estimada no debe convertir por sí sola una silueta de L en un ángulo agudo; siguen exigiéndose separación suficiente de pulgar/índice y los otros tres dedos recogidos. Su activación exige **0.45 s** de muestras continuas en L. Al completarse se compara el centro de la palma (promedio vertical de muñeca y bases de los cuatro dedos) con el centro fijo de la imagen de cámara. No se captura una referencia al activar ni se utiliza el cursor. La comodidad y precisión todavía requieren validación física continuada con cámara real.

| Posición de la palma manteniendo la L | Desplazamiento |
| --- | --- |
| Banda central de la imagen: entre 45 % y 55 % de su altura | Se detiene |
| Por encima del 45 % de altura | Arriba: pasos de rueda positivos |
| Por debajo del 55 % de altura | Abajo: pasos de rueda negativos |
| Más alejada del centro | Mayor velocidad, limitada por `Settings.scroll_rate` |

La velocidad depende de la distancia vertical al centro, no de repetir sacudidas. Fuera de la banda neutra parte del **25 % de `Settings.scroll_rate`** y aumenta linealmente hasta el 100 % en los bordes de imagen; dentro de la banda sigue siendo cero. Con el límite inicial de **6 pasos de rueda por segundo**, resulta aproximadamente **1.5–6 pasos/s**. Esto evita una velocidad casi nula y esperas excesivas junto al borde neutro, sin convertir ruido dentro de él en desplazamiento. No se modifica el gesto, la espera de 0.7 s ni el funcionamiento del scroll de la principal. La dirección arriba/abajo corresponde a la imagen; las inversiones del cursor no cambian el sentido del scroll auxiliar. La cantidad de líneas por paso depende de Windows y de la aplicación.

Para una coordenada vertical de palma `y` normalizada entre 0 y 1, fuera de la banda la magnitud es `scroll_rate × (0.25 + 0.75 × min(1, (abs(0.5 − y) − 0.05) / 0.45))`. Se integra tiempo transcurrido y solo se emiten pasos completos: no se manda una rueda en cada cuadro. La banda central borra restos fraccionarios inmediatamente.

Dejar la L, perder la mano, deshabilitar la auxiliar, pausar, quedar bloqueada por una acción prioritaria o reiniciar el motor descarta temporizadores y restos fraccionarios de rueda. El centro siempre permanece en la mitad de la imagen. Volver a la L exige otros 0.45 s; después desplaza según la zona actual, incluso al empezar directamente arriba o abajo, sin volver al centro ni descargar movimiento acumulado. Volver a la zona muerta detiene el scroll; cambiar de dirección tampoco arrastra restos de la dirección anterior. Las pinzas de edición y la L son usos excluyentes de la auxiliar.

## Orientación y límites actuales

La escala de referencia es el promedio de dos distancias: muñeca–base del corazón y base del índice–base del meñique. Se calculan con la proporción real de los píxeles y la profundidad estimada por MediaPipe. No son centímetros físicos. La extensión de los dedos se basa en sus articulaciones y distancia a la muñeca, de modo que girar la mano no invierte automáticamente extendido/doblado. Las pruebas incluyen giros y cambios sintéticos de escala; las oclusiones y ángulos reales todavía requieren validación con cámara.

La pareja para scroll debe separar sus puntas menos de 0.28 palmas. Para scroll hacia abajo, además, la punta del índice debe separarse más de 0.38 palmas de la del anular, reduciendo la confusión con un puño normal. Victoria exige más de 0.5 palmas entre las puntas de índice/corazón y entre pulgar/índice. Estos umbrales geométricos no garantizan que todas las anatomías produzcan la misma comodidad.

La onda utiliza una apertura más relajada que los otros gestos: acepta **al menos tres de los cuatro dedos largos abiertos**, incluso ligeramente curvados, sin exigir un pulgar extendido. Ya no exige la antigua comprobación de palma frontal; necesita landmarks suficientemente fiables y movimiento lateral alternado. Esta tolerancia solo modifica la onda, no la geometría de clic, scroll o victoria. Arriba/abajo de volumen y desplazamiento lateral de ventana se refieren a los ejes de la imagen; la rotación de la mano no gira esos ejes. Las opciones de invertir horizontal/vertical afectan al cursor.

Solo se aceptan muestras nuevas de las manos asignadas, con confianza mínima inicial de 0.65 y antigüedad máxima de 0.35 s. La etiqueta derecha/izquierda aporta evidencia para recuperar cada rol, nunca un permiso fijo de uso. Una muestra repetida no avanza temporizadores. Una interrupción mayor de 0.35 s reinicia el reconocimiento y aplica las liberaciones anteriores. La mano debe conservar suficiente tamaño y visibilidad: una escala calculada inferior a 5 píxeles se descarta. La recuperación automática de roles no equivale a identificación biométrica ni garantiza la resolución de cualquier oclusión real.

## Gesto de la ventana

Se conserva el gesto original solicitado: **mano extendida, moviéndola a derecha e izquierda**. Se sigue el centro de las bases de los cuatro dedos largos, una referencia estable de la palma. Se cuentan **cuatro recorridos laterales con tres inversiones reales de dirección**, empezando hacia cualquier lado. Cada recorrido debe alcanzar 0.50 palmas, con un mínimo de 12 píxeles en la imagen, dentro de una ventana de 2.2 s que empieza al detectar movimiento inicial. El desvío vertical desde el inicio debe mantenerse dentro de 0.9 palmas. Superar el plazo, ese desvío o un cambio excesivo de escala reinicia el intento; un movimiento insuficiente no cuenta como recorrido.

Mover en una sola dirección no basta. Internamente se cuenta `ONDA 1/4`, `ONDA 2/4`, `ONDA 3/4` y cambio completado; esos estados no son instrucciones que deban aparecer en el overlay final. El primer recorrido permite seguir moviendo el índice; desde el segundo se reserva el movimiento hasta completar la onda. Se toleran huecos de seguimiento de hasta 0.15 s, sin contarlos como recorridos; saltos alternos con menos de 0.08 s entre recorridos reinician el intento.

Después de cambiar el modo se aplica una espera antirrepetición de **0.30 s**, sin contar movimiento residual. Después puede comenzar otra secuencia completa **sin cerrar ni soltar la mano**. El cursor vuelve a estar disponible durante esa espera si el control está activo; una pinza reconocida sigue disponible inmediatamente. Perder seguimiento o pausar no omite la espera antirrepetición.

Con la cámara encendida, la onda también funciona **en pausa**, pero solo cambia la ventana: no reanuda las acciones ni mueve el cursor. Victoria sigue siendo el gesto para reanudar el control. Los diálogos de ajustes/calibración mantienen su bloqueo de acciones hasta cerrarlos.

En la interfaz de pruebas, el modo normal tiene bordes; el fijo permanece encima de otras ventanas, sin bordes y con opacidad inicial de 85%, configurable. Puedes arrastrarla desde el espacio libre de la barra superior. El área se mantiene en **550×375**: barra de 28 píxeles, cámara de **550×335** y estado de 12 píxeles. El video conserva su proporción. **Más** y la bandeja permiten cambiar el modo sin hacer el gesto y recuperar la vista oculta. Esta interfaz sigue siendo de pruebas, no el diseño operativo final aprobado.

## Menú radial conservado

El dibujo permanece centrado en la vista con **ocho etiquetas cortas y una barra horizontal de progreso**, sin texto central, arco ni porcentaje. La selección usa el desplazamiento del pulgar respecto a su posición cuando se abrió el menú, aunque esa posición de la mano esté cerca del borde de cámara. Desde 0.65 palmas de desplazamiento se selecciona una opción; para rearmar hay que regresar a menos de 0.45 palmas. El intervalo intermedio cancela la selección activa. Cada sector exige 1 s continuo y cambiar de sector reinicia ese tiempo. El dibujo no ejecuta comandos al hacer clic sobre él.

La selección se ejecuta una vez y requiere volver al centro, también después de entrar en un submenú o usar `VOLVER`. Eliminar la pose de pulgar cierra el menú; la siguiente apertura empieza en `PRINCIPAL`.

Se conservan los cinco menús originales, sus identificadores de comando y su orden. Los rótulos visibles son breves: `ADMIN` aparece como **Tareas** y abre el Administrador de tareas; `MAYUS`, como **Mayúsculas**, alterna Bloq Mayús; `PESTANYA`, como **Ventanas**, cambia de ventana. En la siguiente tabla se usan los identificadores internos. En cada fila, las ocho opciones avanzan en sentido horario desde la derecha: derecha, abajo-derecha, abajo, abajo-izquierda, izquierda, arriba-izquierda, arriba y arriba-derecha.

| Menú | Opciones en ese orden |
| --- | --- |
| PRINCIPAL | SISTEMA · EDICION · WEB · MEDIA · MAYUS · PESTANYA · INICIO · ESC |
| SISTEMA | CONFIG · ADMIN · BLOQUEAR · BUSCAR · VOL+ · VOL- · MUTE · VOLVER |
| EDICION | COPIAR · PEGAR · DESHACER · REHACER · CORTAR · TODO · DELETE · VOLVER |
| WEB | NUEVA T · CERRAR T · RECARGAR · REGRESAR · AVANCE · FAVORITOS · DESCARGA · VOLVER |
| MEDIA | PLAY/PAUSE · SIGUIENTE · ATRAS 10s · ADELAN 10s · MUTE · FULLSCREEN · SUBTITULOS · VOLVER |

## Perfiles

| Perfil | Finalidad |
| --- | --- |
| Global | Navegación y edición común del escritorio, menú Inicio, Escape, audio global |
| VS Code | Búsqueda en el editor y pantalla completa mediante sus atajos |
| Navegador | Pestañas, navegación, búsqueda y acciones del navegador |
| Multimedia | Reproducción, volumen y navegación multimedia |

El perfil se elige manualmente. Los atajos actúan sobre la aplicación en primer plano; los comandos de audio globales utilizan los controles de Windows. Acciones como subtítulos o pantalla completa dependen del reproductor seleccionado y no son universales del sistema operativo.

La etiqueta histórica `ADMIN` del menú Sistema abre el **Administrador de tareas de Windows**. No representa la autorización de la segunda mano. `CONFIG` abre ajustes y pausa las acciones; `BLOQUEAR` bloquea la sesión al terminar la selección, sin otro diálogo de confirmación. `BUSCAR` usa Windows+S en Global/Multimedia y Ctrl+F en Navegador/VS Code. `VOL+`, `VOL-`, `MUTE`, reproducción y siguiente pista usan controles multimedia de Windows.

`ATRAS 10s`, `ADELAN 10s`, `SUBTITULOS` y la pantalla completa del perfil Multimedia conservan los atajos de YouTube (`j`, `l`, `c`, `f`) y requieren ese reproductor en primer plano. Los tres primeros no están habilitados en los otros perfiles. Navegador y VS Code utilizan F11 para pantalla completa; en Global esa opción no está habilitada. Si se selecciona una acción incompatible con el perfil, la aplicación pausa el control y registra el motivo, consultable en Ajustes → Diagnóstico. La vista limpia no superpone ese mensaje a la cámara.

Las categorías Edición y Web conservan sus combinaciones: Ctrl+C/V/Z/Y/X/A, Suprimir; Ctrl+T/W, F5, Alt+Izquierda/Derecha, Ctrl+D/J. `MAYUS` alterna Bloq Mayús, `INICIO` pulsa Windows y `ESC` pulsa Escape. La etiqueta histórica `PESTANYA` conserva **Alt+Tab: cambia de ventana**, no Ctrl+Tab. Cambiar de perfil no añade nuevas opciones al menú. Copiar, Pegar, Deshacer y Rehacer también tienen pinzas propias en la auxiliar; no se eliminan del menú Edición ni se añaden posiciones al radial. El mapa auxiliar no depende del perfil principal.

## Diferencias intencionales respecto a 1.20.36

Se conservan cursor, clics, arrastre, volumen, scroll, victoria, pulgar/menú, las 40 posiciones de menú y la onda de cambio de ventana. La primera revisión recupera el seguimiento continuo del índice y elimina la restricción de pose y lateralidad. Fix.3 añadió comandos de la auxiliar, recuperación automática de roles y onda de cuatro recorridos con rearme temporizado. Fix.4 conservó el comportamiento de la principal y la elección de roles, sustituyó el mapa auxiliar por edición cotidiana y añadió el desplazamiento en L. Dev.5 cambia la L al centro fijo de la imagen, con banda neutra de 45–55 %. Dev.6 conserva principal y roles, flexibiliza la L visible sin aceptar la palma abierta como L y establece una velocidad mínima fuera de la banda para que la respuesta no tienda a cero al salir apenas de ella. Clic y arrastre usan pulsación/liberación reales, sin un límite breve que haga desaparecer el clic. Los gestos competidores mantienen exclusividad; las medidas se ajustan a escala y orientación de la mano.

El clic izquierdo ya no espera los 0.30/0.35 s del reconocimiento anterior de arrastre: responde al cierre. El indicador cambia a ARRASTRE a los 0.35 s, sin modificar el estado real del botón. La pausa usa 2 s, el scroll 0.7 s y seleccionar en el menú 1 s. La apertura del menú mantiene 0.8 s. El volumen sigue el desplazamiento relativo y el scroll usa tiempo transcurrido.

`CONFIG`, `ADMIN`, `BLOQUEAR`, `BUSCAR`, `VOL+` y `VOL-` ahora tienen implementación. Reproducción, mute y siguiente dejan de depender de las letras de YouTube y utilizan controles multimedia de Windows. Los atajos específicos de reproductor se activan expresamente con el perfil Multimedia. Esta compatibilidad de intención no garantiza que cada aplicación responda igual a una tecla multimedia; se comprobará en las sesiones físicas.

## Preparación para usarlo

Abre el programa pausado, configura cámara y pantalla y muestra solo la mano que usarás como principal. No se exige sostenerla ni esperar un segundo. Realiza la calibración con luz uniforme: la segunda captura válida guarda la zona automáticamente y cierra el diálogo hijo, pero Ajustes permanece abierto. Cierra Ajustes y pulsa Activar antes de probar los bordes; Cancelar en Ajustes no revierte la calibración guardada. Empieza por cursor, clic y pausa; después añade menú, volumen y cambio de ventana. Prueba las pinzas auxiliares sobre contenido de prueba en la aplicación que uses y comprueba su atajo de Rehacer; después evalúa la L, la parada al centro y la cancelación al soltarla. **Ctrl+Alt+F12** es el atajo de emergencia. Las sesiones reales deberán validar comodidad, falsa activación y compatibilidad con el equipo antes de considerar terminada la fase 6.

Desde dev.7 el área de cámara contiene únicamente video, puntos opcionales y radial: **sin mensajes, indicaciones ni estado superpuestos**, tanto en el EXE como desde el código o con `--diagnostics`. **Dibujar puntos de mano** sigue controlando por sí sola los puntos y conexiones de ambas manos. Está desmarcada en ajustes nuevos y respeta una preferencia anterior marcada; no habilita textos. `--clean-ui` y `--diagnostics` permanecen disponibles, pero ninguno activa ayudas dentro de cámara. Los diagnósticos se consultan en Ajustes. Cámara, controles de ventana, ajustes y diálogos separados de fallos de arranque permanecen disponibles; esto no supone aprobar un rediseño visual nuevo. El splash de ancla y la firma **Desarrollado por Luics415** se conservan al iniciar. La [guía de uso 2.0](../README-2.0.md) contiene una prueba paso a paso de L arriba–centro–abajo y las 40 opciones radiales explicadas; el [manual de 17 páginas](manual/Manual-de-usuario.pdf) incorpora diagramas y la firma aprobada al final, sin fotografías privadas.

El inicio normal desde EXE, fuente o VBS tampoco muestra estado en la franja inferior. Solo `--diagnostics` explícito muestra ese estado **fuera del área de cámara**; `--clean-ui` conserva la franja sin estado. Esto no modifica los comandos ni el reconocimiento.
