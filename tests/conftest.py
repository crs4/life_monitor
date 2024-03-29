# Copyright (c) 2020-2024 CRS4
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

import base64
import logging
import os
import pathlib
import random
import re
import shutil
import string
import tempfile
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import lifemonitor.db as lm_db
import pytest
from lifemonitor import auth
from lifemonitor.api.models import (TestingService,
                                    TestingServiceTokenManager,
                                    TestSuite,
                                    User)
from lifemonitor.api.models.repositories import (GithubWorkflowRepository,
                                                 LocalGitWorkflowRepository,
                                                 LocalWorkflowRepository,
                                                 Base64WorkflowRepository,
                                                 ZippedWorkflowRepository)
from lifemonitor.api.services import LifeMonitor
from lifemonitor.cache import cache, clear_cache
from lifemonitor.utils import ClassManager, extract_zip

from tests.utils import register_workflow

from . import conftest_helpers as helpers
from .conftest_types import ClientAuthenticationMethod, RegistryType
from .rate_limit_exceeded import RateLimitExceededTestingService

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
def headers():
    return helpers.get_headers()


@pytest.fixture(scope='session')
def test_repo_collection_path() -> Path:
    return Path(__file__).parent / 'config' / 'data' / 'repos'


@pytest.fixture(scope='session')
def test_crate_collection_path() -> Path:
    return Path(__file__).parent / 'config' / 'data' / 'crates'


@pytest.fixture
def lm() -> LifeMonitor:
    return LifeMonitor.get_instance()


@pytest.fixture
def service_registry() -> ClassManager:
    registry = TestingService.service_type_registry
    registry._load_concrete_types()
    return registry


@pytest.fixture
def token_manager() -> TestingServiceTokenManager:
    return TestingServiceTokenManager.get_instance()


@pytest.fixture
def no_cache(app_context):
    app_context.app.config['CACHE_TYPE'] = "flask_caching.backends.nullcache.NullCache"
    assert app_context.app.config.get('CACHE_TYPE') == "flask_caching.backends.nullcache.NullCache"
    cache.init_app(app_context.app)
    assert cache.cache_enabled is False, "Cache should be disabled"
    return cache


@pytest.fixture
def redis_cache(app_context):
    app_context.app.config['CACHE_TYPE'] = "flask_caching.backends.rediscache.RedisCache"
    assert app_context.app.config.get('CACHE_TYPE') == "flask_caching.backends.rediscache.RedisCache"
    cache.init_app(app_context.app)
    assert cache.cache_enabled is True, "Cache should not be disabled"
    cache.clear()
    return cache


@pytest.fixture(autouse=True)
def initialize(app_settings, request_context, service_registry: ClassManager):
    service_registry.remove_class("unknown")
    helpers.clean_db()
    clear_cache(client_scope=False)
    helpers.init_db(app_settings)
    helpers.disable_auto_login()
    auth.logout_user()
    auth.logout_registry()
    os.environ.pop("FLASK_APP_INSTANCE_PATH", None)
    os.environ.pop("FLASK_APP_CONFIG_FILE", None)


def _get_app_settings(include_env=True, extra=None):
    settings = env_settings.copy() if include_env else {}
    settings.update(helpers.load_settings(app_settings_path))
    settings.update(helpers.load_settings(tests_settings_path))
    if extra:
        settings.update(extra)
    # remove API KEYS
    api_keys = {}
    pattern = re.compile("((\\w+)_API_KEY(_\\w+)?)")
    for k, v in settings.copy().items():
        m = pattern.match(k)
        # logger.debug(m)
        if m:
            settings.pop(k)
            api_keys[k] = v
    settings["API_KEYS"] = api_keys
    return settings


@pytest.fixture(scope="session")
def app_settings(request):
    if hasattr(request, 'param'):
        logger.debug("App settings param: %r", request.param)
        if isinstance(request.param, Iterable):
            return _get_app_settings(*request.param)
        else:
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
def admin_user(app_settings):
    return helpers.get_admin_user(app_settings)


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


@pytest.fixture(params=helpers.get_valid_workflows())
def valid_workflow(request):
    return request.param


@pytest.fixture
def random_valid_workflow():
    return helpers.get_valid_workflow()


@pytest.fixture
def rocrate_archive_path():
    return os.getcwd() + '/tests/config/data/ro-crate-galaxy-sortchangecase.crate.zip'


@pytest.fixture
def rocrate_repository_path(rocrate_archive_path):
    tmp_path = extract_zip(archive_path=rocrate_archive_path)
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def generic_workflow(app_client):
    return {
        'uuid': str(uuid.uuid4()),
        'version': '1',
        'roc_link': "http://webserver:5000/download?file=ro-crate-galaxy-sortchangecase.crate.zip",
        'name': 'sort-and-change-case',
        'testing_service_type': 'jenkins',
        'authorization': app_client.application.config['WEB_SERVER_AUTH_TOKEN']
    }


@pytest.fixture
def encoded_rocrate_workflow(app_client):
    with open('tests/config/data/rocrate.base64') as f:
        data = f.read()
    return {
        'uuid': str(uuid.uuid4()),
        'version': '1',
        'rocrate': data,
        'name': 'sort-and-change-case',
        'testing_service_type': 'jenkins',
        'authorization': app_client.application.config['WEB_SERVER_AUTH_TOKEN']
    }


