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

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import jwt
import requests
from lifemonitor.api.models.repositories.github import (
    GithubWorkflowRepository, InstallationGithubWorkflowRepository)
from lifemonitor.auth.oauth2.client.models import (
    OAuthIdentity, OAuthIdentityNotFoundException)
from lifemonitor.exceptions import IllegalStateException, LifeMonitorException
from lifemonitor.integrations.github.registry import GithubWorkflowRegistry

from github import Github
from github import GithubIntegration as GithubIntegrationBase
from github import Installation
from github.GithubApp import GithubApp
from github.InstallationAuthorization import InstallationAuthorization
from github.PaginatedList import PaginatedList
from github.Repository import Repository as GithubRepository
from github.Requester import Requester

from lifemonitor.integrations.github.utils import CachedGithubRequester

from .config import (DEFAULT_BASE_URL, DEFAULT_PER_PAGE, DEFAULT_TIMEOUT,
                     DEFAULT_TOKEN_EXPIRATION)

# Config a module level logger
logger = logging.getLogger(__name__)


class LifeMonitorGithubApp(GithubApp):

    __instance__: LifeMonitorGithubApp = None
    _signing_key_path = None
    _signing_secret = None
    _app_identifier = None
    _service_token = None

    @classmethod
    def init(cls, app_identifier: str,
             signing_key_path: str, signing_secret: str, service_token: str,
             base_url: str = DEFAULT_BASE_URL,
             token_expiration: timedelta = DEFAULT_TOKEN_EXPIRATION,
             service_repository_full_name: str = None):
        cls._app_identifier = app_identifier
        cls._signing_key_path = signing_key_path
        cls._signing_secret = signing_secret
        cls._service_token = service_token
        if not cls.__instance__ and cls.check_initialization():
            integration = GithubIntegration(cls._app_identifier, cls._get_signing_key(), base_url=base_url)
            cls.__instance__ = cls(integration, cls._service_token, base_url=base_url,
                                   token_expiration=token_expiration,
                                   service_repository_full_name=service_repository_full_name)

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

    def __init__(self, integration: GithubIntegration, service_token: str,
                 base_url=DEFAULT_BASE_URL, token_expiration=DEFAULT_TOKEN_EXPIRATION,
                 service_repository_full_name: str = None) -> None:
        self._integration = integration
        self.service_token = service_token
        self.token_expiration = token_expiration
        self.base_url = base_url
        self.service_repository_full_name = service_repository_full_name
        session = self.app_client_session()
        try:
            app = self._get_app_info(session=session)
            self._requester = __make_requester__(
                jwt=self.integration.create_jwt(expiration=self.token_expiration),
                base_url=self.base_url)
            self.__installations__ = threading.local()
            self.__installations__.loaded = False
            super().__init__(self._requester, session.headers, app, True)
        finally:
            session.close()

    def _get_app_info(self, session: requests.Session = None):
        s = session or self.app_client_session()
        try:
            response = s.get(f"{self.base_url}/app")
            if response.status_code == 200:
                return response.json()
            raise LifeMonitorException(detail=response.content, status=response.status_code)
        finally:
            if s and not session:
                s.close()

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
    def bot(self) -> str:
        return f"{self.slug}[bot]"

    @property
    def integration(self) -> GithubIntegration:
        return self._integration

    @property
    def repository_service(self) -> GithubRepository:
        assert self.service_token, "No service token set"
        gh_client = Github(login_or_token=self.service_token)
        return gh_client.get_repo(self.service_repository_full_name)

    @property
    def _installations(self) -> Dict[str, LifeMonitorInstallation]:
        if not hasattr(self.__installations__, "loaded") or not self.__installations__.loaded:
            self._load_installations()
        return self.__installations__.map

    def _load_installations(self):
        logger.debug("Loading installations...")
        self.__installations__.map = {}
        app_client = self.app_client_session()
        try:
            response = app_client.get(f"{self.base_url}/app/installations")
            if response.status_code == 200:
                for i in response.json():
                    if i['id'] not in self.__installations__.map:
                        self.__installations__.map[i['id']] = LifeMonitorInstallation(self, i, requester=self._requester)
            self.__installations__.loaded = True
            logger.debug("Loading installations... DONE")
        finally:
            app_client.close()

    @property
    def installations(self) -> List[LifeMonitorInstallation]:
        logger.warning("Searching installation: %r", self._installations)
        return list(self._installations.values())

    def get_installation(self, installation_id: int) -> LifeMonitorInstallation:
        logger.debug("Searching installation_id %r", installation_id)
        # Try to reload installations if the installation_id is not loaded
        if installation_id not in self._installations:
            logger.debug("Trying reloading installations...")
            self._load_installations()
            logger.debug("Trying reloading installations... DONE")
        try:
            return self._installations[installation_id]
        except KeyError:
            logger.debug("Installation '%s' not found", installation_id)
            return None


