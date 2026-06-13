import shutil
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.auto_cierre as auto_cierre
import core.db as db


def _estado_tarea(db_path, titulo):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT estado FROM tareas WHERE titulo=? ORDER BY id DESC LIMIT 1",
            (titulo,),
        ).fetchone()[0]


def main():
    source = PROJECT_ROOT / "database.db"
    target = PROJECT_ROOT / "database_test_autocierre_8h.db"
    shutil.copy2(source, target)
    db.DB_PATH = target
    auto_cierre.registrar_tarea_diaria = lambda *args, **kwargs: None

    titulo = "OP_TEST_AUTOCIERRE_8H_ESTRICTO"
    with sqlite3.connect(target) as conn:
        conn.row_factory = sqlite3.Row
        db.ensure_tareas_columns(conn)
        conn.execute(
            """
            INSERT INTO tareas (
                titulo, descripcion, proceso, asignado_a, inicio,
                estado, cantidad, horario_extendido
            )
            VALUES (?, ?, ?, ?, ?, 'En curso', 0, 0)
            """,
            (
                titulo,
                "PRUEBA FUERA DE TURNO CON MENOS DE 8 HORAS",
                "TEST",
                "usuario_prueba",
                "2026-06-12 21:00:00",
            ),
        )

    auto_cierre.now_iso = lambda: "2026-06-15 05:00:00"
    cerradas_antes = auto_cierre.ejecutar_autocierre()
    estado_antes = _estado_tarea(target, titulo)
    assert cerradas_antes == 0
    assert estado_antes == "En curso"

    auto_cierre.now_iso = lambda: "2026-06-15 07:02:00"
    cerradas_despues = auto_cierre.ejecutar_autocierre()
    estado_despues = _estado_tarea(target, titulo)
    assert cerradas_despues == 1
    assert estado_despues == "Finalizado"

    print("OK: fuera de turno no cierra antes de 8 horas.")
    print("OK: cierra al superar 8 horas y el minuto de gracia.")


if __name__ == "__main__":
    main()
