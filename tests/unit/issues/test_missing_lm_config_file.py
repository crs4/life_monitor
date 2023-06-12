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

from lifemonitor.api.models.issues.general.lm import MissingLMConfigFile
from lifemonitor.api.models.repositories.files.base import RepositoryFile
from lifemonitor.schemas.validators import ConfigFileValidator

import pytest
import yaml


logger = logging.getLogger(__name__)


@pytest.fixture
def issue() -> MissingLMConfigFile:
    return MissingLMConfigFile()


def test_cfg_file_present(issue, simple_local_wf_repo):
    result = issue.check(simple_local_wf_repo)
    assert result is False, "LM configuration file not detected"


def test_cfg_file_missing(issue, simple_local_wf_repo):
    repo_path = Path(simple_local_wf_repo.local_path)
    cfg_file = repo_path / '.lifemonitor.yaml'
    assert cfg_file.exists()

    cfg_file.unlink(missing_ok=True)

    result = issue.check(simple_local_wf_repo)
    assert result is True, "Missing LM config not detected"

    # Verify that a configuration to be proposed was generated
    assert issue.has_changes()
    changes = issue.get_changes(simple_local_wf_repo)
    assert len(changes) == 1
    change: RepositoryFile = changes[0]
    assert change.type == 'yaml'
    assert change.extension == '.yaml'

    # Validate its contents
    with open(change.path) as f:
        new_config = yaml.safe_load(f)

    valid = ConfigFileValidator.validate(new_config)
    assert valid, f"Generated LM config has validation errors: {valid}"

    assert new_config['name'] == repo_path.name
    assert new_config['public'] is False
    assert new_config['issues']['check'] is True

    push_branches = new_config['push']['branches']
    assert len(push_branches) == 1
    assert push_branches[0]['name'] == simple_local_wf_repo.main_branch
    assert set(push_branches[0]['update_registries']) == {"wfhub", "wfhubdev"}
    assert push_branches[0]['enable_notifications'] is True

    tags = new_config['push']['tags']
    assert len(tags) == 2
    assert {"v*.*.*", "*.*.*"} == set((t['name'] for t in tags))
    assert all(t['enable_notifications'] for t in tags)
    assert all(set(t['update_registries']) == {"wfhub", "wfhubdev"} for t in tags)
