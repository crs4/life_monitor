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
import json

import logging
import os
from abc import abstractclassmethod
from datetime import datetime
from typing import Dict, List

import lifemonitor.api.models.issues as issues
from lifemonitor.api.models.repositories.files import (RepositoryFile,
                                                       WorkflowFile)
from lifemonitor.test_metadata import get_roc_suites
from rocrate.rocrate import ROCrate

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepository():

    def __init__(self, local_path: str = None) -> None:
        self._local_path = local_path
        self._metadata = None

    @property
    def local_path(self) -> str:
        return self._local_path

    @property
    def metadata(self) -> WorkflowRepositoryMetadata:
        if not self._metadata:
            try:
                self._metadata = WorkflowRepositoryMetadata(self, init=False)
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

    def check(self, fail_fast: bool = True) -> IssueCheckResult:
        found_issues = []
        checked = []
        for issue_type in issues.WorkflowRepositoryIssue.all():
            issue = issue_type()
            to_be_solved = issue.check(self)
            checked.append(issue)
            if to_be_solved:
                found_issues.append(issue)
                if fail_fast:
                    break
        return IssueCheckResult(self, checked, found_issues)

    def make_crate(self):
        self._metadata = WorkflowRepositoryMetadata(self, init=True)
        self._metadata.write(self._local_path)

    def write_zip(self, target_path: str):
        self.metadata.write_zip(target_path)


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

    @property
    def solved(self) -> List[issues.WorkflowRepositoryIssue]:
        if not self._solved:
            self._solved = [i for i in self.checked if i not in self.issues]
        return self._solved


class WorkflowRepositoryMetadata(ROCrate):

    def __init__(self, repo: WorkflowRepository,
                 local_path: str = None, gen_preview=False, init=False):
        super().__init__(source=local_path or repo.local_path, gen_preview=gen_preview, init=init)
        self.repository = repo

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

    def to_json(self) -> Dict:
        file = self.repository.find_file_by_name(self.metadata.id)
        return json.loads(file.get_content(binary_mode=False)) if file else None
