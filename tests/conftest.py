import re
import os
import json
import enum
from base64 import b64encode

import dotenv
import pytest
import logging
import requests

from flask import current_app, g

from flask_login import login_user

import lifemonitor.db as lm_db
import lifemonitor.config as lm_cfg
from lifemonitor.api.models import TestSuite
from lifemonitor.app import create_app, initialize_app

# set the module level logger
from lifemonitor.auth.models import User

logger = logging.getLogger(__name__)

# add lifemonitor and tests to the Python PATH
base_path = os.path.dirname(os.path.abspath(__file__))

#
app_settings_path = os.path.join(base_path, "../settings.conf")
tests_settings_path = os.path.join(base_path, "settings.conf")

# save current env settings
env_settings = os.environ.copy()

# remove FLASK_APP_CONFIG_FILE from environment
# it will be passed to the main app_context fixture via settings
os.environ.pop("FLASK_APP_CONFIG_FILE", None)


def get_headers(extra_data=None):
    data = {"Content-type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
            "Accept-Charset": "ISO-8859-1"}
    if extra_data:
        data.update(extra_data)
    return data


@pytest.fixture
def headers():
    return get_headers()


class TestParam(enum.Enum):

    @classmethod
    def values(cls):
        return [e.value for e in cls]


class SecurityType(TestParam):
    # BASIC = 'AuthBasic'
    API_KEY = 'ApiKey'
    OAUTH2 = 'Oauth2'


class RegistryType(TestParam):
    SEEK = "seek"


@pytest.fixture
def current_path():
    return os.path.dirname(os.path.abspath(__file__))


def _load_settings(filename):
    logger.debug("Loading settings file: %r", filename)
    if os.path.exists(tests_settings_path):
        return dotenv.dotenv_values(dotenv_path=filename)
    return {}


def _get_app_settings(include_env=True):
    settings = env_settings.copy() if include_env else {}
    settings.update(_load_settings(app_settings_path))
    settings.update(_load_settings(tests_settings_path))
    # remove API KEYS
    api_keys = {}
    pattern = re.compile("((\w+)_API_KEY)")
    for k, v in settings.copy().items():
        m = pattern.match(k)
        if m:
            settings.pop(k)
            api_keys[k] = v
    settings["API_KEYS"] = api_keys
    return settings


@pytest.fixture(scope="session")
def app_settings(request):
    if hasattr(request, 'param'):
        return _get_app_settings(request.param)
    return _get_app_settings()


@pytest.fixture
def instance_config_file(request):
    filename = os.path.join("/tmp", request.param[0])
    data = request.param[1]
    try:
        logger.debug("Creating instance config filename %s", filename)
        with open(filename, 'w') as out:
            for k, v in data.items():
                out.write(f"{k}={v}\n")
        yield filename
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to provide (filename, data) as request param")
    finally:
        if filename:
            # os.remove(filename)
            logger.debug("Instance config file deleted")


def _clean_db():
    for table in reversed(lm_db.db.metadata.sorted_tables):
        lm_db.db.session.execute(table.delete())
    lm_db.db.session.commit()


def auto_login():
    if g.user:
        logger.info("Login user: %r", g.user)
        login_user(g.user)


def _app_context(request_settings, init_db=True, clean_db=True, drop_db=False):
    try:
        os.environ.pop("FLASK_APP_CONFIG_FILE", None)
        conn_param = lm_db.db_connection_params(request_settings)
        if init_db:
            lm_db.create_db(conn_params=conn_param)
            logger.debug("DB created (conn params=%r)", conn_param)
        flask_app = create_app(env="testing", settings=request_settings, init_app=False)
        flask_app.before_request(auto_login)
        with flask_app.app_context() as ctx:
            logger.info("Starting application")
            initialize_app(flask_app, ctx)
            if init_db:
                logger.debug("Initializing DB...")
                lm_db.db.create_all()
                logger.debug("DB initialized!")
            yield ctx
        # clean the database and
        # close all sessions and connections
        with flask_app.app_context() as ctx:
            if clean_db:
                # _clean_db()
                logger.debug("DB cleanup")
            if drop_db:
                lm_db.db.close_all_sessions()
                lm_db.db.engine.pool.dispose()
                lm_db.drop_db(conn_param)
                logger.debug("DB deleted (connection params=%r)", conn_param)
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(e)


def _check_settings(settings_param):
    app_conn_params = lm_db.db_connection_params(_get_app_settings())
    request_conn_params = lm_db.db_connection_params(settings_param)
    logger.debug("Connection parameters: %r", request_conn_params)
    if (app_conn_params["host"], app_conn_params["port"], app_conn_params["dbname"]) \
            == (request_conn_params["host"], request_conn_params["port"], request_conn_params["dbname"]):
        raise RuntimeError("You should use another DATABASE with this app_context")
    return settings_param


@pytest.fixture(scope="session")
def app_context(app_settings):
    yield from _app_context(app_settings, init_db=True, clean_db=True, drop_db=False)


@pytest.fixture
def parametric_app_context(request):
    try:
        yield from _app_context(_check_settings(request.param), clean_db=True, drop_db=True)
    except AttributeError:
        raise RuntimeError("Parametrized fixture. "
                           "You need to provide app settings as dict type in the request param")


