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

import logging

from lifemonitor.api.models.issues.common.files.missing import \
    MissingWorkflowFile
from lifemonitor.api.models.repositories import WorkflowRepository
from lifemonitor.api.models.repositories.templates import \
    WorkflowRepositoryTemplate

from . import QuestionStep, UpdateStep, Wizard

# set module level logger
logger = logging.getLogger(__name__)


def get_files(wizard: RepositoryTemplateWizard, repo: WorkflowRepository, target_path: str):

    workflow_title = wizard.workflow_title.answer
    workflow_description = wizard.workflow_description.answer
    workflow_type = wizard.workflow_type.answer

    logger.debug("Preparing template for workflow: %r (type: %r)", workflow_title, workflow_type)

    repo_template = WorkflowRepositoryTemplate("galaxy", local_path=target_path, data={
        'workflow_title': workflow_title, 'workflow_description': workflow_description}
    )
    logger.debug("Template files: %r --> %r", repo_template, repo_template.files)
    logger.debug("Repository files: %r --> %r", repo, repo.files)
    try:
        missing_left, missing_right, differences = repo_template.compare(repo)
        logger.debug("Diff (left, right, changed)=(%r,%r,%r)", missing_left, missing_right, differences)
        return missing_right
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(e)


class RepositoryTemplateWizard(Wizard):
    title = "Repository Template"
    description = ""
    labels = ['enhancement']
    issue = MissingWorkflowFile

    workflow_title = QuestionStep("Choose a name for your workflow?")
    workflow_description = QuestionStep("Type a description for your workflow?")
    workflow_type = QuestionStep("Which type of workflow are going to host on this repository?", options=["galaxy"])
    # questionB = QuestionStep("Question B?", options=["B1", "B2"], when=lambda _: _.questionA.answer == 'B')
    # questionC = QuestionStep("Question C?", options=["C1", "C2"],
    #                          description="This is an optional description for the question C",
    #                          when=lambda _: _.questionA.answer == 'C')

    workflow_template = UpdateStep("Update you Workflow RO-Crate repository",
                                   description="According to the recommended layout for workflow RO-Crates, you should add the following files",
                                   callback=get_files)

    steps = [workflow_title, workflow_description, workflow_type, workflow_template]
