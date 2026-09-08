# Validación — 2.7

## Portada y numeración 2.7

El autor solicita que 2.7 sea la presentación principal del repositorio, reconociendo las revisiones acumuladas hasta `2.0.0-dev.7`. Código y metadatos pasan a **2.7.0**; no se renumeran retrospectivamente las pruebas ni las entregas históricas. Esta transición no modifica motores de gestos, coordenadas, seguimiento, selección de manos ni preferencias del usuario.

`README.md` es la guía actual con descargas separadas de portable y código, manual PDF e instrucciones de tres pasos. El README 1.0 se conserva byte por byte en `legacy/v1.20.36/README.md`; `README-2.0.md` es una referencia de compatibilidad. El splash cambia de 2.0 a 2.7 por autorización expresa, preservando el ancla y el texto de autor; su archivo anterior queda resguardado intacto. El manual usa la numeración actual y la nueva edición de la firma.

- **924 pruebas aprobadas**, ninguna omitida, con Tk y MediaPipe habilitados (17.21 s): `output/validation-27/tests.xml`. Ruff y dependencias correctos. Dos advertencias conocidas de protobuf sobre Python 3.14; objetivo probado Python 3.12.10 x64 en Windows 10. Un primer intento limitado no pudo acceder a sus temporales por permisos del entorno; el pase completo con acceso adecuado terminó sin fallos. No se abrió la cámara ni se enviaron entradas reales.
- Las pruebas nuevas comprueban coherencia de 2.7.0 en código/metadatos/recursos PE, portada con descargas separadas, guía anterior redirigida e integridad del README 1.0 y de ambas firmas. Motores y preferencias sin cambios respecto al commit `a03a75e`.
- Manual de 17 páginas revisado visualmente por completo. Texto dentro de márgenes, 17 marcadores, seis enlaces internos y versión 2.7.0 presente en todas las páginas. Los píxeles de la firma incrustada coinciden con el recurso 2.7; no contiene capturas privadas.
- La compilación debe comprobar el modelo/interfaz en ruta normal y con acentos, sin Python en PATH, y verificar copia del manual, manifiesto y ZIP. El `BUILD-MANIFEST.json` y SHA-256 de cada descarga son la evidencia del binario concreto; no se infiere de esta descripción.

Sigue siendo una edición pública de pruebas, sin Authenticode ni certificación de Windows limpio. Los apartados siguientes conservan evidencia histórica de las revisiones de desarrollo.

## Historial: cámara sin texto y manual revisado — dev.7

Se eliminó la función de ayudas gestuales del dibujo de cámara, incluyendo textos y barras de espera. Los estados vacíos también limpian el lienzo sin escribir mensajes. Puntos/conexiones opcionales y menú radial permanecen. Fuente/VBS/EXE comienzan sin diagnóstico visual; `--diagnostics` solo muestra el pie externo, no instrucciones en el video. Se mantienen Ajustes, registros y diálogos de errores.

Los gestos principales, la L, los comandos auxiliares, el seguimiento y la selección de roles no cambian respecto a dev.6. El manual incorpora manos vectoriales más naturales y una página final con la firma visual aprobada sin recortar ni alterar. Se conserva el README original y las capturas privadas quedan excluidas de publicación.

- **921 pruebas aprobadas** en el pase final con Tk y MediaPipe habilitados, ninguna omitida, en 16.95 s: `output/validation-dev7/tests-final.xml`. Ruff, compilación de módulos y comprobación de dependencias correctos. Permanecen dos advertencias de protobuf sobre Python 3.14; el entorno probado es Python 3.12.10 x64 sobre Windows 10. No se abrió la cámara ni se enviaron entradas reales.
- Se cubren los estados gestuales con puntos activados/desactivados y diagnóstico activado/desactivado, estados vacíos, radial y arranque desde fuente/empaquetado. El diagnóstico explícito permanece fuera del video. Los dibujos de ambas manos siguen dependiendo de la casilla guardada.
- Manual revisado visualmente en sus **17 páginas A4**: diez poses vectoriales diferenciadas, contactos de pinza, cinco dedos y numeración 4/8/12/16/20. Verificados márgenes de texto, 17 marcadores y seis enlaces del índice. Las únicas imágenes raster son el ancla de portada y la firma aprobada al final; no contiene fotografías de sesión. Se conserva la copia pública en `docs/manual/Manual-de-usuario.pdf`.
- El paquete debe superar las comprobaciones de detector/interfaz y ruta con acentos descritas en [Distribución](DISTRIBUTION.md). La evidencia de cada binario descargable es su `BUILD-MANIFEST.json`, el ZIP y su SHA-256. La automatización de GitHub no habilita las 18 pruebas Tk de escritorio; estas sí están incluidas en el pase local completo anterior.

