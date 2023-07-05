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
import random
import re
from urllib.parse import urlparse

import dotenv
import lifemonitor.db as lm_db
import prometheus_client
import requests
from flask import g
from flask_login import login_user, logout_user
from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api.services import LifeMonitor
from lifemonitor.app import create_app, initialize_app
from lifemonitor.auth.models import User
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.auth.services import generate_new_api_key
from lifemonitor.utils import OpenApiSpecs
from tests import utils

from .conftest_types import ClientAuthenticationMethod

# set the module level logger
logger = logging.getLogger(__name__)


def get_headers(extra_data=None):
    data = {"Content-type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
            "Accept-Charset": "ISO-8859-1"}
    if extra_data:
        data.update(extra_data)
    return data


def load_settings(filename):
    logger.debug("Loading settings file: %r", filename)
    if os.path.exists(filename):
        return dotenv.dotenv_values(dotenv_path=filename)
    return {}


def get_admin_user(_app_settings):
    admin = User.find_by_username("admin")
    if admin is None:
        admin = User("admin")
        admin.password = _app_settings['LIFEMONITOR_ADMIN_PASSWORD']
        admin.id = 1
        lm_db.db.session.add(admin)
        lm_db.db.session.commit()
    return admin


def init_db(_app_settings):
    admin = get_admin_user(_app_settings)
    create_client_credentials_registry(_app_settings, admin)


def clean_db():
    lm_db.db.session.rollback()
    for table in reversed(lm_db.db.metadata.sorted_tables):
        lm_db.db.session.execute(table.delete())
    lm_db.db.session.commit()


def process_auto_login():
    enabled = "auto_login" in g and g.auto_login is True
    logger.info("AutoLogin enabled: %r", enabled)
    if enabled:
        if "user" in g:
            logger.info("Login user: %r", g.user)
            login_user(g.user)


def enable_auto_login(user=None):
    g.auto_login = True
    g.user = user


def disable_auto_login():
    g.pop("auto_login", False)
    g.pop("user", False)


def app_context(request_settings,
                init_db=True, clean_db=True, drop_db=False):
    try:
        os.environ.pop("FLASK_APP_CONFIG_FILE", None)
        if init_db:
            lm_db.create_db(settings=request_settings)
        flask_app = create_app(env="testing", settings=request_settings, init_app=False)
        flask_app.before_request(process_auto_login)
        with flask_app.app_context() as ctx:
            logger.info("Starting application")
            initialize_app(flask_app, ctx, prom_registry=prometheus_client.CollectorRegistry())
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
                lm_db.drop_db(settings=request_settings)
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(e)


def get_travis_token():
    return os.environ.get('TRAVIS_TESTING_SERVICE_TOKEN', False)


def get_github_token():
    return os.environ.get('GITHUB_TESTING_SERVICE_TOKEN', False)


def get_valid_workflows():
    wfs = ['sort-and-change-case']
    if get_travis_token():
        wfs.append('sort-and-change-case-travis')
    return wfs


def get_valid_workflow(name=None):
    wfs = get_valid_workflows()
    return wfs[name] if name else random.choice(wfs)


def get_user_workflows(_application, _registry_type, _public=True, _to_skip=None, index_user=0):
    """ Parametric fixture: available params are {wfhub}"""
    try:
        wf_loader = globals()[f"{_registry_type.value}_workflow".lower()]
        return wf_loader(_application, _registry_type, _public, _to_skip, index_user)
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError("Authorization provider {} is not supported".format(_registry_type))
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


def seek_workflow(application, provider, public, to_skip=None, index_user=0):
    # This function assumes that at least one workflow is already loaded on WfHub
    # and accessible through the API Key user
    with requests.session() as s:
        wfhub_url = application.config["SEEK_API_BASE_URL"]
        wfhub_workflows_url = os.path.join(wfhub_url, 'workflows')
        if index_user > 0:
            api_key = application.config["API_KEYS"][f"SEEK_API_KEY_{index_user}"]
        else:
            api_key = application.config["API_KEYS"]["SEEK_API_KEY"]
        headers = get_headers({'Authorization': f'Bearer {api_key}'})
        wr = s.get(wfhub_workflows_url, headers=headers)
        if wr.status_code != 200:
            raise RuntimeError(f"ERROR {wr.status_code}: Unable to get workflows")
        # pick the first and details
        workflows = wr.json()["data"]
        logger.debug("Seek workflows: %r", workflows)
        workflow = None
        result = []
        for w in workflows:
            try:
                wf_id = w['id']
                if to_skip and wf_id in to_skip:
                    continue
                wf_r = s.get(f"{wfhub_workflows_url}/{wf_id}", headers=headers)
                if wf_r.status_code == 200:
                    workflow = wf_r.json()["data"]
                    logger.debug("The workflow: %r", workflow)
                    policy = workflow['attributes'].get('policy', None)
                    is_public = policy and policy.get("access", None) != 'no_access'
                    result.append({
                        'public': is_public,
                        'external_id': workflow['id'],
                        'uuid': workflow['meta']['uuid'],
                        'version': str(workflow["attributes"]["versions"][0]['version']),  # pick the first version
                        'name': workflow["attributes"]["title"],
                        'roc_link': f"{wfhub_workflows_url}/{workflow['id']}/ro_crate?version={str(workflow['attributes']['versions'][0]['version'])}",
                        'registry_name': 'seek',
                        'registry_uri': application.config["SEEK_API_BASE_URL"],
                        'valid': re.search("invalid", workflow["attributes"]["title"]),
                        # TODO: replace the naive identification of service type
                        # (anyway it is compatible with the current test data)
                        'testing_service_type': 'travis' if re.search('travis', workflow["attributes"]["title"], re.IGNORECASE) else 'jenkins'
                    })
            except Exception as e:
                logger.exception(e)
        if len(result) == 0:
            raise RuntimeError("Unable to get workflow details")
        return result


