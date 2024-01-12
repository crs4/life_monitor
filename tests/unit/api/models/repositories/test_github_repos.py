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

import logging
from typing import Dict

import pytest

import lifemonitor.api.models.repositories as repos

logger = logging.getLogger(__name__)


@pytest.fixture
def test_repo_info(simple_local_wf_repo) -> Dict[str, str]:
    return {
        "name": "test-galaxy-wf-repo",
        "owner": "ilveroluca",
        "license": "MIT",
        "exclude": [".*"],
        "local_path": simple_local_wf_repo.local_path,
        "default_branch": "main",
        "active_branch": "main",
        "remote_url": 'https://github.com/ilveroluca/test-galaxy-wf-repo'
    }


def test_github_repo(test_repo_info, simple_local_wf_repo):
    repo = repos.GithubWorkflowRepository(full_name_or_id=simple_local_wf_repo.full_name,
                                          local_path=test_repo_info['local_path'],
                                          exclude=test_repo_info['exclude'],)

    assert repo, "Repository object is None"
    assert isinstance(repo, repos.GithubWorkflowRepository), "Repository is not a WorkflowRepository"
    assert repo.name == test_repo_info['name'], "Repository name is not correct"
    assert repo.owner == test_repo_info['owner'], "Repository owner is not correct"
    assert repo.full_name == f"{test_repo_info['owner']}/{test_repo_info['name']}", "Repository full name is not correct"
    assert repo.license == test_repo_info['license'], "Repository license is not correct"
    assert repo.exclude == test_repo_info['exclude'], "Repository exclude is not correct"
    assert repo.local_path == test_repo_info['local_path'], "Repository local path is not correct"
    assert repo.remote_url == test_repo_info['remote_url'], "Repository remote url is not correct"


def test_github_repo_no_local_path(test_repo_info, simple_local_wf_repo):
    repo = repos.GithubWorkflowRepository(full_name_or_id=simple_local_wf_repo.full_name,
                                          exclude=test_repo_info['exclude'],)

    assert repo, "Repository object is None"
    assert isinstance(repo, repos.GithubWorkflowRepository), "Repository is not a WorkflowRepository"
    assert repo.name == test_repo_info['name'], "Repository name is not correct"
    assert repo.owner == test_repo_info['owner'], "Repository owner is not correct"
    assert repo.full_name == f"{test_repo_info['owner']}/{test_repo_info['name']}", "Repository full name is not correct"
    assert repo.license == test_repo_info['license'], "Repository license is not correct"
    assert repo.exclude == test_repo_info['exclude'], "Repository exclude is not correct"
    assert repo.local_path.startswith('/tmp'), "Repository local path is not correct"
    assert repo.remote_url == test_repo_info['remote_url'], "Repository remote url is not correct"
