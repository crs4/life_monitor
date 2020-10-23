import os
import requests
import pprint
import warnings
import logging
from lifemonitor import config
from urllib.parse import urljoin
from lifemonitor.app import create_app
from lifemonitor.api.models import WorkflowRegistry

#
pp = pprint.PrettyPrinter(indent=2).pprint

#
lifemonitor_root = os.path.abspath('../')

# disable warnings
warnings.filterwarnings('ignore')

# LifeMonitor URLs
lm_base_url = "https://localhost:8443"
lm_token_url = f"{lm_base_url}/oauth2/token"

# Set LifeMonitor Credentials
CLIENT_ID = "ehukdECYQNmXxgJslBqNaJ2J4lPtoX_GADmLNztE8MI"
CLIENT_SECRET = "DuKar5qYdteOrB-eTN4F5qYSp-YrgvAJbz1yMyoVGrk"

# HTTP settings to connect to LifeMonitor
s = requests.session()  # actually not mandatory, but just to share some settings among requests

# if you use self-signed certificates,
# you have to uncomment the line below to disable SSL verification
s.verify = False

# common header settings
s.headers.update({})

# load settings
cfg = config.get_config_by_name('production')
settings = config.load_settings(cfg)
settings['DEBUG'] = False
settings['LOG_LEVEL'] = 'CRITICAL'
settings['POSTGRESQL_HOST'] = '0.0.0.0'
settings['POSTGRESQL_PORT'] = '32780'

# create an app instance
app = create_app(settings=settings)

#
logger = logging.getLogger(__file__)


wfhub_url = "https://seek:3000"
wfhub_password = "workflowhub"

seek_users = {
    'user1': {
        'id': "2",
        'username': 'user1'
    },
    'user2': {
        'id': "3",
        'username': 'user2'
    }
}


def get_registry():
    with app.app_context():
        logger.debug(WorkflowRegistry.all())
        return WorkflowRegistry.find_by_name('seek')


def get_client_credentials():
    return CLIENT_ID, CLIENT_SECRET


def fetch_registry_token(registry):
    # Get an authorization token from LifeMonitor
    with app.app_context():
        if isinstance(registry, str):
            registry = WorkflowRegistry.find_by_name(registry)
        credentials = registry.client_credentials
        token_response = s.post(
            lm_token_url,
            data={
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "grant_type": "client_credentials",
                "scope": "read write"
            }, allow_redirects=True, verify=False)
        assert token_response.status_code == 200, "OAuth2 Error"
        token = token_response.json()
        return token


def get_seek_user_info(username):
    assert username in seek_users.keys(), "Unknown user"
    wfhub_username = username
    seek_session = requests.session()
    seek_session.verify = False
    seek_session.headers.update({
        "Content-type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
        "Accept-Charset": "ISO-8859-1"
    })
    # log the user on WfHub
    seek_session.auth = requests.auth.HTTPBasicAuth(wfhub_username, wfhub_password)
    print(urljoin(wfhub_url, "people", seek_users[username]['id']))
    print(seek_users)
    response = seek_session.get(f"{wfhub_url}/people/{seek_users[username]['id']}")
    return response.json()["data"]


def get_seek_user_workflows(username):
    assert username in seek_users.keys(), "Unknown user"
    wfhub_username = username
    seek_session = requests.session()
    seek_session.verify = False
    seek_session.headers.update({
        "Content-type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
        "Accept-Charset": "ISO-8859-1"
    })
    # log the user on WfHub
    seek_session.auth = requests.auth.HTTPBasicAuth(wfhub_username, wfhub_password)
    workflows_response = seek_session.get(f"{wfhub_url}/workflows")
    workflows = workflows_response.json()["data"]
    return workflows


def get_seek_user_workflow(username, wf_id):
    assert username in seek_users.keys(), "Unknown user"
    wfhub_username = username
    seek_session = requests.session()
    seek_session.verify = False
    seek_session.headers.update({
        "Content-type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
        "Accept-Charset": "ISO-8859-1"
    })
    # log the user on WfHub
    seek_session.auth = requests.auth.HTTPBasicAuth(wfhub_username, wfhub_password)
    response = seek_session.get(f"{wfhub_url}/workflows/{wf_id}")
    assert response.status_code == 200, f"Error: {response.content}"
    return response.json()["data"]
