import os
import dotenv
import logging
from typing import List, Type

basedir = os.path.abspath(os.path.dirname(__file__))

# load "settings.conf" to the environment
settings = None
if os.path.exists("settings.conf"):
    settings = dotenv.dotenv_values(dotenv_path="settings.conf")
    os.environ.update(settings)


def db_uri():
    """
    Build URI to connect to the DataBase
    :return:
    """
    # "sqlite:///{0}/app-dev.db".format(basedir)
    if os.getenv('DATABASE_URI'):
        uri = os.getenv('DATABASE_URI')
    else:
        uri = "postgresql://{user}:{passwd}@{host}:{port}/{dbname}".format(
            user=os.getenv('POSTGRESQL_USERNAME'),
            passwd=os.getenv('POSTGRESQL_PASSWORD', ''),
            host=os.getenv('POSTGRESQL_HOST'),
            port=os.getenv('POSTGRESQL_PORT'),
            dbname=os.getenv('POSTGRESQL_DATABASE'))
    return uri


class BaseConfig:
    CONFIG_NAME = "base"
    USE_MOCK_EQUIVALENCY = False
    DEBUG = os.getenv("DEBUG", False)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG' if os.getenv("DEBUG", False) else 'INFO')
    # Add a random secret (required to enable HTTP sessions)
    SECRET_KEY = os.urandom(24)
    SQLALCHEMY_DATABASE_URI = db_uri()
    # FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
    # overhead and will be disabled by default in the future.  Set it to True
    # or False to suppress this warning.
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    CONFIG_NAME = "development"
    # Add a random secret (required to enable HTTP sessions)
    SECRET_KEY = os.getenv(
        "DEV_SECRET_KEY", "LifeMonitor Development Secret Key"
    )
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    TESTING = False


class ProductionConfig(BaseConfig):
    CONFIG_NAME = "production"
    SECRET_KEY = os.getenv("PROD_SECRET_KEY", "LifeMonitor Production Secret Key")
    TESTING = False


class TestingConfig(BaseConfig):
    CONFIG_NAME = "testing"
    SECRET_KEY = os.getenv("TEST_SECRET_KEY", "Thanos did nothing wrong")
    DEBUG = True
    TESTING = True
    LOG_LEVEL = "DEBUG"
    SQLALCHEMY_DATABASE_URI = "sqlite:///{0}/app-test.db".format(basedir)


_EXPORT_CONFIGS: List[Type[BaseConfig]] = [
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
]
_config_by_name = {cfg.CONFIG_NAME: cfg for cfg in _EXPORT_CONFIGS}


def get_config_by_name(name):
    try:
        config = _config_by_name[name]
        if settings:
            # append properties from settings.conf
            # to the default configuration
            for k, v in settings.items():
                setattr(config, k, v)
        return config
    except KeyError:
        return ProductionConfig


def configure_logging(app):
    level_str = app.config.get('LOG_LEVEL', 'INFO')
    error = False
    try:
        level_value = getattr(logging, level_str)
    except AttributeError:
        level_value = logging.INFO
        error = True

    logging.basicConfig(level=level_value)
    if error:
        app.logger.error("LOG_LEVEL value %s is invalid. Defaulting to INFO", level_str)

    app.logger.info('Logging is active. Log level: %s', logging.getLevelName(app.logger.getEffectiveLevel()))
