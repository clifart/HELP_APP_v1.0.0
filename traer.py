# ==========================================================
# traer.py — Lector de Órdenes de Producción (OPs)
# HELP_APP v0.1.7 — Auto recarga de Excel
# ==========================================================
import os
import pandas as pd
from datetime import datetime

# Ruta fija al Excel\
EXCEL_PATH = r"D:\Desktop\HELP_APP_v0.1\Excel\Bd_HELP_APP 1.1.xlsm"
HOJA = "SEGUIMIENTO OC"
COLUMNA_OP = "OP No."

# Cache interno para evitar recargar el mismo archivo
_cache = {
    "timestamp": None,
    "ops": []
}

def _archivo_modificado():
    """Verifica si el archivo Excel fue modificado desde la última lectura."""
    try:
        mod_time = os.path.getmtime(EXCEL_PATH)
        if _cache["timestamp"] != mod_time:
            _cache["timestamp"] = mod_time
            return True
        return False
    except FileNotFoundError:
        return False

def obtener_ops():
    """
    Devuelve una lista de OPs (solo la columna 'OP No.').
    Se recarga automáticamente si el archivo Excel cambia.
    """
    # ✅ Si el archivo no cambió, devolvemos el último resultado guardado
    if not _archivo_modificado() and _cache["ops"]:
        return _cache["ops"]

    if not os.path.exists(EXCEL_PATH):
        print(f"⚠️ No se encontró el archivo Excel en la ruta especificada: {EXCEL_PATH}")
        _cache["ops"] = []
        return []

    try:
        # Leer el Excel solo con la columna deseada
        df = pd.read_excel(
            EXCEL_PATH,
            sheet_name=HOJA,
            usecols=[COLUMNA_OP],
            engine="openpyxl"
        )

        # Limpiar datos
        df = df.dropna(subset=[COLUMNA_OP])
        df[COLUMNA_OP] = df[COLUMNA_OP].astype(str).str.strip()
        lista_ops = sorted(df[COLUMNA_OP].unique().tolist())

        # Guardar en cache
        _cache["ops"] = lista_ops

        fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        print(f"📦 {len(lista_ops)} OPs cargadas desde Excel ({fecha})")
        return lista_ops

    except Exception as e:
        print(f"⚠️ Error al leer el archivo Excel: {e}")
        _cache["ops"] = []
        return []

# ==========================================================
# PRUEBA LOCAL
# ==========================================================
if __name__ == "__main__":
    ops = obtener_ops()
    print("🔍 Primeras OPs:", ops[:10])
