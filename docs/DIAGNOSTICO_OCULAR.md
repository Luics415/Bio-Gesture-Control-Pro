# Diagnóstico ocular · 3.0.0.dev4

Este modo sirve para investigar por qué la calibración no se aprueba. **No es una solución ya validada de la precisión ni una forma de omitir la comprobación.** Funciona desde la carpeta y `INICIAR_CONTROL.vbs`, o desde el portable dev4 de pruebas. El EXE público 2.7 no incluye estos cambios.

## Una prueba que permita investigar

1. Cierra la aplicación anterior y abre `INICIAR_CONTROL.vbs` o el portable de esta revisión. Debe indicar **3.0.0.dev4**.
2. En Ajustes → Control elige ojos y **Motor ocular → Precisión v2 · OpenVINO**. Guarda y abre la calibración. Usa una postura cómoda y el fondo con el que harás todo el intento. Mira los objetivos con los ojos, sin girar la cabeza para apuntar. Parpadea normalmente.
3. Completa los 21 puntos y los 13 de comprobación. Personal v1 conserva trece y nueve; el geométrico conserva nueve y cinco, si los eliges para comparar. Si falla, **no pulses Reintentar todo todavía**: eso reemplaza las mediciones del intento anterior.
4. Revisa el mapa de error. Si deseas verlo en movimiento, pulsa **P** y mira distintas zonas. **F** alterna la cruz original/estabilizada: esta última tiene el mismo filtro del cursor ocular. **El ratón real no se mueve y las acciones de manos siguen pausadas.** P o Esc regresa al resultado.
5. Pulsa **E** o **Exportar diagnóstico**. Se guarda el intento de calibración, no una grabación del visor P.
6. Cierra el asistente y entra a **Ajustes → Diagnóstico → Abrir carpeta de diagnóstico**. Dentro de `diagnostics/gaze`, busca el archivo `mirada-fecha-identificador.json` más reciente. Adjunta ese archivo para analizarlo; una captura del mapa también ayuda.

En Windows la ubicación habitual es `%LOCALAPPDATA%\BioGestureControlPro\diagnostics\gaze`. Si se configuró `BIOGESTURE_DATA_DIR`, se utiliza esa carpeta de datos. La ruta exacta aparece al exportar. Cada exportación crea un archivo diferente y conserva los anteriores.

## Qué se puede ver

| Control | Qué muestra | Qué no hace |
|---|---|---|
| Mapa tras el fallo | Círculos: objetivos. Cruces: mirada media calculada. Líneas: desvío. Error por punto. | No promedia los errores para ocultar cuadros malos en la aprobación. |
| D · Detalle | Motor, capturas nuevas por segundo, edad de muestra, coste del detector y del cálculo neuronal, dirección de mirada, píxeles de los ojos, apertura, iris, postura y recogida por punto. | No aumenta la resolución de la cámara ni certifica la calidad del iris. |
| P · Probar sin controlar PC | Una cruz de seguimiento usando el ajuste actual, con bloqueos cuando la muestra no es válida o queda fuera del margen. | No mueve el cursor del sistema, no hace clic, no modifica el ajuste y no aprueba la calibración. |
| E · Exportar | Informe numérico local para repetir el análisis sin usar la cámara. | No guarda fotos, vídeo, audio ni envía el informe. |

Durante los objetivos no se muestra la predicción. Mirar una cruz que se mueve en lugar del objetivo contaminaría la prueba. En el visor P no se recogen nuevas muestras de aprendizaje o comprobación.

La estabilización solo afecta la salida del puntero, no los errores que deciden la aprobación. El JSON registra las muestras originales y el identificador/parámetros del filtro; no una grabación de P. No debe confundirse una cruz más quieta con una calibración espacial más precisa. Los tiempos de cálculo dev4 usan un reloj de alta resolución; la instantánea exportada sigue sin equivaler a una medición térmica prolongada.

## Cómo interpretar los datos

