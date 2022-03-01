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
import re
from typing import Tuple

import pygit2

import github

# Config a module level logger
logger = logging.getLogger(__name__)


def get_repo_and_ref_from_event(gh_client: github.Github, event: object) -> Tuple[object, str]:
    return gh_client.get_repo(event['data']['repository']['full_name']), event['data']['ref']


def find_file_by_pattern(repo: object, ref: str, search: str):
    for e in repo.get_contents('.', ref=ref):
        logger.debug("Name: %r -- type: %r", e.name, e.type)
        if re.search(search, e.name):
            return e.decoded_content
    return None


def find_file_by_regex_pattern(repo: object, ref: str, pattern: re.Pattern):
    for e in repo.get_contents('.', ref=ref):
        logger.debug("Name: %r -- type: %r", e.name, e.type)
        if pattern.match(e.name):
            return e.decoded_content
    return None


def clone_repo(repo: object, target_path: str):
    # Clone the newly created repo
    return pygit2.clone_repository(repo.git_url, target_path)


def crate_new_branch(repo: object, branch_name: str):
    head = repo.get_commit('HEAD')
    logger.debug("HEAD commit: %r", head.sha)
    logger.debug("New target branch ref: %r", f'refs/heads/{branch_name}'.format(**locals()))
    return repo.create_git_ref(ref=f'refs/heads/{branch_name}'.format(**locals()), sha=head.sha)
