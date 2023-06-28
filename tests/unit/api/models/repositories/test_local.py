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
import tempfile
from typing import Dict

import pytest

import lifemonitor.api.models.repositories as repos
import lifemonitor.utils as utils

logger = logging.getLogger(__name__)


@pytest.fixture
def test_repo_info(simple_local_wf_repo) -> Dict[str, str]:
    return {
        "name": "test_repo",
        "owner": "test_owner",
        "license": "MIT",
        "exclude": [".*"],
        "local_path": simple_local_wf_repo.local_path,
        "default_branch": "main",
        "active_branch": "main",
        "remote_url": 'https://repo_url.git'
    }


def test_base_repo(test_repo_info):
    repo = repos.WorkflowRepository(local_path=test_repo_info['local_path'],
                                    remote_url=test_repo_info['remote_url'],
                                    name=test_repo_info['name'],
                                    owner=test_repo_info['owner'],
                                    license=test_repo_info['license'],
                                    exclude=test_repo_info['exclude'],)

    assert repo, "Repository object is None"
    assert isinstance(repo, repos.WorkflowRepository), "Repository is not a WorkflowRepository"
    assert repo.name == test_repo_info['name'], "Repository name is not correct"
    assert repo.owner == test_repo_info['owner'], "Repository owner is not correct"
    assert repo.full_name == f"{test_repo_info['owner']}/{test_repo_info['name']}", "Repository full name is not correct"
    assert repo.license == test_repo_info['license'], "Repository license is not correct"
    assert repo.exclude == test_repo_info['exclude'], "Repository exclude is not correct"
    assert repo.local_path == test_repo_info['local_path'], "Repository local path is not correct"
    assert repo.remote_url == test_repo_info['remote_url'], "Repository remote url is not correct"


def test_base_repo_fullname_wo_owner(test_repo_info):
    repo = repos.WorkflowRepository(local_path=test_repo_info['local_path'],
                                    name=test_repo_info['name'])
    assert isinstance(repo, repos.WorkflowRepository), "Repository is not a WorkflowRepository"
    assert repo.name == test_repo_info['name'], "Repository name is not correct"
    assert repo.owner is None, "Repository owner is not correct"
    assert repo.full_name == test_repo_info['name'], "Repository full name is not correct"


def test_base_repo_system_user_as_owner(test_repo_info):
    repo = repos.WorkflowRepository(local_path=test_repo_info['local_path'],
                                    name=test_repo_info['name'],
                                    license=test_repo_info['license'],
                                    exclude=test_repo_info['exclude'],
                                    owner_as_system_user=True)

    current_username = utils.get_current_username()
    assert repo, "Repository object is None"
    assert isinstance(repo, repos.WorkflowRepository), "Repository is not a WorkflowRepository"
    assert repo.name == test_repo_info['name'], "Repository name is not correct"
    assert repo.owner == current_username, "Repository owner is not correct"
    assert repo.full_name == f"{current_username}/{test_repo_info['name']}", "Repository full name is not correct"


#     current_username = utils.get_current_username()
#     assert repo, "Repository object is None"
#     assert isinstance(repo, repos.WorkflowRepository), "Repository is not a WorkflowRepository"
#     assert repo.name == test_repo_info['name'], "Repository name is not correct"
#     assert repo.owner == current_username, "Repository owner is not correct"
#     assert repo.full_name == f"{current_username}/{test_repo_info['name']}", "Repository full name is not correct"


def test_local_git_repo(simple_local_wf_repo):
    assert repos.LocalWorkflowRepository.is_git_repo(simple_local_wf_repo.local_path)
    assert repos.LocalGitWorkflowRepository.is_git_repo(simple_local_wf_repo.local_path)
    assert "main" == simple_local_wf_repo.main_branch


def test_local_git_repo_no_remote_url(simple_local_wf_repo):
    logger.debug("Remote url: %s", simple_local_wf_repo.remote_url)
    assert simple_local_wf_repo.remote_url is not None, "Remote url is None"
    assert simple_local_wf_repo.remote_url == \
        'https://github.com/ilveroluca/test-galaxy-wf-repo.git', \
        "Remote url is not correct"


