from flask import render_template, request, redirect, url_for, session, flash, jsonify, current_app
from . import usuario_bp
from core.db import get_db_connection, ensure_tareas_columns
from core.horarios import (
    segundos_laborales_transcurridos,
    inferir_turno,
    esta_en_ventana,
    ultima_fin_ventana,
)
from core.autocierre_config import AUTO_CIERRE_GRACIA_SEG, AUTO_CIERRE_LIMITE_SEG
from core.horas_extras import calcular_tiempo_total_y_horas_extras
from core.registro_diario import registrar_tarea_diaria
from core import now_iso
from datetime import datetime
import sqlite3
import json
import re
from typing import Optional


def _solo_usuario():
    rol = (session.get("rol") or "").strip().lower()
    if rol == "usuario":
        return True
    # Permite probar flujo de usuario desde Modo Técnico (admin autenticado con clave técnica).
    return rol == "admin" and session.get("clave_tecnica") == current_app.config.get("MASTER_KEY")


def _modo_tecnico_activo() -> bool:
    return session.get("clave_tecnica") == current_app.config.get("MASTER_KEY")


def _debug_aviso_seg_activo() -> int:
    try:
        return int(session.get("debug_aviso_seg") or 0)
    except Exception:
        return 0


def _debug_autocierre_activo() -> bool:
    return bool(session.get("debug_autocierre_activo"))


def _desactivar_debug_aviso():
    session.pop("debug_autocierre_activo", None)
    session.pop("debug_aviso_seg", None)


@usuario_bp.route("/probar_autocierre", methods=["GET", "POST"])
def probar_autocierre():
    if not _modo_tecnico_activo():
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("login"))
    try:
        seg = int(request.values.get("seg") or 0)
    except Exception:
        seg = 0
    seg = max(0, min(seg, 3600))
    session["debug_autocierre_activo"] = 1
    session["debug_aviso_seg"] = seg
    flash(
        f"Modo prueba de autocierre activo: el aviso aparecerá a los {seg} segundos "
        "y luego tendrá 60 segundos para iniciar horas extras.",
        "warning",
    )
    return redirect(url_for("usuario.panel"))


# -------------------------
# REGLAS DE PROCESOS
# -------------------------

def _normalizar_proceso(nombre: str) -> str:
    """
    Normaliza el nombre del proceso:
    - quita espacios extremos
    - pasa a mayúsculas
    - elimina tildes (IMPRESIÓN -> IMPRESION)
    """
    if not nombre:
        return ""
    base = nombre.strip().upper()
    reemplazos = {
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
    }
    for orig, repl in reemplazos.items():
        base = base.replace(orig, repl)
    return base


