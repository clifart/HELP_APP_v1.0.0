# core/exportar_excel.py

import os
import sqlite3
from datetime import datetime
from flask import current_app

from openpyxl import Workbook


def _auto_ajustar_ancho(ws, headers, filas, max_width=50):
    for col_idx, h in enumerate(headers, start=1):
        max_len = len(str(h))
        for fila in filas:
            v = fila.get(h, "")
            if v is None:
                v = ""
            max_len = max(max_len, len(str(v)))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, max_width)


def _leer_tabla(conn, tabla):
    cur = conn.cursor()

    cur.execute(f"PRAGMA table_info({tabla})")
    cols_info = cur.fetchall()
    headers = [c[1] for c in cols_info]

    if not headers:
        return [], []

    cur.execute(f"SELECT * FROM {tabla}")
    rows = cur.fetchall()

    filas = []
    for r in rows:
        filas.append({headers[i]: r[i] for i in range(len(headers))})

    return headers, filas


def _guardar_xlsx(headers, filas, ruta_xlsx, hoja):
    wb = Workbook()
    ws = wb.active
    ws.title = (hoja or "Datos")[:31]

    ws.append(headers)
    for f in filas:
        ws.append([f.get(h, "") for h in headers])

    _auto_ajustar_ancho(ws, headers, filas)
    wb.save(ruta_xlsx)


def exportar_bd_a_excel(conn, carpeta_destino):
    """
    Exporta TODAS las tablas de la base de datos a archivos Excel (.xlsx).
    Crea un archivo .xlsx por tabla dentro de carpeta_destino:
        usuarios.xlsx
        tareas.xlsx
        historial_tareas.xlsx
        ...
    """
    cur = conn.cursor()
    os.makedirs(carpeta_destino, exist_ok=True)

    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
    """)
    tablas = [fila[0] for fila in cur.fetchall()]

    for tabla in tablas:
        try:
            headers, filas = _leer_tabla(conn, tabla)
        except sqlite3.OperationalError:
            continue

        if not filas:
            continue

        ruta_xlsx = os.path.join(carpeta_destino, f"{tabla}.xlsx")
        _guardar_xlsx(headers, filas, ruta_xlsx, hoja=tabla)


def exportar_excel_automatico(conn):
    """
    Exporta la BD a:
      EXPORT_EXCEL_AUTO/AAAA-MM-DD/*.xlsx
    """
    base_dir = os.environ.get("HELP_APP_DATA_DIR", "").strip() or current_app.root_path

    carpeta_base = os.path.join(base_dir, "EXPORT_EXCEL_AUTO")
    os.makedirs(carpeta_base, exist_ok=True)

    hoy = datetime.now().strftime("%Y-%m-%d")
    carpeta_hoy = os.path.join(carpeta_base, hoy)
    os.makedirs(carpeta_hoy, exist_ok=True)

    exportar_bd_a_excel(conn, carpeta_hoy)