Publicar una edición de pruebas no certifica Windows limpio, detección física continua, instalador formal ni firma digital. Los apartados siguientes son evidencia histórica de cada revisión, no el estado de publicación actual.

## Historial: puntos opcionales, L observada y manual ilustrado — dev.6

Fecha: 7 de septiembre de 2026. Windows 10 x64 y Python 3.12.10 x64. El usuario confirma que el portable anterior abre en su equipo, **no que haya pasado una computadora limpia**. Esta revisión no abre su cámara ni ejecuta entradas reales del escritorio.

- **848 pruebas aprobadas** en el pase completo final con Tk y MediaPipe habilitados, ninguna omitida: `output/validation-dev6/tests-release.xml` (15.23 s). El primer pase, anterior a ampliar las guardas del manual, tuvo 830. Incluye geometría, secuencias observadas/sintéticas, roles, pinzas, interfaz, configuración y 69 pruebas de empaquetado. Se valida el PDF explícito, su igualdad por hash, cambios durante compilación y exclusión de capturas privadas; las pruebas unitarias usan una referencia PDF aislada, sin depender del manual local ignorado por Git. Dos advertencias conocidas de protobuf sobre Python 3.14; el entorno probado es Python 3.12. Ruff y comprobación de dependencias correctos.
- Causa de puntos: `_render` exigía diagnóstico además de la casilla. Ahora `show_landmarks` decide por sí solo, en ambos modos. Pruebas con Tk real verifican marcar, Guardar, dibujar, reabrir configuración guardada y desmarcar, usando datos aislados. Ajustes nuevos comienzan sin puntos; se respeta un `True` guardado. No habilita mensajes ni indicaciones.
- Causa reproducida de L: el detector aceptaba la L de la primera captura, pero su centro de palma estaba en y=0.5502928. En dev.5 eso producía aproximadamente 0.0039 pasos/s, es decir, unos 257 segundos por paso si esa muestra se mantuviera. No se afirma que la sesión física tardara esa cantidad: es una reproducción de la observación estática.
- Dev.6 conserva la banda neutra inclusiva 45–55 %. Fuera empieza al 25 % de `scroll_rate` y aumenta hasta el máximo en los bordes: inicialmente 1.5–6 pasos/s. En la reproducción a 15/30 FPS de esa L, el primer paso llega en como máximo 1.2 s, incluida la confirmación de 0.45 s. El centro detiene la rueda; soltar/perder pose, pausa y bloqueos descartan fracciones y tiempos.
- La L auxiliar acepta un ángulo visible 55–125° y flexión leve de índice/pulgar. La L aportada y variantes de giro, espejo, tamaño, aspecto y profundidad estimada se aceptan; las tres palmas abiertas observadas se rechazan. También se prueban dedos adicionales abiertos, pinzas, ruido en el borde neutro y cancelación. Solo se guardan 21 puntos anonimizados por mano en una referencia de pruebas, no píxeles ni rostros. Dos capturas estáticas no certifican precisión continua ni ausencia universal de falsos positivos.
- **Sin cambios byte por byte** en `gestures.py`, `selection.py`, `coordinates.py` y `tracking.py`: el cursor, clics, arrastre, onda y recuperación de roles conservan su implementación. `settings.py` solo cambia el valor inicial de puntos. README 1.0, ancla, splash y modelo conservan sus hashes aprobados.
- Manual PDF: 16 páginas A4 con dibujos vectoriales y el ancla aprobada. Revisadas visualmente todas las páginas y las páginas modificadas tras la auditoría funcional; verificados límites de texto, texto buscable, índice enlazado y ausencia de fotografías de la sesión. La única imagen raster del PDF es el ancla de portada. Los dos originales del usuario se conservan intactos y privados; véase [Registro de capturas](captures/README.md).
- README 2 ampliado con primer arranque, roles, todos los gestos, 40 posiciones radiales, perfiles, cuatro pestañas de ajustes, calibración, recuperación, actualización y retirada del portable. El README 1.0 no recibe modificaciones.