def _slug_modulo(norm: str) -> str:
    """Convierte un nombre normalizado en un slug seguro para 'modulo'."""
    base = (norm or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "general"


def _omite_checklist_y_cantidad(nombre: str) -> bool:
    """
    Procesos exentos de checklist y cantidad para finalizar.
    """
    norm = _normalizar_proceso(nombre)
    return norm in {"ALISTAMIENTO", "DESCARTONE", "REPROCESO"}


def _omite_cantidad(nombre: str) -> bool:
    """
    Procesos que no manejan cantidad, aunque algunos sí requieren checklist.
    """
    norm = _normalizar_proceso(nombre)
    return _omite_checklist_y_cantidad(nombre) or norm == "VARIOS"


def _es_impresion(nombre: str) -> bool:
    """
    True si el proceso es alguna variante de IMPRESION
    (cualquier ítem que contenga la palabra IMPRESION).
    """
    norm = _normalizar_proceso(nombre)
    return "IMPRESION" in norm


def _hay_impresion_activa(conn, op_no: str) -> bool:
    """
    Devuelve True si para la OP dada hay ALGUNA tarea de tipo IMPRESION
    con estado 'En curso' en la tabla tareas.
    """
    cur = conn.cursor()
    try:
        filas = cur.execute(
            """
            SELECT
                t.proceso,
                t.estado,
                t.asignado_a,
                COALESCE(LOWER(TRIM(u.rol)), '') AS rol_asignado
            FROM tareas t
            LEFT JOIN usuarios u
              ON LOWER(TRIM(u.nombre)) = LOWER(TRIM(t.asignado_a))
            WHERE t.titulo = ?
              AND t.proceso IS NOT NULL
              AND TRIM(t.proceso) != ''
            """,
            (op_no,),
        ).fetchall()
    except sqlite3.OperationalError:
        # Fallback si la tabla usuarios no estÃ¡ disponible por algÃºn motivo.
        filas = cur.execute(
            """
            SELECT proceso, estado, asignado_a
            FROM tareas
            WHERE titulo = ?
              AND proceso IS NOT NULL
              AND TRIM(proceso) != ''
            """,
            (op_no,),
        ).fetchall()

    for fila in filas:
        proceso_val = fila[0] if isinstance(fila, tuple) else fila["proceso"]
        estado_val = fila[1] if isinstance(fila, tuple) else fila["estado"]
        rol_asignado = ""
        if isinstance(fila, tuple):
            if len(fila) >= 4:
                rol_asignado = (fila[3] or "").strip().lower()
        else:
            rol_asignado = ((fila["rol_asignado"] if "rol_asignado" in fila.keys() else "") or "").strip().lower()

        # Tareas de cuentas admin no deben bloquear el flujo de producciÃ³n de usuario.
        if rol_asignado == "admin":
            continue

        if estado_val == "En curso" and _es_impresion(proceso_val):
            return True

    return False


def _hay_impresion_finalizada(conn, op_no: str) -> bool:
    """
    Devuelve True si para la OP dada hay ALGUNA tarea de tipo IMPRESION
    en historial_tareas con hora_finalizacion NO nula/ni vacía.
    """
    cur = conn.cursor()
    try:
        filas = cur.execute(
            """
            SELECT tarea, hora_finalizacion
            FROM historial_tareas
            WHERE op_no = ?
            """,
            (op_no,),
        ).fetchall()
    except sqlite3.OperationalError:
        return False

    for fila in filas:
        tarea_val = fila[0] if isinstance(fila, tuple) else fila["tarea"]
        fin_val = fila[1] if isinstance(fila, tuple) else fila["hora_finalizacion"]
        if _es_impresion(tarea_val) and fin_val and str(fin_val).strip():
            return True

    return False


def _puede_tomar_proceso(conn, op_no: str, proceso_solicitado: str) -> bool:
    """
    Regla por OP:

    - CORTE: siempre permitido.
    - IMPRESION (cualquier variante):
        -> permitido solo si NO hay otra IMPRESION EN CURSO para esa OP.
    - Cualquier OTRO proceso:
        -> permitido solo si:
           * ya existe al menos una IMPRESION finalizada en historial_tareas, Y
           * NO hay una IMPRESION EN CURSO en este momento.
    """
    norm = _normalizar_proceso(proceso_solicitado)

    if norm == "CORTE":
        return True

    hay_impresion_activa = _hay_impresion_activa(conn, op_no)
    hay_impresion_finalizada = _hay_impresion_finalizada(conn, op_no)

    if _es_impresion(proceso_solicitado):
        return not hay_impresion_activa

    if hay_impresion_activa:
        return False

    return hay_impresion_finalizada


# -------------------------
# CHECKLIST POR MÓDULO (obligatorio para todos)
# -------------------------

def _modulo_por_proceso(nombre: str) -> Optional[str]:
    """
    Devuelve el módulo de checklist que corresponde al proceso/tarea.
    Checklist obligatorio para TODOS los procesos.
    """
    norm = _normalizar_proceso(nombre)

    # FLEXO: temporalmente usa checklist de IMPRESION
    if "FLEXO" in norm:
        return "impresion"

    # CORTE usa checklist de IMPRESION
    if norm == "CORTE" or norm.startswith("CORTE "):
        return "impresion"

    # MANTENIMIENTO SORMZ/SORM BARNIZADO
    # Acepta variantes como: "MANTENIMIENTO ... BARNIZADO" o "SORMZ-SORM BARNIZADO"
    if (
        ("MANTEN" in norm and ("SORMZ" in norm or "SORM" in norm or "BARNIZ" in norm))
        or (("SORMZ" in norm or "SORM" in norm) and "BARNIZ" in norm)
    ):
        return "mantenimiento_sormz_sorm_barnizado"

    # MANTENIMIENTO general: usar checklist de mantenimiento de maquinas
    if norm == "MANTENIMIENTO" or norm.startswith("MANTENIMIENTO "):
        return "mantenimiento_sormz_sorm_barnizado"

    # IMPRESION (cualquier variante)
    if "IMPRESION" in norm:
        return "impresion"

    # PLASTIFICADO
    if "PLAST" in norm:
        return "plastificado"

    # BRILLO / BARNIZ
    if "BRILLO" in norm or "BARNIZ" in norm:
        return "brillo"

    # PLEGADO
    if "PLEG" in norm:
        return "plegado"

    # PEGUE (incluye variantes como AUXILIAR PEGUE)
    if "PEGUE" in norm:
        return "pegue"

    # REVISION usa checklist de ENCUADERNACION
    if "REVISION" in norm:
        return "encuadernacion"

    # PAQUETE
    if "PAQUETE" in norm:
        return "paquete"

    # ✅ NUEVO: TROQUELADO / REFILADO (debe coincidir con data-module del template)
    if "TROQUEL" in norm or "REFIL" in norm:
        return "troquelado_refilado"

    # Otros procesos: módulo genérico (obligatorio para TODOS)
    return _slug_modulo(norm)



def _asegurar_tabla_checklist_modulos(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS checklist_modulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            op_no   TEXT NOT NULL,
            modulo  TEXT NOT NULL,
            tarea_id INTEGER,
            fecha   TEXT NOT NULL,
            data_json TEXT NOT NULL
        )
    """)
    cur.execute("PRAGMA table_info(checklist_modulos)")
    cols = [row[1] for row in cur.fetchall()]
    if "tarea_id" not in cols:
        try:
            cur.execute("ALTER TABLE checklist_modulos ADD COLUMN tarea_id INTEGER")
        except sqlite3.OperationalError:
            pass
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_checklist_modulos_lookup
        ON checklist_modulos (usuario, op_no, modulo, fecha)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_checklist_modulos_lookup_tarea
        ON checklist_modulos (usuario, op_no, modulo, tarea_id, fecha)
    """)


def _existe_checklist_modulo(
    cur,
    usuario: str,
    op_no: str,
    modulo: str,
    tarea_id: Optional[int] = None
) -> bool:
    """
    True si existe un checklist guardado.
    - Si llega tarea_id, valida SOLO para esa tarea.
    - Si no llega tarea_id, usa compatibilidad por (usuario, op_no, modulo).
    """
    tarea_id_int = None
    if tarea_id is not None:
        try:
            tarea_id_int = int(tarea_id)
        except Exception:
            tarea_id_int = None

    try:
        _asegurar_tabla_checklist_modulos(cur)

        if tarea_id_int is not None:
            ok_tarea = cur.execute("""
                SELECT 1
                FROM checklist_modulos
                WHERE usuario=? AND op_no=? AND modulo=? AND COALESCE(tarea_id, 0)=?
                ORDER BY id DESC
                LIMIT 1
            """, (usuario, op_no, modulo, tarea_id_int)).fetchone()
            return bool(ok_tarea)

        ok = cur.execute("""
                SELECT 1
                FROM checklist_modulos
                WHERE usuario=? AND op_no=? AND modulo=?
                ORDER BY id DESC
                LIMIT 1
            """, (usuario, op_no, modulo)).fetchone()
        if ok:
            return True
    except Exception:
        pass

    if tarea_id_int is None and modulo == "impresion":
        try:
            ok2 = cur.execute("""
                SELECT 1
                FROM checklist_impresion
                WHERE usuario=? AND op_no=?
                ORDER BY id DESC
                LIMIT 1
            """, (usuario, op_no)).fetchone()
            return bool(ok2)
        except sqlite3.OperationalError:
            return False

    return False


# -------------------------
# PAUSA / REANUDAR (cronómetro sin contar pausas)
# -------------------------

