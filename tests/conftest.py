import re
import os
import json
import uuid
import random
import pytest
import string
import logging
from lifemonitor import auth
import lifemonitor.db as lm_db
from lifemonitor.api.models import User, TestSuite
from . import conftest_helpers as helpers
from .conftest_types import ClientAuthenticationMethod, RegistryType
from unittest.mock import MagicMock

# set the module level logger
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


@pytest.fixture
def current_path():
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def headers():
    return helpers.get_headers()


@pytest.fixture(autouse=True)
def initialize(app_settings, request_context):
    helpers.clean_db()
    helpers.init_db(app_settings)
    auth.logout_user()
    auth.logout_registry()


def _get_app_settings(include_env=True):
    settings = env_settings.copy() if include_env else {}
    settings.update(helpers.load_settings(app_settings_path))
    settings.update(helpers.load_settings(tests_settings_path))
    # remove API KEYS
    api_keys = {}
    pattern = re.compile("((\\w+)_API_KEY(_\\w+)?)")
    for k, v in settings.copy().items():
        m = pattern.match(k)
        logger.debug(m)
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


@pytest.fixture
def admin_user():
    return helpers.get_admin_user()


def _check_settings(settings_param):
    app_conn_params = lm_db.db_connection_params(_get_app_settings())
    request_conn_params = lm_db.db_connection_params(settings_param)
    logger.debug("Connection parameters: %r", request_conn_params)
    if (app_conn_params["host"], app_conn_params["port"], app_conn_params["dbname"]) \
            == (request_conn_params["host"], request_conn_params["port"], request_conn_params["dbname"]):
        raise RuntimeError("You should use another DATABASE with this app_context")
    return settings_param


@pytest.fixture(params=RegistryType.values())
def provider_type(request):
    return request.param


@pytest.fixture(params=ClientAuthenticationMethod.values())
def client_auth_method(request):
    return request.param


@pytest.fixture(scope="session")
def app_context(app_settings):
    yield from helpers.app_context(app_settings, init_db=True, clean_db=False, drop_db=False)


@pytest.fixture()
def user1(app_context, provider_type, client_credentials_registry, request):
    register_workflows = False
    if hasattr(request, 'param') and request.param is True:
        register_workflows = True
    yield from helpers.user(app_context, provider_type,
                            _user_index=1, _register_workflows=register_workflows)


@pytest.fixture()
def user1_auth(app_context, user1, client_auth_method, client_credentials_registry):
    return helpers.get_user_auth_headers(client_auth_method, app_context.app,
                                         client_credentials_registry,
                                         user1['user'], user1['session'])


@pytest.fixture()
def user2(app_context, provider_type, client_credentials_registry, request):
    register_workflows = False
    if hasattr(request, 'param') and request.param is True:
        register_workflows = True
    yield from helpers.user(app_context, provider_type,
                            _user_index=2, _register_workflows=register_workflows)


@pytest.fixture()
def user2_auth(app_context, user2, client_auth_method, client_credentials_registry):
    return helpers.get_user_auth_headers(client_auth_method, app_context.app,
                                         client_credentials_registry,
                                         user2['user'], user2['session'])


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
def fake_app_context(request):
    try:
        yield from helpers.app_context(request.param, clean_db=False, init_db=False, drop_db=False)
    except AttributeError:
        raise RuntimeError("Parametrized fixture. "
                           "You need to provide app settings as dict type in the request param")


@pytest.fixture
def cli_runner(app_context):
    return app_context.app.test_cli_runner()


@pytest.fixture
def random_workflow_id():
    return {
        'uuid': str(uuid.uuid4()),
        'version': "{}.{}.{}".format(random.randint(1, 10), random.randint(1, 10), random.randint(1, 10))
    }


@pytest.fixture
def random_valid_uuid():
    return str(uuid.uuid4())


@pytest.fixture
def test_suite_metadata():
    with open(os.path.join(base_path, "data/test-metadata.json")) as df:
        return json.load(df)


@pytest.fixture
def invalid_test_suite_metadata():
    return {}


@pytest.fixture
def suite_uuid():
    return str(TestSuite.all()[0].uuid)


@pytest.fixture
def client_credentials_registry(app_settings, app_context, admin_user):
    return helpers.get_registry(app_settings, admin_user)


@pytest.fixture
def random_string(length=10):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


@pytest.fixture
def fake_uri():
    return "https://myservice.org"


@pytest.fixture
def fake_callback_uri():
    return helpers._fake_callback_uri()


@pytest.fixture
def mock_user():
    u = User()
    u.username = "lifemonitor_user"
    auth.login_user(u)
    yield u
    auth.logout_user()


@pytest.fixture
def mock_registry():
    r = MagicMock()
    r.name = "WorkflowRegistry"
    auth.login_registry(r)
    yield r
    auth.logout_registry()
