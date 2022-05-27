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

import filecmp
import io
import json
import logging
import os
from abc import abstractclassmethod
from datetime import datetime
from typing import Dict, List, Tuple

import lifemonitor.api.models.issues as issues
from lifemonitor.api.models.repositories.config import WorkflowRepositoryConfig
from lifemonitor.api.models.repositories.files import (RepositoryFile,
                                                       WorkflowFile)
from lifemonitor.exceptions import IllegalStateException
from lifemonitor.test_metadata import get_roc_suites, get_workflow_authors
from lifemonitor.utils import to_camel_case
from rocrate.rocrate import Metadata, ROCrate

# set module level logger
logger = logging.getLogger(__name__)

DEFAULT_IGNORED_FILES = ['.git']


class WorkflowRepository():

    def __init__(self, local_path: str = None, exclude: List[str] = None) -> None:
        self._local_path = local_path
        self._metadata = None
        self.exclude = exclude or DEFAULT_IGNORED_FILES
        self._config = None

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

    @abstractclassmethod
    def find_file_by_pattern(self, search: str) -> RepositoryFile:
        pass

    @abstractclassmethod
    def find_file_by_name(self, name: str) -> RepositoryFile:
        pass

    @abstractclassmethod
    def find_workflow(self) -> WorkflowFile:
        pass

    def contains(self, file: RepositoryFile) -> bool:
        return self.__contains__(self.files, file)

    def check(self, fail_fast: bool = True,
              include=None, exclude=None) -> IssueCheckResult:
        found_issues = []
        checked = []
        for issue_type in issues.find_issue_types():
            if (not exclude or issue_type.__name__ not in [to_camel_case(_) for _ in exclude]) or \
                    (not include or issue_type.__name__ in [to_camel_case(_) for _ in include]):
                issue = issue_type()
                to_be_solved = issue.check(self)
                checked.append(issue)
                if to_be_solved:
                    found_issues.append(issue)
                    if fail_fast:
                        break
        return IssueCheckResult(self, checked, found_issues)

    @classmethod
    def __contains__(cls, files, file) -> bool:
        return cls.__find_file__(files, file) is not None

    @classmethod
    def __find_file__(cls, files, file) -> RepositoryFile:
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

    def compare(self, repo: WorkflowRepository, exclude: List[str] = None) -> Tuple[List[RepositoryFile],
                                                                                    List[RepositoryFile],
                                                                                    List[Tuple[RepositoryFile, RepositoryFile]]]:
        assert repo and isinstance(repo, WorkflowRepository), repo
        return self.__compare__(self.files, repo.files, exclude=exclude)

    def generate_metadata(self) -> WorkflowRepositoryMetadata:
        self._metadata = WorkflowRepositoryMetadata(self, init=True, exclude=self.exclude)
        self._metadata.write(self._local_path)
        return self._metadata

    @property
    def config(self) -> WorkflowRepositoryConfig:
        if not self._config:
            if not os.path.exists(os.path.join(self.local_path, WorkflowRepositoryConfig.FILENAME)):
                return None
            else:
                self._config = WorkflowRepositoryConfig(self.local_path)
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

    def get_workflow(self):
        if self.mainEntity and self.mainEntity.id:
            lang = self.mainEntity.get("programmingLanguage", None)
            return WorkflowFile(
                os.path.join(self.source, self.mainEntity.id),
                lang.get("name", lang.id).lower() if lang else None,
                self.mainEntity.get("name", self.mainEntity.id) if self.mainEntity else None
            )
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
