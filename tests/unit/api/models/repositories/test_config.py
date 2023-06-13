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
from pathlib import Path

import pytest

from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api.models.repositories.local import (LocalGitWorkflowRepository,
                                                       LocalWorkflowRepository)
from lifemonitor.api.models.repositories.config import WorkflowRepositoryConfig

logger = logging.getLogger(__name__)


def test_finding_config_file(repository: LocalWorkflowRepository):
    with pytest.raises(ValueError):
        cfg = WorkflowRepositoryConfig(repository.local_path)

    cfg_file_contents = """
                        name: "MyWorkflow"
                        public: true
                        issues:
                            checks: false
                        """
    for fname in ('.lifemonitor', 'lifemonitor'):
        for ext in ('yml', 'yaml'):
            cfg_file = Path(repository.local_path, f"{fname}.{ext}")
            try:
                with cfg_file.open(mode='w+') as f:
                    f.write(cfg_file_contents)

                # The WorkflowRepositoryConfig constructor will raise if it doesn't find a
                # configuration file.
                cfg = WorkflowRepositoryConfig(repository.local_path)
                assert "MyWorkflow" == cfg.workflow_name
            finally:
                cfg_file.unlink()


def test_generate_config(simple_local_wf_repo: LocalGitWorkflowRepository):
    # test with defaults
    new_config = simple_local_wf_repo.generate_config(ignore_existing=True)
    assert new_config.workflow_name is None
    monitored_branches = new_config.branches
    assert len(monitored_branches) == 1
    assert set(monitored_branches) == {'main'}
    assert not new_config.public
    monitored_tags = new_config.tags
    assert len(monitored_tags) == 2
    assert set(monitored_tags) == {'v*.*.*', '*.*.*'}

    # specify some things
    new_config = simple_local_wf_repo.generate_config(ignore_existing=True,
                                                      workflow_title='dummy')
    assert new_config.workflow_name == 'dummy'

    new_config = simple_local_wf_repo.generate_config(ignore_existing=True, public=True)
    assert new_config.public
    new_config = simple_local_wf_repo.generate_config(ignore_existing=True, public=False)
    assert not new_config.public

    new_config = simple_local_wf_repo.generate_config(ignore_existing=True,
                                                      main_branch='develop')
    assert set(new_config.branches) == {'develop'}

    git_repo = simple_local_wf_repo._git_repo  # access private member to implement this test
    # Create and checkout a branch called "develop".  See if generate_config picks it up
    # as the branch to monitor.
    dev_branch = git_repo.create_head('develop')
    dev_branch.checkout()
    new_config = simple_local_wf_repo.generate_config(ignore_existing=True)
    assert set(new_config.branches) == {'develop'}


def test_getting_refs(simple_local_wf_repo: LocalGitWorkflowRepository):
    config = simple_local_wf_repo.config
    assert isinstance(config, WorkflowRepositoryConfig)

    assert len(config.branches) == 1
    assert 'main' in config.branches
    assert len(config.tags) == 2
    assert set(config.tags) == {'v*.*.*', '*.*.*'}

    assert config.get_ref_settings('pippo') is None
    push_to_main = config.get_ref_settings('main')
    assert push_to_main is not None
    assert push_to_main['enable_notifications'] is True
    assert push_to_main['update_registries'] == []
    assert push_to_main['name'] == 'main'

    assert config.get_ref_settings('v1.0.1')['update_registries'] == ['wfhub']
    assert config.get_ref_settings('1.0.1')['update_registries'] == ['seek']

    # The fixture configuration associates v*.*.* with 'wfhub'. This
    # registry id is not registered during the tests.
    # Instead, '*.*.*' pattern is associated with the registry 'seek',
    # which exists during the tests.
    assert config.get_tag_registries('v*.*.*') == []
    assert config.get_branch_registries('main') == []
    test_registry = config.get_tag_registries('*.*.*')[0]
    assert isinstance(test_registry, WorkflowRegistry)
