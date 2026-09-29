# Auditoría de imágenes y contenido visual

Revisión: 28 de septiembre de 2026.

## Identidad del proyecto

- `assets/brand/anchor-approved.png` es el ancla aprobada por Luics415.
- `assets/brand/splash-author.png` es la composición aprobada con “2.7” y “Desarrollado por Luics415”. `splash-author-2.0.png` se conserva como histórico y no se usa como splash del portable.
- `assets/brand/tray.png` y `app.ico` son conversiones del ancla para la bandeja y Windows. No se descargan imágenes de terceros al ejecutar.

## Manual y capturas

El manual PDF público se genera con `scripts/create_user_manual.py` y los dibujos de manos de `scripts/manual_hands.py`. Se eligieron dibujos explicativos, no fotografías de personas ni material tomado de la web. Las capturas aportadas por el usuario están en `docs/captures/private/`, excluidas de Git y del paquete público; no deben publicarse sin aprobación específica.

## Modelos y terceros

Los modelos de manos, rostro, mirada y postura tienen su procedencia y licencia en [`assets/models/README.md`](../assets/models/README.md). Las bibliotecas incluidas y sus avisos están en [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). Una licencia de software no demuestra por sí sola derechos sobre una fotografía, marca o retrato futuro: cada nueva imagen debe conservar su fuente, permiso o licencia verificable.

No se presentan renders sintéticos, capturas históricas ni resultados de pruebas como evidencia de precisión física. Las afirmaciones de rendimiento y compatibilidad deben conservar el alcance y las limitaciones indicadas en [`README-3.0.md`](../README-3.0.md).

