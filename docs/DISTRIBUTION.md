# Distribución 2.7 · Windows x64

La distribución de **2.7.0** es **portable en carpeta**, sin consola y sin Python instalado por separado. No es un EXE suelto ni un instalador firmado. Compilar un paquete no lo publica automáticamente; el estado de publicación se verifica por separado. El resultado concreto de cada compilación queda en su `BUILD-MANIFEST.json` y su archivo `.zip.sha256`.

## Para usar el paquete

1. Extraer todo el ZIP en una carpeta propia de usuario.
2. Abrir `BioGestureControlPro.exe`, conservando `_internal` junto a él.
3. Configurar cámara/monitor y activar el control desde su inicio pausado.
4. Cerrar desde Más o la bandeja antes de mover o retirar la carpeta.

El manual ilustrado de **17 páginas** está junto al ejecutable como **Manual-de-usuario.pdf**, con diagramas y la firma aprobada al final. No necesita Python ni conexión para abrirse en un lector PDF. El README principal incluye la guía completa de gestos, perfiles y ajustes. El original 1.0 queda en `legacy/v1.20.36/README.md`, solo como referencia histórica.

No requiere BAT, VBS, Python, Git ni descargas de modelo al arrancar. No instala servicios ni añade inicio automático. Dentro de la cámara solo se dibujan el video, los puntos opcionales y el radial: no hay mensajes ni ayudas, tampoco con `--diagnostics` o desde el código. Los diagnósticos se consultan en Ajustes. Los datos del usuario están fuera del paquete, en `%LOCALAPPDATA%\BioGestureControlPro`.

El arranque normal no muestra estado en la franja inferior. `--diagnostics` explícito permite verlo únicamente en esa franja, fuera de cámara; `--clean-ui` la mantiene sin estado.

Para retirar el portable basta cerrar la aplicación y eliminar la carpeta extraída. Los ajustes se conservan por separado, no se borran automáticamente. Un instalador con accesos y desinstalador formal sigue pendiente.

## Compilar desde el código

Requiere el entorno de desarrollo del proyecto, Python 3.12 x64 con Tcl/Tk y Windows x64. Las versiones del compilador y sus dependencias están bloqueadas con hashes, conservando el bloqueo de ejecución.

El manual aprobado se versiona en **docs/manual/Manual-de-usuario.pdf**, de modo que existe también en una copia completa del repositorio y el enlace del README principal funciona sin archivos locales ignorados. Compilar utiliza esa copia; no es necesario regenerarla si no has cambiado el manual. Si falta, su cabecera no corresponde a PDF o está incompleto, la comprobación se detiene antes de compilar. Comprobar su formato y sus hashes no sustituye revisar visualmente las páginas.

Para actualizar el manual, desde la raíz del proyecto usa un **Python de documentos separado**, con ReportLab disponible. **scripts/create_user_manual.py** utiliza los dibujos de **scripts/manual_hands.py** y genera **output/pdf/Bio-Gesture-Control-Pro-2.7-Manual-de-usuario.pdf** como borrador local. Sustituye la ruta ilustrativa por la de ese intérprete; no es el Python del portable ni obliga a instalar ReportLab en la `.venv` de la aplicación:

```powershell
& 'C:\ruta\al\entorno-documentos\Scripts\python.exe' .\scripts\create_user_manual.py
```

