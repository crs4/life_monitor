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
from typing import List

from github.GithubException import GithubException
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from ...api.models.wizards import (IOHandler, QuestionStep, Step, UpdateStep,
                                   Wizard)

# Config a module level logger
logger = logging.getLogger(__name__)


def match_ref(ref: str, refs: List[str]) -> str:
    if not ref:
        return None
    for v in refs:
        pattern = rf"^({v})$".replace('*', "[a-zA-Z0-9.-_/]")
        try:
            logger.debug("Searching match for %s (pattern: %s)", ref, pattern)
            match = re.match(pattern, ref)
            if match:
                logger.debug("Match found: %r", match)
                return (match.group(0), pattern.replace("[a-zA-Z0-9.-_/]", '*').strip('^()$'))
        except Exception:
            logger.debug("Unable to find a match for %s (pattern: %s)", ref, pattern)
    return None


def crate_branch(repo: Repository, branch_name: str):
    head = repo.get_commit('HEAD')
    logger.debug("HEAD commit: %r", head.sha)
    logger.debug("New target branch ref: %r", f'refs/heads/{branch_name}'.format(**locals()))
    return repo.create_git_ref(ref=f'refs/heads/{branch_name}'.format(**locals()), sha=head.sha)


def delete_branch(repo: Repository, branch_name: str) -> bool:
    try:
        ref = repo.get_git_ref(f"heads/{branch_name}".format(**locals()))
        ref.delete()
        return True
    except GithubException as e:
        logger.debug("Unable to delete branch '%s': %s", branch_name, str(e))
        return False


def get_labels_from_strings(repo: Repository, labels: List[str]) -> List[Label]:
    result = []
    if labels:
        for name in labels:
            label = None
            try:
                label = repo.get_label(name)
            except GithubException:
                logger.debug("Label %s not found...", name)
                try:
                    label = repo.create_label(name, '1f8787')
                except GithubException as e:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
                    logger.error(f"Unable to create label: {name}: {str(e)}")
            if label:
                result.append(label)
    return result


class GithubIOHandler(IOHandler):

    def __init__(self, app, issue: Issue) -> None:
        super().__init__()
        self.issue = issue
        self.app = app

    def get_input(self, question: QuestionStep) -> object:
        assert isinstance(question, QuestionStep), question
        found = False
        candidates = []
        helper: Wizard = question.wizard
        next_step = helper.get_next_step(question, ignore_skip=True)
        logger.debug("Next step: %r", next_step)
        for c in self.issue.get_comments():
            logger.debug("Checking comment: %r", c.body)
            step = question.wizard.find_step(c.body)
            logger.debug("Current step: %r", step)
            if step and step.title == question.title:
                found = True
            elif found:
                logger.debug("Found")
                if not next_step or step != next_step:
                    logger.debug("Adding... %r", c)
                    candidates.append(c)
                else:
                    break
        logger.debug("Candidates: %r", candidates)
        for ca in reversed(candidates):
            cbody = self.parse_answer(ca)
            logger.debug("Checking candidate: %r -- options: %r", cbody, question.options)
            logger.debug("Check condition: %r", cbody in question.options)
            if question.options is None or len(question.options) == 0 or cbody in question.options:
                return ca
        return None

    def parse_answer(self, answer: object) -> str:
        return re.sub(r'(@lm|%s)\s+' % self.app.bot.strip("[bot]"), '',
                      answer.body) if answer else None

    def get_input_as_text(self, question: QuestionStep) -> object:
        return self.parse_answer(self.get_input(question))

    def as_string(self, step: Step, append_help: bool = False) -> str:
        result = f"<b>{step.title}</b><br/>"
        if step.description:
            result += f"{step.description}<br/>"
        if isinstance(step, QuestionStep) and step.options:
            result += "<br>> Choose among the following options: <b><code>{}</code></b><br>".format(', '.join(step.options))
        if isinstance(step, UpdateStep):
            logger.debug("Preparing PR... %r", step)
        if append_help:
            result += self.get_help()
        return result

    def get_help(self):
        return f'<br>\n> **?** type **@lm** or **@{self.app.bot.strip("[bot]")}** to answer'

    def write(self, step: Step, append_help: bool = False):
        assert isinstance(step, Step), step
        self.issue.create_comment(step.as_string(append_help=append_help))
