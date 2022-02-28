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
import re
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import jwt
import pygit2
import requests
from lifemonitor.cache import IllegalStateException

import github

# Config a module level logger
logger = logging.getLogger(__name__)


class GithubApp():

    app_identifier = None
    app_slug = 'lifemonitorlocal'
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
        if not cls.app_identifier or not cls._signing_key_path or not cls._signing_secret:
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
    def get_installation_client(cls, installation_id: str) -> GithubInstallationClient:
        token = cls.get_installation_token(installation_id)
        logger.debug(token)
        return GithubInstallationClient(installation_id, token)

    @classmethod
    def get_github_client(cls, installation_id: str) -> github.Github:
        token = cls.get_installation_token(installation_id)
        return github.Github(token['token'])

    @classmethod
    def get_app(cls) -> object:
        response = requests.get(f"{cls.github_api_url}/apps/{cls.app_slug}")
        if response.status_code == 200:
            return response.json()
        logger.error(response.content)
        return "Internal Error", 500

    @classmethod
    def get_installations(cls) -> List[object]:
        app_client = cls.get_app_client()
        response = app_client.get(f"{cls.github_api_url}/app/installations")
        if response.status_code == 200:
            return response.json()
        logger.error(response.content)
        return "Internal Error", 500

    @classmethod
    def get_installation(cls, installation_id: str) -> object:
        app_client = cls.get_app_client()
        response = app_client.get(f"{cls.github_api_url}/app/installations/{installation_id}")
        if response.status_code == 200:
            return response.json()
        logger.error(response.content)
        if response.status_code == 404:
            return None
        return "Internal Error", 500

    @classmethod
    def get_installation_by_org(cls, org: str) -> object:
        app_client = cls.get_app_client()
        response = app_client.get(f"{cls.github_api_url}/orgs/{org}/installation")
        if response.status_code == 200:
            return response.json()
        logger.error(response.content)
        if response.status_code == 404:
            return None
        return "Internal Error", 500

    @classmethod
    def get_installation_by_owner_repo(cls, owner: str, repo: str) -> object:
        app_client = cls.get_app_client()
        response = app_client.get(f"{cls.github_api_url}/repos/{owner}/{repo}/installation")
        if response.status_code == 200:
            return response.json()
        logger.error(response.content)
        if response.status_code == 404:
            return None
        return "Internal Error", 500

    @classmethod
    def get_github_client_for_event(cls, event: object) -> github.Github:
        return GithubApp.get_github_client(event['installation']['id'])

    @staticmethod
    def get_repo_and_ref_from_event(gh_client: github.Github, event: object) -> Tuple[object, str]:
        return gh_client.get_repo(event['data']['repository']['full_name']), event['data']['ref']

    @classmethod
    def find_file_by_pattern(cls, repo: object, ref: str, search: str):
        for e in repo.get_contents('.', ref=ref):
            logger.debug("Name: %r -- type: %r", e.name, e.type)
            if re.search(search, e.name):
                return e.decoded_content
        return None

    @classmethod
    def find_file_by_regex_pattern(cls, repo: object, ref: str, pattern: re.Pattern):
        for e in repo.get_contents('.', ref=ref):
            logger.debug("Name: %r -- type: %r", e.name, e.type)
            if pattern.match(e.name):
                return e.decoded_content
        return None

    @staticmethod
    def clone_repo(repo: object, target_path: str):
        # Clone the newly created repo
        return pygit2.clone_repository(repo.git_url, target_path)

    @staticmethod
    def crate_new_branch(repo: object, branch_name: str):
        head = repo.get_commit('HEAD')
        logger.debug("HEAD commit: %r", head.sha)
        logger.debug("New target branch ref: %r", f'refs/heads/{branch_name}'.format(**locals()))
        return repo.create_git_ref(ref=f'refs/heads/{branch_name}'.format(**locals()), sha=head.sha)


class GithubInstallationClient():

    _api_url = GithubApp.github_api_url

    def __init__(self, installation_id: str, token: object) -> None:
        self._installation_id = installation_id
        self._token = token
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f"Bearer {self._token['token']}",
            'Accept': 'application/vnd.github.v3+json'
        })

    @property
    def session(self) -> requests.Session:
        return self._session

    @property
    def installation_id(self) -> str:
        return self._installation_id

    @property
    def installation(self) -> object:
        return GithubApp.get_installation(self._installation_id)

    @property
    def installation_repositories(self) -> List[object]:
        response = self._session.get(f"{self._api_url}/installation/repositories")
        if response.status_code == 200:
            return response.json()['repositories']
        logger.error(response.content)
        return "Internal Error", 500
