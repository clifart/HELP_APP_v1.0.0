import time
import threading
from datetime import datetime

from core import now_iso
from core.db import get_db_connection, ensure_tareas_columns
from core.horarios import (
    segundos_laborales_transcurridos,
    inferir_turno,
)
from core.autocierre_config import AUTO_CIERRE_TOTAL_HORAS
from core.horas_extras import calcular_tiempo_total_y_horas_extras

try:
    from core.registro_diario import registrar_tarea_diaria
except Exception as e:
    print(f"[WARN] No se pudo importar registrar_tarea_diaria: {e}")

    def registrar_tarea_diaria(*args, **kwargs):
        return None


def _asegurar_cols_pausa(cur):
    cur.execute("PRAGMA table_info(tareas)")
    cols = [row[1] for row in cur.fetchall()]
    if "pausa_inicio" not in cols:
        try:
            cur.execute("ALTER TABLE tareas ADD COLUMN pausa_inicio TEXT")
        except Exception:
            pass
    if "pausa_acum" not in cols:
        try:
            cur.execute("ALTER TABLE tareas ADD COLUMN pausa_acum INTEGER DEFAULT 0")
        except Exception:
            pass


def _asegurar_cols_historial(cur):
    cur.execute("""
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
    """)
    cur.execute("PRAGMA table_info(historial_tareas)")
    cols = [row[1] for row in cur.fetchall()]
    if "tiempo_total" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN tiempo_total TEXT")
        except Exception:
            pass
    if "horas_extras" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN horas_extras TEXT")
        except Exception:
            pass
    if "tiempo_pausado" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN tiempo_pausado TEXT")
        except Exception:
            pass
    if "cierre_automatico" not in cols:
        try:
            cur.execute("ALTER TABLE historial_tareas ADD COLUMN cierre_automatico INTEGER DEFAULT 0")
        except Exception:
            pass


