
# === Utilidad de fecha/hora en formato ISO (Colombia) ===
from datetime import datetime
from zoneinfo import ZoneInfo

def now_iso():
    return datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
