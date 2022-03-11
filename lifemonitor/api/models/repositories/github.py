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
import os
import re
import shutil
import tempfile
from datetime import timedelta
from typing import Any, Dict, Union

from lifemonitor.api.models.repositories.base import (
    WorkflowRepository, WorkflowRepositoryMetadata)
from lifemonitor.api.models.repositories.files import (RepositoryFile,
                                                       WorkflowFile)
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository
from lifemonitor.config import BaseConfig
from lifemonitor.exceptions import IllegalStateException
from lifemonitor.utils import clone_repo

from github.ContentFile import ContentFile
from github.Repository import Repository as GithubRepository
from github.Requester import Requester

DEFAULT_BASE_URL = "https://api.github.com"
DEFAULT_TIMEOUT = 15
DEFAULT_PER_PAGE = 30
DEFAULT_TOKEN_EXPIRATION = timedelta(seconds=60)

# Config a module level logger
logger = logging.getLogger(__name__)


class GitRepositoryFile(RepositoryFile):

    def __init__(self, content: ContentFile, type: str = None) -> None:
        super().__init__(content.name, type or content.type, content.path, None)
        self._content = content

    def __repr__(self) -> str:
        return f"{super().__repr__()} (sha: {self.sha})"

    def get_content(self, binary_mode: bool = False):
        result = self._content.decoded_content
        return result if binary_mode else result.decode()

    @property
    def sha(self) -> str:
        return self._content.sha


class TempWorkflowRepositoryMetadata(WorkflowRepositoryMetadata):

    def __init__(self, repo: InstallationGithubWorkflowRepository,
                 local_path: str = None, gen_preview=False, init=False):
        local_path = local_path or tempfile.mkdtemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        try:
            target_path = f'{local_path}/ro-crate-metadata.json'
            mf = repo.find_file_by_name('ro-crate-metadata.json')
            if not mf:
                raise IllegalStateException(detail="RO-Crate metadata not found!")
            with open(target_path, 'w') as out:
                out.write(mf.get_content())
            super().__init__(repo, local_path=local_path, gen_preview=gen_preview, init=init)
        finally:
            if not getattr(self, "source", None):
                logger.debug("Cleaning up temp repository metadata: %r", local_path)
                shutil.rmtree(local_path, ignore_errors=True)

    def __del__(self):
        try:
            logger.debug("Cleaning up temp repository metadata: %r", self.source)
            shutil.rmtree(self.source, ignore_errors=True)
        except AttributeError as e:
            logger.debug(e)


