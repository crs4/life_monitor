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
from typing import Any, Dict, List, Union

from lifemonitor.api.models.repositories.base import (
    WorkflowRepository, WorkflowRepositoryMetadata)
from lifemonitor.api.models.repositories.config import WorkflowRepositoryConfig
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

    def __init__(self, content: ContentFile, type: str = None, dir: str = '.') -> None:
        super().__init__(None, content.name, type or content.type, dir, None)
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
                 ref: str = None, rev: str = None,
                 local_path: str = None, auto_cleanup: bool = True) -> None:
        super().__init__(requester, headers, attributes, completed)
        self.ref = ref if ref is not None else f"refs/heads/{self.default_branch}"
        self.rev = rev
        self.auto_cleanup = auto_cleanup
        self._metadata = None
        self._local_repo: LocalWorkflowRepository = None
        self._local_path = local_path
        self._config = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} bound to {self.url} (ref: {self.ref}, rev: {self.rev})"

    def __get_files__(self, path: str, ref: str) -> List[GitRepositoryFile]:
        files = []
        for e in self.get_contents(path, ref=ref):
            if e.type == 'file':
                files.append(GitRepositoryFile(e, dir=path))
            elif e.type == 'dir':
                files.extend(self.__get_files__(e.path, ref=ref))
        return files

    @property
    def files(self):
        return self.__get_files__('.', ref=self.ref or self.default_branch)

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

    def find_remote_file_by_pattern(self, search: str, ref: str = None,
                                    path: str = ".", include_subdirs: bool = False) -> GitRepositoryFile:
        for e in self.get_contents(path, ref=ref or self.ref):
            logger.debug("Name: %r -- type: %r", e.name, e.type)
            c_file = None
            if include_subdirs and e.type == "dir":
                c_file = self.find_remote_file_by_pattern(search, ref=ref, path=f"{path}/{e.name}")
            if re.search(search, e.name):
                c_file = e
            if c_file:
                return GitRepositoryFile(c_file)
        return None

    def find_file_by_pattern(self, search: str, ref: str = None) -> GitRepositoryFile:
        if not self.local_repo:
            return self.find_remote_file_by_pattern(search, ref=ref)
        return self.local_repo.find_file_by_pattern(search)

    def find_remote_file_by_name(self, name: str, ref: str = None,
                                 path: str = '.', include_subdirs: bool = False) -> GitRepositoryFile:
        for e in self.get_contents(path, ref=ref or self.ref):
            logger.debug("Name: %r -- type: %r", e.name, e.type)
            c_file = None
            if include_subdirs and e.type == "dir":
                c_file = self.find_remote_file_by_name(name, ref=ref, path=f"{path}/{e.name}")
            if e.name == name:
                c_file = e
            if c_file:
                return GitRepositoryFile(c_file)
        return None

    def find_file_by_name(self, name: str, ref: str = None, path: str = '.') -> GitRepositoryFile:
        if not self.local_repo:
            return self.find_remote_file_by_name(name, ref=ref, path=path)
        return self.local_repo.find_file_by_name(name, path=path)

    def find_remote_workflow(self, ref: str = None, path: str = '.') -> GitRepositoryFile:
        for e in self.get_contents(path, ref=ref or self.ref):
            logger.debug("Checking: %r (type: %s)", e.name, e.type)
            if e.type == 'dir':
                wf = self.find_remote_workflow(ref=ref, path=f"{path}/{e.name}")
            else:
                wf = WorkflowFile.is_workflow(GitRepositoryFile(e))
            logger.debug("Is workflow: %r", wf)
            if wf:
                return wf
        return None

    def find_workflow(self, ref: str = None) -> WorkflowFile:
        logger.debug("Local repo: %r", self.local_repo)
        if self.local_repo:
            return self.local_repo.find_workflow()
        return self.find_remote_workflow(ref=ref)

    def generate_metadata(self):
        if self._local_repo:
            if not self.auto_cleanup:
                logger.warning("'auto cleanup' disabled: local temp folder "
                               f"'{self.local_repo._local_path}' will not be deleted")
            else:
                self.cleanup()
        return self.local_repo.generate_metadata()

    def generate_config(self, ignore_existing=False) -> WorkflowRepositoryConfig:
        current_config = self.config
        if current_config and not ignore_existing:
            raise IllegalStateException("Config exists")
        self._config = WorkflowRepositoryConfig.new(self.local_path,
                                                    workflow_title=self.metadata.main_entity_name if self.metadata else None,
                                                    main_branch=self.default_branch)
        return self._config

    def clone(self, branch: str, local_path: str = None) -> RepoCloneContextManager:
        assert isinstance(branch, str), branch
        assert local_path is None or isinstance(str, local_path), local_path
        return RepoCloneContextManager(self.clone_url, repo_branch=branch, local_path=local_path)

    def write_zip(self, target_path: str):
        return self.local_repo.write_zip(target_path=target_path)

    @property
    def local_repo(self) -> LocalWorkflowRepository:
        if not self._local_repo:
            local_path = self._local_path or tempfile.mkdtemp(dir=BaseConfig.BASE_TEMP_FOLDER)
            logger.debug("Cloning %r", self)
            clone_repo(self.clone_url, ref=self.ref, target_path=local_path)
            self._local_repo = LocalWorkflowRepository(local_path=local_path)
        return self._local_repo

    @property
    def local_path(self) -> str:
        return self.local_repo.local_path if self.local_repo else None

    def __del__(self):
        if self.auto_cleanup:
            self.cleanup()

    def cleanup(self):
        logger.debug("Repository cleanup")
        if self._local_repo:
            logger.debug("Removing temp folder %r of %r", self.local_path, self)
            shutil.rmtree(self.local_repo.local_path, ignore_errors=True)
            self._local_repo = None


class GithubWorkflowRepository(InstallationGithubWorkflowRepository):

    def __init__(self, full_name_or_id: str, token: str = None,
                 ref: str = None, local_path: str = None, auto_cleanup: bool = True) -> None:
        assert isinstance(full_name_or_id, (str, int)), full_name_or_id
        url_base = "/repositories/" if isinstance(full_name_or_id, int) else "/repos/"
        url = f"{url_base}{full_name_or_id}"
        super().__init__(
            __make_requester__(token=token), headers={}, attributes={'url': url}, completed=False,
            ref=ref, local_path=local_path, auto_cleanup=auto_cleanup)

    @classmethod
    def from_url(cls, url: str, token: str = None, ref: str = None,
                 local_path: str = None, auto_cleanup: bool = True) -> GithubWorkflowRepository:
        repo_url = url.replace('.git', '')
        if repo_url.startswith('https://github.com'):
            return cls(repo_url.replace('https://github.com/', ''),
                       token=token, ref=ref, local_path=local_path, auto_cleanup=auto_cleanup)
        elif repo_url.startswith('git@github.com'):
            return cls(repo_url.replace('git@github.com:', ''),
                       token=token, ref=ref, local_path=local_path, auto_cleanup=auto_cleanup)


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
            clone_repo(self.repo_url, ref=self.repo_branch,
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
    return Requester(token or None, None, jwt, base_url,
                     DEFAULT_TIMEOUT, "PyGithub/Python", DEFAULT_PER_PAGE,
                     True, None, None)
