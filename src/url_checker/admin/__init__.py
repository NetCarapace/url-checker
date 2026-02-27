from flask import Blueprint

admin = Blueprint("admin", __name__, url_prefix="/admin")

# Import views at the END to avoid circular imports
from . import views  # noqa: E402
