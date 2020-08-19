import logging
from .controllers import blueprint, server

# Config a module level logger
from .models import Token

logger = logging.getLogger(__name__)


def register_api(app, specs_dir):
    # TODO: implement Server configuration
    # see https://docs.authlib.org/en/stable/flask/2/authorization-server.html
    server.init_app(app)
    # register routes of the OAuth server
    app.register_blueprint(blueprint)