class InstallationGithubWorkflowRepository(GithubRepository, WorkflowRepository):

    def __init__(self, requester: Requester,
                 headers: Dict[str, Union[str, int]],
                 attributes: Dict[str, Any], completed: bool,
                 ref: str = None, auto_cleanup: bool = True) -> None:
        super().__init__(requester, headers, attributes, completed)
        self.ref = ref or self.default_branch
        self.auto_cleanup = auto_cleanup
        self._metadata = None
        self._local_repo: LocalWorkflowRepository = None

    @property
    def remote_metadata(self) -> WorkflowRepositoryMetadata:
        if not self._metadata:
            try:
                self._metadata = TempWorkflowRepositoryMetadata(self, init=False)
            except Exception as e:
                logger.debug("Error when loading repository metadata: %s", str(e))
        return self._metadata

    @property
    def metadata(self) -> WorkflowRepositoryMetadata:
        if not self.local_repo:
            return self.remote_metadata
        return self.local_repo.metadata

    def find_remote_file_by_pattern(self, search: str, ref: str = None) -> GitRepositoryFile:
        for e in self.get_contents('.', ref=ref or self.ref):
            logger.debug("Name: %r -- type: %r", e.name, e.type)
            if re.search(search, e.name):
                return GitRepositoryFile(e)
        return None

    def find_file_by_pattern(self, search: str, ref: str = None) -> GitRepositoryFile:
        if not self.local_repo:
            return self.find_remote_file_by_pattern(search, ref=ref)
        return self.local_repo.find_file_by_pattern(search)

    def find_remote_file_by_name(self, name: str, ref: str = None) -> GitRepositoryFile:
        for e in self.get_contents('.', ref=ref or self.ref):
            logger.debug("Name: %r -- type: %r", e.name, e.type)
            if e.name == name:
                return GitRepositoryFile(e)
        return None

    def find_file_by_name(self, name: str, ref: str = None) -> GitRepositoryFile:
        if not self.local_repo:
            return self.find_remote_file_by_name(name, ref=ref)
        return self.local_repo.find_file_by_name(name)

    def find_remote_workflow(self, ref: str = None) -> WorkflowFile:
        for e in self.get_contents('.', ref=ref or self.ref):
            for ext, wf_type in WorkflowFile.extension_map.items():
                if re.search(rf"\.{ext}$", e.name):
                    return GitRepositoryFile(e, type=wf_type)
        return None

    def find_workflow(self, ref: str = None) -> WorkflowFile:
        logger.debug("Local repo: %r", not self.local_repo)
        if not self.local_repo:
            return self.find_remote_workflow(ref=ref)
        return self.local_repo.find_workflow()

    def make_crate(self):
        if self.local_repo:
            if not self.auto_cleanup:
                logger.warning("'auto cleanup' disabled: local temp folder "
                               f"'{self.local_repo.local_path}' will not be deleted")
            else:
                self.cleanup()
        self._local_repo = self._setup_local_clone()
        return self._local_repo.make_crate()

    def _setup_local_clone(self):
        local_path = tempfile.mkdtemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        clone_repo(self.clone_url, branch=self.ref, target_path=local_path)
        return LocalWorkflowRepository(local_path=local_path)

    def clone(self, branch: str, local_path: str = None) -> RepoCloneContextManager:
        assert isinstance(branch, str), branch
        assert local_path is None or isinstance(str, local_path), local_path
        return RepoCloneContextManager(self.clone_url, repo_branch=branch, local_path=local_path)

    def write_zip(self, target_path: str):
        if self.local_repo:
            return self.local_repo.write_zip(target_path=target_path)
        with self.clone(self.ref) as local_path:
            return LocalWorkflowRepository(local_path).write_zip(target_path)

    @property
    def local_repo(self) -> LocalWorkflowRepository:
        return self._local_repo

    @property
    def local_path(self) -> str:
        return self.local_repo.local_path if self.local_repo else None

    def __del__(self):
        if self.auto_cleanup:
            self.cleanup()

    def cleanup(self):
        logger.debug("Repository cleanup")
        if self.local_repo:
            shutil.rmtree(self.local_repo.local_path, ignore_errors=True)
            self._local_repo = None


class GithubWorkflowRepository(InstallationGithubWorkflowRepository):

    def __init__(self, full_name_or_id: str, token: str = None,
                 ref: str = None, auto_cleanup: bool = True) -> None:
        assert isinstance(full_name_or_id, (str, int)), full_name_or_id
        url_base = "/repositories/" if isinstance(full_name_or_id, int) else "/repos/"
        url = f"{url_base}{full_name_or_id}"
        super().__init__(
            __make_requester__(token=token), headers={}, attributes={'url': url}, completed=False,
            ref=ref, auto_cleanup=auto_cleanup)


class RepoCloneContextManager():

    def __init__(self, repo_url: str, repo_branch: str = None, auth_token: str = None,
                 base_dir: str = BaseConfig.BASE_TEMP_FOLDER, local_path: str = None) -> None:
        self.base_dir = base_dir
        self.local_path = local_path
        self.auth_token = auth_token
        self.repo_url = repo_url
        self.repo_branch = repo_branch
        self._current_path = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} for {self.repo_url}"

    def __enter__(self):
        logger.debug("Entering the context %r ...", self)
        self._current_path = self.local_path
        if not self.local_path or not os.path.exists(self.local_path):
            self._current_path = tempfile.TemporaryDirectory(dir=BaseConfig.BASE_TEMP_FOLDER).name
            logger.debug(f"Creating clone of repo {self.repo_url}<{self.repo_branch} @ {self._current_path}...")
            clone_repo(self.repo_url, branch=self.repo_branch,
                       target_path=self._current_path, auth_token=self.auth_token)
        if not os.path.isdir(self._current_path):
            raise ValueError(f"The local path '{self._current_path}' should be a folder")
        return self._current_path

    def __exit__(self, exc_type, exc_value, exc_tb):
        logger.debug("Leaving the context %r ...", self)
        if not self.local_path and self._current_path:
            logger.debug(f"Removing local clone of {self.repo_url} @ '{self._current_path}'")
            shutil.rmtree(self._current_path, ignore_errors=True)


def __make_requester__(jwt: str = None, token: str = None, base_url: str = DEFAULT_BASE_URL) -> Requester:
    return Requester(token, None, jwt, base_url,
                     DEFAULT_TIMEOUT, "PyGithub/Python", DEFAULT_PER_PAGE,
                     True, None, None)