def seek_user_session(application, index=None):
    with requests.session() as session:
        wfhub_url = application.config["SEEK_API_BASE_URL"]
        wfhub_people_details = os.path.join(wfhub_url, 'people/current')
        logger.debug("URL: %s", wfhub_people_details)
        api_key = application.config["API_KEYS"]["SEEK_API_KEY" if not index else f"SEEK_API_KEY_{index}"]
        headers = get_headers({'Authorization': f'Bearer {api_key}'})
        user_info_r = session.get(wfhub_people_details, headers=headers)
        assert user_info_r.status_code == 200, "Unable to get user info from Workflow Hub: code {}" \
            .format(user_info_r.status_code)
        wfhub_user_info = user_info_r.json()['data']
        logger.debug("WfHub user info: %r", wfhub_user_info)
        application.config.pop("SEEK_API_KEY", None)
        retries = 2
        while retries > 0:
            try:
                login_r = session.get(f"https://{application.config.get('SERVER_NAME')}/oauth2/login/seek")
                logger.debug(login_r.content)
                if login_r.status_code == 200:
                    break
            finally:
                retries -= 1
        assert login_r.status_code == 200, "Login Error: status code {} !!!".format(login_r.status_code)
        return OAuthIdentity.find_by_provider_user_id(wfhub_user_info['id'], 'seek').user, session, wfhub_user_info


def get_user_session(application, provider, index=None):
    """ Parametric fixture: available params are {seek}"""
    try:
        user_loader = globals()[f"{provider.value}_user_session".lower()]
        user, session, user_info = user_loader(application, index)
        assert user is not None, "Invalid USER NONE"
        logger.debug("USER: %r", user)
        logger.debug("USER SESSION: %r", session)
        return user, session, user_info
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError("Authorization provider {} is not supported".format(provider))
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


def user(_app_context, _provider_type, _user_index=1, _register_workflows=False):
    session = None
    try:
        user, session, user_info = get_user_session(_app_context.app,
                                                    _provider_type, index=_user_index)
        # load a workflow set
        workflows = get_user_workflows(_app_context.app, _provider_type,
                                       _public=False, index_user=_user_index)
        # user object
        user_obj = {
            "user": user,
            "user_info": user_info,
            "session": session,
            "workflows": workflows
        }
        if _register_workflows:
            utils.register_workflows(user_obj)
        try:
            yield user_obj
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        finally:
            if user and not user.is_anonymous:
                try:
                    logout_user()
                except Exception:
                    pass
    except KeyError as e:
        logger.exception(e)
        raise RuntimeError(f"Authorization provider {_provider_type} is not supported")
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")
    finally:
        if session:
            session.close()


def _fake_callback_uri():
    return "http://fake_client_uri"


def registry_scopes():
    return " ".join(OpenApiSpecs.get_instance().registry_client_scopes.keys())


def registry_code_flow_scopes():
    return " ".join(OpenApiSpecs.get_instance().registry_code_flow_scopes.keys())


def auth_code_flow_scopes():
    return " ".join(OpenApiSpecs.get_instance().authorization_code_scopes.keys())


def create_authorization_code_flow_client(_admin_user, _is_registry=False):
    from lifemonitor.auth.oauth2.server import server
    client = server.create_client(_admin_user,
                                  "test_code_flow", _fake_callback_uri(),
                                  ['authorization_code', 'token', 'id_token'],
                                  ["code", "token"], registry_code_flow_scopes() if _is_registry else auth_code_flow_scopes(),
                                  _fake_callback_uri(), "client_secret_post")
    logger.debug("Registered client: %r", client)
    return client
    # client.delete()


