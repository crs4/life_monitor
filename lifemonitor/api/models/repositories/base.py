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

import filecmp
import io
import json
import logging
import os
from abc import abstractclassmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import git
import giturlparse
import lifemonitor.api.models.issues as issues
import requests
from lifemonitor.api.models.repositories.config import WorkflowRepositoryConfig
from lifemonitor.exceptions import IllegalStateException, LifeMonitorException
from lifemonitor.test_metadata import get_roc_suites, get_workflow_authors
from lifemonitor.utils import to_camel_case
from rocrate.rocrate import Metadata, ROCrate

from .files import RepositoryFile, WorkflowFile

# set module level logger
logger = logging.getLogger(__name__)

DEFAULT_IGNORED_FILES = ['.git']


class WorkflowRepository():

    def __init__(self, local_path: Optional[str] = None,
                 url: Optional[str] = None,
                 name: Optional[str] = None,
                 license: Optional[str] = None,
                 exclude: Optional[List[str]] = None) -> None:
        self._local_path = local_path
        self._metadata = None
        self.exclude = exclude or DEFAULT_IGNORED_FILES
        self._config = None
        self._url = url
        self._name = name
        self._license = license

    @property
    def local_path(self) -> str:
        return self._local_path

    @property
    def files(self) -> List[RepositoryFile]:
        pass

    @property
    def metadata(self) -> WorkflowRepositoryMetadata:
        if not self._metadata:
            try:
                self._metadata = WorkflowRepositoryMetadata(self, init=False, exclude=self.exclude)
            except ValueError:
                return None
        return self._metadata

    @property
    def _remote_parser(self) -> giturlparse.GitUrlParsed:
        try:
            r = git.Repo(self.local_path)
            remote = next((x for x in r.remotes if x.name == 'origin'), r.remotes[0])
            assert remote, "Unable to find a Git remote"
            return giturlparse.parse(remote.url)
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            raise LifeMonitorException(f"Not valid workflow repository: {e}")

    @property
    def name(self) -> str:
        if not self._name:
            try:
                self._name = self._remote_parser.name
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
                raise LifeMonitorException(f"Not valid workflow repository: {e}")
        assert self._name, "Unable to detect repository name"
        return self._name

    @property
    def full_name(self) -> str:
        try:
            parser = self._remote_parser
            return f"{parser.owner}/{parser.name}"
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            raise LifeMonitorException(f"Not valid workflow repository: {e}")

    @property
    def https_url(self) -> str:
        if not self._url:
            try:
                self._url = self._remote_parser.url2https.replace('.git', '')
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
                raise LifeMonitorException(f"Not valid workflow repository: {e}")
        assert self._url, "Unable to detect repository url"
        return self._url

    @property
    def license(self) -> Optional[str]:
        if not self._license:
            try:
                parser = self._remote_parser
                if parser.host == 'github.com':
                    l_info = requests.get(f"https://api.github.com/repos/{self.full_name}/license")
                    self._license = l_info.json()['license']['spdx_id']
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.error(e)
        return self._license

    @abstractclassmethod
    def find_file_by_pattern(self, search: str, path: str = '.') -> RepositoryFile:
        pass

    @abstractclassmethod
    def find_file_by_name(self, name: str, path: str = '.') -> RepositoryFile:
        pass

    @abstractclassmethod
    def find_workflow(self) -> WorkflowFile:
        pass

    def contains(self, file: RepositoryFile) -> bool:
        return self.__contains__(self.files, file)

    @staticmethod
    def _issue_name_included(issue_name: str,
                             include_list: List[str] | None = None,
                             exclude_list: List[str] | None = None) -> bool:
        if include_list and (issue_name in [to_camel_case(_) for _ in include_list]):
            return True

        if exclude_list is None:
            return True

        return issue_name not in [to_camel_case(_) for _ in exclude_list]

    def check(self, fail_fast: bool = True,
              include=None, exclude=None) -> IssueCheckResult:
        found_issues = []
        issue_graph = issues.get_issue_graph()

        visited = set()
        queue = [i for i in issue_graph.neighbors(issues.ROOT_ISSUE)
                 if self._issue_name_included(i.__name__, include, exclude)]
        while queue:
            issue_type = queue.pop()
            if issue_type not in visited:
                issue = issue_type()
                failed = issue.check(self)
                visited.add(issue_type)
                if not failed:
                    neighbors = [i for i in issue_graph.neighbors(issue_type)
                                 if self._issue_name_included(i.__name__, include, exclude)]
                    queue.extend(neighbors)
                else:
                    found_issues.append(issue)
                    if fail_fast:
                        break
        return IssueCheckResult(self, list(visited), found_issues)

    @classmethod
    def __contains__(cls, files, file) -> bool:
        return cls.__find_file__(files, file) is not None

    @classmethod
    def __find_file__(cls, files, file) -> RepositoryFile | None:
        for f in files:
            if f == file or (f.name == file.name and f.dir == file.dir):
                return f
        return None

    @classmethod
    def __file_pointer__(cls, f: RepositoryFile):
        fp = None
        if os.path.exists(f.path):
            fp = open(f.path, 'rb')
        else:
            logger.debug("Reading file content: %r", f.get_content(binary_mode=False).encode())
            fp = io.BytesIO(f.get_content(binary_mode=False).encode())
        return fp

    @classmethod
    def __compare_files__(cls, f1: RepositoryFile, f2: RepositoryFile):
        bufsize = filecmp.BUFSIZE
        with cls.__file_pointer__(f1) as fp1, cls.__file_pointer__(f2) as fp2:
            while True:
                b1 = fp1.read(bufsize)
                b2 = fp2.read(bufsize)
                if b1 != b2:
                    return False
                if not b1:
                    return True

    @classmethod
    def __compare__(cls, left_files, right_files, exclude: List[str] = None):
        missing_left = [_ for _ in right_files
                        if not cls.__contains__(left_files, _) and (not exclude or _.name not in exclude)]
        logger.debug("Missing Left: %r", missing_left)
        to_check = [(f, cls.__find_file__(right_files, f)) for f in left_files if not exclude or f.name not in exclude]
        logger.debug("To Check: %r", to_check)
        missing_right = [_ for _ in left_files
                         if not cls.__contains__(right_files, _) and (not exclude or _.name not in exclude)]
        logger.debug("Missing Right: %r", missing_right)
        differences = []
        for lf, rf in to_check:
            logger.warning("Comparing: %r %r", lf, rf)
            if lf and rf and not cls.__compare_files__(lf, rf):
                differences.append((lf, rf))
        logger.debug("Differences: %r", differences)
        return missing_left, missing_right, differences

    def compare_to(self, repo: WorkflowRepository, exclude: List[str] = None) -> Tuple[List[RepositoryFile],
                                                                                       List[RepositoryFile],
                                                                                       List[Tuple[RepositoryFile, RepositoryFile]]]:
        assert repo and isinstance(repo, WorkflowRepository), repo
        return self.__compare__(self.files, repo.files, exclude=exclude)

    def generate_metadata(self,
                          workflow_name: Optional[str] = None,
                          workflow_version: str = "main",
                          license: Optional[str] = None,
                          repo_url: Optional[str] = None,
                          **kwargs) -> WorkflowRepositoryMetadata:
        workflow = self.find_workflow()
        if not workflow:
            raise IllegalStateException("No workflow found", instance=self)
        workflow_type = workflow.type
        logger.debug("Detected workflow type: %r", workflow_type)
        try:
            from ..rocrate import generators
            generators.generate_crate(workflow_type,
                                      workflow_name=workflow_name or self.name,
                                      workflow_version=workflow_version,
                                      local_repo_path=self.local_path,
                                      license=license or self.license,
                                      repo_url=repo_url or self.https_url, **kwargs)
            self._metadata = WorkflowRepositoryMetadata(self, init=False, exclude=self.exclude,
                                                        local_path=self._local_path)
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            self._metadata = WorkflowRepositoryMetadata(self, init=True, exclude=self.exclude,
                                                        local_path=self._local_path)
            self._metadata.write(self._local_path)
        self.add_file(self._metadata.repository_file)
        return self._metadata

    @property
    def config(self) -> WorkflowRepositoryConfig:
        if self._config is None:
            try:
                self._config = WorkflowRepositoryConfig(self.local_path)
            except ValueError:
                pass
        return self._config

    def generate_config(self, ignore_existing=False) -> WorkflowFile:
        current_config = self.config
        if current_config and not ignore_existing:
            raise IllegalStateException("Config exists")
        self._config = WorkflowRepositoryConfig.new(self.local_path, workflow_title=self.metadata.main_entity_name if self.metadata else None)
        return self._config

    def write_zip(self, target_path: str):
        if not self.metadata:
            raise IllegalStateException(detail="Missing RO Crate metadata")
        return self.metadata.write_zip(target_path)

    def write(self, target_path: str, overwrite: bool = False):
        for f in self.files:
            base_path = os.path.join(target_path, f.dir)
            file_path = os.path.join(base_path, f.name)
            os.makedirs(base_path, exist_ok=True)
            file_exists = os.path.isfile(file_path)
            if not file_exists or overwrite:
                logger.debug("%s file: %r", "Overwriting" if file_exists else "Writing", file_path)
                with open(file_path, "w") as out:
                    out.write(f.get_content())


