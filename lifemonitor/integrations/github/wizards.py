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

from lifemonitor.api.models.wizards import Wizard
from lifemonitor.integrations.github.issues import GithubIssue

from .utils import GithubIOHandler

# Config a module level logger
logger = logging.getLogger(__name__)


class GithubWizard(Wizard):

    @classmethod
    def from_event(cls, event) -> Wizard:
        # detect the current issue from the Github event
        issue: GithubIssue = event.issue or (event.pull_request.as_issue() if event.pull_request else None)
        if not issue:
            logger.debug("Unable to find an issue associated to the event: %r", event)
            return None

        # map the Github issue to a LifeMonitor issue
        repo_issue = issue.as_repository_issue()
        logger.warning("The current github issue: %r", issue)
        logger.warning("Issues comments: %r", issue.comments)
        logger.warning("LifeMonitor issue: %r", issue.as_repository_issue())
        logger.warning("Issue comment: %r --> %r", event.comment, event.comment.body if event.comment else None)

        # detect wizard type
        wizard_type = Wizard.find_by_issue(repo_issue)
        if not wizard_type:
            logger.debug("Unable to detect a wizard for issue %r", repo_issue)
            return None

        # instantiate wizard
        wizard: Wizard = wizard_type(repo_issue, io_handler=GithubIOHandler(event.application, issue))
        logger.debug("Detected wizard: %r", wizard)
        # try to find the step for this event
        comments = [c for c in issue.get_comments() if c.user.login == event.application.bot]
        for cm in reversed(comments):
            logger.debug("Comment user: %r %r", cm.user, event.application.bot)
            logger.debug("Comment %r: %r", cm, cm.body)
            step = wizard.find_step(cm.body)
            if step:
                wizard.current_step = step
                logger.debug("Step found: %r", step)
                break
            else:
                logger.debug("No match for %r", cm)
        return wizard
