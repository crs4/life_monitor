import os
import logging
from typing import List, Type

basedir = os.path.abspath(os.path.dirname(__file__))


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


def config_db_access(flask_app, db):
    """
    Initialize DB
    :param flask_app:
    :param db:
    :return:
    """
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = db_uri()
    # flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(flask_app)
    db.create_all()


class BaseConfig:
    CONFIG_NAME = "base"
    USE_MOCK_EQUIVALENCY = False
    DEBUG = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
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
    DEBUG = False
    TESTING = False


class TestingConfig(BaseConfig):
    CONFIG_NAME = "testing"
    SECRET_KEY = os.getenv("TEST_SECRET_KEY", "Thanos did nothing wrong")
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///{0}/app-test.db".format(basedir)


_EXPORT_CONFIGS: List[Type[BaseConfig]] = [
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
]
_config_by_name = {cfg.CONFIG_NAME: cfg for cfg in _EXPORT_CONFIGS}


def get_config_by_name(name):
    try:
        return _config_by_name[name]
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