def _asegurar_cols_pausa(cur):
    """Asegura columnas para pausa sin romper instalaciones existentes."""
    cur.execute("PRAGMA table_info(tareas)")
    cols = [row[1] for row in cur.fetchall()]
    if "pausa_inicio" not in cols:
        try:
            cur.execute("ALTER TABLE tareas ADD COLUMN pausa_inicio TEXT")
        except sqlite3.OperationalError:
            pass
    if "pausa_acum" not in cols:
        try:
            cur.execute("ALTER TABLE tareas ADD COLUMN pausa_acum INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass


def _segundos_a_hms(total_seg: int) -> str:
    """Convierte segundos acumulados a HH:MM:SS."""
    try:
        seg = max(0, int(total_seg or 0))
    except Exception:
        seg = 0
    horas = seg // 3600
    minutos = (seg % 3600) // 60
    segundos = seg % 60
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def _asegurar_cols_historial(cur):
    """Asegura columnas de historial_tareas para cierres automáticos."""
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


# =========================
# PANEL USUARIO — MIS TAREAS DE HOY
# =========================
@usuario_bp.route("/")
def panel():
    if not _solo_usuario():
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("login"))

    usuario = session.get("usuario")

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)

    tareas_rows = cur.execute("""
        SELECT
            id,
            titulo      AS op,
            descripcion AS descripcion,
            proceso     AS tarea,
            inicio,
            fin,
            cantidad,
            estado,
            COALESCE(horario_extendido, 0) AS horario_extendido,
            COALESCE(pausa_acum, 0) AS pausa_acum
        FROM tareas
        WHERE estado != 'Finalizado'
          AND asignado_a = ?
          AND proceso IS NOT NULL
          AND TRIM(proceso) != ''
        ORDER BY id DESC
    """, (usuario,)).fetchall()

    tareas_list = []
    for t in tareas_rows:
        tid = t[0] if isinstance(t, tuple) else t["id"]
        op = (t[1] if isinstance(t, tuple) else t["op"]) or ""
        desc = (t[2] if isinstance(t, tuple) else t["descripcion"]) or ""
        tarea = (t[3] if isinstance(t, tuple) else t["tarea"]) or ""
        inicio = (t[4] if isinstance(t, tuple) else t["inicio"]) or ""
        fin = (t[5] if isinstance(t, tuple) else t["fin"]) or ""
        cantidad = (t[6] if isinstance(t, tuple) else t["cantidad"]) or 0
        estado = (t[7] if isinstance(t, tuple) else t["estado"]) or ""
        horario_extendido = (t[8] if isinstance(t, tuple) else t["horario_extendido"]) or 0
        pausa_acum_db = int((t[9] if isinstance(t, tuple) else t["pausa_acum"]) or 0)

        modulo = _modulo_por_proceso(tarea) or "general"
        omite_ctrl = _omite_checklist_y_cantidad(tarea)
        omite_cant = _omite_cantidad(tarea)
        ok_chk = True if omite_ctrl else _existe_checklist_modulo(cur, usuario, op.strip(), modulo, tarea_id=tid)

        # Cálculo de tiempo real para el frontend (transcurrir el tiempo)
        seg_trans_neto = 0
        if estado == "En curso":
            try:
                dt_ini = datetime.fromisoformat(str(inicio).replace("Z", ""))
                trno = inferir_turno(dt_ini)
                seg_trans_bruto = segundos_laborales_transcurridos(dt_ini, datetime.now(), trno)
                seg_trans_neto = max(0, seg_trans_bruto - pausa_acum_db)
            except Exception:
                pass

        tareas_list.append({
            "id": tid,
            "op": op,
            "descripcion": desc,
            "tarea": tarea,
            "inicio": str(inicio).strip(),   # ✅ CRUDO (NO formatear aquí)
            "fin": str(fin).strip(),         # ✅ CRUDO (NO formatear aquí)
            "cantidad": int(cantidad or 0),
            "estado": estado,                # ✅ IMPORTANTE para data-estado
            "horario_extendido": int(horario_extendido or 0),
            "modulo": modulo,
            "checklist_ok": bool(ok_chk),
            "omite_controles": bool(omite_ctrl),
            "omite_cantidad": bool(omite_cant),
            "segundos_transcurridos": seg_trans_neto,
            "pausa_acum": pausa_acum_db,
        })

    tareas = tareas_list

    op_preseleccionada = None
    if tareas:
        op_preseleccionada = (tareas[0]["op"] or "").strip()
    if not op_preseleccionada:
        op_preseleccionada = session.get("ultima_op")

    rows = cur.execute("""
        SELECT titulo, descripcion
        FROM tareas
        WHERE titulo IS NOT NULL AND TRIM(titulo) != ''
          AND descripcion IS NOT NULL AND TRIM(descripcion) != ''
          AND estado != 'Finalizado'
        GROUP BY titulo
        ORDER BY titulo
    """).fetchall()

    conn.close()

    ops = [{"titulo": r[0], "descripcion": r[1]} for r in rows]
    ops_map = {o["titulo"]: o["descripcion"] for o in ops}
    debug_aviso_seg = _debug_aviso_seg_activo()
    debug_autocierre_activo = _debug_autocierre_activo()

    return render_template(
        "usuario/panel.html",
        tareas=tareas,
        ops=ops,
        ops_map=ops_map,
        op_preseleccionada=op_preseleccionada,
        debug_aviso_seg=debug_aviso_seg,
        debug_autocierre_activo=debug_autocierre_activo,
        autocierre_limite_seg=AUTO_CIERRE_LIMITE_SEG,
        autocierre_gracia_seg=AUTO_CIERRE_GRACIA_SEG
    )


# =========================
# VALIDAR INICIO (AJAX)
# =========================
@usuario_bp.route("/validar_inicio", methods=["GET"])
def validar_inicio():
    if not _solo_usuario():
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    op_no = (request.args.get("op_no") or "").strip()
    proceso = (request.args.get("proceso") or "").strip()

    if not op_no or not proceso:
        return jsonify({"ok": False, "msg": "Datos incompletos"}), 400

    conn = get_db_connection()
    ensure_tareas_columns(conn)

    norm = _normalizar_proceso(proceso)

    if norm == "CORTE":
        conn.close()
        return jsonify({"ok": True, "needs_confirm": False}), 200

    hay_activa = _hay_impresion_activa(conn, op_no)
    hay_fin = _hay_impresion_finalizada(conn, op_no)

    if _es_impresion(proceso):
        conn.close()
        if hay_activa:
            return jsonify({"ok": False, "needs_confirm": False, "msg": "⚠️ Ya hay una IMPRESIÓN en curso en esta OP."}), 400
        return jsonify({"ok": True, "needs_confirm": False}), 200

    if not hay_fin:
        conn.close()
        return jsonify({
            "ok": True,
            "needs_confirm": True,
            "reason": "sin_impresion",
            "msg": "⚠️ Esta OP aún NO tiene una IMPRESIÓN finalizada. ¿Deseas continuar sin impresión?"
        }), 200

    if hay_activa:
        conn.close()
        return jsonify({
            "ok": True,
            "needs_confirm": True,
            "reason": "impresion_activa",
            "msg": "⚠️ Hay una IMPRESIÓN activa. Estás intentando iniciar una tarea sin impresión. ¿Deseas continuar?"
        }), 200

    conn.close()
    return jsonify({"ok": True, "needs_confirm": False}), 200