La compilación debe comprobar detector e interfaz tanto en ruta normal como con acentos y registrar el PDF incluido en el manifiesto. La evidencia de un paquete concreto es `BUILD-MANIFEST.json`, ZIP y SHA-256, no la mera existencia de estos scripts. Siguen pendientes sesión física continua de dev.6, Windows limpio, instalador formal, firma digital y publicación. Los apartados siguientes son historial, no sustituyen este estado actual.

## Historial: validación 2.0.0-dev.5

Fecha: 7 de septiembre de 2026. Entorno probado: Windows 10 x64, Python 3.12.10 x64, entorno `.venv` del proyecto. No se han publicado estos cambios ni ejecutado la automatización remota de GitHub.

## Centro de imagen, vista limpia y preparación portable — dev.5

- **713 pruebas aprobadas** en el pase completo tras corregir rutas Unicode, con Tk y MediaPipe habilitados, ninguna omitida; incluye 51 pruebas de empaquetado y modelos reales desde rutas con acentos y caracteres japoneses. Informe generado: `output/validation-dev5/tests-unicode-final.xml`. Los pases anteriores tuvieron 690 y 708 antes de ampliar las guardas y probar la ruta Unicode. Ruff y comprobación de dependencias correctos. Permanecen dos advertencias de protobuf sobre Python 3.14; el objetivo es Python 3.12.
- L auxiliar: centro fijo de la imagen y banda neutra inclusiva 45–55 %. Arriba desplaza arriba, abajo hacia abajo. Puede activarse directamente en cualquiera de esas zonas tras 0.45 s. Recuperación sin volver al centro ni acumular rueda pendiente.
- Pruebas de L en múltiples FPS, resoluciones, escalas, giros, espejo y lateralidades. Comparación de cantidades por tiempo y cancelación por pausa/pinza/pérdida. La referencia de palma se alinea con el centro de la vista pese a sus márgenes; invertir el cursor no invierte el scroll.
- SHA-256 de `gestures.py`, `selection.py`, `coordinates.py` y `settings.py` idénticos a fix.4. El motor principal, la selección de roles y su configuración permanecen intactos. La única modificación nueva de `tracking.py` es cargar el modelo como bytes para admitir rutas Unicode; no cambia captura, roles ni gestos.
- Vista limpia del EXE por defecto; fuente de desarrollo con ayudas. Opciones explícitas `--clean-ui` y `--diagnostics`. Se prueban cámara sin landmarks/hints/estado, radial conservado y controles de ventana, además de las dos presentaciones a cuatro escalas Tk.
- Cierre: un fallo al detener el atajo global ya no interrumpe la liberación de recursos ni impide salir. La prueba reproduce el error y verifica que se continúa cerrando.
- Arranque empaquetado preparado para relanzar el mismo EXE con canales nativos válidos, sin buscar Python externo. Las pruebas simulan `sys.frozen` y comprueban guard, argumentos, código de salida y ausencia de elevación.
- Prueba real desde fuente de `--detector-smoke`: 1 cuadro negro, 0 manos, detector cerrado, exit 0, hash correcto. Informe de diagnóstico sin rutas personales. No se abrió una webcam ni se generaron entradas del sistema.
- README 1.0 restituido byte por byte al commit remoto vigente `a2162016244f46e6edf681a0b015526eb2cbfeb6`, verificado con consulta remota. SHA-256: `312dc0df773810135751006f42d42e819ad3b75df8063f1a5719f8a7c13a66da`. No se le añadió ningún enlace. `README-2.0.md` documenta las diferencias y es el README de los metadatos del proyecto.
- Ancla y splash originales protegidos mediante hashes; no hubo rediseño. Se retiró el BAT de compatibilidad redundante, conservando VBS, herramientas de desarrollo y respaldo histórico.
- Capturas: las ventanas de prueba se abrieron y cerraron, pero el capturador falló dos veces con `SetIsBorderRequired failed: Interfaz no compatible (0x80004002)`. **No se guardaron capturas reales válidas**. Véase `docs/captures/README.md`; los renders anteriores no se presentan como screenshots.

