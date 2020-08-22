import logging

from flask import g
from .controllers import create_blueprint
from .services import oauth2_registry

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir, handle_authorize):
    oauth2_registry.init_app(app)
    # Register the OAuth2Registry into the current context
    with app.app_context():
        g.oauth2_registry = oauth2_registry
    # Register the '/oauth2' endpoint
    app.register_blueprint(create_blueprint(handle_authorize), url_prefix="/oauth2")
