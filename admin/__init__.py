# admin/__init__.py
from flask import Blueprint

admin_bp = Blueprint(
    'admin',
    __name__,
    url_prefix='/admin',
    template_folder='templates'
)

# Importa las vistas para registrar las rutas en este blueprint
from . import views  # noqa