@pytest.fixture
def fake_app_context(request):
    try:
        app_config = lm_cfg.get_config_by_name("testing", settings=request.param)
        yield from _app_context(request.param, clean_db=False, init_db=False, drop_db=False)
    except AttributeError:
        raise RuntimeError("Parametrized fixture. "
                           "You need to provide app settings as dict type in the request param")


@pytest.fixture
def clean_db(app_context):
    _clean_db()


@pytest.fixture
def app_client(app_context):
    with app_context.app.test_client() as client:
        yield client


@pytest.fixture
def session_transaction(app_client):
    with app_client.session_transaction() as s:
        yield s


@pytest.fixture
def request_context(app_context, request):
    request_path = request.param if hasattr(request, "param") else '/'
    with app_context.app.test_request_context(request_path) as r:
        yield r


@pytest.fixture
def provider_apikey(app_context, request):
    try:
        # the API_KEYS property is always set via the app_settings fixture
        return app_context.app.config.get("API_KEYS") \
            .get(f"{request.param}_API_KEY".upper(), None)
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to provide a provider type as request param")


def seek_user_session(application, security):
    with requests.session() as session:
        wfhub_url = application.config["SEEK_API_BASE_URL"]
        wfhub_people_details = os.path.join(wfhub_url, 'people/current')
        logger.debug("URL: %s", wfhub_people_details)
        api_key = application.config["API_KEYS"]["SEEK_API_KEY"]
        headers = get_headers({'Authorization': f'Bearer {api_key}'})
        user_info_r = session.get(wfhub_people_details, headers=headers)
        assert user_info_r.status_code == 200, "Unable to get user info from Workflow Hub: code {}" \
            .format(user_info_r.status_code)
        wfhub_user_info = user_info_r.json()['data']
        logger.debug("WfHub user info: %r", wfhub_user_info)
        if security == SecurityType.API_KEY.value:
            application.config["SEEK_API_KEY"] = api_key
            user = User(username=wfhub_user_info['id'])
            user.save()
            return user, session
        elif security == SecurityType.OAUTH2.value:
            application.config.pop("SEEK_API_KEY", None)
            login_r = session.get(f"{application.config.get('BASE_URL')}/oauth2/login/seek")
            assert login_r.status_code == 200, "Login Error: status code {} !!!".format(login_r.status_code)
            return User.find_by_username(wfhub_user_info['id']), session


def _get_user_session(application, provider, security):
    """ Parametric fixture: available params are {seek}"""
    try:
        logger.debug("SECURITY: %r", security)
        user_loader = globals()[f"{provider}_user_session".lower()]
        user, session = user_loader(application, security)
        logger.debug("USER SESSION: %r", session)
        return user, session
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError("Authorization provider {} is not supported".format(provider))
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


@pytest.fixture(params=RegistryType.values())
def registry_type(request):
    return request.param


@pytest.fixture(params=SecurityType.values())
def security_type(request):
    return request.param


@pytest.fixture
def user(app_client, registry_type, security_type):
    """ Parametric fixture: available params are {seek}"""
    try:
        user, session = _get_user_session(app_client.application, registry_type, security_type)
        g.user = user  # store the user on g to allow the auto login
        return user
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError("Authorization provider {} is not supported".format(registry_type))
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


@pytest.fixture
def registry_user(app_client, request):
    """ Parametric fixture: available params are {seek}"""
    try:
        registry = request.param[0]
        security = request.param[1]
        user, session = _get_user_session(app_client.application, registry, security)
        g.user = user  # store the user on g to allow the auto login
        return user
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError("Authorization provider {} is not supported".format(registry_type))
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


def seek_workflow(application, provider, security):
    # This function assumes that at least one workflow is already loaded on WfHub
    # and accessible through the API Key user
    with requests.session() as s:
        wfhub_url = application.config["SEEK_API_BASE_URL"]
        wfhub_workflows_url = os.path.join(wfhub_url, 'workflows')
        api_key = application.config["API_KEYS"]["SEEK_API_KEY"]
        headers = get_headers({'Authorization': f'Bearer {api_key}'})
        wr = s.get(wfhub_workflows_url, headers=headers)
        if wr.status_code != 200:
            raise RuntimeError(f"ERROR {wr.status_code}: Unable to get workflows")
        # pick the first and details
        workflows = wr.json()["data"]
        logger.debug("Seek workflows: %r", workflows)
        wf_r = s.get(f"{wfhub_workflows_url}/{workflows[0]['id']}", headers=headers)
        if wf_r.status_code != 200:
            raise RuntimeError(f"ERROR {wf_r.status_code}: Unable to get workflow details")
        logger.debug("workflow details: %r", wf_r)
        workflow = wf_r.json()["data"]
        return {
            'uuid': workflow['meta']['uuid'],
            'version': str(workflow["attributes"]["versions"][0]['version']),  # pick the first version
            'name': workflow["attributes"]["title"],
            'roc_link': f'{workflow["attributes"]["content_blobs"][0]["link"]}/download'
        }


@pytest.fixture
def workflow(app_context, registry_type, security_type):
    """ Parametric fixture: available params are {wfhub}"""
    try:
        wf_loader = globals()[f"{registry_type}_workflow".lower()]
        return wf_loader(app_context.app, registry_type, security_type)
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError("Authorization provider {} is not supported".format(registry_type))
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


@pytest.fixture
def test_suite_metadata():
    with open(os.path.join(base_path, "test-suite-definition.json")) as df:
        return json.load(df)


@pytest.fixture
def suite_uuid():
    return str(TestSuite.all()[0].uuid)
