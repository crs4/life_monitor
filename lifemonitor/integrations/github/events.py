
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

import json
import logging
from typing import Dict, List, Optional

from flask import Request
from flask import request as current_request
from lifemonitor.api.models.repositories.github import (
    GithubWorkflowRepository, RepoCloneContextManager)
from lifemonitor.auth.models import HostingService
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.integrations.github.app import (LifeMonitorGithubApp,
                                                 LifeMonitorInstallation)
from lifemonitor.integrations.github.issues import (GithubIssue,
                                                    GithubIssueComment)
from lifemonitor.integrations.github.pull_requests import GithubPullRequest

from github.Workflow import Workflow
from github.WorkflowRun import WorkflowRun

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
    def id(self) -> str:
        return self.delivery

    @property
    def type(self) -> str:
        return self._headers.get("X-Github-Event", None)

    @property
    def action(self) -> str:
        return self._raw_data.get('action', None)

    @property
    def delivery(self) -> str:
        return self._headers.get("X-Github-Delivery", None)

    @property
    def application_id(self) -> int:
        return int(self.installation_target_id) if self.installation_target_id else None

    @property
    def installation_target_id(self) -> str:
        return self._headers.get("X-Github-Hook-Installation-Target-Id", None)

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
    def pusher(self) -> str:
        return self._raw_data['pusher']['name'] if 'pusher' in self._raw_data else None

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
        try:
            return HostingService.from_url('https://github.com', 'https://api.github.com')
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            return None

    @property
    def application(self) -> LifeMonitorGithubApp:
        app = LifeMonitorGithubApp.get_instance()
        logger.debug("Comparing: %r - %r", self.application_id, app.id)
        assert self.application_id == app.id, "Invalid application ID"
        return app

    @property
    def installation(self) -> LifeMonitorInstallation:
        installation = self.application.get_installation(self.installation_id)
        logger.debug("Loaded installation: %r", installation)
        return installation

    @property
    def repository_reference(self) -> GithubRepositoryReference:
        if not self._repository_reference:
            if 'repositories' in self._raw_data or 'repositories_added' in self._raw_data:
                raise ValueError("Multiple repositories associated to this event")
            self._repository_reference = GithubRepositoryReference(event=self)
        return self._repository_reference

    @property
    def repositories_added(self) -> List[GithubRepositoryReference]:
        result = []
        repos = self._raw_data.get('repositories', None) or self._raw_data.get('repositories_added', None)
        if repos is None:
            logger.warning("No repo info attached to the %r github event")
        else:
            for repo_info in repos:
                try:
                    installation = self.installation
                    if installation:
                        repo: GithubWorkflowRepository = self.installation.get_repo(repo_info['full_name'])
                        logger.debug("Got repo: %r", repo)
                        result.append(GithubRepositoryReference(self, repo))
                    else:
                        logger.warning("Unable to load installation %r", self.installation_id)
                except Exception as e:
                    logger.warning("Unable to load data of repo: %r", repo)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
        return result

    @property
    def repositories_removed(self) -> List[GithubRepositoryReference]:
        result = []
        repos = self._raw_data.get('repositories', None) or self._raw_data.get('repositories_removed', None)
        if repos is None:
            logger.warning("No repo info attached to the %r github event")
        else:
            for repo_info in repos:
                try:
                    installation = self.installation
                    if installation:
                        repo: GithubWorkflowRepository = self.installation.get_repo(repo_info['full_name'])
                        logger.debug("Got repo: %r", repo)
                        result.append(GithubRepositoryReference(self, repo))
                    else:
                        logger.warning("Unable to load installation %r", self.installation_id)
                except Exception as e:
                    logger.warning("Unable to load data of repo: %r", repo_info)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
        return result

    @property
    def issue(self) -> Optional[GithubIssue]:
        return None if 'issue' not in self.payload else \
            GithubIssue(self.installation._requester, {}, self.payload['issue'], True)

    @property
    def pull_request(self) -> Optional[GithubPullRequest]:
        return None if 'pull_request' not in self.payload else \
            GithubPullRequest(self.installation._requester, {}, self.payload['pull_request'], True)

    @property
    def comment(self) -> Optional[GithubIssueComment]:
        issue = self.issue
        if issue:
            return None if 'comment' not in self.payload else \
                GithubIssueComment(self.installation._requester, {}, self.payload['comment'], True, issue=issue)
        return None

    @property
    def workflow(self) -> Optional[Workflow]:
        return None if 'workflow' not in self.payload else \
            Workflow(self.installation._requester, {}, self.payload['workflow'], True)

    @property
    def workflow_run(self) -> Optional[WorkflowRun]:
        if 'workflow_run' in self.payload:
            return WorkflowRun(self.installation._requester, {}, self.payload['workflow_run'], True)
        if 'workflow_job' in self.payload:
            return WorkflowRun(self.installation._requester, {}, {
                'id': self.payload['workflow_job']['run_id'],
                'url': self.payload['workflow_job']['run_url']
            }, False)
        return None

    @property
    def workflow_build_id(self) -> Optional[str]:
        if 'workflow_job' in self.payload:
            job = self.payload['workflow_job']
            if job:
                return f"{job['run_id']}_{job['run_attempt']}"
        return None

    @staticmethod
    def from_request(request: Request = None) -> GithubEvent:
        request = request or current_request
        assert isinstance(request, Request), request
        return GithubEvent(request.headers, request.get_json())

    @classmethod
    def from_dict(cls, data: Dict) -> GithubEvent:
        return cls(data.get('headers', {}), data.get('data', {}))

    def to_dict(self) -> Dict:
        logger.debug("Headers: %r", self._headers)
        return {
            'headers': {k: v for k, v in self._headers.items()},
            'data': self._raw_data
        }

    @classmethod
    def from_json(cls, data: str) -> GithubEvent:
        raw_data = json.loads(data)
        return cls(raw_data.get('headers', {}), raw_data.get('data', {}))

    def to_json(self) -> str:
        logger.debug("Headers: %r", self._headers)
        return json.dumps(self.to_dict())


class GithubRepositoryReference(object):

    def __init__(self, event: GithubEvent, repo: GithubWorkflowRepository = None) -> None:
        self._event = event
        self._raw_data = {'repository': repo.raw_data} if repo else self._event._raw_data
        self._repo: GithubWorkflowRepository = repo

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
        if self.event.workflow_run:
            return f"refs/heads/{self.event.workflow_run.head_branch}"
        ref = self._repo.ref if self._repo else self._raw_data.get('ref', None)
        ref_type = self._raw_data.get('ref_type', None)
        if ref and ref_type == 'tag' and not ref.startswith('refs/'):
            return f"refs/tags/{ref}"
        return ref

    @property
    def rev(self) -> str:
        if self.event.workflow_run:
            return self.event.workflow_run.head_sha
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
        if not self._repo:
            ref = self.ref
            if self.branch:
                ref = f"refs/heads/{self.branch}"
            elif self.tag:
                ref = f"refs/tags/{self.tag}"
            repo = self.event.installation.get_repo(self.full_name, ref=ref)
            repo.rev = self.rev
            self._repo = repo
        return self._repo

    def clone(self, local_path: str = None) -> RepoCloneContextManager:
        assert local_path is None or isinstance(str, local_path), local_path
        return RepoCloneContextManager(self.clone_url, repo_branch=self.branch, local_path=local_path)