def _parse_iso(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", ""))
    except Exception:
        return None


def _segundos_a_hms(total_seg):
    try:
        seg = max(0, int(total_seg or 0))
    except Exception:
        seg = 0
    horas = seg // 3600
    minutos = (seg % 3600) // 60
    segundos = seg % 60
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def ejecutar_autocierre(limite_horas=AUTO_CIERRE_TOTAL_HORAS, max_batch=200):
    """
    Autocierra tareas 'En curso' con inicio >= limite_horas (descontando pausa_acum),
    cuando NO están en horario extendido.
    Se añaden 1 minuto (1/60h) de gracia para el aviso al operario.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)
    _asegurar_cols_pausa(cur)
    _asegurar_cols_historial(cur)

    filas = cur.execute("""
        SELECT
            id,
            titulo,
            descripcion,
            proceso,
            asignado_a,
            inicio,
            fin,
            COALESCE(pausa_acum, 0) AS pausa_acum,
            COALESCE(cantidad, 0) AS cantidad,
            COALESCE(horario_extendido, 0) AS horario_extendido,
            COALESCE(extendido_desde, '') AS extendido_desde
        FROM tareas
        WHERE estado = 'En curso'
          AND (COALESCE(horario_extendido, 0) = 0)
          AND asignado_a IS NOT NULL
          AND TRIM(asignado_a) != ''
          AND inicio IS NOT NULL
          AND TRIM(inicio) != ''
        ORDER BY id ASC
        LIMIT ?
    """, (int(max_batch),)).fetchall()

    ahora = _parse_iso(now_iso())
    if not ahora:
        conn.close()
        return 0

    cerradas = 0
    limite_seg = int(limite_horas * 3600)

    for fila in filas:
        try:
            tarea_id = fila[0] if isinstance(fila, tuple) else fila["id"]
            op_db = (fila[1] if isinstance(fila, tuple) else fila["titulo"]) or ""
            desc_db = (fila[2] if isinstance(fila, tuple) else fila["descripcion"]) or ""
            tarea_db = (fila[3] if isinstance(fila, tuple) else fila["proceso"]) or ""
            usuario = (fila[4] if isinstance(fila, tuple) else fila["asignado_a"]) or ""
            inicio_db = (fila[5] if isinstance(fila, tuple) else fila["inicio"]) or ""
            pausa_acum_db = int((fila[7] if isinstance(fila, tuple) else fila["pausa_acum"]) or 0)
            cantidad_db = int((fila[8] if isinstance(fila, tuple) else fila["cantidad"]) or 0)
            horario_extendido_db = int((fila[9] if isinstance(fila, tuple) else fila["horario_extendido"]) or 0)
            extendido_desde_db = (fila[10] if isinstance(fila, tuple) else fila["extendido_desde"]) or ""

            dt_inicio = _parse_iso(inicio_db)
            if not dt_inicio:
                continue

            turno = inferir_turno(dt_inicio)
            elapsed = segundos_laborales_transcurridos(dt_inicio, ahora, turno)
            elapsed = int(elapsed) - int(pausa_acum_db or 0)
            elapsed = max(0, elapsed)

            if elapsed < limite_seg:
                continue

            ahora_iso = now_iso().strip()
            inicio = str(inicio_db).strip() or ahora_iso

            fin = ahora_iso

            # Calcular tiempo_total
            tiempo_total = ""
            horas_extras = "00:00:00"
            tiempo_pausado = _segundos_a_hms(pausa_acum_db)
            try:
                tiempo_total, horas_extras = calcular_tiempo_total_y_horas_extras(
                    inicio=inicio,
                    fin=fin,
                    pausa_acum_seg=pausa_acum_db,
                    horario_extendido=horario_extendido_db,
                    extendido_desde=extendido_desde_db,
                )
            except Exception:
                tiempo_total = ""
                horas_extras = "00:00:00"

            cur.execute("""
                UPDATE tareas
                SET cantidad = ?,
                    inicio   = ?,
                    fin      = ?,
                    estado   = 'Finalizado'
                WHERE id = ?
                  AND asignado_a = ?
                  AND estado = 'En curso'
            """, (int(cantidad_db or 0), inicio, fin, tarea_id, usuario))

            if cur.rowcount <= 0:
                conn.commit()
                continue

            existe = cur.execute("""
                SELECT id
                FROM historial_tareas
                WHERE usuario = ?
                  AND op_no = ?
                  AND descripcion = ?
                  AND tarea = ?
                  AND cantidad = ?
                  AND hora_inicio = ?
                  AND hora_finalizacion = ?
                LIMIT 1
            """, (usuario, op_db, desc_db, tarea_db, int(cantidad_db or 0), inicio, fin)).fetchone()

            if not existe:
                cur.execute("""
                    INSERT INTO historial_tareas
                        (usuario, op_no, descripcion, tarea, cantidad,
                         hora_inicio, hora_finalizacion, tiempo_total, horas_extras, tiempo_pausado, cierre_automatico)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (usuario, op_db, desc_db, tarea_db, int(cantidad_db or 0), inicio, fin, tiempo_total, horas_extras, tiempo_pausado, 1))

            cur.execute("""
                CREATE TABLE IF NOT EXISTS registro_excel_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL,
                    op_no TEXT NOT NULL,
                    tarea TEXT NOT NULL,
                    inicio TEXT NOT NULL,
                    fin TEXT NOT NULL,
                    UNIQUE(usuario, op_no, tarea, inicio, fin)
                )
            """)
            cur.execute("""
                INSERT OR IGNORE INTO registro_excel_log (usuario, op_no, tarea, inicio, fin)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario, op_db, tarea_db, inicio, fin))
            excel_token_ok = (cur.rowcount == 1)

            conn.commit()

            if excel_token_ok:
                try:
                    registrar_tarea_diaria(
                        titulo=op_db,
                        descripcion=desc_db,
                        proceso=tarea_db,
                        usuario=usuario,
                        estado="Finalizado",
                        cantidad=int(cantidad_db or 0),
                        inicio=inicio,
                        fin=fin
                    )
                except Exception as e:
                    print(f"⚠️ No se pudo registrar en el diario (Excel) [autocierre]: {e}")

            cerradas += 1

        except Exception as e:
            conn.rollback()
            print("⚠️ Error en autocierre automático:", e)

    conn.close()
    return cerradas


def _loop_autocierre(intervalo_seg=10):
    while True:
        try:
            n = ejecutar_autocierre()
            if n > 0:
                print(f"[AUTOCIERRE] {n} tareas cerradas automáticamente.")
        except Exception as e:
            print(f"⚠️ Error loop autocierre: {e}")
        time.sleep(max(5, int(intervalo_seg or 10)))


def iniciar_hilo_autocierre(intervalo_seg=10):
    print(f"[SISTEMA] Hilo de autocierre iniciado (cada {intervalo_seg}s)")
    t = threading.Thread(
        target=_loop_autocierre,
        args=(intervalo_seg,),
        daemon=True
    )
    t.start()
    return t
