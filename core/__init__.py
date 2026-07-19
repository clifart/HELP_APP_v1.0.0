# === Utilidades de fecha/hora de la aplicacion (Colombia) ===
from datetime import datetime
from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("America/Bogota")


def local_now() -> datetime:
    """Fecha/hora actual de Colombia, independiente de la zona del servidor."""
    return datetime.now(APP_TIMEZONE)


def now_iso() -> str:
    return local_now().strftime("%Y-%m-%d %H:%M:%S")
