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

import configparser
import logging
import os
import re
from base64 import b64encode
from logging.config import dictConfig
from typing import List, Type

import dotenv
from flask import current_app

from lifemonitor.utils import boolean_value

from .db import db_uri

basedir = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger(__name__)


def load_settings(config=None):
    result = None
    if config:
        file_path = config.SETTINGS_FILE
    else:
        file_path = "settings.conf"
    result = {}
    test_settings = None
    if config.CONFIG_NAME in ('development', 'testing', 'testingSupport'):
        test_settings = dotenv.dotenv_values(dotenv_path=TestingConfig.SETTINGS_FILE)
        if not config.TESTING:
            for k, v in test_settings.items():
                if not hasattr(config, k):
                    result[k] = v
    if os.path.exists(file_path):
        result.update(dotenv.dotenv_values(dotenv_path=file_path))
    if config.CONFIG_NAME in ('testingSupport', 'testing'):
        result.update(test_settings)
    return result


def load_proxy_entries(config=None):
    config = config or current_app.config
    pattern = re.compile(r'PROXY_(.+)_URL')
    result = {}
    try:
        from .utils import get_external_server_url
        result['default'] = {'name': 'default', 'url': get_external_server_url()}
    except KeyError:
        pass
    for k in config:
        service_match = pattern.match(k)
        if service_match:
            try:
                service_name = service_match.group(1)
                service_url = config[f"PROXY_{service_name}_URL"]
                logger.info(f"Read proxy entry '{service_name.lower()}': {service_url}")
                result[service_name.lower()] = {
                    'name': service_name.lower(),
                    'url': service_url
                }
            except (KeyError, IndexError) as e:
                logger.error(f"Error when reading entry '{service_match}': {str(e)}")
    return result


class BaseConfig:
    CONFIG_NAME = "base"
    SETTINGS_FILE = "settings.conf"
    USE_MOCK_EQUIVALENCY = False
    DEBUG = False
    # Initialize SERVER_NAME from env
    SERVER_NAME = os.environ.get('SERVER_NAME', None)
    # Initialize LOG_LEVEL from env
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')
    # Add a random secret (required to enable HTTP sessions)
    SECRET_KEY = os.getenv("SECRET_KEY", b64encode(os.urandom(24)).decode('utf-8'))
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = SECRET_KEY
    # FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
    # overhead and will be disabled by default in the future.  Set it to True
    # or False to suppress this warning.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Enable refresh token generation.
    # Refresh tokens will be issued as part of authorization code flow tokens
    OAUTH2_REFRESH_TOKEN_GENERATOR = True
    # Refresh the token <N> seconds before its expiration
    OAUTH2_REFRESH_TOKEN_BEFORE_EXPIRATION = 5 * 60
    # JWT Settings
    JWT_SECRET_KEY_PATH = os.getenv("JWT_SECRET_KEY_PATH", 'certs/jwt-key')
    JWT_EXPIRATION_TIME = int(os.getenv("JWT_EXPIRATION_TIME", "3600"))
    # Disable the Flask APScheduler REST API, by default
    SCHEDULER_API_ENABLED = False
    WORKER = False
    WEBSOCKET_SERVER = boolean_value(os.environ.get("WEBSOCKET_SERVER", False))
    GUNICORN_SERVER = boolean_value(os.environ.get("GUNICORN_SERVER", False))
    # Default Cache Settings
    CACHE_TYPE = "flask_caching.backends.simplecache.SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 60
    # Default Temp folder
    BASE_TEMP_FOLDER = '/tmp/lifemonitor'
    # Workflow Data Folder
    DATA_WORKFLOWS = "./data"
    # Base URL of the LifeMonitor web app associated with this back-end instance
    WEBAPP_URL = "https://app.lifemonitor.eu"
    # Enable/disable integrations
    ENABLE_GITHUB_INTEGRATION = False
    ENABLE_REGISTRY_INTEGRATION = False


class DevelopmentConfig(BaseConfig):
    CONFIG_NAME = "development"
    # Add a random secret (required to enable HTTP sessions)
    SECRET_KEY = os.getenv("DEV_SECRET_KEY", BaseConfig.SECRET_KEY)
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    TESTING = False
    CACHE_TYPE = "flask_caching.backends.rediscache.RedisCache"


class ProductionConfig(BaseConfig):
    CONFIG_NAME = "production"
    SECRET_KEY = os.getenv("PROD_SECRET_KEY", BaseConfig.SECRET_KEY)
    TESTING = False
    CACHE_TYPE = "flask_caching.backends.rediscache.RedisCache"


class TestingConfig(BaseConfig):
    CONFIG_NAME = "testing"
    SETTINGS_FILE = "tests/settings.conf"
    SECRET_KEY = os.getenv("TEST_SECRET_KEY", BaseConfig.SECRET_KEY)
    DEBUG = True
    TESTING = True
    LOG_LEVEL = "DEBUG"
    # SQLALCHEMY_DATABASE_URI = "sqlite:///{0}/app-test.db".format(basedir)
    # CACHE_TYPE = "flask_caching.backends.nullcache.NullCache"
    CACHE_TYPE = "flask_caching.backends.rediscache.RedisCache"
    DATA_WORKFLOWS = f"{BaseConfig.BASE_TEMP_FOLDER}/lm_tests_data"


class TestingSupportConfig(TestingConfig):
    CONFIG_NAME = "testingSupport"
    DEBUG = True
    TESTING = False
    LOG_LEVEL = "DEBUG"
    DATA_WORKFLOWS = f"{BaseConfig.BASE_TEMP_FOLDER}/lm_tests_data"


