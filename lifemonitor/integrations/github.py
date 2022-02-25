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

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
import requests
from flask import Blueprint, Flask, request
from lifemonitor.api.models import TestInstance
from lifemonitor.cache import IllegalStateException, cache

import github

# Config a module level logger
logger = logging.getLogger(__name__)


def __lifemonitor_service__():
    from lifemonitor.api.services import LifeMonitor
    return LifeMonitor.get_instance()


class GithubAppHelper():

    app_identifier = None
    _signing_key_path = None
    _signing_secret = None
    token_expiration = timedelta(minutes=10)
    github_api_url = 'https://api.github.com'

    @classmethod
    def init(cls, app_identifier: str, signing_key_path: str, signing_secret: str):
        cls.app_identifier = app_identifier
        cls._signing_key_path = signing_key_path
        cls._signing_secret = signing_secret

    @classmethod
    def check_initialization(cls) -> bool:
        if not cls.app_identifier or not cls.signing_key_path or not cls.signing_secret:
            logger.warning("Github App integration not properly configured: "
                           "check GITHUB_INTEGRATION_* properties on your settings.conf")
            return False
        return True

    @classmethod
    def _get_signing_key(cls):
        if not cls._signing_key_path:
            raise IllegalStateException(f"{cls.__name__}")
        with open(cls._signing_key_path, 'rb') as fh:
            return jwt.jwk_from_pem(fh.read())

    @classmethod
    def get_app_client(cls) -> requests.Session:
        message = {
            # The time that this JWT was issued, _i.e._ now.
            "iat": jwt.utils.get_int_from_datetime(datetime.now(timezone.utc)),
            # JWT expiration time (10 minute maximum)
            "exp": jwt.utils.get_int_from_datetime(datetime.now(timezone.utc) + cls.token_expiration),
            # Your GitHub App's identifier number
            "iss": cls.app_identifier
        }
        # Cryptographically sign the JWT
        token = jwt.JWT().encode(message, cls._get_signing_key(), alg='RS256')
        s = requests.Session()
        s.headers.update({
            'Authorization': f"Bearer {token}",
            'Accept': 'application/vnd.github.v3+json'
        })
        return s

    @classmethod
    def get_installation_token(cls, installation_id: str) -> str:
        # Authenticate as installed app
        app_client = cls.get_app_client()
        response = app_client.post(f"{cls.github_api_url}/app/installations/{installation_id}/access_tokens")
        logger.debug("Status code: %r" % response.status_code)
        assert response.status_code == 201, "Unable to create access token"
        return response.json()

    @classmethod
    def get_installation_client(cls, installation_id: str) -> requests.Session:
        token = cls.get_installation_token(installation_id)
        installation_client = requests.Session()
        installation_client.headers.update({
            'Authorization': f"Bearer {token['token']}",
            'Accept': 'application/vnd.github.v3+json'
        })
        return installation_client

    @classmethod
    def get_github_client(cls, installation_id: str) -> github.Github:
        token = cls.get_installation_token(installation_id)
        return github.Github(token['token'])

    @classmethod
    def validate_signature(cls, request) -> bool:
        # Get the signature from the payload
        signature_header = request.headers.get('X-Hub-Signature-256', None)
        if not signature_header:
            raise ValueError("Signature not found")
        sha_name, github_signature = signature_header.split('=')
        if sha_name != 'sha256':
            raise ValueError('ERROR: X-Hub-Signature in payload headers was not sha256=****')
        # Create our own signature
        local_signature = hmac.new(cls._signing_secret.encode('utf-8'),
                                   msg=request.data, digestmod=hashlib.sha256)
        # See if they match
        return hmac.compare_digest(local_signature.hexdigest(), github_signature)

    @classmethod
    def get_installations(cls) -> List[object]:
        app_client = cls.get_app_client()
        response = app_client.get(f"{cls.github_api_url}/app/installations")
        if response.status_code == 200:
            return response.json()
        logger.error(response.content)
        return "Internal Error", 500

    @classmethod
    def get_installation_repositories(cls, installation_client):
        response = installation_client.get(f"{cls.github_api_url}/installation/repositories")
        if response.status_code == 200:
            return response.json()['repositories']
        logger.error(response.content)
        return "Internal Error", 500


# Event Handlers
def ping(event: object):
    logger.debug("Ping event: %r", event)
    return "Pong", 200


def workflow_run(event: object):
    try:
        logger.debug("Workflow run event: %r", event)
        repository = event['data']['repository']
        logger.debug("Workflow repository: %r", repository)
        workflow = event['data']['workflow']
        logger.debug("Workflow: %r", workflow)
        workflow_run = event['data']['workflow_run']
        logger.debug("Workflow run: %r", workflow_run)
        workflow_name = workflow['path'].replace('.github/workflows/', '')
        logger.debug("Workflow NAME: %r", workflow_name)
        workflow_resource = f"repos/{repository['full_name']}/actions/workflows/{workflow_name}"
        logger.debug("Workflow Resource: %r", workflow_resource)
        instances = TestInstance.find_by_resource(workflow_resource)
        logger.debug("Instances: %r", instances)
        with cache.transaction():
            for i in instances:
                i.get_test_builds(limit=10)
                i.get_test_build(workflow_run['id'])
                i.last_test_build
        return f"Test instance related with resource '{workflow_resource}' updated", 200
    except Exception as e:
        logger.error(e)
        return "Internal Error", 500


# Register Handlers
__event_handlers__ = {
    "ping": ping,
    "workflow_run": workflow_run
}


# Integration Blueprint
blueprint = Blueprint("github_integration", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static')


@blueprint.route("/integrations/github", methods=("POST",))
def webhook_test():
    logger.debug("Request header keys: %r", [k for k in request.headers.keys()])
    logger.debug("Request header values: %r", request.headers)
    if not GithubAppHelper.check_initialization():
        return "GitHub Integration not configured", 503
    valid = GithubAppHelper.validate_signature(request)
    logger.debug("Signature valid?: %r", valid)
    if not valid:
        return "Signature Invalid", 401
    data = request.get_json()
    event = {
        "id": request.headers.get("X-Github-Delivery"),
        "type": request.headers.get("X-Github-Event"),
        "action": data.get("action", None),
        "signature": request.headers.get("X-Hub-Signature-256").replace("256=", ""),
        "data": data
    }
    event_handler = __event_handlers__.get(event['type'], None)
    logger.debug("Event: %r", event)
    if not event_handler:
        action = f"- action: {event['action']}" if event['action'] else None
        logger.warning(f"No event handler registered for the event GitHub event '{event['type']}' {action}")
        return f"No handler registered for the '{event['type']}' event", 204
    else:
        return event_handler(event)


def init_integration(app: Flask):
    # Initialize GitHub App Integration
    app_identifier = app.config.get('GITHUB_INTEGRATION_APP_ID')
    webhook_secret = app.config.get('GITHUB_INTEGRATION_WEB_SECRET')
    private_key_path = app.config.get('GITHUB_INTEGRATION_PRIVATE_KEY_PATH')
    GithubAppHelper.init(app_identifier, private_key_path, webhook_secret)
    app.register_blueprint(blueprint)
    logger.info("Integration registered for GitHub App: %r", app_identifier)
