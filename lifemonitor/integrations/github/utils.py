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
from typing import List

from github.GithubException import GithubException
from github.Label import Label
from github.Repository import Repository

# Config a module level logger
logger = logging.getLogger(__name__)


def crate_branch(repo: Repository, branch_name: str):
    head = repo.get_commit('HEAD')
    logger.debug("HEAD commit: %r", head.sha)
    logger.debug("New target branch ref: %r", f'refs/heads/{branch_name}'.format(**locals()))
    return repo.create_git_ref(ref=f'refs/heads/{branch_name}'.format(**locals()), sha=head.sha)


def delete_branch(repo: Repository, branch_name: str) -> bool:
    try:
        ref = repo.get_git_ref(f"heads/{branch_name}")
        ref.delete()
        return True
    except GithubException as e:
        logger.debug("Unable to delete branch '%s': %s", branch_name, str(e))
        return False


def get_labels_from_strings(repo: Repository, labels: List[str]) -> List[Label]:
    result = []
    if labels:
        for l in labels:
            label = repo.get_label(l)
            if not label:
                label = repo.create_label(l, 'orange')
            result.append(label)
    return result
