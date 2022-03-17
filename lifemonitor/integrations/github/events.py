
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

import logging

from flask import Request
from flask import request as current_request
from lifemonitor.auth.models import HostingService
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.integrations.github.app import (LifeMonitorGithubApp,
                                                 LifeMonitorInstallation)
from lifemonitor.api.models.repositories.github import (
    RepoCloneContextManager, GithubWorkflowRepository)

# Config a module level logger
logger = logging.getLogger(__name__)


class GithubEvent():

    def __init__(self, headers: dict, payload: dict) -> None:
        self._headers = headers
        self._repository_reference = None
        self._sender = None
        assert isinstance(payload, dict), payload
        try:
            self._raw_data = payload['payload']
        except KeyError:
            self._raw_data = payload

    @property
    def type(self) -> str:
        return self._headers.get("X-Github-Event", None)

    @property
    def delivery(self) -> str:
        return self._headers.get("X-Github-Delivery", None)

    @property
    def application_id(self) -> int:
        return int(self.installation_target_id) if self.installation_target_id else None

    @property
    def installation_target_id(self) -> str:
        return self._headers.get("X-GitHub-Hook-Installation-Target-ID", None)

    @property
    def installation_target_type(self) -> str:
        return self._headers.get("X-Github-Hook-Installation-Target-Type", None)

    @property
    def installation_id(self) -> str:
        inst = self._raw_data.get('installation', None)
        assert isinstance(inst, dict), "Invalid installation data"
        return inst.get('id')

    @property
    def headers(self) -> dict:
        return self._headers

    @property
    def sender(self) -> OAuthIdentity:
        if not self._sender:
            # search user identity
            identity: OAuthIdentity = self.hosting_service.server_credentials\
                .find_identity_by_provider_user_id(str(self._raw_data['sender']['id']))
            self._sender = identity
        return self._sender

    @property
    def payload(self) -> dict:
        return self._raw_data

    @property
    def signature(self) -> str:
        return self._headers.get("X-Hub-Signature-256").replace("256=", "")

    @property
    def hosting_service(self) -> HostingService:
        return HostingService.from_url('https://github.com')

    @property
    def application(self) -> LifeMonitorGithubApp:
        app = LifeMonitorGithubApp.get_instance()
        logger.debug("Comparing: %r - %r", self.application_id, app.id)
        assert self.application_id == app.id, "Invalid application ID"
        return app

    @property
    def installation(self) -> LifeMonitorInstallation:
        return self.application.get_installation(self.installation_id)

    @property
    def repository_reference(self) -> GithubRepositoryReference:
        if not self._repository_reference:
            self._repository_reference = GithubRepositoryReference(event=self)
        return self._repository_reference

    @staticmethod
    def from_request(request: Request = None) -> GithubEvent:
        request = request or current_request
        assert isinstance(request, Request), request
        return GithubEvent(request.headers, request.get_json())


class GithubRepositoryReference(object):

    def __init__(self, event: GithubEvent) -> None:
        self._event = event
        self._raw_data = self._event._raw_data

    @property
    def event(self) -> GithubEvent:
        return self._event

    @property
    def hosting_service(self) -> HostingService:
        return self.event.hosting_service

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.full_name} (id: {self.id}, ref: {self.ref}, rev. {self.rev})"

    @property
    def id(self) -> int:
        return self._raw_data['repository']['id']

    @property
    def url(self) -> str:
        return self._raw_data['repository']['url']

    @property
    def clone_url(self) -> str:
        return self._raw_data['repository']['clone_url']

    @property
    def owner(self) -> str:
        return self._raw_data['repository']['owner']['login']

    @property
    def owner_id(self) -> str:
        return self._raw_data['repository']['owner']['id']

    @property
    def owner_info(self) -> object:
        return self._raw_data['repository']['owner']

    @property
    def name(self) -> str:
        return self._raw_data['repository']['name']

    @property
    def full_name(self) -> str:
        return self._raw_data['repository']['full_name']

    @property
    def ref(self) -> str:
        ref = self._raw_data.get('ref', None)
        ref_type = self._raw_data.get('ref_type', None)
        if ref and ref_type == 'tag' and not ref.startswith('ref/'):
            return f"refs/tags/{ref}"
        return ref

    @property
    def rev(self) -> str:
        try:
            key = 'before' if self.deleted else 'after'
            return self._raw_data.get(key, None)
        except KeyError:
            return None

    @property
    def branch(self) -> str:
        ref = self.ref
        ref_type = self._raw_data.get('ref_type', None)
        if not ref or ref_type == 'tag' or 'refs/tags' in ref:
            return None
        return ref.replace('refs/heads/', '')

    @property
    def tag(self) -> str:
        ref = self.ref
        ref_type = self._raw_data.get('ref_type', None)
        if not ref or (ref_type and ref_type != 'tag') or 'refs/heads' in ref:
            return None
        return ref.replace('refs/tags/', '')

    @property
    def created(self) -> bool:
        return self._raw_data.get('created', False)

    @property
    def deleted(self) -> bool:
        return self._raw_data.get('deleted', False)

    @property
    def forced(self) -> bool:
        return self._raw_data.get('forced', False)

    @property
    def repository(self) -> GithubWorkflowRepository:
        repo = self.event.installation.get_repo(self.full_name)
        repo.ref = self.ref
        repo.rev = self.rev
        return repo

    def clone(self, local_path: str = None) -> RepoCloneContextManager:
        assert local_path is None or isinstance(str, local_path), local_path
        return RepoCloneContextManager(self.clone_url, repo_branch=self.branch, local_path=local_path)
