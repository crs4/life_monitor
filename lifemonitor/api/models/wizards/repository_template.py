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
import os

from lifemonitor.api.models.issues.general.repo_layout import \
    RepositoryNotInitialised
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.repositories.templates import \
    WorkflowRepositoryTemplate

from . import QuestionStep, UpdateStep, Wizard

# set module level logger
logger = logging.getLogger(__name__)

valid_workflow_types = ["galaxy", "snakemake", "nextflow", "other"]
supported_workflows = ["snakemake", "galaxy", "nextflow"]


def get_files(wizard: RepositoryTemplateWizard, repo: GithubWorkflowRepository, target_path: str):

    workflow_name = wizard.workflow_title.answer
    workflow_description = wizard.workflow_description.answer
    workflow_type = wizard.workflow_type.answer

    logger.debug("Preparing template for workflow: %r (type: %r)", workflow_name, workflow_type)

    # Temporary workaround to assign the proper name
    # to the workflow and its related entities. Generators do not support
    # the workflow name as input: they use the root name as workflow name.
    # TODO: remove this fix when generators support
    # the workflow_name as input
    try:
        workflow_path = os.path.join(target_path, workflow_name)
        if workflow_type != 'nextflow':
            os.makedirs(workflow_path)
    except Exception:
        workflow_path = target_path

    repo_template = WorkflowRepositoryTemplate.new_instance(workflow_type, data={
        'workflow_name': workflow_name, 'workflow_description': workflow_description,
        'workflow_version': repo.default_branch,
        'repo_url': repo.html_url, 'repo_full_name': repo.full_name, 'main_branch': repo.default_branch
    }, local_path=workflow_path).generate()

    logger.debug("Template files: %r --> %r", repo_template, repo_template.files)
    logger.debug("Repository files: %r --> %r", repo, repo.files)
    try:
        missing_left, missing_right, differences = repo_template.compare_to(repo)
        logger.debug("Diff (left, right, changed)=(%r,%r,%r)", missing_left, missing_right, differences)
        return missing_right
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(e)


class RepositoryTemplateWizard(Wizard):
    title = "Repository Template"
    description = ""
    labels = ['config']
    issue = RepositoryNotInitialised

    workflow_type = QuestionStep("Which type of workflow are we going to host on this repository?",
                                 description="",
                                 options=valid_workflow_types)
    workflow_title = QuestionStep("Choose a name for your workflow",
                                  when=lambda _: _.workflow_type.answer in supported_workflows)
    workflow_description = QuestionStep("Type a description for your workflow")

    workflow_template = UpdateStep("Repository initialisation",
                                   description="Merge this PR to initialise your Workflow Testing RO-Crate repository",
                                   callback=get_files)
    wizard_stop = QuestionStep("Unsupported workflow type",
                               description="Your chosen workflow type is not supported at the moment",
                               when=lambda _: _.workflow_type.answer not in supported_workflows)

    steps = [workflow_type, wizard_stop, workflow_title, workflow_description, workflow_template]
