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

from lifemonitor.api.models.issues import IssueMessage, WorkflowRepositoryIssue
from lifemonitor.api.models.issues.general.repo_layout import \
    GitRepositoryWithoutMainBranch
from lifemonitor.api.models.repositories import WorkflowRepository
from lifemonitor.schemas.validators import ValidationError, ValidationResult
from lifemonitor.utils import get_validation_schema_url

# set module level logger
logger = logging.getLogger(__name__)


class MissingLMConfigFile(WorkflowRepositoryIssue):
    name = "Missing LifeMonitor configuration file"
    description = "No <code>lifemonitor.yaml</code> configuration file found on this repository.<br>"\
        "The <code>lifemonitor.yaml</code> should be placed on the root of this repository."
    labels = ['lifemonitor']
    depends_on = [GitRepositoryWithoutMainBranch]

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.config is None:
            config = repo.generate_config()
            validation_result = config.validate()
            if validation_result:
                self.add_change(config)
            else:
                logger.error("MissingLMConfigFile generated an invalid configuration!")
                logger.error("Error:\n%s", validation_result)
                logger.error("Configuration:\n%s", config)
            return True
        return False


class InvalidConfigFile(WorkflowRepositoryIssue):

    name = "Invalid LifeMonitor configuration file"
    description = "The LifeMonitor configuration file found on this repository "\
                  f"is not valid according to the schema " \
                  f"<a href='{get_validation_schema_url()}'>{get_validation_schema_url()}</a>.<br>"
    labels = ['lifemonitor']
    depends_on = [MissingLMConfigFile]

    def check(self, repo: WorkflowRepository) -> bool:
        if repo.config is None:
            return True
        result: ValidationResult = repo.config.validate()
        if not result.valid:
            if isinstance(result, ValidationError):
                self.add_message(IssueMessage(IssueMessage.TYPE.ERROR, result.error))
                return True
        return False
