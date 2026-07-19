"""Punto de entrada WSGI para el hosting permanente de TrazOp."""

import os
import secrets
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = Path.home() / ".trazop"
PRIVATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def _persistent_secret() -> str:
    configured = os.environ.get("HELP_APP_SECRET_KEY", "").strip()
    if configured:
        return configured
    secret_file = PRIVATE_DIR / "flask-secret-key"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(48)
    secret_file.write_text(value, encoding="utf-8")
    try:
        secret_file.chmod(0o600)
    except OSError:
        pass
    return value


os.environ.setdefault("HELP_APP_HOSTING", "pythonanywhere")
os.environ.setdefault("HELP_APP_HTTPS", "1")
os.environ.setdefault("HELP_APP_DATA_DIR", str(Path.home() / "trazop-data"))
os.environ.setdefault("HELP_APP_ENABLE_AUTOCIERRE", "1")
os.environ.setdefault("HELP_APP_AUTOCIERRE_INTERVAL", "60")
os.environ.setdefault("HELP_APP_SECRET_KEY", _persistent_secret())

from app import create_app  # noqa: E402


application = create_app()
app = application
