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
from typing import Dict, List

import pytest

from lifemonitor.api.models import repositories as repos
from lifemonitor.api.models.repositories import templates

logger = logging.getLogger(__name__)


@pytest.fixture
def repo_info() -> Dict[str, str]:
    return {
        "name": "MyWorkflowTest",
        "owner": "lm",
        "description": "My workflow test description",
        "license": "MIT",
        "exclude": [".*"],
        "default_branch": "main",
        "active_branch": "main",
        "full_name": "lm/MyWorkflowTest",
        "remote_url": 'https://github.com/lm/MyWorkflowTest',
    }


def repo_template_types() -> List[str]:
    return ['galaxy', 'snakemake']  # , 'nextflow', 'other']


@pytest.fixture(params=repo_template_types())
def repo_template_type(request):
    return request.param


@pytest.mark.skip(reason="Template type not supported")
def test_repo_template(user1, repo_info, repo_template_type):
    with tempfile.TemporaryDirectory(prefix=f"template-{repo_template_type}") as workflow_path:
        logger.debug("Creating a new Galaxy workflow repository template in %r", workflow_path)
        # instantiate the template
        tmpl = templates.WorkflowRepositoryTemplate.new_instance(repo_template_type, data={
            'workflow_name': repo_info['name'], 'workflow_description': repo_info['description'],
            'workflow_version': '1.0.0', 'workflow_author': 'lm', 'workflow_license': repo_info['license'],
            'repo_url': repo_info['remote_url'], 'repo_full_name': repo_info['full_name'],
            'main_branch': repo_info['default_branch']
        }, local_path=workflow_path)
        # check the template type
        assert isinstance(tmpl, templates.WorkflowRepositoryTemplate), "Template is not a WorkflowRepositoryTemplate"
        assert tmpl.type == repo_template_type, "Template type is not correct"

        # check if the template is the expected one
        if repo_template_type == 'galaxy':
            assert isinstance(tmpl, templates.galaxy.GalaxyRepositoryTemplate), "Template is not a GalaxyWorkflowTemplate"
        if repo_template_type == 'nextflow':
            assert isinstance(tmpl, templates.nextflow.NextflowRepositoryTemplate), "Template is not a SnakeMakeWorkflowTemplate"
        if repo_template_type == 'snakemake':
            assert isinstance(tmpl, templates.snakemake.SnakemakeRepositoryTemplate), "Template is not a NextflowWorkflowTemplate"

        # generate the repository
        repo = tmpl.generate()

        # check the repository metadata
        assert repo, "Repository object is None"
        assert isinstance(repo, repos.LocalWorkflowRepository), "Repository is not a WorkflowRepository"
        assert repo.name == repo_info['name'], "Repository name is not correct"
        assert repo.owner == repo_info['owner'], "Repository owner is not correct"
        assert repo.full_name == f"{repo_info['owner']}/{repo_info['name']}", "Repository full name is not correct"
        assert repo.license == repo_info['license'], "Repository license is not correct"
        assert repo.local_path == workflow_path, "Repository local path is not correct"
        assert repo.remote_url == repo_info['remote_url'], "Repository remote url is not correct"
