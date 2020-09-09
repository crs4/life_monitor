import logging
from flask import g
from .controllers import create_blueprint
from .services import config_oauth2_registry

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir, merge_identity_view):
    # Register the OAuth2Registry into the current context
    config_oauth2_registry(app)
    # Register the '/oauth2' endpoint
    app.register_blueprint(create_blueprint(merge_identity_view), url_prefix="/oauth2")
