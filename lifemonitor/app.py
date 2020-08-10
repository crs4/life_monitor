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


def create_app(env=None):
    """
    App factory method
    :param env:
    :return:
    """

    # create Flask app instance
    app = Flask(__name__)
    # Add a random secret (required to enable HTTP sessions)
    app.secret_key = os.urandom(24)

    # configure logging
    config.configure_logging(app)

    # configure app routes
    register_routes(app)

    # logger.debug("Initializing DB...")
    with app.app_context():
        config.config_db_access(app, db)

    # append routes to check app health
    @app.route("/health")
    def health():
        return jsonify("healthy")

    return app
