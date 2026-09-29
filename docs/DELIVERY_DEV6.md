# Entrega local dev.6 — 7 de septiembre de 2026

Portable Windows x64, no instalador ni Release firmada. Esta nota se registra después de verificar la entrega; no se modifica el ZIP ya generado.

## Archivos entregados

- ZIP: `dist/BioGestureControlPro-2.0.0-dev.6-windows-x64-20260907T224726308728Z.zip`.
- Tamaño ZIP: 153341770 bytes.
- SHA-256 ZIP: `5aab41f74e046373e24b223a3528bb5cd2bbe1f37c19f86b1214ec1c3daafeb1`.
- Ejecutable: dentro de la carpeta homónima, `BioGestureControlPro/BioGestureControlPro.exe`.
- Manual: `output/pdf/Bio-Gesture-Control-Pro-2.0-Manual-de-usuario.pdf`; copia idéntica en la raíz del portable como `Manual-de-usuario.pdf`.
- SHA-256 PDF: `864d226d80eeb8a6150331969d26471fa6961ebc061dd7e0c375d25999a44e89`.
- PDF: 2482867 bytes, 16 páginas A4, texto buscable, 16 marcadores y 6 enlaces internos en el índice. Dibujos vectoriales; la única imagen raster es el ancla aprobada de portada. Todas las páginas finales fueron renderizadas y revisadas visualmente, además de comprobar límites del texto y ausencia de capturas personales.

La entrega dev.5 válida del ZIP terminado en `20260907T212915464061Z` se conserva como respaldo. No se cerró ni sustituyó la sesión que tuviera abierta el usuario.

## Comprobaciones realizadas

- 848 pruebas aprobadas, ninguna omitida, Tk y MediaPipe habilitados: `output/validation-dev6/tests-release.xml`, 15.23 s. Incluye 69 pruebas del empaquetado. Dos advertencias conocidas de protobuf sobre una futura versión de Python; no fallos en Python 3.12.
- Ruff, compilación de módulos y comprobación de dependencias correctos.
- `build_portable.py --check` y compilación completa correctos.
- Detector empaquetado: un cuadro negro, cero manos, modelo aprobado, salida 0. Interfaz empaquetada: apertura y cierre de prueba, salida 0. Ambas comprobaciones se repiten desde `Prueba portable á`, sin Python en PATH y con datos aislados. No abren cámara ni generan entradas reales del sistema.
- Manifiesto, hashes de 1427 archivos, miembros del ZIP y CRC comprobados. El inventario de fuentes coincide con el proyecto al terminar la compilación. PDF incluido idéntico por hash; no hay capturas privadas, registros personales ni claves en el inventario del paquete.
- Versión de producto y archivo del EXE: `2.0.0-dev.6`. Subsistema gráfico, firma Authenticode: `NotSigned`.
- README original intacto: SHA-256 `312dc0df773810135751006f42d42e819ad3b75df8063f1a5719f8a7c13a66da`. Ancla y splash conservados; no hubo rediseño. Gestos principales, selección, coordenadas y seguimiento sin cambios respecto a dev.5.

## Correcciones y límites

La casilla de puntos ahora funciona en vista limpia y diagnóstica, sin activar textos ni mensajes. Las preferencias anteriores marcadas se respetan; los ajustes nuevos comienzan desmarcados.

La L de la captura ya se reconocía, pero su palma estaba apenas fuera del centro: la velocidad anterior era prácticamente nula. Dev.6 conserva el centro 45–55 %, establece velocidad útil del 25–100 % del ajuste fuera de la banda y tolera una L natural. La reproducción de la muestra aporta un primer paso en como máximo 1.2 s; eso **no certifica** el comportamiento continuo con una webcam real. Se rechazan las tres palmas abiertas observadas y se prueban transformaciones, ruido y bloqueos.

Los dos originales del usuario se conservan byte por byte en `docs/captures/private`, fuera de Git y del portable. El manual usa dibujos por petición expresa. No se publicaron imágenes ni cambios en GitHub.

Pendiente: prueba física de dev.6 con ambas manos, luces/distancias y aplicaciones habituales; Windows limpio sin Python; instalador/desinstalador formal, firma digital y publicación.

## Cómo probar esta entrega

Cierra la versión anterior desde Más o la bandeja. Extrae todo el ZIP nuevo en otra carpeta, manteniendo `_internal` junto al EXE. Abre el programa, elige la principal mostrando una sola mano y luego usa ambas. Para comprobar puntos, marca la casilla y Guarda; vuelve a elegir la principal tras reiniciar la cámara y pulsa Activar.

Prueba la L auxiliar sobre un documento desplazable, con la principal sin otro gesto exclusivo: palma arriba, centro y abajo. La referencia es la palma, no la punta del índice. Usa `Ctrl+Alt+F12` para pausar y recuperar la ventana si el atajo global está disponible. El manual y el README 2 detallan los demás controles.
