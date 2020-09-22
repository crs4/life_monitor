import os
import pytest
import logging
import lifemonitor.config as lm_cfg
from lifemonitor.app import create_app

logger = logging.getLogger()

# settings example
testing_settings = {"PROPERTY": "123456"}


@pytest.mark.xfail(raises=KeyError)
def test_not_valid_base_config():
    lm_cfg.get_config_by_name("InvalidConfig")


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
