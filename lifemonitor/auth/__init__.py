import logging
import lifemonitor.auth.oauth2 as oauth2
from .services import login_manager
from .controllers import blueprint as auth_blueprint
from .services import (
    current_user, current_registry, authorized,
    login_user, logout_user,
    login_registry, logout_registry,
    NotAuthorizedException
)

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir):
    logger.debug("Registering auth blueprint")
    oauth2.client.register_api(app, specs_dir, "auth.merge")
    oauth2.server.register_api(app, specs_dir)
    app.register_blueprint(auth_blueprint)
    login_manager.init_app(app)


__all__ = [
    register_api, current_user, current_registry, authorized,
    login_user, logout_user, login_registry, logout_registry,
    NotAuthorizedException
]
