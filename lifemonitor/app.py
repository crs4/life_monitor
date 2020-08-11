import os
import logging
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import lifemonitor.config as config
from lifemonitor.routes import register_routes

# set DB instance
db = SQLAlchemy()

# set module level logger
logger = logging.getLogger(__name__)


def create_app(env=None, instance_config_name=None):
    """
    App factory method
    :param instance_config_name:
    :param env:
    :return:
    """
    # set app env
    app_env = env or os.environ.get("FLASK_ENV", "production")
    # create Flask app instance
    app = Flask(__name__, instance_relative_config=True)
    # set config object
    app.config.from_object(config.get_config_by_name(app_env))
    # load the file specified by the FLASK_APP_CONFIG_FILE environment variable
    # variables defined here will override those in the default configuration
    if os.environ.get("FLASK_APP_CONFIG_FILE", None):
        app.config.from_envvar("FLASK_APP_CONFIG_FILE")
    # load instance configuration
    # variables defined here will override those in the default configuration
    # and in the FLASK_APP_CONFIG_FILE
    if instance_config_name:
        app.config.from_pyfile(instance_config_name)
    # configure logging
    config.configure_logging(app)
    # configure app DB
    db.init_app(app)
    # configure app routes
    register_routes(app)

    # append routes to check app health
    @app.route("/health")
    def health():
        return jsonify("healthy")

    return app
