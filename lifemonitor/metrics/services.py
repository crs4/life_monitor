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

from .model import (users, workflow_registries,
                    workflow_suites,
                    workflow_test_instances,
                    workflow_versions, workflows)

from . import stats

# initialise logger
logger = logging.getLogger(__name__)


def update_stats() -> bool:
    logger.debug("Updating global metrics...")
    try:
        # number of users
        users.set(stats.users())
        # number of workflows
        workflows.set(stats.workflows())
        # number of workflow versions
        workflow_versions.set(stats.workflow_versions())
        # number of workflow registries
        workflow_registries.set(stats.workflow_registries())
        # number of workflow suites
        workflow_suites.set(stats.workflow_suites())
        # number of workflow test instances
        workflow_test_instances.set(stats.workflow_test_instances())
        logger.debug("Updating global metrics... DONE")
        return True
    except Exception as e:
        logger.warning("Unable to update metrics")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return False
