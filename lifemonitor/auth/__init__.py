import logging
import lifemonitor.auth.oauth2 as oauth2
from .services import login_manager
from .controllers import blueprint as auth_blueprint

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir):
    logger.debug("Registering auth blueprint")
    oauth2.client.register_api(app, specs_dir, "auth.view")
    oauth2.server.register_api(app, specs_dir)
    app.register_blueprint(auth_blueprint)
    login_manager.init_app(app)
