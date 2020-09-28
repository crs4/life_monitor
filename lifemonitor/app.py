import os
import logging
from flask import Flask, jsonify

from .db import db
from . import commands
from .serializers import ma
import lifemonitor.config as config
from lifemonitor.routes import register_routes
from .common import handle_exception


# set module level logger
logger = logging.getLogger(__name__)


def create_app(env=None, settings=None, init_app=True, **kwargs):
    """
    App factory method
    :param env:
    :param settings:
    :param init_app:
    :return:
    """
    # set app env
    app_env = env or os.environ.get("FLASK_ENV", "production")
    # load app config
    app_config = config.get_config_by_name(app_env, settings=settings)
    # set the FlaskApp instance path
    flask_app_instance_path = getattr(app_config, "FLASK_APP_INSTANCE_PATH", None)
    # create Flask app instance
    app = Flask(__name__, instance_relative_config=True, instance_path=flask_app_instance_path, **kwargs)
    # register handler for app specific exception
    app.register_error_handler(Exception, handle_exception)
    # set config object
    app.config.from_object(app_config)
    # load the file specified by the FLASK_APP_CONFIG_FILE environment variable
    # variables defined here will override those in the default configuration
    if os.environ.get("FLASK_APP_CONFIG_FILE", None):
        app.config.from_envvar("FLASK_APP_CONFIG_FILE")
    # initialize the application
    if init_app:
        with app.app_context() as ctx:
            initialize_app(app, ctx)

    # append routes to check app health
    @app.route("/health")
    def health():
        return jsonify("healthy")

    return app


def initialize_app(app, app_context):
    # configure logging
    config.configure_logging(app)
    # configure app DB
    db.init_app(app)
    # configure serializer engine (Flask Marshmallow)
    ma.init_app(app)
    # configure app routes
    register_routes(app)
    # register commands
    commands.register_commands(app)
