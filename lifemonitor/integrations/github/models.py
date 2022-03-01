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

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
import requests
from lifemonitor.exceptions import IllegalStateException, LifeMonitorException

from github import Github
from github import GithubIntegration as GithubIntegrationBase
from github.GithubApp import GithubApp
from github.Installation import Installation
from github.InstallationAuthorization import InstallationAuthorization
from github.Requester import Requester

DEFAULT_BASE_URL = "https://api.github.com"
DEFAULT_TIMEOUT = 15
DEFAULT_PER_PAGE = 30
DEFAULT_TOKEN_EXPIRATION = timedelta(seconds=60)

# Config a module level logger
logger = logging.getLogger(__name__)


class LifeMonitorGithubApp(GithubApp):

    __instance__: LifeMonitorGithubApp = None
    _signing_key_path = None
    _signing_secret = None
    _app_identifier = None

    @classmethod
    def init(cls, app_identifier: str,
             signing_key_path: str, signing_secret: str,
             base_url: str = DEFAULT_BASE_URL,
             token_expiration: timedelta = DEFAULT_TOKEN_EXPIRATION):
        cls._app_identifier = app_identifier
        cls._signing_key_path = signing_key_path
        cls._signing_secret = signing_secret
        if not cls.__instance__:
            integration = GithubIntegration(cls._app_identifier, cls._get_signing_key(), base_url=base_url)
            cls.__instance__ = cls(integration, base_url=base_url, token_expiration=token_expiration)

    @classmethod
    def get_instance(cls) -> LifeMonitorGithubApp:
        if not cls.check_initialization():
            raise IllegalStateException(detail="Github App not initializaed")
        return cls.__instance__

    @classmethod
    def check_initialization(cls) -> bool:
        if not cls._app_identifier or not cls._signing_key_path or not cls._signing_secret:
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

    def __init__(self, integration: GithubIntegration,
                 base_url=DEFAULT_BASE_URL, token_expiration=DEFAULT_TOKEN_EXPIRATION) -> None:
        self._integration = integration
        self.token_expiration = token_expiration
        self.base_url = base_url
        session = self.app_client_session()
        app = self._get_app_info(session=session)
        self._requester = __make_requester__(
            jwt=self.integration.create_jwt(expiration=self.token_expiration),
            base_url=self.base_url)
        super().__init__(self._requester, session.headers, app, True)

    def _get_app_info(self, session: requests.Session = None):
        session = session or self.app_client_session()
        response = session.get(f"{self.base_url}/app")
        if response.status_code == 200:
            return response.json()
        raise LifeMonitorException(detail=response.content, status=response.status_code)

    def app_client(self, expiration=None) -> Github:
        return Github(jwt=self.integration.create_jwt(expiration=expiration or self.token_expiration))

    def app_client_session(self, expiration=None) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            'Authorization': f"Bearer {self.integration.create_jwt(expiration=expiration or self.token_expiration)}",
            'Accept': 'application/vnd.github.v3+json'
        })
        return s

    @property
    def integration(self) -> GithubIntegration:
        return self._integration

    @property
    def installations(self) -> List[LifeMonitorInstallation]:
        app_client = self.app_client_session()
        response = app_client.get(f"{self.base_url}/app/installations")
        if response.status_code == 200:
            return [LifeMonitorInstallation(self, i, requester=self._requester) for i in response.json()]
        logger.error(response.content)
        return "Internal Error", 500

    def get_installation(self, installation_id: str) -> LifeMonitorInstallation:
        logger.debug("Searching installation_id %r", installation_id)
        for i in self.installations:
            logger.debug("Installation: %r %r %r", i, i.id, i.app)
            if str(i.id) == str(installation_id):
                return i
        return None


class GithubIntegration(GithubIntegrationBase):

    def create_jwt(self, expiration=timedelta(seconds=20)) -> str:
        now = datetime.now(timezone.utc)
        message = {
            # The time that this JWT was issued, _i.e._ now.
            "iat": jwt.utils.get_int_from_datetime(now),
            # JWT expiration time (10 minute maximum)
            "exp": jwt.utils.get_int_from_datetime(now + expiration),
            # Your GitHub App's identifier number
            "iss": self.integration_id
        }
        logger.debug("Token message: %r", message)
        # Cryptographically sign the JWT
        return jwt.JWT().encode(message, self.private_key, alg='RS256')


class LifeMonitorInstallation(Installation):

    def __init__(self, app: LifeMonitorGithubApp, data: object, requester=None, headers={}, completed=True):
        super().__init__(requester, headers, data, completed)
        self.app = app
        self._auth: InstallationAuthorization = None

    @property
    def auth(self) -> InstallationAuthorization:
        generate_token = False
        if not self._auth:
            generate_token = True
        elif jwt.utils.get_int_from_datetime(self._auth.expires_at) < jwt.utils.get_int_from_datetime(datetime.now()):
            generate_token = True
        if generate_token:
            self._auth = self.app.integration.get_access_token(self.id)
            assert isinstance(self._auth, InstallationAuthorization), "Invalid authorization"
        return self._auth

    @property
    def _requester(self):
        if self.__requester:
            self.__requester = __make_requester__(token=self.auth.token, base_url=self.app.base_url)
        return self.__requester

    @_requester.setter
    def _requester(self, value: Requester):
        self.__requester = value

    @classmethod
    def from_event(cls, event: object) -> LifeMonitorInstallation:
        app = LifeMonitorGithubApp.get_instance()
        return app.get_installation(event['installation']['id'])


def __make_requester__(jwt: str = None, token: str = None, base_url: str = DEFAULT_BASE_URL) -> Requester:
    assert jwt or token, "Auth JWT or TOKEN should be set"
    return Requester(token, None, jwt, base_url,
                     DEFAULT_TIMEOUT, "PyGithub/Python", DEFAULT_PER_PAGE,
                     True, None, None)
