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

from __future__ import annotations

import logging

from lifemonitor.api.models.issues import WorkflowRepositoryIssue
from lifemonitor.api.models.repositories import WorkflowRepository

# set module level logger
logger = logging.getLogger(__name__)


class RepositoryNotInitialised(WorkflowRepositoryIssue):
    name = "Repository not intialised"
    description = "No workflow and crate metadata found on this repository."
    labels = ['best-practices']

    def check(self, repo: WorkflowRepository) -> bool:
        return repo.find_workflow() is None and repo.metadata is None


class MissingWorkflowFile(WorkflowRepositoryIssue):
    name = "Missing workflow file"
    description = "No workflow found on this repository.<br>"\
        "You should place the workflow file (e.g., <code>.ga</code> file) according to the best practices ."
    labels = ['best-practices']
    depends_on = [RepositoryNotInitialised]

    def check(self, repo: WorkflowRepository) -> bool:
        return repo.find_workflow() is None


class MissingROCrateFile(WorkflowRepositoryIssue):
    name = "Missing RO-Crate metadata"
    description = "No <code>ro-crate-metadata.json</code> found on this repository.<br>"\
        "The <code>ro-crate-metadata.json</code> should be placed on the root of this repository."
    labels = ['metadata']
    depends_on = [MissingWorkflowFile]

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.metadata is None:
            metadata = repo.generate_metadata()
            self.add_change(metadata.repository_file)
            return True
        return False


class MissingROCrateWorkflowFile(WorkflowRepositoryIssue):
    name = "Missing RO-Crate workflow file"
    description = "The workflow file declared on RO-Crate metadata is missing in this repository."
    labels = ['metadata']
    depends_on = [MissingROCrateFile]

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.metadata:
            wf_file = repo.metadata.get_workflow()
            if wf_file:
                logger.debug("Workflow file: %r - %s %s",
                             wf_file, wf_file.dir, wf_file.name)
            return not wf_file or not repo.find_file_by_name(wf_file.name, path=wf_file.dir)
        return False
