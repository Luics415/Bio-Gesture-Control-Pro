# Entrega local verificada · 2.0.0-dev.5

Fecha: 2026-09-07. Estado: portable de pruebas local, sin firma digital y sin publicación en GitHub.

## Artefacto válido

- ZIP: `dist/BioGestureControlPro-2.0.0-dev.5-windows-x64-20260907T212915464061Z.zip`.
- SHA-256: `99a67e66e764f167c132f6a4dd74d6cf3844fb8811d86165f71c66ff80708570`.
- Ejecutable: carpeta homónima en `dist`, subcarpeta `BioGestureControlPro/BioGestureControlPro.exe`.
- Se conserva el archivo `.zip.sha256` junto al ZIP.
- Debe extraerse toda la carpeta; el EXE necesita `_internal`. No requiere Python externo.

## Evidencia de esta compilación

713 pruebas aprobadas con Tk y MediaPipe habilitados, cero omitidas, dos advertencias conocidas de protobuf. Ruff, compilación de módulos y dependencias correctos. Informe fuente: `output/validation-dev5/tests-unicode-final.xml`.

El manifiesto del paquete registra código 0 en detector e interfaz, tanto desde la ruta normal como desde `Prueba portable á`, con un PATH sin Python y datos aislados. La inferencia sobre un cuadro negro utilizó el modelo aprobado, detectó cero manos y cerró correctamente.

Después se extrajo el ZIP final en otra carpeta, `Verificación á`, y se verificaron otra vez todos los hashes, el detector y el arranque/cierre de la interfaz: códigos 0. Registros conservados en `output/portable-final-dev5/probes/smoke-data`.

La comprobación del subsistema PE confirmó una aplicación gráfica; `Get-AuthenticodeSignature` devolvió `NotSigned`. No se abrió la webcam ni se generaron entradas reales del sistema durante estas verificaciones.

## Corrección encontrada al empaquetar

La primera compilación fallaba cuando MediaPipe abría el modelo mediante una ruta con acentos. La corrección lee el modelo con Python y pasa sus bytes a MediaPipe. Se probó también el seguimiento continuo desde una ruta con acentos y caracteres japoneses. Cursor, clics, geometría, roles y configuración principal conservan sus archivos anteriores; solo cambió la carga inicial del modelo en seguimiento.

## Limpieza y conservación

Se retiraron el primer ZIP fallido, su SHA, su carpeta de distribución y las tres copias desechables de verificación. Eran artefactos generados; no se enviaron a la papelera. La entrega corregida y los registros se conservan; las copias de prueba pueden regenerarse desde el ZIP válido.

También se eliminó el BAT de compatibilidad redundante de la raíz. Se mantienen `INICIAR_CONTROL.vbs`, el preparador de desarrollo, el entorno activo, el `venv` histórico y la carpeta `legacy`. No se eliminó configuración del usuario.

`README.md` coincide byte por byte con el original publicado; toda la explicación de cambios está en `README-2.0.md`. El ancla y splash aprobados no se modificaron.

## Pendientes antes de cerrar 2.0

- Validación física con ambas manos y el scroll L de centro fijo, cámaras, luces, foco y sesiones prolongadas.
- Prueba en Windows limpio sin Python: quitar Python del PATH en este equipo no equivale a ese entorno.
- Instalador/desinstalador formal, certificado de firma y publicación autorizada.
- Capturas reales: el capturador disponible falló por incompatibilidad con este Windows; no se produjeron imágenes válidas. Véase [Registro de capturas](captures/README.md).

Esta entrega no se presenta como instalador final firmado ni como aprobación de un rediseño visual completo.
