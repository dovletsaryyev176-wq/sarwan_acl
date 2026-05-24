from flask import Blueprint
marketing_bp = Blueprint('marketing_api', __name__)
from . import marketing_info