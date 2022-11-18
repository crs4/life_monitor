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

import logging
import os

import pytest
from lifemonitor.api.models.issues.general.repo_layout import MissingWorkflowFile
from lifemonitor.api.models.repositories import ZippedWorkflowRepository
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository

logger = logging.getLogger(__name__)


@pytest.fixture
def crates_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crates')


@pytest.fixture
def repository(crates_path) -> LocalWorkflowRepository:
    repo = ZippedWorkflowRepository(
        os.path.join(crates_path, 'ro-crate-galaxy-sortchangecase.crate.zip'))
    return repo


@pytest.fixture
def issue() -> MissingWorkflowFile:
    return MissingWorkflowFile()


def test_check_true(repository: LocalWorkflowRepository, issue: MissingWorkflowFile):
    logger.debug("Workflow RO-Crate: %r", repository)

    # detect workflow file
    workflow_file = repository.find_workflow()
    logger.debug("Detected workflow file: %r", workflow_file)
    assert workflow_file, "Workflow file not found"

    # test if issue doesn't apply to the current repo
    result = issue.check(repository)
    assert result is False, "Workflow RO-Crate should have the workflow file"


def test_check_false(repository: LocalWorkflowRepository, issue: MissingWorkflowFile):
    logger.debug("Workflow RO-Crate: %r", repository)

    # detect workflow file
    workflow_file = repository.find_workflow()
    logger.debug("Detected workflow file: %r", workflow_file)
    assert workflow_file, "Workflow file not found"

    # temporary remove workflow file from repo
    repository.remove_file(workflow_file)
    logger.debug(repository._transient_files)
    assert repository.find_workflow() is None, "Unexpected workflow on repo"

    # test if issue applies to the current modified repo
    result = issue.check(repository)
    assert result is True, "Workflow RO-Crate should not have the workflow file"
