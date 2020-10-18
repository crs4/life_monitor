import logging
from .controllers import create_blueprint
from .services import config_oauth2_registry
from .providers import register_providers

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir, merge_identity_view):
    # Register the OAuth2Registry into the current context
    config_oauth2_registry(app)
    # register providers
    register_providers()
    # Register the '/oauth2' endpoint
    app.register_blueprint(create_blueprint(merge_identity_view), url_prefix="/oauth2")