### Verificación de distribución

El generador portable verifica cabecera gráfica, intérprete y recursos incluidos, modelo/arte sin cambios, límites de archivos públicos, inferencia sintética y apertura/cierre desde otra carpeta con un PATH sin Python. Solo crea el ZIP después de estas comprobaciones. **La existencia del script y sus pruebas no demuestra por sí sola que un paquete concreto haya pasado**: la evidencia de cada entrega es su `BUILD-MANIFEST.json`, junto con el ZIP y su SHA-256.

La prueba de inferencia desde fuente y las simulaciones de frozen anteriores no sustituyen la prueba del EXE. El manifiesto debe confirmar sus comprobaciones de detector e interfaz con código 0; los registros locales de compilación no se incluyen como información personal en el portable.

La primera compilación pasó detector y GUI en su carpeta original, pero una prueba adicional del ZIP extraído en `Prueba portable á` detectó que MediaPipe no podía abrir el modelo por su ruta Unicode. Se corrigió la entrega del modelo usando bytes en memoria tanto en seguimiento como en diagnóstico, sin modificar el archivo aprobado. Esta prueba se incorpora al generador como requisito anterior a crear el ZIP; el primer artefacto no se considera una entrega válida.

Siguen pendientes: sesión física con dos manos y L, cámaras/luces reales, sesiones prolongadas, Windows limpio sin Python, instalador/desinstalador formal, firma digital y publicación. La vista limpia no constituye aprobación de un rediseño completo de ventana. No se declara terminada la fase 6 ni una Release final firmada.

## Historial: edición cotidiana y desplazamiento auxiliar en L — fix.4

El usuario aprobó orientar la auxiliar a Copiar, Pegar, Deshacer, Rehacer y desplazamiento, incorporando una L sin cambiar los gestos de la principal. La asignación inicial de la L es desplazamiento vertical; su comodidad y precisión requieren prueba física.

- **542 pruebas aprobadas**, con las integraciones de Tk y MediaPipe habilitadas y ninguna omitida. Ruff, compilación de módulos y comprobación de dependencias correctos; persisten las dos advertencias de protobuf ya documentadas.
- Comparación SHA-256 antes/después: **sin cambios** en `gestures.py`, `selection.py`, `coordinates.py`, `tracking.py` y `settings.py`. También permanecen idénticos el ancla y el splash aprobados. La ampliación se limita al motor auxiliar, su despacho, los atajos auxiliares y la información de diagnóstico.
- Pinzas auxiliares 4–8/12/16/20: Copiar/Pegar/Deshacer/Rehacer mediante Ctrl+C/V/Z/Y. Sustituyen los cuatro comandos de programación de fix.3. Se probaron las combinaciones en todos los perfiles principales y su liberación sin teclas retenidas. No se ejecutaron atajos reales; cada aplicación decide su selección, historial y compatibilidad con Ctrl+Y.
- L auxiliar: pulgar e índice extendidos a unos 90° —rango geométrico 60–120°— y otros dedos recogidos. Mantener 0.45 s establece la referencia de palma; la desviación vertical controla la rueda. Zona muerta de 0.15 palmas, velocidad proporcional y límite preexistente `scroll_rate`, inicialmente 6 pasos/s. No mueve el cursor ni hace clic para enfocar una ventana.
- Pruebas sintéticas de L a 5/10/15/30/60 FPS configurados, cambios de escala/proporción/rotación/espejo y ambas etiquetas anatómicas. Cubren ruido en reposo, dirección, parada en el centro, cambio de sentido, pérdida de pose, muestras antiguas/repetidas, pausa y deshabilitación. Un bloqueo o pérdida explícita descarta referencia y fracciones; al volver se adquiere un centro nuevo, sin rueda acumulada.
- Integración de ambos roles: movimiento del índice principal antes de la rueda auxiliar, sin clics de enfoque. Comparación exacta de eventos de clic izquierdo, arrastre y clic derecho con y sin la extensión auxiliar. El arrastre cancela el scroll auxiliar; las guardas de menú/onda/scroll/volumen, pausa y configuración siguen dando prioridad a la principal. La pérdida de la auxiliar no detiene el puntero de la principal.
- El escritorio distingue eventos auxiliares de edición y rueda; rechaza clics, cambios de ventana o movimientos de cursor procedentes del motor auxiliar. Los fallos de entrada detienen el resto del lote y conservan la pausa de seguridad.
- Geometría de interfaz y diagnóstico comprobados en las cuatro escalas de Tk. El modo de prueba `control.py --smoke --smoke-seconds 1` abrió y cerró correctamente, con ambos eventos en el registro aislado. No se cerró ni reinició la sesión del usuario.

