# core/db.py
import os
import sys
import sqlite3
import shutil
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


APP_DIR = _base_dir()
DATA_DIR = Path(os.environ.get("HELP_APP_DATA_DIR", str(APP_DIR))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "database.db"


def _initialize_persistent_database():
    copy_seed = os.environ.get("HELP_APP_COPY_SEED_DATABASE", "1").strip()
    if copy_seed != "1":
        return
    source_db = APP_DIR / "database.db"
    if DB_PATH == source_db or DB_PATH.exists() or not source_db.exists():
        return
    shutil.copy2(source_db, DB_PATH)


_initialize_persistent_database()


def get_db_connection():
    """Devuelve una conexión sqlite3 con row_factory=Row."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # No cambiar journal_mode aquí: requiere un bloqueo exclusivo y puede
    # bloquear peticiones simultáneas en servidores WSGI como PythonAnywhere.
    conn.execute("PRAGMA busy_timeout=30000;")
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


def _table_exists(conn, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;",
        (table_name,),
    )
    return cur.fetchone() is not None


def _ensure_column(conn, table: str, column: str, col_def: str):
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def};")


def _chunks(values, size: int = 200):
    for i in range(0, len(values), size):
        yield values[i:i + size]


def _normalize_user_names(conn):
    """
    Normaliza nombres de usuarios existentes:
    - usuarios.nombre -> UPPER(TRIM(nombre))
    - columnas relacionadas con usuario en otras tablas -> UPPER(TRIM(...))

    Seguridad:
    - Si hay duplicados por mayúsc/minúsc (ej. 'ana' y 'ANA'), esos casos se omiten
      para no romper la restricción UNIQUE(nombre).
    """
    if not _table_exists(conn, "usuarios"):
        return

    cur = conn.cursor()
    canon_rows = cur.execute(
        """
        SELECT DISTINCT UPPER(TRIM(nombre)) AS canon
        FROM usuarios
        WHERE nombre IS NOT NULL AND TRIM(nombre) != ''
        """
    ).fetchall()
    duplicated_rows = cur.execute(
        """
        SELECT UPPER(TRIM(nombre)) AS canon, COUNT(*) AS total
        FROM usuarios
        WHERE nombre IS NOT NULL AND TRIM(nombre) != ''
        GROUP BY UPPER(TRIM(nombre))
        HAVING COUNT(*) > 1
        """
    ).fetchall()

    canon_all = sorted({row["canon"] for row in canon_rows if row["canon"]})
    duplicated = {row["canon"] for row in duplicated_rows if row["canon"]}
    safe_canon = [name for name in canon_all if name not in duplicated]

    if not safe_canon:
        return

    # 1) Normaliza tabla principal de usuarios
    for group in _chunks(safe_canon):
        marks = ",".join("?" for _ in group)
        cur.execute(
            f"""
            UPDATE usuarios
               SET nombre = UPPER(TRIM(nombre))
             WHERE nombre IS NOT NULL
               AND TRIM(nombre) != ''
               AND nombre != UPPER(TRIM(nombre))
               AND UPPER(TRIM(nombre)) IN ({marks})
            """,
            tuple(group),
        )

    # 2) Normaliza referencias de usuario en tablas relacionadas
    references = (
        ("tareas", "asignado_a"),
        ("tareas", "usuario_asignado"),
        ("historial_tareas", "usuario"),
        ("checklist_impresion", "usuario"),
        ("checklist_modulos", "usuario"),
        ("registro_excel_log", "usuario"),
    )

    for table_name, column_name in references:
        if not _table_exists(conn, table_name):
            continue
        if not _column_exists(conn, table_name, column_name):
            continue

        for group in _chunks(safe_canon):
            marks = ",".join("?" for _ in group)
            cur.execute(
                f"""
                UPDATE {table_name}
                   SET {column_name} = UPPER(TRIM({column_name}))
                 WHERE {column_name} IS NOT NULL
                   AND TRIM({column_name}) != ''
                   AND {column_name} != UPPER(TRIM({column_name}))
                   AND UPPER(TRIM({column_name})) IN ({marks})
                """,
                tuple(group),
            )


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
                rol TEXT,
                must_change_password INTEGER DEFAULT 0
            );
        """)
        _ensure_column(
            conn,
            "usuarios",
            "must_change_password",
            "INTEGER DEFAULT 0",
        )

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
        _ensure_column(conn, "tareas", "reinicio_pendiente", "INTEGER DEFAULT 0")
        _ensure_column(conn, "tareas", "trabajo_acum", "INTEGER DEFAULT 0")

        # Compatibilidad: tu archivo mezcla usuario_asignado y asignado_a
        _ensure_column(conn, "tareas", "asignado_a", "TEXT")
        _ensure_column(conn, "tareas", "usuario_asignado", "TEXT")

        # Migración segura: nombres de usuario en MAYÚSCULAS y referencias alineadas.
        try:
            _normalize_user_names(conn)
        except Exception as e:
            print(f"[WARN] No se pudo normalizar nombres de usuarios: {e}")

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
        _ensure_column(c, "tareas", "reinicio_pendiente", "INTEGER DEFAULT 0")
        _ensure_column(c, "tareas", "trabajo_acum", "INTEGER DEFAULT 0")

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
