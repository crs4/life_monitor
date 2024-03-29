# Copyright (c) 2020-2024 CRS4
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
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from rocrate.rocrate import Metadata, ROCrate

import lifemonitor.api.models.issues as issues
from lifemonitor.api.models.repositories.config import WorkflowRepositoryConfig
from lifemonitor.exceptions import IllegalStateException
from lifemonitor.test_metadata import get_roc_suites, get_workflow_authors
from lifemonitor.utils import get_current_username, to_camel_case

from .files import RepositoryFile, WorkflowFile

# set module level logger
logger = logging.getLogger(__name__)

DEFAULT_IGNORED_FILES = ['.git']


class WorkflowRepository():

    def __init__(self, local_path: str,
                 remote_url: Optional[str] = None,
                 owner: Optional[str] = None,
                 name: Optional[str] = None,
                 license: Optional[str] = None,
                 exclude: Optional[List[str]] = None,
                 owner_as_system_user: bool = False) -> None:
        if not local_path:
            raise ValueError("empty local_path argument")
        self._local_path = local_path
        self._metadata = None
        self.exclude = exclude if exclude is not None else DEFAULT_IGNORED_FILES
        self._config = None
        self._remote_url = remote_url
        self._name = name
        self._owner = owner
        if not owner and owner_as_system_user:
            self._owner = get_current_username()
        self._license = license

    @property
    def local_path(self) -> str:
        return self._local_path

    @property
    def files(self) -> List[RepositoryFile]:
        raise NotImplementedError()

    @property
    def metadata(self) -> Optional[WorkflowRepositoryMetadata]:
        if not self._metadata:
            try:
                self._metadata = WorkflowRepositoryMetadata(self, init=False, exclude=self.exclude)
            except ValueError:
                return None
        return self._metadata

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def owner(self) -> str:
        return self._owner

    @owner.setter
    def owner(self, value):
        self._owner = value

    @property
    def full_name(self) -> str:
        if self.owner:
            return f"{self.owner}/{self.name}"
        return self.name

    @property
    def remote_url(self) -> str:
        return self._remote_url

    @remote_url.setter
    def remote_url(self, value):
        self._remote_url = value

    @property
    def license(self) -> Optional[str]:
        return self._license

    @license.setter
    def license(self, value):
        self._license = value

    @abstractclassmethod
    def find_file_by_pattern(self, search: str, path: str = '.') -> RepositoryFile:
        raise NotImplementedError()

    @abstractclassmethod
    def find_file_by_name(self, name: str, path: str = '.') -> RepositoryFile:
        raise NotImplementedError()

    @abstractclassmethod
    def find_workflow(self) -> WorkflowFile:
        raise NotImplementedError()

    def contains(self, file: RepositoryFile) -> bool:
        return self.__contains__(self.files, file)

    @staticmethod
    def _issue_name_included(issue_name: str,
                             include_list: Optional[List[str]] = None,
                             exclude_list: Optional[List[str]] = None) -> bool:
        if include_list and (issue_name in [to_camel_case(_) for _ in include_list]):
            return True

        if exclude_list is None:
            return True

        return issue_name not in [to_camel_case(_) for _ in exclude_list]

    def check(self, fail_fast: bool = True,
              include=None, exclude=None) -> IssueCheckResult:
        found_issues = []
        issue_graph = issues.get_issue_graph()

        checked = set()
        visited = set()
        queue = [i for i in issue_graph.neighbors(issues.ROOT_ISSUE)
                 if self._issue_name_included(i.__name__, include, exclude)]
        while queue:
            issue_type = queue.pop()
            if issue_type not in visited:
                issue = issue_type()
                try:
                    failed = issue.check(self)
                except Exception as e:
                    logger.error("Issue %s failed to run.  It raised an exception: %s",
                                 issue_type.__name__, e)
                    continue  # skip this issue by not marking it as visited (otherwise it shows as "passed")
                visited.add(issue_type)
                checked.add(issue)
                if not failed:
                    neighbors = [i for i in issue_graph.neighbors(issue_type)
                                 if self._issue_name_included(i.__name__, include, exclude)]
                    queue.extend(neighbors)
                else:
                    found_issues.append(issue)
                    if fail_fast:
                        break
        return IssueCheckResult(self, list(checked), found_issues)

    @classmethod
    def __contains__(cls, files, file) -> bool:
        return cls.__find_file__(files, file) is not None

    @classmethod
    def __find_file__(cls, files, file) -> Optional[RepositoryFile]:
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
            content = f.get_content(binary_mode=True)
            if content:
                logger.debug("Reading file content: %r bytes", len(content))
                fp = io.BytesIO(content)
            else:
                logger.debug("Reading file content: %s", "<empty content>")
                fp = io.BytesIO(b"")
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
    def __compare__(cls, left_files, right_files, exclude: Optional[List[str]] = None):
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

    def compare_to(self, repo: WorkflowRepository, exclude: Optional[List[str]] = None) -> Tuple[List[RepositoryFile],
                                                                                                 List[RepositoryFile],
                                                                                                 List[Tuple[RepositoryFile, RepositoryFile]]]:
        assert repo and isinstance(repo, WorkflowRepository), repo
        return self.__compare__(self.files, repo.files, exclude=exclude)

    @property
    def config(self) -> Optional[WorkflowRepositoryConfig]:
        if self._config is None and self.local_path:
            try:
                self._config = WorkflowRepositoryConfig(self.local_path)
            except ValueError:
                pass
        return self._config

    def generate_config(self, ignore_existing=False,
                        workflow_title: Optional[str] = None,
                        public: bool = False, main_branch: Optional[str] = None) -> WorkflowRepositoryConfig:
        current_config = self.config
        if current_config and not ignore_existing:
            raise IllegalStateException("Config exists")
        if not self.local_path:
            raise IllegalStateException("local_path not defined. Can't generate WorkflowRepositoryConfig")
        self._config = WorkflowRepositoryConfig.new(self.local_path,
                                                    workflow_title=workflow_title,
                                                    public=public,
                                                    main_branch=main_branch if main_branch else getattr(self, "main_branch", "main"))
        return self._config

    def write_zip(self, target_path: str):
        if not self.metadata:
            raise IllegalStateException(detail="Missing RO-Crate metadata")
        return self.metadata.write_zip(target_path)

    def write(self, target_path: str, overwrite: bool = False) -> None:
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

    def get_issue(self, issue_name: str) -> Optional[issues.WorkflowRepositoryIssue]:
        return next((_ for _ in self.issues if _.name == issue_name), None)

    def found_issues(self) -> bool:
        return len(self.issues) > 0

    def is_checked(self, issue: Union[Type[issues.WorkflowRepositoryIssue], issues.WorkflowRepositoryIssue]) -> bool:
        if issue and issue in self.checked:
            return True
        if isinstance(issue, issues.WorkflowRepositoryIssue):
            for issue_type in self.checked:
                if isinstance(issue, issue_type):
                    return True
        return False

    @property
    def solved(self) -> List[issues.WorkflowRepositoryIssue]:
        if not self._solved:
            self._solved = [i for i in self.checked if i not in self.issues]
        return self._solved