class GithubIntegration(GithubIntegrationBase):

    _current_jwt = threading.local()

    @property
    def current_jwt(self) -> Dict:
        try:
            return self._current_jwt.token
        except AttributeError:
            return None

    def create_jwt(self, expiration=DEFAULT_TOKEN_EXPIRATION, encoded: bool = True) -> str:
        now = datetime.now()
        expires_at = now + expiration
        token = {
            # The time that this JWT was issued, _i.e._ now.
            "iat": jwt.utils.get_int_from_datetime(now),
            # JWT expiration time (10 minute maximum)
            "exp": jwt.utils.get_int_from_datetime(expires_at),
            # Your GitHub App's identifier number
            "iss": self.integration_id
        }
        # Save the current thread-local JWT
        self._current_jwt.token = token
        # Cryptographically sign the JWT if required
        if encoded:
            return jwt.JWT().encode(token, key=self.private_key, alg='RS256')
        return token


class LifeMonitorInstallation(Installation.Installation):

    def __init__(self, app: LifeMonitorGithubApp, data: object, requester=None, headers={}, completed=True):
        super().__init__(requester, headers, data, completed)
        self.app = app
        self._auth: InstallationAuthorization = None
        self._gh_client = None

    @property
    def github_registry(self) -> GithubWorkflowRegistry:
        try:
            identity: OAuthIdentity = OAuthIdentity.find_by_provider_user_id(str(self.app.owner.id), "github")
            registry = GithubWorkflowRegistry.find(identity.user, self.app.id, self.id)
            if not registry:
                registry = GithubWorkflowRegistry(identity.user, self.app.id, self.id)
            return registry
        except OAuthIdentityNotFoundException as e:
            logger.warning("Github identity '%r' doesn't match with any LifeMonitor user identity", self.app.owner.id)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)

    @property
    def github_client(self) -> Github:
        if not self._gh_client:
            self._gh_client = Github(login_or_token=self.auth.token)
        return self._gh_client

    @property
    def auth(self) -> InstallationAuthorization:
        generate_token = self._auth is None
        if self._auth:
            now = datetime.now(timezone.utc)
            expires_at = jwt.utils.get_time_from_int(self.app.integration.current_jwt['exp'])
            logger.warning("Checking token expiration: now=%r, expires_at=%r, expired: %r",
                           now, expires_at, expires_at <= now)
            if expires_at <= now:
                generate_token = True
        if generate_token:
            logger.debug("Generating a new access token...")
            self._auth = self.app.integration.get_access_token(self.id)
            logger.warning("Created auth: %r - %r", self._auth, self._auth.raw_data)
            assert isinstance(self._auth, InstallationAuthorization), "Invalid authorization"
            logger.debug("Generating a new access token... DONE")
        else:
            logger.warning("Reusing existing token: %r", self._auth)
        return self._auth

    @property
    def _requester(self):
        if self.__requester:
            self.__requester = __make_requester__(token=self.auth.token, base_url=self.app.base_url)
        return self.__requester

    @_requester.setter
    def _requester(self, value: Requester):
        self.__requester = value

    def get_repo(self, full_name_or_id, ref: str = None, rev: str = None, lazy=False) -> InstallationGithubWorkflowRepository:
        assert isinstance(full_name_or_id, (str, int)), full_name_or_id
        url_base = "/repositories/" if isinstance(full_name_or_id, int) else "/repos/"
        url = f"{url_base}{full_name_or_id}"
        if lazy:
            return GithubWorkflowRepository(
                self._requester, {}, {"url": url}, completed=False, ref=ref, rev=rev
            )
        headers, data = self._requester.requestJsonAndCheck("GET", url)
        return InstallationGithubWorkflowRepository(self._requester, headers, data, completed=True, ref=ref, rev=rev)

    def get_repos(self) -> List[InstallationGithubWorkflowRepository]:
        url_parameters = dict()
        return PaginatedList(
            contentClass=InstallationGithubWorkflowRepository,
            requester=self._requester,
            firstUrl="/installation/repositories",
            firstParams=url_parameters,
            headers=Installation.INTEGRATION_PREVIEW_HEADERS,
            list_item="repositories",
        )

    def get_repo_from_event(self, event: object, ignore_errors: bool = False) -> GithubRepository:
        try:
            return self.get_repo(event['payload']['repository']['full_name'])
        except KeyError:
            if not ignore_errors:
                raise LifeMonitorException(title="Bad request",
                                           detail="Missing payload.repository property", status=400)
            return None

    @classmethod
    def from_event(cls, event: object, ignore_errors: bool = False) -> LifeMonitorInstallation:
        try:
            app = LifeMonitorGithubApp.get_instance()
            return app.get_installation(event['payload']['installation']['id'])
        except KeyError:
            if not ignore_errors:
                raise LifeMonitorException(title="Bad request",
                                           detail="Missing payload.installation.id property", status=400)
            return None


def __make_requester__(jwt: str = None, token: str = None, base_url: str = DEFAULT_BASE_URL) -> Requester:
    assert jwt or token, "Auth JWT or TOKEN should be set"
    return CachedGithubRequester(token or None, None, jwt or None, base_url,
                                 DEFAULT_TIMEOUT, "PyGithub/Python", DEFAULT_PER_PAGE,
                                 True, None, None)
