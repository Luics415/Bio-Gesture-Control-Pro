# Aviso de privacidad

**Bio-Gesture Control Pro · vigente desde el 28 de septiembre de 2026**

Este aviso describe la aplicación de escritorio y su portable. El repositorio y cualquier página alojada por GitHub son servicios independientes y tienen sus propios avisos.

## Responsable y datos tratados

El proyecto es desarrollado por **Luics415**. La cámara se procesa localmente para detectar manos, rostro e iris. Los fotogramas permanecen en memoria durante la inferencia: la aplicación no los envía ni los guarda como fotografías o vídeo y no identifica al propietario.

Puede guardarse lo siguiente en `%LOCALAPPDATA%/BioGestureControlPro`:

- preferencias de control, monitor y cámara;
- un JSON numérico de diagnóstico ocular únicamente si el usuario pulsa **Exportar diagnóstico**. Incluye geometría, tiempos, errores y configuración; no incluye imágenes ni vídeo.

El usuario puede borrar esa carpeta. No se crean cuentas ni perfiles publicitarios.

## Red, analítica e integraciones

El uso normal no hace solicitudes de red y no incorpora analítica, publicidad, SDK de seguimiento ni cookies. El script opcional de preparación descarga los modelos desde los dominios de Open Model Zoo indicados en la documentación; no se ejecuta al arrancar. MediaPipe, OpenCV, OpenVINO, pynput, pystray y las demás dependencias se usan para las funciones descritas y sus avisos están en [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

La mirada y la imagen facial pueden ser datos personales o sensibles si se relacionan con una persona. El tratamiento local se limita a la función que activa el usuario. Para una solicitud de acceso, rectificación, cancelación u oposición, utiliza un canal privado que el responsable publique junto con la versión; no compartas datos personales en issues públicos. La referencia pública es <https://github.com/Luics415/Bio-Gesture-Control-Pro>.

Si se añade una cuenta, nube, analítica o envío de imágenes, este aviso y el consentimiento se revisarán antes de activarlo.

> Este texto es informativo y no constituye asesoría jurídica. Revisa la ley aplicable a tu caso.

