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

import pytest
from lifemonitor.api.models.issues.general.repo_layout import MissingROCrateFile
from lifemonitor.api.models.repositories import GithubWorkflowRepository

logger = logging.getLogger(__name__)


@pytest.fixture
def repository() -> GithubWorkflowRepository:
    repo = GithubWorkflowRepository('iwc-workflows/gromacs-mmgbsa', ref="HEAD")
    logger.debug("Github workflow repository: %r", repo)
    return repo


@pytest.fixture
def issue() -> MissingROCrateFile:
    return MissingROCrateFile()


def test_check_true(repository: GithubWorkflowRepository, issue: MissingROCrateFile):
    logger.debug("Workflow RO-Crate: %r", repository)

    # detect workflow metadata
    metadata = repository.metadata
    logger.debug("Detected workflow metadata: %r", metadata)
    assert metadata, "Workflow metadata not found"

    # test if issue doesn't apply to the current repo
    result = issue.check(repository)
    assert result is False, "Workflow RO-Crate should have the workflow file"


def test_check_false(repository: GithubWorkflowRepository, issue: MissingROCrateFile):
    logger.debug("Workflow RO-Crate: %r", repository)

    # detect workflow file
    metadata = repository.metadata
    logger.debug("Detected workflow file: %r", metadata)
    assert metadata, "Workflow file not found"

    # set reference to local copy of the remote repo
    local = repository.local_repo

    # temporary remove workflow metadata from the local repo
    local.remove_file(metadata.repository_file)
    logger.debug(local._transient_files)
    assert local.metadata is None, "Unexpected workflow on repo"

    # test if issue applies to the local modified repo
    result = issue.check(local)
    assert result is True, "Workflow RO-Crate should not have metadata"

    # test proposed changes
    assert issue.has_changes(), "No changes found"
    changes = issue.get_changes(local)
    assert len(changes) == 1, "Unexpected number of changes"
    metadata_file = changes[0]
    assert metadata_file == local.metadata.repository_file, "Unexpected metadata file"
    assert metadata_file.get_content() == local.metadata.repository_file.get_content(), "Unexpected metadata file content"
