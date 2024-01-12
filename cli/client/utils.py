# Copyright (c) 2020-2024 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitatioån the rights
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
import os
import shutil
import sys
from urllib.parse import urlparse

from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository, LocalGitWorkflowRepository
from rich.prompt import Prompt

# Set module logger
logger = logging.getLogger(__name__)


def is_url(value):
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_repository(repository: str, local_path: str):
    assert repository, repository
    try:
        if is_url(repository):
            remote_repo_url = repository
            if remote_repo_url.endswith('.git'):
                return GithubWorkflowRepository.from_url(remote_repo_url, auto_cleanup=False, local_path=local_path)
        else:
            local_copy_path = os.path.join(local_path, os.path.basename(repository))
            shutil.copytree(repository, local_copy_path)
            if LocalGitWorkflowRepository.is_git_repo(local_copy_path):
                return LocalGitWorkflowRepository(local_copy_path)
            return LocalWorkflowRepository(local_copy_path)
        raise ValueError("Repository type not supported")
    except Exception as e:
        raise ValueError("Error while loading the repository: %s" % e)


def init_output_path(output_path):
    logger.debug("Output path: %r", output_path)
    if os.path.exists(output_path):
        files = os.listdir(output_path)
        logger.debug("File: %r", files)
        if len(files) > 0:
            answer = Prompt.ask(f"The folder '{output_path}' is not empty. "
                                "Would like to delete its content?", choices=["y", "n"], default="y")
            logger.debug("Answer: %r", answer)
            if answer == 'y':
                for root, dirs, files in os.walk(output_path):
                    for f in files:
                        os.unlink(os.path.join(root, f))
                    for d in dirs:
                        shutil.rmtree(os.path.join(root, d))
            else:
                sys.exit(0)
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)
