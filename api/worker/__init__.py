from flask import Blueprint
worker_bp = Blueprint('worker_api', __name__)
from . import staff