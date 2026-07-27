from flask import Blueprint

client_bp = Blueprint('client_app', __name__)

from . import auth  # noqa: E402,F401
from . import cities  # noqa: E402,F401
