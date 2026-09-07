# Bio-Gesture Control Pro · Guía 2.0

**Desarrollado por Luics415** ⚓

Bio-Gesture permite navegar y realizar acciones en el escritorio de Windows con las manos y una cámara web. No está limitado a una aplicación: combina cursor, clics, desplazamiento, atajos y controles del sistema. La aplicación que esté en primer plano decide cómo interpreta cada atajo.

Esta guía describe **2.0.0-dev.7**, una versión de desarrollo, y sus diferencias respecto a 1.0. El [README original](README.md) conserva intactas su explicación e imágenes históricas; sus instrucciones de instalación no son las de 2.0. El ancla aprobada y el splash con **Desarrollado por Luics415** se mantienen sin rediseñar.

Dev.6 corrigió el control de los puntos de ambas manos y la respuesta de la L auxiliar cerca de la zona central. Dev.7 elimina los textos y ayudas del área de cámara también al ejecutar desde el código o con diagnóstico, y amplía el manual ilustrado. No cambia los gestos de la principal ni la elección de roles. El estado comprobado de cada paquete y las pruebas pendientes están en [Validación](docs/VALIDATION.md) y [Distribución](docs/DISTRIBUTION.md). Esta guía no certifica una instalación en Windows limpio ni una versión final firmada.

También tienes un [manual ilustrado en PDF de 17 páginas](docs/manual/Manual-de-usuario.pdf), con diagramas de las manos y la firma aprobada al final. Se conserva en el repositorio para poder consultarlo al descargar el código. En el portable se encuentra como **Manual-de-usuario.pdf**, junto al EXE: abre esa copia local, no la ruta del repositorio del enlace anterior. Sus diagramas no son capturas de sesiones personales.

## Contenido