No se utilizó la webcam ni se enviaron entradas reales. Estas pruebas **no certifican** el reconocimiento físico de la L, la comodidad, el foco/destino real de la rueda ni la respuesta de cada aplicación. La principal conserva su implementación probada; la interacción nueva todavía debe comprobarse en uso real. Para cargar fix.4 hay que salir de la versión abierta e iniciar de nuevo mediante `INICIAR_CONTROL.vbs`.

El menú radial y la ventana de pruebas no se rediseñan en esta revisión. Se conserva el requisito final de ausencia de mensajes e indicaciones superpuestas, salvo el menú radial. Modificadores Ctrl/Mayús sostenidos, otros gestos auxiliares, instalador y publicación permanecen pendientes.

## Historial: dos manos, recuperación automática y onda de cuatro recorridos — fix.3

El usuario confirmó que la onda de fix.2 ya alternaba correctamente los modos de ventana, pero rechazó el bloqueo de identidad, retirar ambas manos un segundo y cerrar la mano después de la onda. Solicitó uso simultáneo de ambos roles, cuatro movimientos y una presentación más simple. Eligió Guardar, Buscar, Terminal y Paleta para la auxiliar, y elegir la principal dejando una sola mano visible al inicio.

- **439 pruebas aprobadas**, con Tk y MediaPipe optativos habilitados y ninguna omitida. Ruff y comprobación de dependencias correctos. Dos advertencias de protobuf, iguales a las anteriores, no afectan al objetivo Python 3.12.
- Elección inmediata con el primer cuadro válido de una sola mano; con ambas al arranque basta retirar una, sin permanencia obligatoria. Las pruebas cubren principal izquierda/derecha, orden variable, ambas manos a la vez, ausencia de la principal mientras la auxiliar permanece y recuperación tras huecos de 50 ms a 60 s.
- No existe un bloqueo persistente por identidad ambigua ni un temporizador para retirar ambas manos. Un cuadro solapado o incoherente puede descartarse; el siguiente cuadro utilizable recupera los roles sin otra elección. Se verificaron cruces rápidos y que la auxiliar no reciba el cursor. Las etiquetas anatómicas son evidencia de la elección de esa sesión, no una asignación fija de permisos a izquierda/derecha.
- La auxiliar emite una sola acción tras mantener 0.45 s las pinzas 4–8/12/16/20: Guardar/Buscar/Terminal/Paleta. No genera clics ni cursor. Integración con entradas de Windows simuladas verifica las combinaciones y su liberación; no se ejecutó ningún atajo real. Su pérdida cancela intentos incompletos sin repetir una pinza ya ejecutada.
- El cursor de la principal y los comandos auxiliares pueden coexistir. Durante clic/arrastre, menú, onda, scroll/volumen, pausa, ajustes o calibración se cancelan los intentos auxiliares pendientes. La auxiliar asignada puede emitir atajos cuando la principal falta momentáneamente, sin tomar su cursor. Los atajos están pensados para el editor en primer plano, especialmente VS Code; su respuesta física y distribución de teclado siguen pendientes de prueba.
- Onda de **cuatro recorridos y tres inversiones**, dentro del plazo inicial de 2.2 s. Al cambiar vuelve el cursor inmediatamente; 0.30 s descartan movimientos residuales y luego puede comenzar otra secuencia de cuatro con la mano todavía abierta. Se probaron repetición abierta, tres movimientos insuficientes, ruido, pérdidas breves y cambio pausado sin entradas de mouse.
- Radial con ocho rótulos breves y barra horizontal: sin texto central duplicado, porcentaje, arco de progreso ni instrucciones. Se revisó la vista sintética generada por el mismo dibujo y se comprobaron geometría y textos en las cuatro escalas de Tk. **La ventana de pruebas no constituye un diseño final aprobado.**
- Más permite reelegir la principal o activar/desactivar los comandos auxiliares. Las pruebas de interfaz verifican que reelegir no reinicie la cámara y que activar/desactivar la auxiliar no altere el cursor ni la pausa. La visualización de pruebas dibuja las dos manos asignadas.
- Arranque y cierre de `control.py --smoke --smoke-seconds 1` correctos, con ambos eventos en el registro aislado de pruebas. No modifica la sesión que el usuario tenga abierta.
- Se anotó el requisito final: **sin mensajes, indicaciones ni diagnóstico superpuesto; solo el menú radial**. No se presenta como implementado el diseño limpio definitivo. El ancla y el splash aprobado no cambian.

