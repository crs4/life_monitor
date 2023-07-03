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

from lifemonitor.api.models.repositories.files.base import RepositoryFile
from lifemonitor.api.models.repositories.files.workflows import WorkflowFile
from lifemonitor.api.models.repositories.files.workflows.galaxy import \
    GalaxyWorkflowFile
from lifemonitor.api.models.repositories.files.workflows.jupyter import \
    JupyterWorkflowFile
from lifemonitor.api.models.repositories.files.workflows.nextflow import \
    NextflowWorkflowFile
from lifemonitor.api.models.repositories.files.workflows.other import \
    OtherWorkflowFile
from lifemonitor.api.models.repositories.files.workflows.snakemake import \
    SnakemakeWorkflowFile
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from tests.conftest_helpers import get_github_token

logger = logging.getLogger(__name__)


@pytest.fixture
def repo_path() -> str:
    return '/tmp/test'


@pytest.fixture
def github_token():
    return get_github_token()


@pytest.fixture
def remote_galaxy_github_repository(github_token) -> GithubWorkflowRepository:
    return GithubWorkflowRepository("iwc-workflows/fragment-based-docking-scoring", token=github_token)


@pytest.fixture
def remote_snakemake_github_repository(github_token) -> GithubWorkflowRepository:
    return GithubWorkflowRepository("crs4/fair-crcc-send-data", token=github_token)


def test_workflow_types():

    expected_types = (GalaxyWorkflowFile, SnakemakeWorkflowFile, JupyterWorkflowFile, NextflowWorkflowFile, OtherWorkflowFile)
    actual_types = WorkflowFile.get_types()
    assert len(actual_types) == len(expected_types), "Unexpected number of supported workflow types"
    for w_type in expected_types:
        assert w_type in actual_types, f"{w_type} should be supported"


def test_workflow_type_extensions():

    expected_extensions = {_[1] for _ in GalaxyWorkflowFile.FILE_PATTERNS}
    actual_extension = GalaxyWorkflowFile.get_workflow_extensions('galaxy')
    assert len(expected_extensions) == len(actual_extension), "Unexpected number of extensions for Galaxy workflow type"
    for ext in expected_extensions:
        assert ext in actual_extension, f"Extension '{ext}' not found on Galaxy workflow type"


def test_snakemake(repo_path):

    file = RepositoryFile(repo_path, "Snakefile")
    w_file = SnakemakeWorkflowFile.is_workflow(file)
    assert w_file, f"{file} not detected as workflow"
    assert isinstance(w_file, WorkflowFile), f"{file} should be a WorkflowFile"
    assert isinstance(w_file, SnakemakeWorkflowFile), f"{file} should be a SnakemakeWorkflowFile"

    file = RepositoryFile(repo_path, "Snakefile", dir="workflow")
    w_file = SnakemakeWorkflowFile.is_workflow(file)
    assert w_file, f"{file} not detected as workflow"
    assert isinstance(w_file, WorkflowFile), f"{file} should be a WorkflowFile"
    assert isinstance(w_file, SnakemakeWorkflowFile), f"{file} should be a SnakemakeWorkflowFile"

    file = RepositoryFile(repo_path, "SnakemakeX", dir="workflow")
    w_file = SnakemakeWorkflowFile.is_workflow(file)
    assert not w_file, f"{file} is not a workflow file"


def test_galaxy(repo_path):

    file = RepositoryFile(repo_path, "GalaxyWorkflow.ga")
    w_file = GalaxyWorkflowFile.is_workflow(file)
    assert w_file, f"{file} not detected as workflow"
    assert isinstance(w_file, WorkflowFile), f"{file} should be a WorkflowFile"
    assert isinstance(w_file, GalaxyWorkflowFile), f"{file} should be a GalaxyWorkflowFile"

    file = RepositoryFile(repo_path, "GalaxyWorkflow.ga", dir="workflow")
    w_file = GalaxyWorkflowFile.is_workflow(file)
    assert w_file, f"{file} not detected as workflow"
    assert isinstance(w_file, WorkflowFile), f"{file} should be a WorkflowFile"
    assert isinstance(w_file, GalaxyWorkflowFile), f"{file} should be a GalaxyWorkflowFile"

    file = RepositoryFile(repo_path, "GalaxyWorkflow.gax", dir="workflow")
    w_file = GalaxyWorkflowFile.is_workflow(file)
    assert not w_file, f"{file} is not a workflow file"


def test_jupyter(repo_path):

    file = RepositoryFile(repo_path, "workflow.ipynb")
    w_file = JupyterWorkflowFile.is_workflow(file)
    assert w_file, f"{file} not detected as workflow"
    assert isinstance(w_file, WorkflowFile), f"{file} should be a WorkflowFile"
    assert isinstance(w_file, JupyterWorkflowFile), f"{file} should be a JupyterWorkflowFile"

    file = RepositoryFile(repo_path, "workflow.ipynb", dir="workflow")
    w_file = JupyterWorkflowFile.is_workflow(file)
    assert w_file, f"{file} not detected as workflow"
    assert isinstance(w_file, WorkflowFile), f"{file} should be a WorkflowFile"
    assert isinstance(w_file, JupyterWorkflowFile), f"{file} should be a GalaxyWorkflowFile"

    file = RepositoryFile(repo_path, "GalaxyWorkflow.ga", dir="workflow")
    w_file = JupyterWorkflowFile.is_workflow(file)
    assert not w_file, f"{file} is not a Jupyter workflow file"
    w_file = WorkflowFile.is_workflow(file)
    assert isinstance(w_file, GalaxyWorkflowFile), f"{file} should be a GalaxyWorkflowFile"


def test_remote_galaxy_workflow_type(remote_galaxy_github_repository: GithubWorkflowRepository):
    remote_workflow = remote_galaxy_github_repository.find_remote_workflow()
    logger.debug(remote_workflow)
    assert isinstance(remote_workflow, GalaxyWorkflowFile), "Unexpected remote workflow file"


def test_remote_snakemake_workflow_type(remote_snakemake_github_repository: GithubWorkflowRepository):
    remote_workflow = remote_snakemake_github_repository.find_remote_workflow()
    logger.debug(remote_workflow)
    assert isinstance(remote_workflow, SnakemakeWorkflowFile), "Unexpected remote workflow file"