- [Instalación portable y primer arranque](#instalación-portable-y-primer-arranque)
- [Ventana, pausa y segundo plano](#ventana-pausa-y-segundo-plano)
- [Elegir y recuperar las dos manos](#elegir-y-recuperar-las-dos-manos)
- [Gestos de la mano principal](#gestos-de-la-mano-principal)
- [Mano auxiliar: edición y desplazamiento en L](#mano-auxiliar-edición-y-desplazamiento-en-l)
- [Menú radial: las 40 posiciones](#menú-radial-las-40-posiciones)
- [Perfiles y aplicación en primer plano](#perfiles-y-aplicación-en-primer-plano)
- [Ajustes, pestaña por pestaña](#ajustes-pestaña-por-pestaña)
- [Calibrar una zona cómoda](#calibrar-una-zona-cómoda)
- [Prioridades y seguridad de los gestos](#prioridades-y-seguridad-de-los-gestos)
- [Solución de problemas](#solución-de-problemas)
- [Actualizar, conservar ajustes y retirar el portable](#actualizar-conservar-ajustes-y-retirar-el-portable)
- [Privacidad, alcance y desarrollo](#privacidad-alcance-y-desarrollo)

## Instalación portable y primer arranque

El paquete está preparado para **Windows 10/11 de 64 bits, arquitectura x64**. Incluye Python, las bibliotecas y el modelo de detección. Para usar el portable no necesitas instalar Python, Git, paquetes ni ejecutar comandos. No es un instalador ni un EXE independiente de los demás archivos.

1. Recibe el ZIP de la revisión que vas a probar. Consulta su versión y las comprobaciones que lo acompañan; no confundas un paquete anterior con dev.7.
2. Usa **Extraer todo** y elige una carpeta donde puedas guardar tus programas. No abras el EXE directamente dentro del ZIP.
3. Dentro de la carpeta extraída, abre **BioGestureControlPro.exe** con doble clic. Conserva la carpeta `_internal` a su lado: contiene recursos indispensables.
4. Espera el splash del ancla y la firma del autor. El arranque normal no necesita mostrar el símbolo del sistema.
5. Con ajustes nuevos, abre **pausado**, con cámara 0, vista espejo y auxiliar habilitada. Entra en **Ajustes** para elegir cámara y monitor antes de activar.
6. Deja visible solo la mano que quieres usar como principal. En cuanto se detecte un cuadro válido queda elegida; después puedes mostrar ambas.
7. Cierra Ajustes y pulsa **Activar**. Empieza en un documento de prueba: cursor, clic, pausa y, después, los demás gestos.

Si no es la cámara correcta, cambia **Ajustes → Cámara → Índice de cámara**, guarda y espera la reconexión. La numeración depende del equipo; 0 suele ser la primera disponible, pero no garantiza que sea la integrada. Resolución y FPS son solicitudes: el dispositivo puede entregar otros valores.

No se usa BAT ni VBS para abrir el portable. Puedes crear un acceso directo de Windows al EXE, manteniendo la carpeta completa en su ubicación. El programa no añade inicio automático, servicios ni tareas programadas.

El binario de desarrollo no tiene firma digital Authenticode. El ancla y la firma visual del splash **no sustituyen** esa firma. No desactives las protecciones de Windows para probarlo; ante un aviso, comprueba la procedencia y el paquete recibido. Firma digital, instalador y publicación se gestionan por separado.

## Ventana, pausa y segundo plano

La ventana mide **550 × 375 píxeles**: barra superior de 28, área de cámara de 550 × 335 y franja inferior de 12. El video conserva su proporción, por lo que pueden aparecer márgenes. Cambiar la resolución de captura no agranda la ventana.

Los controles principales son **Activar/Pausar**, **Ajustes** y **Más**. El radial se maneja con gestos: sus rótulos no son botones para hacer clic con el mouse.

| Control | Qué hace | ¿La cámara sigue encendida? |
| --- | --- | --- |
| Pausar | Detiene acciones y suelta botones retenidos. Mantiene detección para victoria y cambio de ventana | Sí |
| Activar | Reanuda acciones; requiere cámara disponible y diálogos de configuración cerrados | Sí |
| Más → Ocultar en la bandeja | Oculta la ventana; si estaba activo, sigue actuando en segundo plano | Sí |
| Más → Apagar cámara | Pausa y cierra la captura del dispositivo | No, al terminar el cierre |
| Más → Encender cámara | Reconecta; el control permanece pausado hasta que lo actives | Sí, tras conectarse |
| Más → Salir, bandeja → Salir o cerrar con X | Libera entradas, cierra cámara e integraciones y termina el programa | No |

**Ocultar no significa pausar ni apagar.** Para liberar la webcam utiliza Apagar cámara o Salir. Para detener gestos sin perder la posibilidad de reanudar con la mano utiliza Pausar.

### Recuperación rápida

**Ctrl+Alt+F12** pausa las acciones y recupera la ventana, siempre que el atajo global esté disponible. Conserva teclado y mouse al alcance durante las primeras pruebas. Desde el ancla de la bandeja de Windows puedes mostrar la cámara, pausar, alternar normal/fija, encender/apagar cámara, abrir Configuración o salir. Si no ves el icono, revisa los iconos ocultos junto al reloj. **Alt+M**, con la ventana del programa enfocada, abre Más.

### Ventana normal y fija transparente

- **Normal:** tiene bordes y opacidad completa.
- **Fija:** sin bordes, encima de otras ventanas y con opacidad inicial del **85 %**, ajustable. La transparencia afecta a la ventana completa; no implica que los clics la atraviesen.

Alterna con **Más → Fijar ventana transparente / Volver a ventana normal**, con la bandeja o con la onda de la principal. Arrastra desde el espacio libre de la barra superior para recolocarla. La onda también cambia el modo estando pausado; no activa el control.

### Vista limpia y puntos de las manos

El área de cámara conserva únicamente el video, los puntos opcionales y el radial cuando se utiliza. **No muestra mensajes, estados ni indicaciones**, tanto en el EXE como al ejecutar desde el código o con `--diagnostics`. Los controles de la barra y los diálogos de Ajustes permanecen disponibles.

**Ajustes → Escritorio → Dibujar puntos de mano** controla por sí sola los puntos y conexiones de **ambas manos**, también en vista limpia. Está desmarcada en una configuración nueva. Si ya la tenías marcada, se respeta esa preferencia: actualizar no la desactiva. Marcarla no activa mensajes ni ayudas de diagnóstico. Guarda los ajustes, espera la reconexión y vuelve a activar cuando quieras continuar.

Métricas y estado se consultan en **Ajustes → Diagnóstico**. Las opciones técnicas `--clean-ui` y `--diagnostics` se conservan, pero **ninguna habilita textos dentro de la cámara**. Solo `--diagnostics`, solicitado expresamente, añade un estado en la franja inferior **fuera del video**; el inicio normal desde EXE, fuente o VBS no lo muestra. `--clean-ui` mantiene esa franja sin estado. No necesitas estas opciones para el uso normal. Los errores que impiden arrancar pueden mostrar un diálogo separado para que puedas identificar el problema.

## Elegir y recuperar las dos manos

Principal y auxiliar son **roles**, no identidades personales ni manos derecha/izquierda obligatorias. Cualquiera de tus manos puede ocupar cualquiera de los roles. La etiqueta histórica «ADMIN» del menú no elige roles: corresponde al Administrador de tareas.

1. Al iniciar la detección, muestra **solo la mano elegida como principal**. No exige mantener una pose ni esperar un segundo; basta la primera detección válida.
2. Si empezaste con ambas visibles, retira una momentáneamente y deja que se detecte la elegida. Luego vuelve a mostrar la segunda.
3. La principal controla el cursor y conserva sus gestos. La auxiliar añade sus propias pinzas y la L, **sin tomar el cursor**.

Tras perder detección, el sistema intenta recuperar los roles automáticamente. No hay que retirar ambas manos ni reiniciar por cada interrupción. Si se cruzan, se ocultan o no se distinguen de forma fiable, algunas observaciones se descartan para no inventar acciones. Esto no es identificación biométrica ni garantiza resolver cualquier solapamiento real.

Para intercambiar papeles usa **Más → Reelegir mano principal**. Pausa el control y borra la elección anterior; deja una sola mano visible para elegirla y pulsa Activar cuando esté lista. Reiniciar la cámara también inicia una nueva selección de roles.

La auxiliar viene habilitada. Puedes desactivarla en **Más → Desactivar mano auxiliar** o desmarcando **Ajustes → Escritorio → Comandos de mano auxiliar**. Bloquea sus comandos; no cambia la principal ni apaga la cámara. La activación/desactivación manual es el mecanismo actual: no existe un gesto nuevo oculto de autorización «admin/invitado».

## Gestos de la mano principal

En las referencias de puntos, **4** es la punta del pulgar, **8** la del índice, **12** la del corazón, **16** la del anular y **20** la del meñique. No necesitas ver los puntos para usar los gestos.

Los tiempos y distancias siguientes son los valores iniciales. Una «palma» es una medida calculada a partir de la mano detectada, no una distancia fija en centímetros.

| Gesto | Acción y forma de terminar |
| --- | --- |
| Mover el índice | Mueve el cursor con la punta del índice. No exige los otros dedos doblados; los gestos exclusivos tienen prioridad |
| Cerrar pulgar–índice, 4–8, y abrir | Clic izquierdo: cerrar presiona el botón y abrir lo suelta, como un mouse. Sin espera artificial para empezar a pulsar |
| Mantener pulgar–índice y mover | Arrastre hasta abrir. El indicador cambia a arrastre a los **0.35 s**; no retrasa la pulsación |
| Pinza pulgar–corazón, 4–12 | Un clic derecho en la posición del índice. Abre antes de repetir |
| Pinza pulgar–anular, 4–16, y mover verticalmente | Subir aumenta volumen; bajar lo reduce. Quieta no repite cambios; abrir termina |
| Índice/corazón juntos y extendidos; pulgar recogido, anular/meñique doblados | Desplazar arriba tras **0.7 s**; continúa mientras mantengas la pose |
| Esa pareja junta, pero doblada y separada del anular; pulgar recogido y otros dedos doblados | Desplazar abajo tras **0.7 s**. Cambiar de dirección reinicia la espera; un puño normal no basta |
| Victoria: índice/corazón extendidos y separados, anular/meñique doblados, pulgar separado del índice y sin tocar corazón/anular | Mantener **2 s** alterna pausa/activación. Suelta antes de repetir; apoyar el pulgar en el anular impide reanudar |
| Pulgar extendido, otros cuatro dedos doblados, sin pinza | Mantener **0.8 s** abre el radial. No exige apuntar el pulgar verticalmente hacia arriba |
| Mantener esa pose y desplazar el pulgar desde donde abriste el menú | Mantener una dirección **1 s** selecciona; vuelve al punto de apertura para otra selección. Dejar la pose cierra |
| Mano abierta relajada con movimiento lateral alternado | **Cuatro recorridos y tres cambios de dirección** dentro de **2.2 s** alternan normal/fija; también pausado |

La pinza cierra por debajo de **0.25 palmas** y abre desde **0.36 palmas**. El margen evita abrir/cerrar por pequeños temblores; ambos límites son ajustables. Un clic izquierdo completado al abrir no añade un segundo clic artificial. Si se pierde la mano, se pausa o cambia una pose incompatible, se libera el botón retenido; si se interrumpió esa pinza, ábrela antes de iniciar otra.

### La onda de cambio de ventana

Abre la mano de forma relajada: se aceptan al menos **tres de los cuatro dedos largos abiertos**, sin exigir el pulgar estirado. Desplaza la palma a un lado, al otro, al primero y al segundo, o empieza al revés. Cada recorrido debe medir al menos **media palma**; no basta mover solo las puntas ni hacer un único barrido.

Mantén la altura aproximadamente estable y la mano visible. El primer recorrido todavía permite mover el cursor; desde el segundo se reserva el movimiento para completar la onda. Tras cambiar de modo hay una espera antirrepetición de **0.30 s**: luego puedes iniciar otra secuencia sin cerrar la mano. Una pinza cancela el intento de onda y conserva su función de clic o volumen.

## Mano auxiliar: edición y desplazamiento en L

### Cuatro pinzas de edición

| Pinza de la auxiliar | Mantener | Acción enviada |
| --- | --- | --- |
| Pulgar–índice, 4–8 | **0.45 s** | Copiar · Ctrl+C |
| Pulgar–corazón, 4–12 | **0.45 s** | Pegar · Ctrl+V |
| Pulgar–anular, 4–16 | **0.45 s** | Deshacer · Ctrl+Z |
| Pulgar–meñique, 4–20 | **0.45 s** | Rehacer · Ctrl+Y |

Cada pinza produce **un comando hasta abrirla**. Mantenerla cerrada no repite. Si se perdió la mano después de ejecutar, volver con la misma pinza tampoco autoriza otra ejecución: primero debe observarse abierta.

Selecciona el contenido y enfoca la aplicación destino antes de Copiar/Pegar. Los cuatro atajos son independientes del perfil de la principal y no abren un editor. Funcionan donde se reconozcan, no solo en VS Code. **Rehacer envía Ctrl+Y**: algunas aplicaciones usan otra combinación o interpretan Ctrl+Y de otra manera. Este mapa sustituye Guardar, Buscar, Terminal y Paleta de revisiones anteriores.

### Desplazamiento continuo con L

Forma una **L con pulgar e índice claramente separados**, aproximadamente en ángulo recto, y recoge corazón, anular y meñique. Se acepta un ángulo visible de **55–125°** con leve curvatura natural; no hace falta forzar una L rígida. Mantén la pose **0.45 s**. Juntar pulgar e índice es una pinza de Copiar, no una L.

El desplazamiento usa el **centro de la palma respecto al centro fijo de la imagen de cámara**, no la punta del índice, el cursor ni el lugar donde empezaste. La palma se estima con la muñeca y las bases de los cuatro dedos. Las zonas se refieren al video, no a la pantalla completa ni a sus márgenes.

| Centro de la palma en la imagen | Resultado manteniendo la L |
| --- | --- |
| Por encima del 45 % de su altura | Desplazamiento arriba |
| Banda central, del 45 % al 55 % | Detenido |
| Por debajo del 55 % de su altura | Desplazamiento abajo |
| Más lejos del centro | Más velocidad, hasta el máximo configurado |

No hacen falta sacudidas: una L quieta **fuera** de la banda desplaza continuamente; una L quieta **dentro** se detiene. Desde dev.6, fuera de la banda parte del **25 % de la velocidad configurada** y aumenta progresivamente hasta el máximo hacia los bordes. Con el valor inicial de 6, equivale aproximadamente a **1.5–6 pasos de rueda por segundo**. Evita una respuesta casi nula al salir apenas del centro. Las líneas por paso dependen de Windows y de la aplicación.

Volver al centro o dejar la L detiene el scroll. Una pinza, pérdida de detección, pausa o acción prioritaria también lo cancela, sin guardar una ráfaga para después. Al recuperarla debes mantenerla de nuevo 0.45 s; puede comenzar directamente arriba o abajo, sin pasar antes por el centro. Las inversiones del cursor no invierten este gesto: arriba/abajo corresponden a la imagen.

### Primera prueba: arriba → centro → abajo

1. Abre un documento o página de prueba con suficiente contenido en ambos sentidos. Colócate aproximadamente a la mitad y deja esa aplicación enfocada.
2. Comprueba control activo, auxiliar habilitada y Ajustes cerrados. Puedes marcar Dibujar puntos de mano durante la preparación; no es un requisito del gesto.
3. Evita pinza, menú, scroll u onda de la principal. Una vez asignados los roles, puedes retirar momentáneamente la principal para aislar la auxiliar; no vuelvas a elegir roles a mitad de la prueba.
4. Forma la L con la palma en el centro del video y mantenla 0.45 s. Debe permanecer sin desplazarse.
5. Sube **la palma completa** manteniendo la L. Por encima de la banda debe desplazar arriba. Una salida pequeña puede tardar una fracción de segundo en completar el primer paso tras confirmar; no se espera una rueda nueva en cada cuadro.
6. Vuelve al centro: debe detenerse. Baja la palma por debajo de la banda y comprueba desplazamiento abajo.
7. Suelta la L mientras desplaza: debe detenerse. Vuelve a formarla directamente abajo, espera su confirmación y comprueba que retoma hacia abajo sin saltos acumulados.

Si no ocurre nada, comprueba que el documento tenga desplazamiento disponible, conserve el foco y no esté en su extremo. Después revisa rol, pose, visibilidad de los dedos recogidos y posición del **centro de palma**, no de la punta del índice. La comodidad debe verificarse en tu cámara; esta guía no certifica cualquier mano o iluminación.

## Menú radial: las 40 posiciones

Abre el radial con el pulgar de la **principal** durante 0.8 s. Manteniendo la pose, desplaza el pulgar en la dirección de una etiqueta y permanece allí **1 s**. La barra horizontal indica el tiempo de selección; cambiar de dirección reinicia la espera.

La referencia es **la posición del pulgar al abrirlo**, no el centro dibujado del radial. Después de ejecutar una acción, entrar en un grupo o volver, regresa a esa posición para preparar otra selección. Dejar la pose cierra el menú; la siguiente apertura empieza en el principal.

Las cinco tablas contienen las **40 posiciones** conservadas, incluidas entradas a grupos y Volver. En todas se avanza en sentido horario desde la derecha. No hay un gesto distinto por comando: comparten apertura, dirección y espera.

### Principal

| Dirección | Etiqueta | Resultado |
| --- | --- | --- |
| Derecha | Sistema | Abre el grupo Sistema |
| Abajo-derecha | Edición | Abre el grupo Edición |
| Abajo | Web | Abre el grupo Web |
| Abajo-izquierda | Multimedia | Abre el grupo Multimedia |
| Izquierda | Mayúsculas | Alterna Bloq Mayús; no mantiene Mayús presionada |
| Arriba-izquierda | Ventanas | Alt+Tab: cambia de ventana, no de pestaña |
| Arriba | Inicio | Pulsa la tecla Windows |
| Arriba-derecha | Escape | Pulsa Esc |

### Sistema

| Dirección | Etiqueta | Resultado |
| --- | --- | --- |
| Derecha | Ajustes | Abre configuración y pausa |
| Abajo-derecha | Tareas | Abre el Administrador de tareas de Windows |
| Abajo | Bloquear | Bloquea la sesión **al completar la selección, sin otra confirmación** |
| Abajo-izquierda | Buscar | Windows+S en Global/Multimedia; Ctrl+F en Navegador/VS Code |
| Izquierda | Volumen + | Sube volumen de Windows |
| Arriba-izquierda | Volumen − | Baja volumen de Windows |
| Arriba | Silenciar | Alterna silencio de Windows |
| Arriba-derecha | Volver | Regresa al principal |

### Edición

| Dirección | Etiqueta | Resultado |
| --- | --- | --- |
| Derecha | Copiar | Ctrl+C |
| Abajo-derecha | Pegar | Ctrl+V |
| Abajo | Deshacer | Ctrl+Z |
| Abajo-izquierda | Rehacer | Ctrl+Y |
| Izquierda | Cortar | Ctrl+X |
| Arriba-izquierda | Seleccionar todo | Ctrl+A |
| Arriba | Eliminar | Suprimir; depende de selección y aplicación |
| Arriba-derecha | Volver | Regresa al principal |

Las pinzas auxiliares no eliminan esos comandos de Edición. Practica con contenido prescindible: Cortar, Eliminar, Deshacer o cerrar una pestaña pueden modificar el trabajo de la ventana activa.

### Web

| Dirección | Etiqueta | Resultado |
| --- | --- | --- |
| Derecha | Nueva pestaña | Ctrl+T |
| Abajo-derecha | Cerrar pestaña | Ctrl+W |
| Abajo | Recargar | F5 |
| Abajo-izquierda | Atrás | Alt+Izquierda |
| Izquierda | Adelante | Alt+Derecha |
| Arriba-izquierda | Favoritos | Ctrl+D |
| Arriba | Descargas | Ctrl+J |
| Arriba-derecha | Volver | Regresa al principal |

Estos atajos no abren ni seleccionan automáticamente un navegador. Fuera de él pueden tener otro significado: F5 no siempre significa recargar.

### Multimedia

| Dirección | Etiqueta | Resultado |
| --- | --- | --- |
| Derecha | Play/pausa | Tecla multimedia de Windows: reproducir/pausar |
| Abajo-derecha | Siguiente | Tecla multimedia de Windows: siguiente pista |
| Abajo | −10 s | `j`, solo en perfil Multimedia, pensado para YouTube |
| Abajo-izquierda | +10 s | `l`, solo en perfil Multimedia, pensado para YouTube |
| Izquierda | Silenciar | Alterna silencio de Windows |
| Arriba-izquierda | Pantalla completa | `f` en Multimedia; F11 en Navegador/VS Code; no disponible en Global |
| Arriba | Subtítulos | `c`, solo en perfil Multimedia, pensado para YouTube |
| Arriba-derecha | Volver | Regresa al principal |

Las teclas multimedia pueden ser atendidas por el reproductor que Windows tenga asociado. Las letras `j`, `l`, `c` y `f` necesitan el reproductor compatible enfocado, sin un campo de texto capturándolas. No son controles universales de cualquier reproductor.

## Perfiles y aplicación en primer plano

El perfil se elige **manualmente** en **Ajustes → Escritorio → Perfil**. No detecta automáticamente la aplicación, no abre un programa al cambiarlo y no modifica las ocho posiciones de cada menú.

| Perfil | Buscar | Pantalla completa | −10 s / +10 s / Subtítulos |
| --- | --- | --- | --- |
| Global | Windows+S | No disponible | No disponibles |
| VS Code | Ctrl+F | F11 | No disponibles |
| Navegador | Ctrl+F | F11 | No disponibles |
| Multimedia | Windows+S | `f`, pensado para YouTube | `j` / `l` / `c`, pensados para YouTube |

Los demás comandos comunes conservan sus atajos. VS Code no convierte la auxiliar en Guardar/Terminal/Paleta: sus pinzas siguen siendo Copiar/Pegar/Deshacer/Rehacer. Los perfiles no son un editor libre de combinaciones de teclas.

Si eliges una acción no disponible en el perfil, el programa **pausa el control** y registra el motivo. Consúltalo en Ajustes → Diagnóstico, cambia el perfil si corresponde, cierra Ajustes y activa. En vista limpia no se superpone ese mensaje a la cámara.

## Ajustes, pestaña por pestaña

Abrir Ajustes **pausa** las acciones. **Guardar** valida los valores, los conserva, aplica los cambios y reinicia la cámara; permanece pausado. Tras reconectarse, deja visible la principal sola para asignarla y después activa. **Cancelar** cierra sin aplicar los campos editados, pero no reactiva. La calibración tiene su propio guardado al completar las dos capturas: Cancelar en Ajustes no revierte una calibración ya guardada.

Escribe decimales con **punto**, como `0.25` o `0.85`. Un valor inválido muestra un aviso para corregirlo. La ventana de ajustes puede redimensionarse y tiene barras de desplazamiento para escalados grandes.

### Cámara

| Campo | Inicial | Significado |
| --- | --- | --- |
| Índice de cámara | 0 | Dispositivo que se abre; admite 0–16. Cambia si hay varias cámaras o una virtual |
| Ancho solicitado | 640 | Resolución horizontal de captura; no el ancho de la ventana |
| Alto solicitado | 480 | Resolución vertical de captura; el video se encaja sin deformarse |
| FPS de cámara | 30 | Frecuencia solicitada al dispositivo; puede no alcanzarla |
| FPS de detección | 30 | Límite de frecuencia del análisis; bajar reduce trabajo, con menos actualizaciones |
| Vista espejo | Activada | Refleja horizontalmente la imagen. Revisa calibración si lo cambias |

Empieza con 640 × 480 y valores iniciales; subir resolución o FPS no garantiza mejor respuesta. Si hay demasiado consumo, prueba un límite de detección menor y compara comodidad y métricas. No se promete una mejora porcentual para todos los equipos.

### Precisión

| Campo | Inicial | Significado |
| --- | --- | --- |
| Cierre de pinza / palma | 0.25 | Distancia para reconocer pinza. Mayor permite cerrarla con más separación |
| Apertura de pinza / palma | 0.36 | Distancia para soltar. Debe superar el cierre; el margen reduce oscilaciones |
| Indicador de arrastre (s) | 0.35 | Tiempo para cambiar el indicador; **no retrasa** la pulsación real |
| Suavizado en reposo | 1.8 | Menor filtra más temblor, pero puede sentirse más lento; mayor sigue más los cambios |
| Respuesta al movimiento | 0.03 | Aumentarlo reduce filtrado cuando te mueves; equilibra respuesta y temblor |
| Velocidad de desplazamiento | 6 | Máximo de pasos de rueda por segundo de la L; también velocidad del scroll principal. Admite 1–20 |
| Sensibilidad de volumen | 1.5 | Mayor produce más respuesta al movimiento vertical de la pinza de volumen |
| Invertir horizontal | Desactivada | Invierte el cursor horizontal, no las direcciones del menú |
| Invertir vertical | Desactivada | Invierte el cursor vertical, no la L ni el gesto de volumen |

Los umbrales de pinza se comparten entre principal y auxiliar. Ajusta una cosa a la vez y prueba sobre contenido prescindible. Pausa, apertura/selección radial y confirmación de L mantienen los tiempos descritos; no todos los parámetros internos aparecen como campos editables.

### Escritorio

| Campo | Inicial | Significado |
| --- | --- | --- |
| Monitor | `primary` | `primary`: principal de Windows; `virtual`: todas las pantallas; otros identificadores: una concreta |
| Perfil | Global | Cambia atajos dependientes de aplicación según la tabla de perfiles |
| Opacidad fija (0.4–1) | 0.85 | 0.85 = 85 %. No modifica opacidad del modo normal |
| Iniciar pausado | Activado | Estado de acciones al abrir. Desmarcar permite iniciar activo; evita hacerlo en las primeras pruebas |
| Dibujar puntos de mano | Desactivado en ajustes nuevos | Puntos y conexiones de ambas manos, independiente de vista limpia. Respeta una preferencia existente marcada |
| Comandos de mano auxiliar | Activado | Habilita sus cuatro pinzas y L. También se cambia en Más |
| Calibrar zona de trabajo… | Botón | Ajusta el área cómoda del índice para cubrir el monitor seleccionado |

Cambiar la distribución física de monitores hace que el programa pause y restablezca el mapeo. Revisa Monitor y calibra si corresponde antes de reanudar.

### Diagnóstico

Muestra versión, recordatorio de controles, estado y ruta de configuración/registros. Incluye **FPS de captura**, **tiempo de detección**, **CPU**, **memoria** y **antigüedad del cuadro**, actualizados al consultar la pestaña. El tiempo de detección no es la latencia completa entre tu movimiento y la respuesta del escritorio. Como Ajustes pausa acciones, estas métricas tampoco sustituyen una prueba de respuesta durante uso activo.

**Abrir carpeta de diagnóstico** abre la ubicación de datos. Normalmente es `%LOCALAPPDATA%\BioGestureControlPro`: contiene `settings.json`, `biogesture.log` y, cuando se generan, registros nativos. No necesitas editarlos para usar el programa. Antes de compartir registros, revísalos: pueden contener rutas del equipo o mensajes de dependencias.

## Calibrar una zona cómoda

Convierte un rectángulo alcanzable por tu índice en toda el área del monitor seleccionado. Por defecto usa el 12–88 % de la imagen en cada eje; no hace falta llevar la mano hasta los bordes de cámara.

1. Elige cámara, espejo y monitor; **guarda primero** y espera la reconexión.
2. Elige la principal mostrando solo esa mano. Abre **Ajustes → Escritorio → Calibrar zona de trabajo…**.
3. Coloca el índice en el extremo **superior izquierdo de la imagen** que alcances cómodamente. Mantén aproximadamente un segundo y pulsa **Capturar** con mouse o teclado.
4. Repite en el extremo **inferior derecho** y pulsa Capturar. Se estiman las esquinas con muestras recientes; si faltan datos o el área es muy pequeña, aparece un aviso.
5. La segunda captura válida **guarda automáticamente** la zona y cierra el diálogo de calibración, pero Ajustes sigue abierto. Cierra Ajustes y pulsa **Activar** antes de comprobar que alcanzas los bordes sin forzar la mano. Cancelar en Ajustes no deshace esa calibración.

La referencia es el video con tu espejo actual, no la posición final del cursor. No se generan acciones de mouse ni auxiliar durante la calibración. Usa luz uniforme, evita tapar el índice y deja solo la mano que usarás. Si cambias mucho la posición de cámara o cómo te sientas, vuelve a calibrar.

## Prioridades y seguridad de los gestos

El programa no ejecuta todas las poses a la vez. Esta exclusividad evita, por ejemplo, pegar mientras arrastras con la principal.

- Pausa, Ajustes, calibración, cambio de cámara y cierre bloquean a la auxiliar. Cerrar un diálogo no reactiva automáticamente.
- Pinzas, clic/arrastre, menú, onda, scroll y volumen de la principal tienen prioridad. Para probar la auxiliar, deja la principal en seguimiento normal o retírala momentáneamente tras asignar roles.
- Una auxiliar asignada puede actuar sin la principal visible si está activo y no permanece una operación incompatible.
- Un gesto pendiente debe confirmarse de nuevo tras una interrupción. Una pinza auxiliar ejecutada conserva su bloqueo hasta una apertura reconocida: esconderla no sustituye abrirla.
- Muestras antiguas o repetidas no acumulan tiempo para ejecutar. Perder seguimiento libera botones retenidos y cancela acciones pendientes; no se reproducen después como una cola atrasada.
- En pausa quedan disponibles victoria para reanudar y onda para cambiar solo el modo de ventana. Con cámara apagada no se reconocen gestos.

No dejes documentos importantes sin guardar durante las primeras pruebas. Bloquear sesión, Eliminar, Cortar o cerrar pestañas son acciones reales. El programa no se eleva como administrador ni maneja el escritorio seguro de Windows; aplicaciones con permisos superiores pueden rechazar sus entradas.

## Solución de problemas

| Lo que observas | Qué revisar |
| --- | --- |
| El EXE no abre o faltan bibliotecas/recursos | Extrae la carpeta **completa**; conserva `_internal` al lado del EXE y comprueba que sea el paquete x64 esperado. No mezcles versiones |
| Sigue sin arrancar | Conserva el mensaje y revisa diagnóstico. Un modelo/recurso ausente no se resuelve instalando Python global para el portable |
| No hay cámara o imagen negra | Revisa índice, permisos de cámara para aplicaciones de escritorio en Windows y si otro programa usa el dispositivo. Prueba Apagar/Encender cámara y consulta Diagnóstico |
| Hay cámara pero el cursor no se mueve | Comprueba Activar, cámara disponible, diálogos cerrados y principal elegida. Si empezaste con dos, usa Reelegir y deja visible una |
| Tras guardar o calibrar no responde | Permanece pausado por diseño. Tras Guardar espera reconexión y elección de principal; cierra diálogos y activa |
| Cursor invertido o sin alcanzar bordes | Revisa espejo, monitor e inversiones; calibra las dos esquinas de la imagen. Invertir cursor no cambia la L |
| Los puntos no se dibujan | Marca Dibujar puntos de mano, guarda y espera muestras válidas. Funciona en vista limpia sin activar diagnóstico |
| Veo puntos al actualizar pese a vista limpia | Se respeta tu preferencia marcada anterior. Desmárcala en Escritorio si quieres ocultarlos |
| Auxiliar no copia ni desplaza | Verifica habilitación, rol asignado, pose continua 0.45 s y ausencia de gesto prioritario de la principal. Pausa también la bloquea |
| Copiar/Pegar/Deshacer no hace lo esperado | Comprueba foco, selección y efecto de Ctrl+C/V/Z/Y en esa aplicación; Ctrl+Y no siempre es Rehacer |
| Formo L pero no desplaza | Revisa **centro de palma** fuera de 45–55 %, otros tres dedos recogidos, foco y documento desplazable. No avanza más allá del extremo del documento |
| L quieta sigue desplazando | Fuera del centro es lo previsto. Vuelve al centro, suelta la L o pausa para detenerla |
| Una pinza no vuelve a ejecutar | Ábrela claramente. Sacar y meter la mano cerrada no demuestra una liberación |
| Perdí detección durante arrastre | Se libera por seguridad. Abre antes de iniciar otro y comprueba el resultado en la aplicación |
| La onda no cambia ventana | Haz cuatro recorridos alternados con tres dedos largos abiertos y altura estable, no un barrido. Usa Más como alternativa |
| El radial selecciona mal o no repite | Parte del punto donde abriste el pulgar; mantén dirección 1 s y vuelve allí después de cada selección, también al cambiar de grupo |
| Se pausa con una opción multimedia | Revisa perfil y compatibilidad en Diagnóstico. Subtítulos, por ejemplo, no está disponible en Global |
| Oculté y sigue actuando | Ocultar no pausa: usa Ctrl+Alt+F12 o Pausar control en la bandeja |
| Cámara ocupada estando pausado | La pausa conserva detección. Apagar cámara o Salir libera el dispositivo |
| No encuentro ventana o hay otra instancia | Busca el ancla junto al reloj y Mostrar cámara; usa Ctrl+Alt+F12 si está disponible. No abras repetidamente más copias |
| Una aplicación elevada/aviso de Windows no responde | No se controla el escritorio seguro ni se elevan permisos. Usa teclado/mouse; no desactives protecciones |
| Retraso, temblor o mucho consumo | Revisa luz, tamaño visible de mano, resolución y FPS de detección. Ajusta suavizado gradualmente y compara Diagnóstico |
| Aparece una consola | En portable abre el EXE, no BAT antiguos ni Python global. Para fuente usa el VBS local; `--console` es una opción expresa de desarrollo |

Al informar un fallo, anota versión, resultado esperado/observado, perfil, cámara/resolución, pausa y si pertenece a principal o auxiliar. Comparte solo registros pertinentes después de revisarlos. No necesitas publicar fotografías personales para describirlo.

## Actualizar, conservar ajustes y retirar el portable

### Actualizar sin mezclar archivos

1. Cierra Bio-Gesture desde **Salir** antes de cambiar de versión.
2. Para una copia de seguridad, abre `%LOCALAPPDATA%\BioGestureControlPro` en el Explorador y copia `settings.json` a una ubicación elegida por ti.
3. Extrae el nuevo ZIP en **otra carpeta completa**; no copies solo el EXE encima del anterior.
4. Abre el nuevo EXE. Los ajustes válidos permanecen en el perfil de Windows, fuera del paquete: cámara, monitor, calibración, perfil y preferencias no dependen de la carpeta extraída.
5. Revisa ajustes y prueba brevemente antes de retirar la carpeta antigua. Actualiza accesos directos que apunten al EXE anterior.

Se reconocen los formatos anteriores contemplados por esta versión; no se promete compatibilidad con cualquier versión futura o una vuelta arbitraria a antiguas. Si `settings.json` es inválido o incompatible, se usan valores iniciales y se registra el problema sin borrarlo al cargar. **Guardar sí escribe la configuración actual**: conserva primero una copia para investigar o recuperar la anterior.

Cambiar de usuario de Windows puede cambiar qué ajustes están disponibles. La preferencia existente de Dibujar puntos de mano se respeta; desmarcada solo es el valor de ajustes nuevos. No ejecutes simultáneamente versiones distintas para comparar el mismo perfil.

### Retirar el programa

1. Usa **Salir** y espera el cierre de cámara.
2. Elimina la carpeta extraída y los accesos directos que creaste. No hay desinstalador formal porque no se instaló un servicio ni un producto mediante instalador.
3. Ajustes y registros en `%LOCALAPPDATA%\BioGestureControlPro` **se conservan**. Solo si quieres borrar también preferencias, cierra todas las copias, respalda lo necesario y elimina expresamente esa carpeta de datos. Eso elimina calibración y registros, no únicamente el programa.

No necesitas borrar Python ni otros programas del equipo para retirar el portable.

## Privacidad, alcance y desarrollo

El reconocimiento usa un modelo incluido y funciona localmente: el arranque normal no descarga modelos ni necesita un servicio de reconocimiento en la nube. No se graban fotos ni video en uso normal. Oculto sigue capturando para reconocer gestos; Apagar cámara o Salir termina la captura.

La base 2.0 separa captura, detección, gestos, acciones e interfaz, procesa el cuadro reciente y adapta coordenadas a monitor y escala de Windows. Esto no garantiza un porcentaje de rendimiento ni elimina la prueba de luz, anatomía, oclusiones, falsas activaciones y comodidad en cada equipo.

Las pruebas automáticas, imágenes sintéticas y un EXE sin Python en su ruta **no equivalen a una computadora recién instalada**. La validación física de dos manos, Windows 10/11 limpio, cámara, audio y aplicaciones reales sigue el registro de [Validación](docs/VALIDATION.md). Un portable local no implica instalador firmado ni Release publicada en GitHub.

Para desarrollar desde código sí se requiere **Python 3.12 x64**. Se conservan **PREPARAR_DESARROLLO.bat** para preparar el entorno e **INICIAR_CONTROL.vbs** para abrirlo sin consola una vez preparado. No forman parte del uso del portable; las instrucciones técnicas están en [Desarrollo](docs/DEVELOPMENT.md).

### Referencias de 2.0

- [Gestos, medidas y límites técnicos](docs/GESTURES.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Fases y criterios de aceptación](docs/PHASES_1_4.md)
- [Pruebas realizadas y pendientes](docs/VALIDATION.md)
- [Distribución y comprobación del paquete](docs/DISTRIBUTION.md)
- [Registro de capturas](docs/captures/README.md)
- [Licencia](LICENSE) y [avisos de terceros](THIRD_PARTY_NOTICES.md)

⚓ **Desarrollado por Luics415**. El ancla y la firma visual siguen siendo la identidad del proyecto.