def test_local_git_repo_no_name(simple_local_wf_repo):
    logger.debug("Repository name: %s", simple_local_wf_repo.name)
    assert simple_local_wf_repo.name is not None, "Repository name is None"
    assert simple_local_wf_repo.name == 'test-galaxy-wf-repo', \
        "Repository name is not correct"


def test_local_git_repo_no_owner(simple_local_wf_repo):
    assert simple_local_wf_repo.owner == 'ilveroluca'


def test_local_git_repo_owner_overwrite(simple_local_wf_repo):
    assert simple_local_wf_repo.owner == 'ilveroluca'

    repo = repos.LocalGitWorkflowRepository(simple_local_wf_repo.local_path, owner='test_owner')
    assert repo.owner == 'test_owner', "Repository owner is not correct"


def test_local_git_repo_no_license(simple_local_wf_repo):
    logger.debug("Repository license: %s", simple_local_wf_repo.license)
    assert simple_local_wf_repo.license is not None, "Repository license is None"


def test_zip_repo_empty_local_path(simple_zip_wf_repo):
    # check if the repository is a zip repository
    assert isinstance(simple_zip_wf_repo, repos.ZippedWorkflowRepository)

    logger.debug("Archive path: %s", simple_zip_wf_repo.archive_path)

    # create a new repository from the zip file
    # NOTE: the local_path is None
    repo = repos.ZippedWorkflowRepository(
        simple_zip_wf_repo.archive_path,
        local_path=None
    )
    # check if the repository is a zip repository
    assert isinstance(repo, repos.ZippedWorkflowRepository)
    assert repo.archive_path == simple_zip_wf_repo.archive_path
    assert repo.local_path is not None


def test_zip_repo(test_repo_info, simple_zip_wf_repo):
    # check if the repository is a zip repository
    assert isinstance(simple_zip_wf_repo, repos.ZippedWorkflowRepository)

    logger.debug("Archive path: %s", simple_zip_wf_repo.archive_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        # create a new repository from the zip file
        repo = repos.ZippedWorkflowRepository(
            simple_zip_wf_repo.archive_path,
            local_path=tmpdir,
            name=test_repo_info['name'],
            owner=test_repo_info['owner'],
            license=test_repo_info['license'],
            exclude=test_repo_info['exclude'],
        )
        # check if the repository is a zip repository
        assert isinstance(repo, repos.ZippedWorkflowRepository)
        # check paths
        assert repo.archive_path == simple_zip_wf_repo.archive_path
        assert repo.local_path is tmpdir, "Repository local path is not correct"
        # check metadata
        assert repo.owner == test_repo_info['owner'], "Repository owner is not correct"
        assert repo.name == test_repo_info['name'], "Repository name is not correct"
        assert repo.full_name == f"{test_repo_info['owner']}/{test_repo_info['name']}", "Repository full name is not correct"
        assert repo.license == test_repo_info['license'], "Repository license is not correct"


def test_base64_repo(test_repo_info, simple_base64_wf_repo):
    assert isinstance(simple_base64_wf_repo, repos.Base64WorkflowRepository)

    # check paths
    with tempfile.TemporaryDirectory() as tmpdir:
        # create a new repository from the zip file
        repo = repos.Base64WorkflowRepository(
            simple_base64_wf_repo.base64_archive,
            local_path=tmpdir,
            name=test_repo_info['name'],
            owner=test_repo_info['owner'],
            license=test_repo_info['license'],
            exclude=test_repo_info['exclude'],
        )
        # check if the repository is a base64 repository
        assert isinstance(repo, repos.Base64WorkflowRepository), "Repository is not a Base64WorkflowRepository"
        # check encodede archive
        assert repo.base64_archive == simple_base64_wf_repo.base64_archive, "Repository base64 archive is not correct"
        # check paths
        assert repo.local_path is tmpdir, "Repository local path is not correct"
        # check metadata
        assert repo.owner == test_repo_info['owner'], "Repository owner is not correct"
        assert repo.name == test_repo_info['name'], "Repository name is not correct"
        assert repo.full_name == f"{test_repo_info['owner']}/{test_repo_info['name']}", "Repository full name is not correct"
        assert repo.license == test_repo_info['license'], "Repository license is not correct"