# =========================
# AGREGAR TAREA (POST clásico)
# =========================
@usuario_bp.route('/agregar', methods=['POST'])
def agregar():
    if not _solo_usuario():
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for('login'))

    op_no = (request.form.get('titulo') or '').strip()
    descripcion = (request.form.get('descripcion') or '').strip()
    proceso = (request.form.get('tarea') or '').strip()
    usuario = session.get('usuario')

    if not op_no or not proceso:
        flash("⚠️ Debes seleccionar una OP y un proceso.", "warning")
        return redirect(url_for('usuario.panel'))

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)

    force = (request.form.get("force_continue") or "0").strip() == "1"
    norm = _normalizar_proceso(proceso)

    if norm != "CORTE":
        hay_activa = _hay_impresion_activa(conn, op_no)
        hay_fin = _hay_impresion_finalizada(conn, op_no)

        if _es_impresion(proceso) and hay_activa:
            conn.close()
            flash("⚠️ Ya hay una IMPRESIÓN en curso en esta OP.", "warning")
            return redirect(url_for('usuario.panel'))

        if (not _es_impresion(proceso)) and (not hay_fin) and (not force):
            conn.close()
            flash("⚠️ Esta OP aún NO tiene una IMPRESIÓN finalizada. Debes confirmar para continuar sin impresión.", "warning")
            return redirect(url_for('usuario.panel'))

        if (not _es_impresion(proceso)) and hay_activa and (not force):
            conn.close()
            flash("⚠️ Hay una IMPRESIÓN activa. Debes confirmar para iniciar esta tarea sin impresión.", "warning")
            return redirect(url_for('usuario.panel'))

    if not _puede_tomar_proceso(conn, op_no, proceso) and not force:
        conn.close()
        flash(
            "⚠️ No puedes seleccionar esta tarea todavía.\n"
            "- Si hay una IMPRESIÓN activa, ninguna otra tarea se puede iniciar.",
            "warning"
        )
        return redirect(url_for('usuario.panel'))

    cur.execute("""
        INSERT INTO tareas (titulo, descripcion, proceso, asignado_a, inicio, estado, cantidad)
        VALUES (?, ?, ?, ?, ?, 'En curso', 0)
    """, (op_no, descripcion, proceso, usuario, now_iso()))
    conn.commit()
    conn.close()

    session["ultima_op"] = op_no
    flash(f"✅ Proceso '{proceso}' iniciado para la OP {op_no}.", "success")
    return redirect(url_for('usuario.panel'))


