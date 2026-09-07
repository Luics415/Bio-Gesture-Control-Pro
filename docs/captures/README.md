# Registro de capturas para la documentación 2.0

## 2026-09-07 · capturas aportadas por el usuario

Se conservaron dos originales, byte por byte, en `private/`: `2026-09-07-gesto-L-original.png` y `2026-09-07-dos-manos-original.png`. Muestran dev.5 a 1920×1080. Son referencias de postura, no pruebas de desplazamiento ni evidencia de la corrección dev.6. Sin puntos visibles no puede deducirse qué rol tenía cada mano.

Por decisión del usuario, el manual utiliza **dibujos explicativos**, no estas capturas. Los originales contienen otras ventanas del escritorio: `private/` está excluido de Git y del paquete público. No se modificaron ni recortaron. No se publicarán sin aprobación específica.

SHA-256 para comprobar su conservación:

- Gesto L: `ef49e9f447aa52579dcca5201729f34c29ecb2ad48c831c16f816f76bd6ef6cb`.
- Dos manos: `19d9269e33d645cf691154251e275f0dc9cb19920f73112ffceb033e6b957284`.

El análisis del detector utilizó la zona de cámara en memoria; las pruebas conservan únicamente 21 puntos normalizados por mano, sin imagen ni información del escritorio. Esto reproduce observaciones estáticas, no una sesión física continua.

## Historial · capturador automático incompatible

Se abrió la ventana real de Bio-Gesture en modo de prueba sin cámara ni entradas del sistema. La captura mediante Windows Graphics Capture falló con `SetIsBorderRequired failed: Interfaz no compatible (0x80004002)`. Se renovó la selección de ventana y se realizó un segundo intento con el mismo resultado. Las dos ventanas de prueba abiertas durante la comprobación se cerraron automáticamente.

**No se generaron capturas de pantalla válidas en esta sesión.** La vista previa `output/desktop-preview.svg` de revisiones anteriores es un render sintético, no una captura ni evidencia de detección física. No debe presentarse como fotografía de una sesión real.

## Capturas pendientes

| Archivo propuesto | Qué documentar | Condición |
| --- | --- | --- |
| `01-splash.png` | Ancla y firma del autor durante el arranque | Ventana real, arte aprobado intacto |
| `02-vista-limpia.png` | Cámara sin puntos ni mensajes | Ejecutable dev.6, casilla de puntos desmarcada |
| `03-radial.png` | Menú simple y barra de carga | Selección real, sin datos privados de otras ventanas |
| `04-dos-manos.png` | Principal y auxiliar simultáneas | Diagnóstico temporal con landmarks; no confundir con vista final |
| `05-l-superior.png` | L en mitad superior | Comprobar además scroll arriba en la prueba física |
| `06-l-inferior.png` | L en mitad inferior | Comprobar además scroll abajo en la prueba física |
| `07-ajustes.png` | Configuración y diagnóstico | Recortar a la ventana del proyecto |

Para cada captura real guardar fecha, versión, modo, resolución y observación. No fotografiar documentos privados, claves, otras aplicaciones ni contenido innecesario del escritorio. La imagen por sí sola no prueba la dirección del desplazamiento: registrar también el resultado observado.

Si este capturador sigue siendo incompatible, las capturas pueden proporcionarse manualmente con la herramienta de recortes de Windows y guardarse en esta carpeta. Mantenerlas locales hasta aprobar su inclusión pública.
