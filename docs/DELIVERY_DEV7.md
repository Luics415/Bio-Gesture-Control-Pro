# Entrega local 3.0.0.dev4 — 28 de septiembre de 2026

Esta nota describe el artefacto portable preparado para publicar. No sustituye una prueba física con cámara, una prueba en Windows limpio, una firma Authenticode ni una revisión jurídica profesional.

## Artefacto

- ZIP portable x64: el nombre y la suma SHA-256 exactos se registran en `BUILD-MANIFEST.json` junto al artefacto de cada compilación.
- El ejecutable está dentro de la carpeta homónima como `BioGestureControlPro.exe`; `_internal` debe permanecer junto al ejecutable.
- El manifiesto marca `signed: false`, `physical_validation: pending` y `clean_pc_validation: pending`.

## Comprobaciones reproducidas

- `39 passed, 2 skipped` en las pruebas de documentación, legalidad y estabilización ocular. Las dos omitidas son comprobaciones Tk nativas optativas; el entorno no tiene los archivos Tcl/Tk requeridos.
- Ruff: correcto.
- Dependencias: correctas (`pip check`).
- `scripts/build_portable.py --check`: correcto con el entorno bloqueado, incluido `setuptools==80.9.0`.
- El manifiesto del portable confirma detector, escritorio y mirada sintéticos con salida 0, sin cámara, entradas reales, red, telemetría ni conversión OpenVINO durante la prueba.
- El ZIP contiene los avisos de privacidad, términos, cookies, seguridad y derechos de recursos; no contiene entornos virtuales, credenciales, capturas privadas ni registros personales.

## Puerta de publicación

Antes de publicar hay que completar dos acciones externas al código:

1. Configurar un canal privado real del responsable para solicitudes ARCO/contacto legal y sustituir la indicación provisional de `docs/legal/PRIVACIDAD.md`. No se debe inventar ni publicar un correo sin confirmación del autor.
2. Autenticar GitHub y crear el commit/push desde una sesión con permisos de escritura. El checkout actual no puede escribir `.git/index` por sus permisos ACL y la sesión de GitHub disponible no tiene un token válido.

La publicación no debe presentarse como un instalador firmado ni como validación universal de Windows hasta completar esas comprobaciones.
