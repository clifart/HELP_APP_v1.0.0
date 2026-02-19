# usuario/__init__.py
from flask import Blueprint
usuario_bp = Blueprint("usuario", __name__, url_prefix="/usuario", template_folder="../templates")
from . import views  # noqa

