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

    titulo = "OP_TEST_AUTOCIERRE_FIN_DE_TURNO"
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
                "PRUEBA CIERRE AL FIN DE TURNO CON MENOS DE 8 HORAS",
                "TEST",
                "usuario_prueba",
                "2026-06-12 17:00:00",
            ),
        )

    # La tarea arranca dentro del turno tarde (14:01-22:00) del viernes 12/06.
    # Antes de que termine ese turno (22:00) no debe cerrarse, aunque lleve
    # muchas menos de 8 horas laborales acumuladas.
    auto_cierre.now_iso = lambda: "2026-06-12 21:30:00"
    cerradas_antes = auto_cierre.ejecutar_autocierre()
    estado_antes = _estado_tarea(target, titulo)
    assert cerradas_antes == 0
    assert estado_antes == "En curso"

    # Una vez terminado el turno tarde (22:00), el autocierre debe cerrar la
    # tarea por fin de turno, sin exigir 8 horas acumuladas ni importar la
    # hora de entrada dentro del turno.
    auto_cierre.now_iso = lambda: "2026-06-12 22:01:00"
    cerradas_despues = auto_cierre.ejecutar_autocierre()
    estado_despues = _estado_tarea(target, titulo)
    assert cerradas_despues == 1
    assert estado_despues == "Finalizado"

    print("OK: no cierra antes de terminar el turno en que arrancó.")
    print("OK: cierra al terminar el turno, sin esperar 8 horas acumuladas.")


if __name__ == "__main__":
    main()
