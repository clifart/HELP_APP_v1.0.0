import argparse
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

import core.db as db


def _parse_dt(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _ultimo_sabado(hora, minuto):
    hoy = datetime.now()
    # weekday(): lunes=0 .. domingo=6; sabado=5
    offset = (hoy.weekday() - 5) % 7
    if offset == 0:
        offset = 7
    base = (hoy - timedelta(days=offset)).replace(
        hour=hora, minute=minuto, second=0, microsecond=0
    )
    return base


def _ultimo_viernes(hora, minuto):
    hoy = datetime.now()
    # weekday(): lunes=0 .. domingo=6; viernes=4
    offset = (hoy.weekday() - 4) % 7
    if offset == 0:
        offset = 7
    base = (hoy - timedelta(days=offset)).replace(
        hour=hora, minute=minuto, second=0, microsecond=0
    )
    return base


def main():
    parser = argparse.ArgumentParser(
        description="Prueba autocierre en una copia de la BD (no toca la real)."
    )
    parser.add_argument(
        "--db",
        default="database.db",
        help="Ruta a la base real (solo lectura).",
    )
    parser.add_argument(
        "--db-copy",
        default="database_test_autocierre.db",
        help="Ruta a la copia para pruebas.",
    )
    parser.add_argument(
        "--sabado-diurno",
        default=None,
        help="Inicio diurno sabado (YYYY-MM-DD HH:MM:SS).",
    )
    parser.add_argument(
        "--viernes-nocturno",
        "--sabado-nocturno",
        default=None,
        help="Inicio nocturno viernes (YYYY-MM-DD HH:MM:SS).",
    )
    parser.add_argument(
        "--no-cierre",
        default=None,
        help="Inicio de caso que NO debe cerrar (YYYY-MM-DD HH:MM:SS).",
    )
    args = parser.parse_args()

    src = Path(args.db)
    dst = Path(args.db_copy)
    if not src.exists():
        raise SystemExit(f"No existe la base: {src}")

    shutil.copy2(src, dst)

    # Redirigir DB_PATH a la copia
    if hasattr(db, "DB_PATH"):
        db.DB_PATH = dst

    from core.db import ensure_tareas_columns
    import core.auto_cierre as ac

    # Evitar escritura de Excel en prueba
    ac.registrar_tarea_diaria = lambda *a, **k: None

    sabado_diurno = _parse_dt(args.sabado_diurno) if args.sabado_diurno else _ultimo_sabado(6, 0)
    viernes_noct = _parse_dt(args.viernes_nocturno) if args.viernes_nocturno else _ultimo_viernes(21, 30)
    no_cierre = _parse_dt(args.no_cierre) if args.no_cierre else datetime.now().replace(
        hour=16, minute=30, second=0, microsecond=0
    )

    test_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    op_sabado = f"OP_TEST_SABADO_{test_id}"
    op_noct = f"OP_TEST_NOCT_VIE_{test_id}"
    op_no_cierre = f"OP_TEST_NO_CIERRE_{test_id}"

    conn = sqlite3.connect(str(dst))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ensure_tareas_columns(conn)

    cur.execute(
        """
        INSERT INTO tareas (titulo, descripcion, proceso, asignado_a, inicio, estado, cantidad, horario_extendido)
        VALUES (?, ?, ?, ?, ?, 'En curso', 0, 0)
        """,
        (op_sabado, "PRUEBA SABADO AUTOCIERRE", "TEST", "usuario_olvido", sabado_diurno.strftime("%Y-%m-%d %H:%M:%S")),
    )
    cur.execute(
        """
        INSERT INTO tareas (titulo, descripcion, proceso, asignado_a, inicio, estado, cantidad, horario_extendido)
        VALUES (?, ?, ?, ?, ?, 'En curso', 0, 0)
        """,
        (op_noct, "PRUEBA NOCTURNO VIERNES", "TEST", "usuario_olvido", viernes_noct.strftime("%Y-%m-%d %H:%M:%S")),
    )
    cur.execute(
        """
        INSERT INTO tareas (titulo, descripcion, proceso, asignado_a, inicio, estado, cantidad, horario_extendido)
        VALUES (?, ?, ?, ?, ?, 'En curso', 0, 0)
        """,
        (op_no_cierre, "PRUEBA NO CIERRE", "TEST", "usuario_olvido", no_cierre.strftime("%Y-%m-%d %H:%M:%S")),
    )

    conn.commit()
    conn.close()

    cerradas = ac.ejecutar_autocierre()

    conn = sqlite3.connect(str(dst))
    cur = conn.cursor()
    row1 = cur.execute(
        "SELECT estado, fin FROM tareas WHERE titulo=? ORDER BY id DESC LIMIT 1",
        (op_sabado,),
    ).fetchone()
    row1h = cur.execute(
        "SELECT cierre_automatico FROM historial_tareas WHERE op_no=? ORDER BY id DESC LIMIT 1",
        (op_sabado,),
    ).fetchone()

    row2 = cur.execute(
        "SELECT estado, fin FROM tareas WHERE titulo=? ORDER BY id DESC LIMIT 1",
        (op_noct,),
    ).fetchone()
    row2h = cur.execute(
        "SELECT cierre_automatico FROM historial_tareas WHERE op_no=? ORDER BY id DESC LIMIT 1",
        (op_noct,),
    ).fetchone()

    row3 = cur.execute(
        "SELECT estado, fin FROM tareas WHERE titulo=? ORDER BY id DESC LIMIT 1",
        (op_no_cierre,),
    ).fetchone()
    row3h = cur.execute(
        "SELECT cierre_automatico FROM historial_tareas WHERE op_no=? ORDER BY id DESC LIMIT 1",
        (op_no_cierre,),
    ).fetchone()
    conn.close()

    print("inicio_sabado_diurno", sabado_diurno.strftime("%Y-%m-%d %H:%M:%S"))
    print("inicio_viernes_noct", viernes_noct.strftime("%Y-%m-%d %H:%M:%S"))
    print("inicio_no_cierre", no_cierre.strftime("%Y-%m-%d %H:%M:%S"))
    print("cerradas", cerradas)
    print("sabado_diurno_tarea", row1, "historial", row1h)
    print("viernes_noct_tarea", row2, "historial", row2h)
    print("no_cierre_tarea", row3, "historial", row3h)
    print("db_copy", str(dst))


if __name__ == "__main__":
    main()
