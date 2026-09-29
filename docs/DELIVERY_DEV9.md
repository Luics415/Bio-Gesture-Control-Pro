# Entrega dev9 · fijación ocular y calibración limpia

## Cambios de esta revisión

- El puntero ocular conserva la última fijación cuando el movimiento filtrado es menor que `0.0055` en coordenadas normalizadas. Solo libera esa fijación después de superar `0.010`, evitando que el cursor tiemble por cambios mínimos sin bloquear desplazamientos intencionales.
- La histéresis es únicamente de salida: no modifica las muestras, el ajuste personal ni los límites de aceptación.
- Durante la recogida de puntos, la ventana de calibración muestra solo el objetivo. El centro alterna dos colores estáticos entre puntos; no hay animación continua ni textos superpuestos cerca de objetivos periféricos.
- El diagnóstico exportado identifica también `fixation_radius` y `fixation_release_radius` para que el comportamiento pueda reproducirse.

## Diagnóstico recibido

El informe `mirada-20260928-224540-dee40a84.json` corresponde a `3.0.0.dev4` y sigue siendo **no apto para desbloquear**:

- error medio: `5.1 %` (límite `4.0 %`);
- error máximo: `10.5 %` (límite `8.0 %`);
- peor objetivo: `(0.8, 0.5)`;
- muestras válidas recogidas: `181`.

Por seguridad, el resultado no se convierte en una calibración utilizable. El mejor intento no tiene que ser el primero, pero cada comprobación debe superar de forma independiente ambos límites antes de permitir acciones. El filtro de fijación puede hacer el cursor más estable después de aprobar; no puede convertir una comprobación fallida en válida.

## Validación local

La batería ocular y de diagnóstico quedó en `128 passed, 12 skipped`. Las omisiones corresponden a geometría Tk nativa optativa y no a la lógica de calibración. Ruff permanece correcto.

La prueba física y la verificación en un equipo limpio siguen siendo pasos separados de esta validación local.