No se abrió la cámara ni se enviaron entradas reales durante esta revisión. La nueva interacción de dos manos y la onda de cuatro requieren la prueba del usuario: sus confirmaciones anteriores no validan automáticamente estos cambios. Para cargarlos debe cerrar la versión abierta y volver a iniciar `INICIAR_CONTROL.vbs`. El instalador para equipos sin Python y la publicación siguen pendientes.

## Historial: onda de ventana e interfaz — fix.2

El usuario confirmó físicamente que el cursor volvió a responder correctamente tras fix.1, pero informó que la onda no cambiaba la ventana. El acceso desde la interfaz era una alternativa: no debía reemplazar el gesto. Esta revisión conserva cursor y pinzas y corrige el reconocimiento de la onda y la continuidad de la mano durante movimientos rápidos.

- **252 pruebas aprobadas**, incluyendo Tk y MediaPipe optativos; sin pruebas omitidas. Ruff, compilación de módulos y comprobación de dependencias correctos. Se mantienen las dos advertencias internas de protobuf descritas abajo. El primer intento completo quedó bloqueado por permisos del directorio temporal de pruebas; la repetición autorizada terminó correctamente.
- Onda con apertura relajada de al menos tres dedos largos: tres recorridos y dos inversiones, amplitud inicial de 0.50 palmas y plazo de 2.2 s. No depende de la etiqueta izquierda/derecha ni de una palma perfectamente frontal. Las pinzas conservan prioridad inmediata sobre un intento de onda.
- Reproducciones sintéticas a 15/30 FPS, ambas etiquetas anatómicas, espejo activado/desactivado, dedos curvados, huecos breves de detección, ruido y rearme. Los intentos incompletos vencen y devuelven el cursor; una onda completada exige relajar/cerrar la mano antes de repetirse.
- Integración selector → motor → ventana simulada: onda de la principal con una segunda mano visible, ida a modo fijo y vuelta a normal. En pausa solo se emite cambio de ventana: ninguna entrada de mouse/teclado. Se comprueban bordes, topmost y opacidad por separado con una ventana real de Tk.
- Corrección de un intercambio reproducible al aparecer la segunda mano en la posición anterior de la principal. Ante evidencia contradictoria de continuidad y anatomía se suspende la selección; no se concede un rol por derecha/izquierda. Esto sigue siendo seguimiento por continuidad, no identificación biométrica garantizada.
- Configuración de esquema 3: migra únicamente el antiguo par predeterminado de onda (0.65 / 1.6), conservando los pares personalizados y los ajustes de cursor, clic, cámara y calibración. No se modificó manualmente la configuración del usuario.
- Cliente **550 × 375**: barra de 28, cámara de 550 × 335 y estado de 12. Pruebas de Tk equivalentes a escalas 100/125/150/200% verifican controles, ajustes, calibración y todas las selecciones de los cinco menús radiales sin texto superpuesto ni recortado. Las métricas solo se actualizan al consultar Diagnóstico.
- `control.py --smoke --smoke-seconds 1` inició y cerró correctamente; el registro aislado confirma ambos eventos. No abre cámara, bandeja ni atajos globales. El usuario eliminó su BAT externo y utiliza `INICIAR_CONTROL.vbs`; no se recreó aquel BAT.
- Se revisó visualmente `output/desktop-preview.png`, generado desde `scripts/preview-desktop.py` y las funciones de dibujo usadas por la aplicación. Es una **vista previa sintética**, no una captura de la webcam ni de la composición nativa de Windows.
- Integridad del ancla, splash aprobado y modelo local verificada por SHA-256; ninguno fue modificado en fix.2.