def create_authorization_code_access_token(_application,
                                           _authorization_code_flow_client,
                                           _user=None, _session=None, _is_registry=False):
    """ Parametric fixture: available params are {seek}"""
    try:
        client = _authorization_code_flow_client
        application = _application
        logger.debug(_user)
        logger.debug(_session)
        user, session = _user, _session
        g.user = None  # store the user on g to allow the auto login; None to avoid the login
        client_id = client.client_id
        client_secret = client.client_info["client_secret"]
        authorization_url = f"https://{application.config['SERVER_NAME']}/oauth2/authorize"
        token_url = f"https://{application.config['SERVER_NAME']}/oauth2/token"
        # base_url = application.config[f"{registry_type}_API_BASE_URL".upper()]

        session.auth = None
        auth_response = session.get(authorization_url, params={
            "client_id": client_id,
            "grant_type": "authorization_code",
            "response_type": "code",
            "confirm": "true",
            "state": "5ca75bd30",
            "redirect_uri": _fake_callback_uri(),
            "scope": registry_code_flow_scopes() if _is_registry else auth_code_flow_scopes()
        }, data={"client_secret": client_secret}, allow_redirects=False)
        logger.debug("The Response: %r", auth_response.content)
        assert auth_response.status_code == 302, "No redirection with auth code"
        # get the auth code from response header
        location = urlparse(auth_response.headers.get("Location"))
        query_params = location.query.split('&')
        code = query_params[0].replace("code=", "")
        logger.debug("Authorization code: %r", code)

        # remove auth basic
        session.auth = None
        session.headers.update({"Content-type": "application/x-www-form-urlencoded"})
        token_response = session.post(token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _fake_callback_uri(),
            "client_id": client_id,
            "client_secret": client_secret
        })
        assert token_response.status_code == 200, f"Invalid token response: {token_response.description}"
        logger.debug("TOKEN response: %r" % token_response)
        token = token_response.json()
        token["user"] = user
        return token
    except AttributeError as e:
        logger.exception(e)
        raise RuntimeError("Parametrized fixture. "
                           "You need to pass a provider type as request param")


def create_client_credentials_access_token(application, credentials):
    token_url = f"https://{application.config.get('SERVER_NAME')}/oauth2/token"
    response = requests.post(token_url, data={
        'grant_type': 'client_credentials',
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scope': registry_scopes()
    })
    logger.debug("TOKEN RESPONSE: %r", response.content)
    assert response.status_code == 200, "Error"
    return response.json()


def create_app_client_headers(_client_auth_method, _application,
                              _client_credentials_registry,
                              _app_user, _app_user_session=None):
    registry = _client_credentials_registry
    access_token = api_key = None
    if _client_auth_method == ClientAuthenticationMethod.AUTHORIZATION_CODE:
        _client = create_authorization_code_flow_client(_app_user, _is_registry=False)
        access_token = create_authorization_code_access_token(
            _application, _client,
            _user=_app_user, _session=_app_user_session, _is_registry=False)["access_token"]
    elif _client_auth_method == ClientAuthenticationMethod.REGISTRY_CODE_FLOW:
        _client = _client_credentials_registry.client_credentials
        access_token = create_authorization_code_access_token(
            _application, _client,
            _user=_app_user, _session=_app_user_session, _is_registry=True)["access_token"]
    elif _client_auth_method == ClientAuthenticationMethod.CLIENT_CREDENTIALS:
        _client = None
        access_token = create_client_credentials_access_token(
            _application, registry.client_credentials)["access_token"]
    elif _client_auth_method == ClientAuthenticationMethod.API_KEY:
        api_key = generate_new_api_key(_app_user, " ".join(OpenApiSpecs.get_instance().apikey_scopes.keys())).key
    try:
        headers = None
        if access_token:
            headers = get_headers({'Authorization': f'Bearer {access_token}'})
        elif api_key:
            headers = get_headers({'ApiKey': f'{api_key}'})
        else:
            headers = get_headers()
        return headers
    except KeyError as e:
        logger.exception(e)
        return get_headers()


def get_user_auth_headers(_auth_method, _application, _registry, _user, _session):
    return create_app_client_headers(_auth_method,
                                     _application, _registry,
                                     _user, _session)


def create_client_credentials_registry(_app_settings, _admin_user, name='seek'):
    lm = LifeMonitor.get_instance()
    try:
        return lm.get_workflow_registry_by_name(name)
    except Exception:
        return LifeMonitor.get_instance().add_workflow_registry(
            "seek", name,
            _app_settings.get('SEEK_CLIENT_ID'),
            _app_settings.get('SEEK_CLIENT_SECRET'),
            api_base_url=_app_settings.get('SEEK_API_BASE_URL'),
            redirect_uris=_fake_callback_uri())


def get_registry(_app_settings, _admin_user) -> WorkflowRegistry:
    registry = WorkflowRegistry.find_by_client_name("seek")
    if registry is None:
        registry = create_client_credentials_registry(_app_settings, _admin_user)
    return registry


def get_random_slice_indexes(num_of_slices, max_value):
    slices = []
    if max_value <= 0:
        logger.warning("The max value should be greater than 0")
    else:
        while len(slices) < num_of_slices:
            limit = random.randint(0, max_value)
            offset = random.randint(0, limit - 1)
            slices.append((offset, limit))
    return slices
