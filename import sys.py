import sys
import platform

print("--- DIAGNÓSTICO ---")
print(f"Versión de Python: {platform.python_version()}")
print(f"Ruta del ejecutable: {sys.executable}")

try:
    import mediapipe as mp
    print("✅ MediaPipe detectado correctamente.")
except ImportError:
    print("❌ MediaPipe NO detectado en esta versión.")