No se abrió la webcam, no se enviaron entradas reales y no se cerró la sesión del usuario. Debe salir de la versión abierta y volver a iniciar desde VBS para cargar los cambios. La comodidad y fiabilidad física de la onda, la nueva presentación y la transparencia real siguen pendientes de su prueba; la confirmación del cursor no se extiende automáticamente a esos aspectos.

## Corrección posterior a la prueba del usuario — fix.1

La versión **2.0.0-dev.4+fix.1** corrigió problemas que la batería anterior no representaba correctamente. La prueba real del usuario detectó la restricción indebida de lateralidad, falta de continuidad del cursor y pérdida del clic izquierdo. También rechazó el diseño de la ventana y del menú radial. El rediseño visual quedó pendiente en ese momento; el ancla y el splash no se modificaron en esa revisión.

- **159 pruebas aprobadas**, incluidas las integraciones optativas de Tk y MediaPipe. Ruff sin errores; arranque/cierre seguro comprobados. Persisten las dos advertencias internas de protobuf descritas abajo.
- El cursor sigue el punto 8 sin exigir que los otros dedos estén doblados. Un solo barrido horizontal no lo congela; la onda toma prioridad al confirmar una inversión de dirección.
- Pinza 8–4: pulsación inmediata al cerrar y liberación al abrir. Mantener y mover arrastra, sin clic sintético adicional. Pinza 12–4: clic derecho una vez hasta abrir. El cursor se posiciona antes de la entrada del mismo cuadro.
- El selector adquiere cualquier mano estable y sola en unos 350 ms. Detecta hasta dos para conservar identidad por continuidad; la segunda no recibe comandos. Cruces ambiguos o una sustitución después de oclusión suspenden acciones. Retirar ambas un segundo permite volver a elegir. Esto no es identidad biométrica ni garantiza resolver oclusiones invisibles; requiere prueba física.
- La configuración anterior migra al esquema 2 conservando cámara, monitor, calibración y demás preferencias; desaparece el ajuste `dominant_hand`.
- Se verificó el lanzador realmente utilizado: el antiguo `ACTIVAR_CAMARA.bat` del Escritorio activaba incorrectamente un `.ps1` desde CMD y ejecutaba Python global. Se corrigió para delegar a VBS y cerrar CMD. El original se conserva solo localmente en el respaldo histórico y no se publica porque contiene una ruta personal. Abrir el VBS directamente evita incluso el posible destello inicial de un BAT.
- El punto de entrada elige `.venv/pythonw`, evita relanzamientos infinitos y registra salida Python/C/Win32 en `native.log`. Pruebas en procesos aislados verificaron los tres canales y ausencia de consola. `--console` queda disponible expresamente para desarrollo.

No se abrió la webcam ni se ejecutaron entradas reales del programa en esta revisión. La sesión antigua que el usuario tenía abierta no se cerró automáticamente: debe salir de ella y volver a iniciar para cargar estas correcciones.

## Resultados de la entrega anterior, antes de fix.1

