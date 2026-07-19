"""Servidor TrazOp privado que se ejecuta dentro del proceso Android."""

import os
import threading
from pathlib import Path

from werkzeug.serving import make_server


_server = None
_server_lock = threading.Lock()


def _configure_storage(app_home: str) -> Path:
    home = Path(app_home).resolve()
    data_dir = home / "trazop-data"
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HOME"] = str(home)
    os.environ["HELP_APP_DATA_DIR"] = str(data_dir)
    os.environ["HELP_APP_HOSTING"] = "android-local"
    os.environ["HELP_APP_HTTPS"] = "0"
    os.environ["HELP_APP_ENABLE_AUTOCIERRE"] = "1"
    os.environ["HELP_APP_COPY_SEED_DATABASE"] = "0"
    return data_dir


def start_server(app_home: str):
    """Inicia Flask en loopback. La llamada permanece en el hilo nativo."""
    global _server

    with _server_lock:
        if _server is not None:
            return "already-running"

        _configure_storage(app_home)

        from app import create_app

        flask_app = create_app()
        flask_app.add_url_rule(
            "/__mobile_health",
            endpoint="mobile_health",
            view_func=lambda: ("ok", 200, {"Cache-Control": "no-store"}),
        )
        _server = make_server(
            "127.0.0.1",
            5000,
            flask_app,
            threaded=True,
        )

    _server.serve_forever()
    return "stopped"