El generador actual usa las fuentes Segoe UI de Windows y el arte aprobado del proyecto. Después de revisar visualmente todas las páginas, enlaces y contenido, actualiza expresamente la copia aprobada de **docs/manual/Manual-de-usuario.pdf** con ese PDF. No publiques el resto de `output`. El empaquetador no genera el manual ni instala ReportLab. `-CheckOnly` también exige la copia aprobada presente y completa; no la crea automáticamente. Las pruebas unitarias usan documentos mínimos aislados y no importan el generador ni dependen de un PDF local en `output` o de ReportLab en CI.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-portable.ps1 -InstallBuildTools
```

La excepción de ejecución aplica únicamente a ese proceso. Con las herramientas ya instaladas, omite `-InstallBuildTools`. Para revisar requisitos sin compilar usa `-CheckOnly`. El script funciona independientemente de la carpeta desde la que se invoque.

El proceso crea carpetas nuevas identificadas por fecha UTC, sin sobrescribir entregas anteriores:

```text
dist/
  BioGestureControlPro-<version>-windows-x64-<fecha>/
    BioGestureControlPro/
      BioGestureControlPro.exe
      _internal/
      README-2.0.md             Referencia hacia la guía actual
      Manual-de-usuario.pdf     Manual ilustrado local
      README.md                 Guía actual 2.7
      legacy/v1.20.36/README.md  Histórico 1.0 intacto
      docs/                     Documentación pública seleccionada
      BUILD-MANIFEST.json
  BioGestureControlPro-<version>-windows-x64-<fecha>.zip
  BioGestureControlPro-<version>-windows-x64-<fecha>.zip.sha256
```

## Qué se comprueba antes de crear el ZIP

- Versiones de dependencias y hash del modelo local.
- Subsistema gráfico del EXE: no usa una consola.
- Presencia del intérprete integrado y recursos Tcl/Tk.
- Igualdad de ancla, splash, iconos, modelo y documentación con sus entradas.
- Copia exacta del único PDF aprobado a `Manual-de-usuario.pdf`: cabecera PDF, marcador final y SHA-256 iguales al original. El PDF, su generador y `scripts/manual_hands.py` quedan identificados en el inventario de fuentes; modificarlos durante la compilación impide crear el ZIP.
- Inferencia del modelo sobre un cuadro negro: `--detector-smoke`, sin cámara ni entradas del sistema.
- Apertura y cierre de la interfaz: `--smoke`, sin cámara, bandeja ni atajos globales.
- Ejecución desde otra carpeta, sin Python en `PATH` y con datos de prueba aislados fuera del paquete.
- Segunda ejecución completa desde una carpeta con espacios y acentos, con datos de diagnóstico también en esa ruta; un fallo impide crear el ZIP. El modelo se entrega a MediaPipe como bytes para no depender de su apertura nativa de rutas Unicode.
- Exclusión de entornos virtuales, cachés de proyecto, registros personales, ajustes, claves y enlaces externos al paquete.
- Manifiesto de archivos y SHA-256 del ZIP.

Las dependencias se acompañan de metadatos y textos de licencia disponibles en las distribuciones instaladas, además de la licencia del intérprete. El inventario no equivale a una certificación legal completa del producto final.

Las entradas están fijadas, pero no se promete un EXE binariamente idéntico entre equipos. El manifiesto identifica los archivos usados en cada compilación. El mapeo es explícito: `docs/manual/Manual-de-usuario.pdf` → `Manual-de-usuario.pdf`. No se incluye una carpeta `output` ni se recorren PDF o previsualizaciones adicionales. Las imágenes de sesiones personales y `docs/captures/private` no forman parte del paquete; esa carpeta privada se rechaza también si apareciera dentro de `_internal`.

## Lo que aún requiere otro entorno o aprobación

Un `PATH` sin Python **no equivale a una computadora recién instalada**. Debe probarse extracción, arranque, cámara, audio, gestos y cierre en Windows 10/11 x64 limpio, sin Python ni bibliotecas de desarrollo. Debe comprobarse también el comportamiento del portable desde una carpeta de solo lectura: la configuración pertenece al perfil del usuario.

La prueba física de dos manos y scroll en L sigue el checklist de [Fases](PHASES_1_4.md). El usuario aportó dos capturas de dev.5 conservadas como material privado; las capturas automáticas de la revisión actual siguen pendientes por incompatibilidad del capturador disponible. El manual utiliza dibujos explicativos y el arte de firma aprobado, no capturas de sesión; véase [Registro](captures/README.md).

Este binario de desarrollo no tiene firma Authenticode. No se promete que Windows lo trate como un ejecutable de editor verificado. La firma visual “Desarrollado por Luics415” y el ancla no son una firma digital. Certificado de firma, instalador y publicación se gestionan por separado; no se modifican las protecciones de Windows para probar el programa.
