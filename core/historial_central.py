import csv
import json
import os
import sqlite3
from datetime import datetime, timedelta

from core import local_now
from core.db import get_db_connection
from core.registro_diario import CARPETA_TAREAS_DIARIAS


HISTORIAL_CENTRAL_DIR = os.path.join(
    os.path.dirname(CARPETA_TAREAS_DIARIAS),
    "HISTORIAL CENTRAL",
)
STATE_FILE = os.path.join(HISTORIAL_CENTRAL_DIR, "_estado_mensual.json")


def _ensure_historial_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS historial_tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            op_no TEXT,
            descripcion TEXT,
            tarea TEXT,
            cantidad INTEGER,
            hora_inicio TEXT,
            hora_finalizacion TEXT,
            tiempo_total TEXT,
            horas_extras TEXT,
            tiempo_pausado TEXT,
            cierre_automatico INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_impresion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            op_no TEXT,
            fecha TEXT,
            p1_entrega_paquete TEXT,
            p2_verificar_planchas TEXT,
            p3_alistamiento_corte_papel TEXT,
            p4_control_50_tiros TEXT,
            p41_tonos_carta_color TEXT,
            p42_tonos_muestra_aprobada TEXT
        )
        """
    )

    cur.execute("PRAGMA table_info(historial_tareas)")
    cols = [row[1] if not isinstance(row, sqlite3.Row) else row["name"] for row in cur.fetchall()]

    if "tiempo_total" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN tiempo_total TEXT")
        except sqlite3.OperationalError:
            pass
    if "horas_extras" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN horas_extras TEXT")
        except sqlite3.OperationalError:
            pass
    if "tiempo_pausado" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN tiempo_pausado TEXT")
        except sqlite3.OperationalError:
            pass
    if "cierre_automatico" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN cierre_automatico INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass


def _write_csv(path, headers, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _mes_dia(fecha):
    fecha = fecha or local_now()
    return fecha.strftime("%Y_%m"), fecha.strftime("%d"), fecha.strftime("%Y_%m_%d_%H%M%S")


def _fetch_admin_rows(cur):
    headers = [
        "id",
        "op_no",
        "descripcion",
        "operario_impresion",
        "cantidad",
        "fin",
        "cierre_automatico",
    ]
    rows = cur.execute(
        """
        SELECT
            t.id,
            t.titulo,
            t.descripcion,
            (
                SELECT h.usuario
                FROM historial_tareas h
                WHERE h.op_no = t.titulo
                ORDER BY h.id ASC
                LIMIT 1
            ) AS operario_impresion,
            t.cantidad,
            t.fin,
            EXISTS(
                SELECT 1
                FROM historial_tareas h2
                WHERE h2.op_no = t.titulo
                  AND COALESCE(h2.cierre_automatico, 0) = 1
            ) AS cierre_automatico
        FROM tareas t
        WHERE t.estado = 'Finalizado'
          AND (t.asignado_a IS NULL OR TRIM(t.asignado_a) = '')
        ORDER BY t.fin DESC, t.id DESC
        """
    ).fetchall()
    return headers, [list(r) for r in rows]


def _fetch_usuario_rows(cur):
    headers = [
        "id",
        "usuario",
        "op_no",
        "descripcion",
        "tarea",
        "cantidad",
        "hora_inicio",
        "hora_finalizacion",
        "tiempo_total",
        "horas_extras",
        "tiempo_pausado",
        "cierre_automatico",
    ]
    rows = cur.execute(
        """
        SELECT
            id,
            usuario,
            op_no,
            descripcion,
            tarea,
            cantidad,
            hora_inicio,
            hora_finalizacion,
            tiempo_total,
            COALESCE(horas_extras, '00:00:00') AS horas_extras,
            COALESCE(tiempo_pausado, '') AS tiempo_pausado,
            COALESCE(cierre_automatico, 0) AS cierre_automatico
        FROM historial_tareas
        ORDER BY id DESC
        """
    ).fetchall()
    return headers, [list(r) for r in rows]


def respaldar_historial_en_central(conn, fecha=None):
    cur = conn.cursor()
    _ensure_historial_tables(cur)

    mes, dia, sello = _mes_dia(fecha)
    admin_dir = os.path.join(HISTORIAL_CENTRAL_DIR, f"Historial_admin_{mes}", dia)
    usuario_dir = os.path.join(HISTORIAL_CENTRAL_DIR, f"Historial_usuario_{mes}", dia)

    admin_headers, admin_rows = _fetch_admin_rows(cur)
    usuario_headers, usuario_rows = _fetch_usuario_rows(cur)

    admin_csv = os.path.join(admin_dir, f"historial_admin_{sello}.csv")
    usuario_csv = os.path.join(usuario_dir, f"historial_usuario_{sello}.csv")

    _write_csv(admin_csv, admin_headers, admin_rows)
    _write_csv(usuario_csv, usuario_headers, usuario_rows)

    return {
        "admin_path": admin_csv,
        "usuario_path": usuario_csv,
        "admin_rows": len(admin_rows),
        "usuario_rows": len(usuario_rows),
    }


def limpiar_historial_con_respaldo(conn, fecha=None):
    cur = conn.cursor()
    resumen = respaldar_historial_en_central(conn, fecha=fecha)

    _ensure_historial_tables(cur)
    cur.execute("DELETE FROM historial_tareas")
    cur.execute("DELETE FROM checklist_impresion")
    cur.execute(
        """
        DELETE FROM tareas
        WHERE estado = 'Finalizado'
          AND (asignado_a IS NULL OR TRIM(asignado_a) = '')
        """
    )
    try:
        cur.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ('historial_tareas', 'checklist_impresion')"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return resumen


def _read_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(data):
    os.makedirs(HISTORIAL_CENTRAL_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ejecutar_mantenimiento_mensual_historial(force=False, now=None):
    ahora = now or local_now()
    mes_actual = ahora.strftime("%Y_%m")
    estado = _read_state()
    ultimo_mes = estado.get("ultimo_mes_procesado")

    if not force and not ultimo_mes:
        _write_state(
            {
                "ultimo_mes_procesado": mes_actual,
                "ultimo_ejecutado": ahora.isoformat(timespec="seconds"),
                "inicializado": True,
            }
        )
        return {"ejecutado": False, "motivo": "inicializado"}

    if not force and ultimo_mes == mes_actual:
        return {"ejecutado": False, "motivo": "sin_cambios"}

    fecha_respaldo = ahora
    if not force:
        # Al cambiar de mes, archivamos como "cierre" del mes anterior.
        fecha_respaldo = ahora.replace(day=1) - timedelta(days=1)

    conn = get_db_connection()
    try:
        resumen = limpiar_historial_con_respaldo(conn, fecha=fecha_respaldo)
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()

    _write_state(
        {
            "ultimo_mes_procesado": mes_actual,
            "ultimo_ejecutado": ahora.isoformat(timespec="seconds"),
            "ultimo_resumen": resumen,
        }
    )
    return {"ejecutado": True, "resumen": resumen}
