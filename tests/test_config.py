# Copyright (c) 2020-2021 CRS4
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

import lifemonitor.api.models as api_models
import lifemonitor.config as lm_cfg
import lifemonitor.exceptions as lm_exceptions
import prometheus_client
import pytest
from lifemonitor.app import create_app

logger = logging.getLogger(__name__)

# settings example
testing_settings = {"PROPERTY": "123456"}


def test_db(app_context, app_settings):
    logger.debug("App settings: %r", app_context.app.config)
    assert app_context.app.config['POSTGRESQL_DATABASE'] == "lmtest", "Unexpected database in use"


def test_not_valid_base_config():
    assert lm_cfg.get_config_by_name("InvalidConfig") == lm_cfg.ProductionConfig, \
        "A production config should be returned as a fallback"


def check_config_properties(settings, flask_app=None):
    logger.debug("App settings:  %r", settings)
    if flask_app is None:
        flask_app = create_app(env="testing", settings=settings, init_app=False)
    logger.debug("App Config: %r", flask_app.config)

    for k, v in settings.items():
        if k == "API_KEYS":
            continue
        conf_value = str(flask_app.config.get(k, None))
        logger.debug("Checking %s: %s - %s", k, v, conf_value)
        assert conf_value == v, \
            f"Inconsistent property '{k}': found {v} in settings, but {conf_value} in the Flask config"


@pytest.mark.parametrize("app_settings", [False], indirect=True)
def test_config_from_settings(app_settings):
    logger.debug("App settings:  %r", app_settings)
    # disable the instance config 'FLASK_APP_CONFIG_FILE'
    os.environ.pop("FLASK_APP_CONFIG_FILE", None)
    app_settings.pop("FLASK_APP_CONFIG_FILE", None)
    # check app configuration wrt the app_settings
    check_config_properties(app_settings)


@pytest.mark.parametrize("fake_app_context", [{}], indirect=True)
def test_instance_not_defined(fake_app_context):
    logger.debug("CONFIG: %r", fake_app_context.app.config)
    assert fake_app_context.app.config.get("FLASK_APP_CONFIG_FILE", None) is None, \
        "Unexpected FLASK_APP_CONFIG_FILE "


@pytest.mark.parametrize("instance_config_file", [("test_config.py", testing_settings)], indirect=True)
def test_absolute_path_instance_folder(instance_config_file):
    settings = {"FLASK_APP_INSTANCE_PATH": "a_relative_path"}
    with pytest.raises(ValueError, match=r".*must be absolute.*"):
        create_app(env="testing", settings=settings, init_app=False)


@pytest.mark.parametrize("instance_config_file", [("test_config.py", testing_settings)], indirect=True)
def test_config_instance(instance_config_file):
    instance_path = os.path.dirname(instance_config_file)
    instance_file = os.path.basename(instance_config_file)
    settings = {"FLASK_APP_INSTANCE_PATH": instance_path, "FLASK_APP_CONFIG_FILE": instance_file}
    settings.update({"PROPERTY": "_OLD_VALUE_"})  # this should be overwritten from instance_config
    flask_app = create_app(env="testing", settings=settings, init_app=False)
    # check if settings from config instance are set
    # and the "PROPERTY" from settings has been overwritten
    check_config_properties(testing_settings, flask_app)


@pytest.fixture(params=("travis", "travis_org", "TRAVIS_ORG", "TRAVIS_COM"))
def testing_service_label(request):
    return request.param


@pytest.fixture
def testing_service_config(testing_service_label):
    service_label = testing_service_label.upper()
    return {
        "FLASK_ENV": "testing",
        f"{service_label}_TESTING_SERVICE_URL": "https://api.travis-ci.org",
        f"{service_label}_TESTING_SERVICE_TOKEN": "123456789"
    }


def test_valid_config_service_token(testing_service_label, testing_service_config):
    service_label = testing_service_label.upper()
    flask_app = create_app(env="testing", settings=testing_service_config, init_app=True)
    prometheus_client.REGISTRY = prometheus_client.CollectorRegistry(auto_describe=True)
    logger.debug(flask_app.config)
    mgt = api_models.TestingServiceTokenManager.get_instance()
    with flask_app.app_context():
        logger.info(flask_app.config)
        token = mgt.get_token(testing_service_config[f'{service_label}_TESTING_SERVICE_URL'])
        assert token.value == \
            testing_service_config[f'{service_label}_TESTING_SERVICE_TOKEN'], "Unexpected token"


def test_config_service_token_unsupported_service_type():
    settings = {
        "TRAVI_ORG_TESTING_SERVICE_URL": "https://api.travis-ci.org",
        "TRAVI_ORG_TESTING_SERVICE_TOKEN": "123456789"
    }
    with pytest.raises(lm_exceptions.TestingServiceNotSupportedException):
        create_app(env="testing", settings=settings, init_app=True)
