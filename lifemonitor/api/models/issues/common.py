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

from lifemonitor.api.models.repositories import (RepositoryFile, WorkflowRepositoryMetadata,
                                                 WorkflowRepository)

from . import WorkflowRepositoryIssue

# set module level logger
logger = logging.getLogger(__name__)


class MissingConfigFile(WorkflowRepositoryIssue):
    name = "Missing config file"
    description = "No <code>lifemonitor.yaml</code> configuration file found on this repository.<br>"\
        "The <code>lifemonitor.yaml</code> should be placed on the root of this repository."
    labels = ['config', 'enhancement']

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.config is None:
            config = repo.make_config()
            self.add_change(config)
            return True
        return False


class MissingWorkflowFile(WorkflowRepositoryIssue):
    name = "Missing workflow file"
    description = "No workflow found on this repository.<br>"\
        "You should place the workflow file (e.g., <code>.ga</code> file) on the root of this repository."
    labels = ['invalid', 'enhancement']

    def check(self, repo: WorkflowRepository) -> bool:
        return repo.find_workflow() is None


class MissingMetadataFile(WorkflowRepositoryIssue):
    name = "Missing RO-Crate metadata"
    description = "No <code>ro-crate-metadata.json</code> found on this repository.<br>"\
        "The <code>ro-crate-metadata.json</code> should be placed on the root of this repository."
    labels = ['invalid', 'enhancement']
    depends_on = [MissingWorkflowFile]

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.metadata is None:
            metadata = repo.generate_metadata()
            self.add_change(metadata.repository_file)
            return True
        return False


class OutdatedMetadataFile(WorkflowRepositoryIssue):
    name = "RO-Crate metadata outdated"
    description = "The <code>ro-crate-metadata.json</code> needs to be updated."
    labels = ['invalid', 'bug']
    depends_on = [MissingMetadataFile]

    def check(self, repo: WorkflowRepository) -> bool:
        return False
