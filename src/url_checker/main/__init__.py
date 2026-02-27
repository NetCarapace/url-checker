from flask import Blueprint

main = Blueprint("main", __name__, url_prefix="/main")

# Import views at the END to avoid circular imports
from . import views  # noqa: E402
