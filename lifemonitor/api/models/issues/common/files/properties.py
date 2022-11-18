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

from __future__ import annotations

import logging

from lifemonitor.api.models.issues import WorkflowRepositoryIssue
from lifemonitor.api.models.issues.common.files.missing import \
    MissingMetadataFile, MissingConfigFile
from lifemonitor.api.models.repositories import WorkflowRepository

# set module level logger
logger = logging.getLogger(__name__)


class MissingWorkflowName(WorkflowRepositoryIssue):
    name = "Missing property name for Workflow RO-Crate"
    description = "No name defined for this workflow. <br>You can set the workflow name on the `ro-crate-metadata.yaml` or `lifemonitor.yaml` file"
    labels = ['invalid', 'bug']
    depends_on = [MissingConfigFile, MissingMetadataFile]

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.config.workflow_name:
            return False
        if repo.metadata.main_entity_name:
            return False
        return True