# =========================
# FINALIZAR (JSON) — por ID
# =========================
@usuario_bp.route("/finalizar_tarea_usuario", methods=["POST"])
def finalizar_tarea_usuario():
    if not _solo_usuario():
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    data = request.get_json(silent=True) or {}

    tarea_id = data.get("id")
    try:
        tarea_id = int(tarea_id)
    except Exception:
        return jsonify({"ok": False, "msg": "ID inválido"}), 400

    op_no = (data.get("op_no") or "").strip()
    descripcion = (data.get("descripcion") or "").strip()
    tarea = (data.get("tarea") or "").strip()
    cantidad_raw = (data.get("cantidad") or "").strip()

    raw_inicio = (data.get("inicio") or "").strip()
    raw_fin = (data.get("fin") or "").strip()

    usuario = session.get("usuario", "Desconocido")

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)
    _asegurar_cols_pausa(cur)

    fila_estado = cur.execute(
        """SELECT titulo, descripcion, proceso, estado, inicio, fin,
                  COALESCE(pausa_acum,0) AS pausa_acum,
                  COALESCE(horario_extendido,0) AS horario_extendido,
                  COALESCE(extendido_desde,'') AS extendido_desde
           FROM tareas
           WHERE id=? AND asignado_a=?
           LIMIT 1""",
        (tarea_id, usuario)
    ).fetchone()

    if not fila_estado:
        conn.close()
        return jsonify({"ok": False, "msg": "Tarea no encontrada"}), 404

    op_db = (fila_estado[0] if isinstance(fila_estado, tuple) else fila_estado["titulo"]) or ""
    desc_db = (fila_estado[1] if isinstance(fila_estado, tuple) else fila_estado["descripcion"]) or ""
    tarea_db = (fila_estado[2] if isinstance(fila_estado, tuple) else fila_estado["proceso"]) or ""
    est_db = (fila_estado[3] if isinstance(fila_estado, tuple) else fila_estado["estado"]) or ""
    inicio_db = (fila_estado[4] if isinstance(fila_estado, tuple) else fila_estado["inicio"]) or ""
    fin_db = (fila_estado[5] if isinstance(fila_estado, tuple) else fila_estado["fin"]) or ""
    pausa_acum_db = int((fila_estado[6] if isinstance(fila_estado, tuple) else fila_estado["pausa_acum"]) or 0)
    horario_extendido_db = int((fila_estado[7] if isinstance(fila_estado, tuple) else fila_estado["horario_extendido"]) or 0)
    extendido_desde_db = (fila_estado[8] if isinstance(fila_estado, tuple) else fila_estado["extendido_desde"]) or ""

    op_no = op_no or str(op_db).strip()
    descripcion = descripcion or str(desc_db).strip()
    tarea = tarea or str(tarea_db).strip()
    omite_ctrl = _omite_checklist_y_cantidad(tarea)
    omite_cant = _omite_cantidad(tarea)

    if omite_cant:
        cantidad = 0
    else:
        if not cantidad_raw.isdigit():
            conn.close()
            return jsonify({"ok": False, "msg": "Cantidad inválida"}), 400
        cantidad = int(cantidad_raw)

    if (est_db or "").strip() == "Pausada":
        conn.close()
        return jsonify({"ok": False, "msg": "⏸️ La tarea está en PAUSA. Reanúdala para poder finalizar."}), 400

    # ✅ inicio/fin: preferir BD si el front manda "-" o vacío
    inicio = raw_inicio
    fin = raw_fin

    if (not inicio or inicio == "-") and inicio_db:
        inicio = str(inicio_db).strip()
    if (not fin or fin == "-") and fin_db:
        fin = str(fin_db).strip()

    if not inicio or inicio == "-":
        inicio = now_iso().strip()
    if not fin or fin == "-":
        fin = now_iso().strip()

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
    except Exception as e:
        print("⚠️ No se pudo calcular tiempo_total:", e)
        tiempo_total = ""
        horas_extras = "00:00:00"

    modulo = _modulo_por_proceso(tarea) or "general"
    if (not omite_ctrl) and (not _existe_checklist_modulo(cur, usuario, op_no, modulo, tarea_id=tarea_id)):
        conn.close()
        return jsonify({
            "ok": False,
            "msg": f"Debes llenar el checklist del módulo {modulo.upper()} para poder cerrar la tarea."
        }), 400

    checklist_modulo_excel = ""
    checklist_fecha_excel = ""
    checklist_data_excel = None
    if not omite_ctrl:
        checklist_modulo_excel = modulo
        try:
            fila_chk = cur.execute("""
                SELECT modulo, fecha, data_json
                FROM checklist_modulos
                WHERE usuario=? AND op_no=? AND modulo=? AND COALESCE(tarea_id, 0)=?
                ORDER BY id DESC
                LIMIT 1
            """, (usuario, op_no, modulo, int(tarea_id))).fetchone()

            if not fila_chk:
                fila_chk = cur.execute("""
                    SELECT modulo, fecha, data_json
                    FROM checklist_modulos
                    WHERE usuario=? AND op_no=? AND modulo=?
                    ORDER BY id DESC
                    LIMIT 1
                """, (usuario, op_no, modulo)).fetchone()

            if fila_chk:
                chk_mod = (fila_chk[0] if isinstance(fila_chk, tuple) else fila_chk["modulo"]) or modulo
                chk_fecha = (fila_chk[1] if isinstance(fila_chk, tuple) else fila_chk["fecha"]) or ""
                chk_data_raw = (fila_chk[2] if isinstance(fila_chk, tuple) else fila_chk["data_json"]) or ""

                checklist_modulo_excel = str(chk_mod).strip() or modulo
                checklist_fecha_excel = str(chk_fecha).strip()
                if chk_data_raw:
                    try:
                        checklist_data_excel = json.loads(chk_data_raw)
                    except Exception:
                        checklist_data_excel = {"raw": str(chk_data_raw)}
        except Exception as e:
            print("âš ï¸ No se pudo recuperar checklist para Excel:", e)

    registrar_en_excel = False
    excel_token_ok = False

    try:
        cur.execute("""
            UPDATE tareas
            SET cantidad = ?,
                inicio   = ?,
                fin      = ?,
                estado   = 'Finalizado'
            WHERE id = ?
              AND asignado_a = ?
              AND estado != 'Finalizado'
        """, (cantidad, inicio, fin, tarea_id, usuario))

        filas_afectadas = cur.rowcount

        if filas_afectadas > 0:
            registrar_en_excel = True

            _asegurar_cols_historial(cur)

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
            """, (usuario, op_no, descripcion, tarea, cantidad, inicio, fin)).fetchone()

            if not existe:
                cur.execute("""
                INSERT INTO historial_tareas
                    (usuario, op_no, descripcion, tarea, cantidad,
                     hora_inicio, hora_finalizacion, tiempo_total, horas_extras, tiempo_pausado, cierre_automatico)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (usuario, op_no, descripcion, tarea, cantidad, inicio, fin, tiempo_total, horas_extras, tiempo_pausado, 0))
            else:
                print("ℹ️ Ya existía en historial_tareas; no se inserta de nuevo.")

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
            """, (usuario, op_no, tarea, inicio, fin))
            excel_token_ok = (cur.rowcount == 1)

        else:
            print("ℹ️ No se actualizaron filas (posible doble finalización o ID no válido).")

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("⚠️ Error en finalizar_tarea_usuario:", e)
        conn.close()
        return jsonify({"ok": False, "msg": "Error BD"}), 500

    conn.close()

    if registrar_en_excel and excel_token_ok:
        try:
            registrar_tarea_diaria(
                titulo=op_no,
                descripcion=descripcion,
                proceso=tarea,
                usuario=usuario,
                estado="Finalizado",
                cantidad=int(cantidad),
                inicio=inicio,
                fin=fin,
                checklist_modulo=checklist_modulo_excel,
                checklist_tarea_id=tarea_id,
                checklist_fecha=checklist_fecha_excel,
                checklist_data=checklist_data_excel,
            )
        except Exception as e:
            print(f"⚠️ No se pudo registrar en el diario (Excel): {e}")

    if _debug_autocierre_activo():
        _desactivar_debug_aviso()

    return jsonify({"ok": True, "tiempo_total": tiempo_total, "horas_extras": horas_extras}), 200


# =========================
# EXTENDER HORARIO (JSON) — por ID
# =========================
@usuario_bp.route("/extender_horario_tarea", methods=["POST"])
def extender_horario_tarea():
    if not _solo_usuario():
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    data = request.get_json(silent=True) or {}
    tarea_id = data.get("id")
    force_test = int(data.get("force_test") or 0)
    force_test = 1 if (force_test and _debug_autocierre_activo()) else 0
    try:
        tarea_id = int(tarea_id)
    except Exception:
        return jsonify({"ok": False, "msg": "ID inválido"}), 400

    usuario = session.get("usuario", "Desconocido")

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)

    fila = cur.execute(
        "SELECT estado, COALESCE(horario_extendido,0) AS horario_extendido "
        "FROM tareas WHERE id=? AND asignado_a=? LIMIT 1",
        (tarea_id, usuario)
    ).fetchone()

    if not fila:
        conn.close()
        return jsonify({"ok": False, "msg": "Tarea no encontrada"}), 404

    est_db = (fila[0] if isinstance(fila, tuple) else fila["estado"]) or ""
    ext_db = int((fila[1] if isinstance(fila, tuple) else fila["horario_extendido"]) or 0)

    if (est_db or "").strip() != "En curso":
        conn.close()
        return jsonify({"ok": False, "msg": "La tarea no está en curso"}), 400

    if ext_db == 1:
        conn.close()
        if _debug_autocierre_activo():
            _desactivar_debug_aviso()
        return jsonify({"ok": True, "already": True}), 200

    try:
        cur.execute(
            "UPDATE tareas SET horario_extendido=1, extendido_desde=? "
            "WHERE id=? AND asignado_a=?",
            (now_iso(), tarea_id, usuario)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        print("⚠️ Error en extender_horario_tarea:", e)
        return jsonify({"ok": False, "msg": "Error BD"}), 500

    conn.close()
    if _debug_autocierre_activo():
        _desactivar_debug_aviso()
    return jsonify({"ok": True}), 200


# =========================
# AUTOCIERRE (JSON) — por ID
# =========================
@usuario_bp.route("/autocerrar_tarea_usuario", methods=["POST"])
def autocerrar_tarea_usuario():
    if not _solo_usuario():
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    data = request.get_json(silent=True) or {}
    tarea_id = data.get("id")
    force_test = int(data.get("force_test") or 0)
    force_test = 1 if (force_test and _debug_autocierre_activo()) else 0
    try:
        tarea_id = int(tarea_id)
    except Exception:
        return jsonify({"ok": False, "msg": "ID inválido"}), 400

    usuario = session.get("usuario", "Desconocido")

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)
    _asegurar_cols_pausa(cur)

    fila_estado = cur.execute(
        """SELECT titulo, descripcion, proceso, estado, inicio, fin,
                  COALESCE(pausa_acum,0) AS pausa_acum, COALESCE(cantidad,0) AS cantidad,
                  COALESCE(horario_extendido,0) AS horario_extendido,
                  COALESCE(extendido_desde,'') AS extendido_desde
           FROM tareas
           WHERE id=? AND asignado_a=?
           LIMIT 1""",
        (tarea_id, usuario)
    ).fetchone()

    if not fila_estado:
        conn.close()
        return jsonify({"ok": False, "msg": "Tarea no encontrada"}), 404

    op_db = (fila_estado[0] if isinstance(fila_estado, tuple) else fila_estado["titulo"]) or ""
    desc_db = (fila_estado[1] if isinstance(fila_estado, tuple) else fila_estado["descripcion"]) or ""
    tarea_db = (fila_estado[2] if isinstance(fila_estado, tuple) else fila_estado["proceso"]) or ""
    est_db = (fila_estado[3] if isinstance(fila_estado, tuple) else fila_estado["estado"]) or ""
    inicio_db = (fila_estado[4] if isinstance(fila_estado, tuple) else fila_estado["inicio"]) or ""
    fin_db = (fila_estado[5] if isinstance(fila_estado, tuple) else fila_estado["fin"]) or ""
    pausa_acum_db = int((fila_estado[6] if isinstance(fila_estado, tuple) else fila_estado["pausa_acum"]) or 0)
    cantidad_db = int((fila_estado[7] if isinstance(fila_estado, tuple) else fila_estado["cantidad"]) or 0)
    horario_extendido_db = int((fila_estado[8] if isinstance(fila_estado, tuple) else fila_estado["horario_extendido"]) or 0)
    extendido_desde_db = (fila_estado[9] if isinstance(fila_estado, tuple) else fila_estado["extendido_desde"]) or ""

    if (est_db or "").strip() == "Finalizado":
        conn.close()
        return jsonify({"ok": True, "already": True}), 200

    if (est_db or "").strip() == "Pausada":
        conn.close()
        return jsonify({"ok": False, "msg": "La tarea está en PAUSA"}), 400

    # ✅ inicio/fin: usar BD si existe
    ahora_iso = now_iso().strip()
    inicio = str(inicio_db).strip() if inicio_db else ahora_iso
    fin = ahora_iso

    # ✅ Validar 8 horas laborables según turno (o fuera de turno)
    try:
        dt_inicio = datetime.fromisoformat(inicio.replace("Z", ""))
        dt_fin = datetime.fromisoformat(fin.replace("Z", ""))
        turno = inferir_turno(dt_inicio)
        elapsed = segundos_laborales_transcurridos(dt_inicio, dt_fin, turno)
        elapsed = int(elapsed) - int(pausa_acum_db or 0)
        elapsed = max(0, elapsed)
        fuera_turno = not esta_en_ventana(dt_fin, turno)
        if (elapsed < AUTO_CIERRE_LIMITE_SEG) and (not fuera_turno) and (not force_test):
            conn.close()
            return jsonify({"ok": False, "msg": "La tarea requiere 8 horas de actividad para autocierre."}), 400
        if fuera_turno and (not force_test):
            fin_corte = ultima_fin_ventana(dt_fin, turno)
            if fin_corte and fin_corte > dt_inicio:
                fin = fin_corte.strftime("%Y-%m-%d %H:%M:%S")
                dt_fin = fin_corte
    except Exception:
        # Si no podemos validar, seguimos con autocierre (best-effort)
        pass

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
    except Exception as e:
        print("⚠️ No se pudo calcular tiempo_total (autocierre):", e)
        tiempo_total = ""
        horas_extras = "00:00:00"

    registrar_en_excel = False
    excel_token_ok = False

    try:
        cur.execute("""
            UPDATE tareas
            SET cantidad = ?,
                inicio   = ?,
                fin      = ?,
                estado   = 'Finalizado'
            WHERE id = ?
              AND asignado_a = ?
              AND estado != 'Finalizado'
        """, (int(cantidad_db or 0), inicio, fin, tarea_id, usuario))

        filas_afectadas = cur.rowcount

        if filas_afectadas > 0:
            registrar_en_excel = True

            _asegurar_cols_historial(cur)

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
            else:
                print("ℹ️ Ya existía en historial_tareas (autocierre); no se inserta de nuevo.")

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

    except Exception as e:
        conn.rollback()
        print("⚠️ Error en autocerrar_tarea_usuario:", e)
        conn.close()
        return jsonify({"ok": False, "msg": "Error BD"}), 500

    conn.close()

    if registrar_en_excel and excel_token_ok:
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

    if _debug_autocierre_activo():
        _desactivar_debug_aviso()

    return jsonify({"ok": True, "tiempo_total": tiempo_total, "horas_extras": horas_extras}), 200


# =========================
# PAUSAR / REANUDAR (JSON)
# =========================
@usuario_bp.route("/pausar_tarea_usuario", methods=["POST"])
def pausar_tarea_usuario():
    if not _solo_usuario():
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    data = request.get_json(silent=True) or {}
    tarea_id = data.get("id")
    usuario = session.get("usuario", "Desconocido")

    try:
        tarea_id = int(tarea_id)
    except Exception:
        return jsonify({"ok": False, "msg": "ID inválido"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)
    _asegurar_cols_pausa(cur)

    try:
        fila = cur.execute(
            "SELECT estado, COALESCE(pausa_inicio,'') AS pausa_inicio FROM tareas WHERE id=? AND asignado_a=? LIMIT 1",
            (tarea_id, usuario)
        ).fetchone()

        if not fila:
            conn.close()
            return jsonify({"ok": False, "msg": "Tarea no encontrada"}), 404

        estado = (fila[0] if isinstance(fila, tuple) else fila["estado"]) or ""
        pausa_inicio = (fila[1] if isinstance(fila, tuple) else fila["pausa_inicio"]) or ""

        if estado.strip() == "Finalizado":
            conn.close()
            return jsonify({"ok": False, "msg": "No se puede pausar una tarea finalizada"}), 400

        if estado.strip() == "Pausada":
            conn.close()
            return jsonify({"ok": False, "msg": "La tarea ya está en PAUSA"}), 400

        if not pausa_inicio:
            pausa_inicio = now_iso()
            cur.execute(
                "UPDATE tareas SET estado='Pausada', pausa_inicio=? WHERE id=? AND asignado_a=?",
                (pausa_inicio, tarea_id, usuario)
            )
        else:
            cur.execute(
                "UPDATE tareas SET estado='Pausada' WHERE id=? AND asignado_a=?",
                (tarea_id, usuario)
            )

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "estado": "Pausada", "pausa_inicio": pausa_inicio}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        print("⚠️ Error en pausar_tarea_usuario:", e)
        return jsonify({"ok": False, "msg": "Error BD"}), 500


@usuario_bp.route("/reanudar_tarea_usuario", methods=["POST"])
def reanudar_tarea_usuario():
    if not _solo_usuario():
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    data = request.get_json(silent=True) or {}
    tarea_id = data.get("id")
    usuario = session.get("usuario", "Desconocido")

    try:
        tarea_id = int(tarea_id)
    except Exception:
        return jsonify({"ok": False, "msg": "ID inválido"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    ensure_tareas_columns(conn)
    _asegurar_cols_pausa(cur)

    try:
        fila = cur.execute(
            "SELECT estado, COALESCE(pausa_inicio,'') AS pausa_inicio, COALESCE(pausa_acum,0) AS pausa_acum "
            "FROM tareas WHERE id=? AND asignado_a=? LIMIT 1",
            (tarea_id, usuario)
        ).fetchone()

        if not fila:
            conn.close()
            return jsonify({"ok": False, "msg": "Tarea no encontrada"}), 404

        estado = (fila[0] if isinstance(fila, tuple) else fila["estado"]) or ""
        pausa_inicio = (fila[1] if isinstance(fila, tuple) else fila["pausa_inicio"]) or ""
        pausa_acum = int((fila[2] if isinstance(fila, tuple) else fila["pausa_acum"]) or 0)

        if estado.strip() == "Finalizado":
            conn.close()
            return jsonify({"ok": False, "msg": "No se puede reanudar una tarea finalizada"}), 400

        if estado.strip() != "Pausada":
            conn.close()
            return jsonify({"ok": False, "msg": "La tarea no está en PAUSA"}), 400

        if pausa_inicio:
            try:
                dt_pi = datetime.fromisoformat(pausa_inicio.replace("Z", ""))
                dt_now = datetime.fromisoformat(now_iso().replace("Z", ""))
                seg = int((dt_now - dt_pi).total_seconds())
                seg = max(0, seg)
                pausa_acum = int(pausa_acum) + seg
            except Exception as e:
                print("⚠️ No se pudo acumular pausa:", e)

        cur.execute(
            "UPDATE tareas SET estado='En curso', pausa_inicio=NULL, pausa_acum=? WHERE id=? AND asignado_a=?",
            (int(pausa_acum), tarea_id, usuario)
        )

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "estado": "En curso", "pausa_acum": int(pausa_acum)}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        print("⚠️ Error en reanudar_tarea_usuario:", e)
        return jsonify({"ok": False, "msg": "Error BD"}), 500


# =========================
# HISTORIAL USUARIO
# =========================
@usuario_bp.route('/historial_usuario')
def historial_usuario():
    if not _solo_usuario():
        flash("Debes iniciar sesión como usuario.", "danger")
        return redirect(url_for('login'))

    usuario = session.get('usuario')

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    _asegurar_cols_historial(cur)

    cur.execute("""
        SELECT
            id,
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
        WHERE usuario = ?
        ORDER BY id DESC
    """, (usuario,))
    tareas = cur.fetchall()
    conn.close()

    return render_template('historial_usuario.html', tareas=tareas, usuario=usuario)


# =========================
# CHECKLIST (MULTI-MÓDULO) - RUTA CONSERVA EL NOMBRE /checklist_impresion
# =========================
@usuario_bp.route('/checklist_impresion', methods=['GET', 'POST'])
def checklist_impresion():
    if not _solo_usuario():
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for('login'))

    usuario = session.get('usuario')

    tarea_id = (request.args.get("id") or request.form.get("id") or "").strip()
    tarea_id_int = None
    op_no = (request.args.get('op_no') or request.form.get('op_no') or '').strip()
    proceso = (request.args.get('proceso') or request.form.get('proceso') or '').strip()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        ensure_tareas_columns(conn)
    except Exception:
        pass

    # ✅ Si viene ID, OP/PROCESO reales vienen de BD (fuente de verdad)
    if tarea_id:
        try:
            tid = int(tarea_id)
            tarea_id_int = tid
            fila = cur.execute("""
                SELECT titulo, proceso, estado
                FROM tareas
                WHERE id=? AND asignado_a=?
                LIMIT 1
            """, (tid, usuario)).fetchone()

            if not fila:
                conn.close()
                flash("⚠️ Tarea no encontrada para checklist.", "warning")
                return redirect(url_for("usuario.panel"))

            op_db = (fila[0] if isinstance(fila, tuple) else fila["titulo"]) or ""
            proc_db = (fila[1] if isinstance(fila, tuple) else fila["proceso"]) or ""
            est_db = (fila[2] if isinstance(fila, tuple) else fila["estado"]) or ""

            op_no = op_no or str(op_db).strip()
            proceso = proceso or str(proc_db).strip()

            if (est_db or "").strip() == "Pausada":
                conn.close()
                flash("⏸️ La tarea está en PAUSA. Reanúdala para poder usar el checklist.", "warning")
                return redirect(url_for("usuario.panel"))
        except Exception:
            pass

    # ✅ Si no llega proceso, inferirlo (última en curso para esa OP)
    if op_no and not proceso:
        try:
            fila_proc = cur.execute("""
                SELECT proceso
                FROM tareas
                WHERE asignado_a = ?
                  AND titulo = ?
                  AND estado = 'En curso'
                ORDER BY id DESC
                LIMIT 1
            """, (usuario, op_no)).fetchone()

            if fila_proc:
                proceso = (fila_proc[0] if isinstance(fila_proc, tuple) else fila_proc["proceso"]) or ""
        except Exception:
            pass

    proceso = (proceso or "").strip()

    # ⛔ Bloquear checklist SOLO si ESA tarea (OP + proceso + usuario) está Pausada
    if op_no and proceso and (not tarea_id):
        try:
            fila_p = cur.execute("""
                SELECT estado
                FROM tareas
                WHERE asignado_a = ?
                  AND titulo = ?
                  AND proceso = ?
                ORDER BY id DESC
                LIMIT 1
            """, (usuario, op_no, proceso)).fetchone()

            est = ""
            if fila_p:
                est = (fila_p[0] if isinstance(fila_p, tuple) else fila_p["estado"]) or ""
                est = est.strip()

            if est == "Pausada":
                conn.close()
                flash("⏸️ La tarea está en PAUSA. Reanúdala para poder usar el checklist.", "warning")
                return redirect(url_for("usuario.panel"))
        except Exception:
            pass

    modulo_activo = (request.args.get("modulo") or request.form.get("modulo") or "").strip().lower()
    if not modulo_activo and proceso:
        modulo_activo = (_modulo_por_proceso(proceso) or "").strip().lower()
    if not modulo_activo:
        modulo_activo = "impresion"

    cur.execute("""
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
    """)

    _asegurar_tabla_checklist_modulos(cur)

    if request.method == "GET" and op_no and modulo_activo:
        try:
            if _existe_checklist_modulo(cur, usuario, op_no, modulo_activo, tarea_id=tarea_id_int):
                conn.close()
                flash("✅ Checklist ya realizado. Finaliza la tarea para continuar.", "info")
                return redirect(url_for("usuario.panel"))
        except Exception:
            pass

    if request.method == 'POST':
        modulo = (request.form.get("modulo") or modulo_activo or "impresion").strip().lower()
        if tarea_id_int is None:
            try:
                tarea_id_int = int((request.form.get("id") or "").strip())
            except Exception:
                tarea_id_int = None
        try:
            if _existe_checklist_modulo(cur, usuario, op_no, modulo, tarea_id=tarea_id_int):
                conn.close()
                flash("✅ Checklist ya realizado. Finaliza la tarea para continuar.", "info")
                return redirect(url_for("usuario.panel"))
        except Exception:
            pass
        if modulo == "varios" and not (request.form.get("observaciones_varios") or "").strip():
            conn.close()
            flash("⚠️ Debes llenar las observaciones para guardar el checklist.", "warning")
            return redirect(request.url)
        fecha = now_iso()

        data_dict = request.form.to_dict(flat=True)
        data_dict.pop("modulo", None)
        data_dict.pop("id", None)

        cur.execute("""
            INSERT INTO checklist_modulos (usuario, op_no, modulo, tarea_id, fecha, data_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (usuario, op_no, modulo, tarea_id_int, fecha, json.dumps(data_dict, ensure_ascii=False)))

        if modulo == "impresion":
            p1 = (request.form.get('p1_entrega_paquete') or 'NA').strip()
            p2 = (request.form.get('p2_verificar_planchas') or 'NA').strip()
            p3 = (request.form.get('p3_alistamiento_corte_papel') or 'NA').strip()
            p4 = (request.form.get('p4_control_50_tiros') or 'NA').strip()
            p41 = (request.form.get('p41_tonos_carta_color') or 'NA').strip()
            p42 = (request.form.get('p42_tonos_muestra_aprobada') or 'NA').strip()

            cur.execute("""
                INSERT INTO checklist_impresion (
                    usuario, op_no, fecha,
                    p1_entrega_paquete,
                    p2_verificar_planchas,
                    p3_alistamiento_corte_papel,
                    p4_control_50_tiros,
                    p41_tonos_carta_color,
                    p42_tonos_muestra_aprobada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (usuario, op_no, fecha, p1, p2, p3, p4, p41, p42))

        conn.commit()
        conn.close()

        flash(f"✅ Checklist guardado correctamente ({modulo.upper()}).", "success")
        return redirect(url_for('usuario.panel'))

    from jinja2 import TemplateNotFound
    template_name = "usuario/checklist_impresion.html"
    if modulo_activo == "flexo":
        template_name = "usuario/checklist_flexo.html"
    if modulo_activo == "mantenimiento_sormz_sorm_barnizado" or ("sorm" in modulo_activo and "barniz" in modulo_activo):
        template_name = "usuario/checklist_mantenimiento_sormz_sorm_barnizado.html"
    if modulo_activo == "pegue" or ("pegue" in modulo_activo):
        template_name = "usuario/checklist_pegue_cajas.html"
    if modulo_activo == "varios":
        template_name = "usuario/checklist_varios.html"
    try:
        return render_template(
            template_name,
            op_no=op_no,
            usuario=usuario,
            modulo_activo=modulo_activo,
            tarea_id=tarea_id_int or ""
        )
    except TemplateNotFound:
        return render_template(
            template_name.replace("usuario/", ""),
            op_no=op_no,
            usuario=usuario,
            modulo_activo=modulo_activo,
            tarea_id=tarea_id_int or ""
        )