class WorkflowRepositoryMetadata(ROCrate):

    DEFAULT_METADATA_FILENAME = Metadata.BASENAME

    def __init__(self, repo: WorkflowRepository,
                 local_path: Optional[str] = None, gen_preview=False, init=False, exclude=None):
        super().__init__(source=local_path or repo.local_path, gen_preview=gen_preview, init=init, exclude=exclude)
        self.repository = repo
        self._file = None

    def get_workflow(self) -> Optional[WorkflowFile]:
        if self.mainEntity and self.mainEntity.id:
            if self.source is None:
                raise IllegalStateException(
                    f"Internal error: trying to construct WorkflowFile but self.source is '{self.source}")
            lang = self.mainEntity.get("programmingLanguage", None)
            path, filename = os.path.split(self.mainEntity.id)
            return WorkflowFile(str(self.source), filename,
                                type=lang.get("name", lang.id).lower() if lang else None,
                                dir=path)
        return None

    @property
    def main_entity_name(self):
        return self.mainEntity.get("name", self.mainEntity.id) if self.mainEntity else None

    @property
    def dataset_name(self):
        return self.name

    # TODO: the type of a roc_suite is probably better defined than "Any"
    def get_roc_suites(self) -> Optional[Dict[str, Any]]:
        return get_roc_suites(self)

    def get_authors(self, suite_id: Optional[str] = None) -> List[Dict]:
        return get_workflow_authors(self, suite_id=suite_id)

    def get_get_roc_suite(self, roc_suite_identifier) -> Any:
        suites = self.get_roc_suites()
        if suites is not None:
            try:
                return suites[roc_suite_identifier]
            except KeyError:
                logger.warning("Unable to find the roc_suite with identifier: %r", roc_suite_identifier)
        return None

    @property
    def local_path(self) -> str:
        logger.debug("SOURCE: %r - ID: %r", self.source, self.metadata.id)
        return os.path.join(str(self.source), self.metadata.id)

    @property
    def repository_file(self) -> MetadataRepositoryFile:
        if not self._file:
            self._file = MetadataRepositoryFile(self)
        return self._file

    def to_json(self) -> Optional[Dict[str, Any]]:
        file = self.repository.find_file_by_name(self.metadata.id)
        if file:
            text = file.get_content(binary_mode=False)
            if text:
                return json.loads(text)
        return None


class MetadataRepositoryFile(RepositoryFile):

    def __init__(self, metadata: WorkflowRepositoryMetadata) -> None:
        super().__init__(metadata.repository.local_path,
                         WorkflowRepositoryMetadata.DEFAULT_METADATA_FILENAME, 'json', '.')
        self.metadata = metadata

    def get_content(self, binary_mode: bool = False) -> str:
        # TODO: why parse a JSON string just to re-serialize it?
        return json.dumps(self.metadata.to_json(), indent=4, sort_keys=True)
