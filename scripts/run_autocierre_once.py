"""Ejecuta una revision de autocierre y termina (util para tareas programadas)."""

from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from core.auto_cierre import ejecutar_autocierre  # noqa: E402


if __name__ == "__main__":
    total = ejecutar_autocierre()
    print(f"Autocierre completado: {total} tarea(s) cerrada(s).")