- **Error de entrenamiento:** qué bien reproduce los puntos que ya aprendió. Un resultado pequeño por sí solo no demuestra que funcione.
- **Error de comprobación:** qué bien estima puntos nuevos. Sigue decidiendo la aprobación con los mismos límites de error normalizado medio 4 % y máximo 8 %, evaluando cada cuadro.
- **Desvío X/Y y dispersión:** ayudan a distinguir una estimación estable pero desplazada de una que varía mucho dentro del mismo punto.
- **Rango de la señal y sensibilidad del modelo:** en el motor anterior permiten comprobar si un cambio diminuto en el iris se amplifica excesivamente. El motor personal no publica coeficientes lineales ficticios: identifica su familia, regularización y error de selección entre objetivos de aprendizaje. Este error tampoco equivale a una comprobación aprobada.
- **FPS de observaciones/detector:** son cifras medidas, distintas de los FPS solicitados a la cámara. Una cámara configurada a 60 FPS no asegura 60 estimaciones por segundo.
- **Telemetría del contexto exportado:** es la última instantánea al generar el informe, no un historial de rendimiento de toda la calibración. Las muestras y los resúmenes por objetivo sí corresponden al intento recogido.
- **Rechazos:** una predicción bloqueada no cuenta como acierto. Un resumen con menos cuadros calculables debe leerse junto a su número de rechazos.

Las primeras pruebas reales de dev2 tuvieron errores medios entre 7.11 % y 21.40 %, con variación intrapunto entre 1.27 % y 3.29 %. Esto apunta a un desfase de posición mayor que la dispersión. **No determina todavía si la causa es señal ocular débil, representación, aprendizaje o variación entre fases**, ni permite responsabilizar a los lentes o a cómo se realizó el gesto.

## Privacidad y alcance

La exportación se realiza **solo al pulsar E o su botón**. Incluye las diez características geométricas, objetivos, tiempos relativos de las muestras, errores y configuración técnica permitida. El motor personal añade seis números por observación: vector unitario de mirada XYZ y postura yaw/pitch/roll en radianes. También identifica el motor, el esquema y la selección del ajuste. Son datos de la prueba ocular; revisa con quién los compartes.

No incluye imágenes, vídeo, audio ni una identidad facial. No se sube a GitHub ni a servicios externos, no cambia tus ajustes y no se carga como perfil al abrir el programa. Cerrar un intento fallido descarta su diagnóstico en memoria; si se aprueba una calibración, el programa conserva sus datos durante la sesión ocular para poder usarla. Los JSON que elegiste exportar permanecen hasta que decidas borrarlos. El visor P conserva únicamente la observación actual y un historial acotado de tiempos, no una grabación.

## Reproducir un informe sin cámara (opcional)

No necesitas este comando para usar los botones. Desde la raíz del proyecto, en PowerShell, sustituye la ruta por el archivo que exportaste:

```powershell
.\.venv\Scripts\python.exe -m biogesture.gaze_replay "C:\ruta\mirada-prueba.json"
```

Para obtener el análisis completo como JSON en la consola:

```powershell
.\.venv\Scripts\python.exe -m biogesture.gaze_replay "C:\ruta\mirada-prueba.json" --json
```

La herramienta vuelve a ajustar con las muestras de entrenamiento y comprueba las muestras independientes en su orden original. Admite los informes antiguos (esquema 1) y los informes del motor personal (esquema 2). El registro de motores es cerrado: un JSON no puede seleccionar módulos arbitrarios. No abre cámara o interfaz, no envía entradas al escritorio, no modifica el archivo y no instala la calibración en el programa.

La reproducción usa números ya extraídos: **no vuelve a ejecutar las redes sobre imágenes**, porque el informe no las contiene. Por eso los informes antiguos no permiten medir cómo se habría comportado el motor nuevo. Se necesita una prueba física nueva. Usar otra revisión del algoritmo en el futuro puede producir resultados diferentes; el informe identifica la revisión de origen.

⚓ Desarrollado por Luics415
