# Corrección ocular y splash 3.5 — 28 de septiembre de 2026

El diagnóstico `mirada-20260928-221718-50e1bd2d.json` no autorizó el cursor ocular: el error medio fue **3.4 %**, pero el máximo **8.5 %** superó el límite de 8.0 %. El bloqueo es deliberado y seguro; no se relaja el umbral ni se habilita el control con una calibración fallida.

## Estabilidad

El puntero ocular mantiene el filtro One Euro independiente del índice y baja sus parámetros de `min_cutoff=0.30, beta=5.0` a `min_cutoff=0.22, beta=4.0`. Esto reduce el tambaleo durante fijaciones y mantiene una respuesta rápida a desplazamientos intencionales. El filtro no modifica la calibración ni sus límites de aprobación.

## Identidad visual

El splash conserva exactamente el ancla, el nombre, ADMIN, INVITADO, la barra y la firma **Desarrollado por Luics415**. Solo se actualiza el número visible de **2.7** a **3.5**. La edición anterior se conserva en `assets/brand/splash-author-2.7.png`; la edición 2.0 histórica permanece intacta.

La suma SHA-256 del splash 3.5 es `cc4b90b98228a07cb54fb95231bd7de65e0ad40c8817d7c5ab216049bfd996d9`.

## Próxima prueba

Después de iniciar la aplicación, repite la calibración con la cabeza cómoda y mueve solo los ojos hacia el centro de cada objetivo. Si vuelve a fallar, exporta el diagnóstico antes de repetirlo. El filtro más estable solo actúa después de aprobar; no puede convertir un resultado de calibración insuficiente en uno válido.