_EXPORT_CONFIGS: List[Type[BaseConfig]] = [
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    TestingSupportConfig
]
_config_by_name = {cfg.CONFIG_NAME: cfg for cfg in _EXPORT_CONFIGS}


def get_config(settings=None):
    # set app env
    app_env = os.environ.get("FLASK_ENV", "production")
    if app_env != 'production':
        # Set the DEBUG_METRICS env var to also enable the
        # prometheus metrics exporter when running in development mode
        os.environ['DEBUG_METRICS'] = 'true'
    # load app config
    return get_config_by_name(app_env, settings=settings)


def get_config_by_name(name, settings=None):
    try:
        config = type(f"AppConfigInstance{name}".title(), (_config_by_name[name],), {})
        # load settings from file
        if settings is None:
            settings = load_settings(config)
        if settings and "SQLALCHEMY_DATABASE_URI" not in settings:
            settings["SQLALCHEMY_DATABASE_URI"] = db_uri(settings=settings)
        # always set the FLASK_APP_CONFIG_FILE variable to the environment
        if settings and "FLASK_APP_CONFIG_FILE" in settings:
            os.environ["FLASK_APP_CONFIG_FILE"] = settings["FLASK_APP_CONFIG_FILE"]
        # append properties from settings.conf
        # to the default configuration
        if settings:
            for k, v in settings.items():
                setattr(config, k, v)
        return config
    except KeyError:
        logger.warning("Unable to load the configuration %s: using 'production'", name)
        return ProductionConfig


class LogFilter(logging.Filter):
    def __init__(self, param=None):
        self.param = param
        try:
            config = configparser.ConfigParser()
            config.read('setup.cfg')
            self.filters = [_.strip() for _ in config.get('logging', 'filters').split(',')]
        except Exception:
            self.filters = []

    def filter(self, record):
        try:
            filtered = False
            for k in self.filters:
                if k in record.name:
                    filtered = True
            if not filtered:
                if 'Requester' in record.name:
                    record.msg = "Request to Github API"
                    logger.debug("Request args: %r %r %r %r", record.args[0], record.args[1], record.args[2], record.args[3])
                    record.args = None
        except Exception as e:
            logger.exception(e)
        return not filtered


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"


def formatter_message(message, use_color=True):
    if use_color:
        message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
    else:
        message = message.replace("$RESET", "").replace("$BOLD", "")
    return message


COLORS = {
    'WARNING': YELLOW,
    'INFO': WHITE,
    'DEBUG': BLUE,
    'CRITICAL': YELLOW,
    'ERROR': RED
}


class ColorFormatter(logging.Formatter):
    def __init__(self, format, use_color=True):
        logging.Formatter.__init__(self, format)
        self.use_color = use_color

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            record.levelname = f"{COLOR_SEQ % (30 + COLORS[levelname])}{levelname}{RESET_SEQ}"
            record.module = f"{COLOR_SEQ % (30 + COLORS[levelname])}{record.module}{RESET_SEQ}"
        return logging.Formatter.format(self, record)


def configure_logging(app):
    level_str = app.config.get('LOG_LEVEL', 'INFO')
    error = False
    try:
        level_value = getattr(logging, level_str)
    except AttributeError:
        level_value = logging.INFO
        error = True

    log_format = f'[{COLOR_SEQ % (90)}%(asctime)s{RESET_SEQ}] %(levelname)s in %(module)s: {COLOR_SEQ % (90)}%(message)s{RESET_SEQ}'
    if level_value == logging.DEBUG:
        log_format = f'[{COLOR_SEQ % (90)}%(asctime)s{RESET_SEQ}] %(levelname)s in %(module)s::%(funcName)s @ line: %(lineno)s: {COLOR_SEQ % (90)}%(message)s{RESET_SEQ}'

    dictConfig({
        'version': 1,
        'formatters': {'default': {
            '()': ColorFormatter,
            'format': log_format,
        }},
        'filters': {
            'myfilter': {
                '()': LogFilter,
                # 'param': '',
            }
        },
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default',
            'filters': ['myfilter']
        }},
        'response': {
            'level': logging.INFO,
            'handlers': ['wsgi'],
        },
        'root': {
            'level': level_value,
            'handlers': ['wsgi']
        },
        # Lower the log level for the github.Requester object -- else it'll flood us with messages
        'Requester': {
            'level': logging.ERROR,
            'handlers': ['wsgi']
        },
        'disable_existing_loggers': False,
    })
    # Remove Flask's default handler
    # (https://flask.palletsprojects.com/en/2.0.x/logging/#removing-the-default-handler)
    from flask.logging import default_handler
    app.logger.removeHandler(default_handler)
    # Raise the level of the default flask request logger (actually, it's the one defined by werkzeug)
    try:
        from werkzeug._internal import _log as werkzeug_log
        werkzeug_log("info", "Raising werkzeug logging level to ERROR")
        from werkzeug._internal import _logger as werkzeug_logger
        werkzeug_logger.setLevel(logging.ERROR)
    except ImportError:
        app.logger.warning("Unable to access werkzeug logger to raise its logging level")

    if error:
        app.logger.error("LOG_LEVEL value %s is invalid. Defaulting to INFO", level_str)

    app.logger.info('Logging is active. Log level: %s', logging.getLevelName(app.logger.getEffectiveLevel()))
