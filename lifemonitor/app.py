# Copyright (c) 2020-2022 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import os
import time

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS
from flask_migrate import Migrate

import lifemonitor.config as config
from lifemonitor import redis
from lifemonitor.auth.services import current_user, auto_logout
from lifemonitor.integrations import init_integrations
from lifemonitor.metrics import init_metrics
from lifemonitor.routes import register_routes
from lifemonitor.tasks import init_task_queues
from lifemonitor.utils import get_domain

from . import commands
from .cache import init_cache
from .db import db
from .exceptions import handle_exception
from .mail import init_mail
from .serializers import ma

# set module level logger
logger = logging.getLogger(__name__)


def create_app(env=None, settings=None, init_app=True, init_integrations=True,
               worker=False, load_jobs=True, **kwargs):
    """
    App factory method
    :param env:
    :param settings:
    :param init_app:
    :return:
    """
    # set app env
    app_env = env or os.environ.get("FLASK_ENV", "production")
    if app_env != 'production':
        # Set the DEBUG_METRICS env var to also enable the
        # prometheus metrics exporter when running in development mode
        os.environ['DEBUG_METRICS'] = 'true'
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
    # set worker flag
    app.config['WORKER'] = worker
    # append proxy settings
    app.config['PROXY_ENTRIES'] = config.load_proxy_entries(app.config)

    # initialize the application
    if init_app:
        with app.app_context() as ctx:
            initialize_app(app, ctx, load_jobs=load_jobs, load_integrations=init_integrations)

    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return render_template("index.j2")
        return redirect(url_for('auth.index'))

    @app.route("/profile")
    def profile():
        return redirect(url_for('auth.index', back=request.args.get('back', False)))

    # append routes to check app health
    @app.route("/health")
    def health():
        return jsonify("healthy")

    @app.route("/openapi.html")
    def openapi():
        return redirect('/static/specs/apidocs.html', code=302)

    @app.before_request
    def set_request_start_time():
        request.start_time = time.time()

    @app.after_request
    def log_response(response):
        logger = logging.getLogger("response")
        # log the request
        processing_time = (time.time() * 1000.0 - request.start_time * 1000.0)
        logger.info(
            "resp: %s %s %s %s %s %s %s %s %0.3fms",
            request.remote_addr,
            request.method,
            request.path,
            request.scheme,
            response.status,
            response.content_length,
            request.referrer,
            request.user_agent,
            processing_time
        )
        # remove user from the current session when the authentication
        # is performed via API key or OAuth2 token
        auto_logout()
        # return the response
        return response

    return app


def initialize_app(app: Flask, app_context, prom_registry=None, load_jobs: bool = True, load_integrations: bool = True):
    # init tmp folder
    os.makedirs(app.config.get('BASE_TEMP_FOLDER'), exist_ok=True)
    # enable CORS
    CORS(app, expose_headers=["Content-Type", "X-CSRFToken"], supports_credentials=True)
    # configure logging
    config.configure_logging(app)
    # init Redis connection
    redis.init(app)
    # configure app DB
    db.init_app(app)
    # initialize Migration engine
    Migrate(app, db)
    # initialize cache
    init_cache(app)
    # configure serializer engine (Flask Marshmallow)
    ma.init_app(app)
    # configure app routes
    register_routes(app)
    # init scheduler/worker for async tasks
    init_task_queues(app, load_jobs=load_jobs)
    # init mail system
    init_mail(app)
    # initialize integrations
    if load_integrations:
        init_integrations(app)
    # initialize metrics engine
    init_metrics(app, prom_registry)
    # register commands
    commands.register_commands(app)
    # register the domain filter with Jinja
    app.jinja_env.filters['domain'] = get_domain