@pytest.fixture
def workflow_no_name(app_client):
    return {
        'uuid': str(uuid.uuid4()),
        'version': '1',
        'roc_link': "http://webserver:5000/download?file=ro-crate-galaxy-sortchangecase-no-name.crate.zip",
        'name': 'Galaxy workflow from Generic Link (no name)',
        'testing_service_type': 'jenkins',
        'authorization': app_client.application.config['WEB_SERVER_AUTH_TOKEN']
    }


@pytest.fixture
def rate_limit_exceeded_workflow(app_client, service_registry: ClassManager, user1):
    service_registry.add_class("unknown", RateLimitExceededTestingService)
    wfdata = {
        'uuid': str(uuid.uuid4()),
        'version': '1',
        'roc_link': "http://webserver:5000/download?file=ro-crate-galaxy-sortchangecase-rate-limit-exceeded.crate.zip",
        'name': 'Galaxy workflow (rate limit exceeded)',
        'testing_service_type': 'unknown',
        'authorization': app_client.application.config['WEB_SERVER_AUTH_TOKEN']
    }
    wfdata, workflow_version = register_workflow(user1, wfdata)
    logger.info(wfdata)
    logger.info(workflow_version)
    assert workflow_version, "Workflows not found"
    workflow = workflow_version.workflow
    workflow.public = True
    workflow.save()
    assert workflow.public is True, "Workflow should be public"
    return workflow


@pytest.fixture
def unmanaged_test_instance(app_client):
    return {
        "managed": False,
        "name": "test_instance",
        "service": {
            "type": "travis",
            "url": "https://travis-ci.org/"
        },
        "resource": "github/crs4/pydoop"
    }


@pytest.fixture
def managed_test_instance(app_client):
    return {
        "managed": True,
        "name": "test_instance",
        "service": {
            "type": "travis",
            "url": "https://travis-ci.org/"
        },
        "resource": "github/crs4/pydoop"
    }


@pytest.fixture
def test_suite_metadata():
    return {
        'roc_suite': '#test1',
        'name': 'test1',
        'instances': [
                {
                    'roc_instance': '#test1_1',
                    'name': 'test1_1',
                    'resource': 'job/test/',
                    'service': {
                        'type': 'jenkins',
                        'url': 'http://jenkins:8080/'}
                }
        ],
        'definition': {
            'test_engine': {
                'type': 'planemo',
                'version': '>=0.70'
            },
            'path': 'test1/sort-and-change-case-test.yml'
        }
    }


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
def fake_registry(app_settings, admin_user, random_string, fake_uri):
    return LifeMonitor.get_instance().add_workflow_registry(
        "seek", random_string, random_string, random_string, api_base_url=fake_uri)


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


# pytest's default tmpdir returns a py.path object
@pytest.fixture
def tmpdir(tmpdir):
    return pathlib.Path(tmpdir)


@pytest.fixture
def repository() -> Generator[LocalWorkflowRepository, None, None]:
    crate_path = Path(__file__).parent / 'crates' / 'ro-crate-galaxy-sortchangecase.crate.zip'
    repo = ZippedWorkflowRepository(crate_path)
    try:
        yield repo
    finally:
        repo.cleanup()


@pytest.fixture
def github_repository() -> GithubWorkflowRepository:
    repo = GithubWorkflowRepository('iwc-workflows/gromacs-mmgbsa', ref="HEAD")
    logger.debug("Github workflow repository: %r", repo)
    return repo


@pytest.fixture
def simple_local_wf_repo(test_repo_collection_path: Path) -> Generator[LocalGitWorkflowRepository, None, None]:
    """
    On-disk git repository with a dummy Galaxy workflow.  Should follow best practices.
    """
    source_repo_path = test_repo_collection_path / 'test-galaxy-wf-repo'

    # make a temporary copy of the source repository so that tests can freely
    # modify it.
    with tempfile.TemporaryDirectory(prefix=f"tmp-{source_repo_path.name}") as tmpdir:
        tmp_repo_path = shutil.copytree(source_repo_path,
                                        Path(tmpdir) / source_repo_path.name,
                                        symlinks=True)
        logger.debug("Staging '%s' repository to temporary path '%s'", source_repo_path, tmp_repo_path)
        # move the .dot-git directory to .git, so that the repository works as a normal git repository
        (tmp_repo_path / '.dot-git').rename(tmp_repo_path / '.git')
        repo = LocalGitWorkflowRepository(str(tmp_repo_path))
        yield repo


@pytest.fixture
def simple_zip_wf_repo(simple_local_wf_repo) -> Generator[ZippedWorkflowRepository, None, None]:
    from rocrate.rocrate import ROCrate
    with tempfile.NamedTemporaryFile(suffix='.zip') as tmpzip:
        crate = ROCrate(simple_local_wf_repo.local_path)
        crate.write_zip(tmpzip.name)
        tmpzip.seek(0)
        repo = ZippedWorkflowRepository(tmpzip.name)
        yield repo


@pytest.fixture
def simple_base64_wf_repo(simple_zip_wf_repo: ZippedWorkflowRepository) -> Generator[Base64WorkflowRepository, None, None]:
    base64_encoded_repo = None
    with open(simple_zip_wf_repo.archive_path, mode="rb") as zip_file:
        contents = zip_file.read()
        base64_encoded_repo = base64.b64encode(contents)
    if not base64_encoded_repo:
        raise RuntimeError("Could not base64 encode the repository")
    return Base64WorkflowRepository(base64_encoded_repo)
