
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

from .base import (IssueCheckResult, WorkflowRepository,
                   WorkflowRepositoryMetadata)
from .config import WorkflowRepositoryConfig
from .files import RepositoryFile, TemplateRepositoryFile, WorkflowFile
from .github import (GithubWorkflowRepository,
                     InstallationGithubWorkflowRepository,
                     RepoCloneContextManager)
from .local import (LocalGitWorkflowRepository, LocalWorkflowRepository,
                    Base64WorkflowRepository, ZippedWorkflowRepository)
from .templates import WorkflowRepositoryTemplate

__all__ = [
    "RepositoryFile", "WorkflowRepositoryConfig", "WorkflowFile", "TemplateRepositoryFile",
    "WorkflowRepository", "WorkflowRepositoryMetadata", "IssueCheckResult",
    "LocalWorkflowRepository", "LocalGitWorkflowRepository",
    "Base64WorkflowRepository", "ZippedWorkflowRepository",
    "InstallationGithubWorkflowRepository", "GithubWorkflowRepository", "RepoCloneContextManager",
    "WorkflowRepositoryTemplate"
]
