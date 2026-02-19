# core/db.py
import os
import sys
import sqlite3
from pathlib import Path
from contextlib import closing


# ==========================================================
# RUTA DE BD (FIJA Y PREDECIBLE)
# - En .exe (PyInstaller): database.db junto al .exe
# - En desarrollo: database.db en la raíz del proyecto
# ==========================================================
def _base_dir() -> Path:
    if getattr(sys, "frozen", False):  # ejecutándose como .exe
        return Path(sys.executable).resolve().parent
    # proyecto normal: .../core/db.py -> subir 2 niveles
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
DB_PATH = BASE_DIR / "database.db"


def get_db_connection():
    """Devuelve una conexión sqlite3 con row_factory=Row."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_rol(rol: str) -> str:
    """Normaliza a 'admin' o 'usuario'."""
    if not rol:
        return "usuario"
    r = str(rol).strip().lower()
    return "admin" if r in ("admin", "administrador", "adm") else "usuario"


# ---------- Helpers internos ----------
def _column_exists(conn, table_name: str, column_name: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table_name});")
    return any(row["name"] == column_name for row in cur.fetchall())


def _ensure_column(conn, table: str, column: str, col_def: str):
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def};")


# ---------- Esquema ----------
def ensure_schema():
    """Crea tablas si no existen y asegura columnas mínimas."""
    with closing(get_db_connection()) as conn:
        # usuarios
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE,
                celular TEXT,
                contrasena TEXT,
                rol TEXT
            );
        """)

        # tareas (definición base)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tareas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                descripcion TEXT,
                proceso TEXT,
                inicio TEXT,
                fin TEXT,
                estado TEXT,
                cantidad INTEGER
            );
        """)

        # columnas mínimas + compatibilidad
        _ensure_column(conn, "tareas", "titulo", "TEXT")
        _ensure_column(conn, "tareas", "descripcion", "TEXT DEFAULT ''")
        _ensure_column(conn, "tareas", "proceso", "TEXT DEFAULT ''")
        _ensure_column(conn, "tareas", "inicio", "TEXT")
        _ensure_column(conn, "tareas", "fin", "TEXT")
        _ensure_column(conn, "tareas", "estado", "TEXT DEFAULT 'En curso'")
        _ensure_column(conn, "tareas", "cantidad", "INTEGER DEFAULT 0")
        _ensure_column(conn, "tareas", "horario_extendido", "INTEGER DEFAULT 0")
        _ensure_column(conn, "tareas", "extendido_desde", "TEXT")

        # Compatibilidad: tu archivo mezcla usuario_asignado y asignado_a
        _ensure_column(conn, "tareas", "asignado_a", "TEXT")
        _ensure_column(conn, "tareas", "usuario_asignado", "TEXT")

        conn.commit()


def ensure_tareas_columns(conn=None):
    """Asegura columnas e índice único para OP maestras."""
    def _apply(c):
        _ensure_column(c, "tareas", "descripcion", "TEXT DEFAULT ''")
        _ensure_column(c, "tareas", "proceso", "TEXT DEFAULT ''")
        _ensure_column(c, "tareas", "inicio", "TEXT")
        _ensure_column(c, "tareas", "fin", "TEXT")
        _ensure_column(c, "tareas", "estado", "TEXT DEFAULT 'En curso'")
        _ensure_column(c, "tareas", "cantidad", "INTEGER DEFAULT 0")
        _ensure_column(c, "tareas", "horario_extendido", "INTEGER DEFAULT 0")
        _ensure_column(c, "tareas", "extendido_desde", "TEXT")

        # Compatibilidad (por si el resto del código usa uno u otro)
        _ensure_column(c, "tareas", "asignado_a", "TEXT")
        _ensure_column(c, "tareas", "usuario_asignado", "TEXT")

        # Índice único para OP maestras activas
        try:
            c.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_op_maestra_unica
                ON tareas (UPPER(titulo))
                WHERE (proceso IS NULL OR TRIM(proceso) = '')
                  AND (asignado_a IS NULL OR TRIM(asignado_a) = '')
                  AND estado != 'Finalizado'
            """)
        except Exception:
            # Si hay duplicados existentes, este CREATE puede fallar.
            # La lógica de inserción debería evitar nuevos duplicados.
            pass

    if conn is None:
        with closing(get_db_connection()) as c:
            _apply(c)
            c.commit()
    else:
        _apply(conn)
        conn.commit()