class IssueCheckResult:

    def __init__(self, repo: WorkflowRepository,
                 checked: List[issues.WorkflowRepositoryIssue],
                 issues: List[issues.WorkflowRepositoryIssue]):
        self.repo = repo
        self.checked = checked
        self.issues = issues
        self.created = datetime.utcnow()
        self._solved = None

    def __repr__(self) -> str:
        return f"Check repo {self.repo.local_path} @ {self.created} " \
            f"=> checks: {len(self.checked)}, issues: {len(self.issues)}"

    def get_issue(self, issue_name: str) -> issues.WorkflowRepositoryIssue:
        return next((_ for _ in self.issues if _.name == issue_name), None)

    def found_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def solved(self) -> List[issues.WorkflowRepositoryIssue]:
        if not self._solved:
            self._solved = [i for i in self.checked if i not in self.issues]
        return self._solved


class WorkflowRepositoryMetadata(ROCrate):

    DEFAULT_METADATA_FILENAME = Metadata.BASENAME

    def __init__(self, repo: WorkflowRepository,
                 local_path: str = None, gen_preview=False, init=False, exclude=None):
        super().__init__(source=local_path or repo.local_path, gen_preview=gen_preview, init=init, exclude=exclude)
        self.repository = repo
        self._file = None

    def get_workflow(self) -> WorkflowFile:
        if self.mainEntity and self.mainEntity.id:
            lang = self.mainEntity.get("programmingLanguage", None)
            path, filename = os.path.split(self.mainEntity.id)
            return WorkflowFile(self.source, filename,
                                type=lang.get("name", lang.id).lower() if lang else None,
                                dir=path)
        return None

    @property
    def main_entity_name(self):
        return self.mainEntity.get("name", self.mainEntity.id) if self.mainEntity else None

    @property
    def dataset_name(self):
        return self.name

    def get_roc_suites(self):
        return get_roc_suites(self)

    def get_authors(self, suite_id: str = None) -> List[Dict]:
        return get_workflow_authors(self, suite_id=suite_id)

    def get_get_roc_suite(self, roc_suite_identifier):
        try:
            return self.get_roc_suites()[roc_suite_identifier]
        except KeyError:
            logger.warning("Unable to find the roc_suite with identifier: %r", roc_suite_identifier)
        return None

    @property
    def local_path(self) -> str:
        logger.debug("SOURCE: %r - ID: %r", self.source, self.metadata.id)
        return os.path.join(self.source, self.metadata.id)

    @property
    def repository_file(self) -> MetadataRepositoryFile:
        if not self._file:
            self._file = MetadataRepositoryFile(self)
        return self._file

    def to_json(self) -> Dict:
        file = self.repository.find_file_by_name(self.metadata.id)
        return json.loads(file.get_content(binary_mode=False)) if file else None


class MetadataRepositoryFile(RepositoryFile):

    def __init__(self, metadata: WorkflowRepositoryMetadata) -> None:
        super().__init__(metadata.repository.local_path,
                         WorkflowRepositoryMetadata.DEFAULT_METADATA_FILENAME, 'json', '.')
        self.metadata = metadata

    def get_content(self, binary_mode: bool = False):
        return json.dumps(self.metadata.to_json(), indent=4, sort_keys=True)