- **118 pruebas aprobadas**, incluyendo las integraciones optativas de interfaz Tk y del modelo real MediaPipe con imágenes sintéticas. Ninguna abre la webcam ni ejecuta entradas reales de mouse/teclado.
- Análisis estático y compilación de módulos: correctos. Comprobación de dependencias: sin incompatibilidades declaradas.
- Preparador ejecutado correctamente desde una carpeta distinta a la del proyecto. Versiones bloqueadas con hashes, modelo local verificado y entorno original conservado.
- Arranque y cierre de `control.py --smoke`: correctos. El lanzador `INICIAR_CONTROL.vbs --smoke`, ejecutado desde otra carpeta, inició mediante `pythonw` y dejó registrados tanto el inicio como el cierre normal. Esta prueba no usa cámara, bandeja ni atajo global.
- Interfaz Tk: geometría interna 550 × 375 y área de video 550 × 297; los controles principales caben en escalas simuladas equivalentes a 100, 125, 150 y 200 %. Ajustes desplazables y cancelación segura de calibración.
- Integración MediaPipe LIVE_STREAM: cuatro cargas reales del modelo local, al menos 16 resultados asíncronos, timestamps crecientes, inversión de imagen correcta, reinicios y cierres sin hilos restantes. Son imágenes sintéticas sin manos.
- Regresiones cubiertas: liberación del arrastre ante pérdida de mano/cuadros, rechazo de resultados antiguos, pinzas incompatibles, rearme del clic derecho, onda sin activaciones duplicadas, pausa y bloqueo de controles durante ajustes.
- Comparación estática con 1.20.36: los cinco menús conservan sus 40 posiciones, etiquetas y orden. Los cambios de tiempos, reconocimiento y perfiles están detallados en `GESTURES.md`.
- El PNG del icono conserva exactamente el SHA-256 del ancla aprobada. El splash incluye **Desarrollado por Luics415**; no se ha solicitado un rediseño de su composición.

La integración del modelo emite dos advertencias internas de protobuf acerca de una futura incompatibilidad con Python 3.14. No son errores en el objetivo validado Python 3.12; por ello no se ofrece compatibilidad con versiones arbitrarias de Python.

## Medición sintética

Una ejecución local de 5.000 actualizaciones del motor y 60 cuadros negros de 640 × 480 obtuvo:

| Componente | Media | Percentil 95 |
| --- | ---: | ---: |
| Motor de gestos, sin ejecutar acciones | 0,0359 ms | 0,0439 ms |
| Inferencia MediaPipe sobre cuadros negros | 16,64 ms | 17,23 ms |

Esto **no mide** la latencia cámara → detección → movimiento visible, la precisión con manos, los FPS reales de la webcam ni un porcentaje de mejora frente a la versión histórica. Tampoco se extrapola a otras computadoras.

## Límites de esta comprobación

La inspección automática mediante capturas de ventanas no pudo completarse: la habilidad de control de escritorio devolvió `SetIsBorderRequired failed: Interfaz no compatible (0x80004002)` en el intento y su reintento. Se verificó el ciclo de vida y la geometría de los controles desde Tk, pero eso no sustituye una inspección visual humana.

Quedan por probar físicamente la cámara, luces/distancias, comodidad y falsos positivos, bandeja y atajo global, audio, acciones en aplicaciones reales, desconexiones de dispositivos y monitores con DPI distintos. La ventana fija y sus propiedades se prueban desde Tk; su composición transparente debe revisarse en el escritorio real. Véase la lista de aceptación de `PHASES_1_4.md`.

Esta es una **base local de desarrollo**, no un instalador para Windows limpio, ejecutable firmado ni GitHub Release. La habilitación deliberada y los comandos de la segunda mano continúan pendientes de la fase 5; distinguirla para evitar interferencias ya forma parte del selector actual.

## Repetir la batería completa

```powershell
$env:BIOGESTURE_TEST_MEDIAPIPE = '1'
$env:BIOGESTURE_TEST_GUI = '1'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
```

Las pruebas de interfaz abren ventanas de prueba temporalmente y se cierran al terminar. Sin estas variables, las integraciones optativas se omiten de forma explícita.
