
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
import os
import shutil
import time

from lifemonitor.api.models import TestInstance
from lifemonitor.cache import cache
from lifemonitor.integrations.github.models import GithubApp

# Config a module level logger
logger = logging.getLogger(__name__)


def ping(event: object):
    logger.debug("Ping event: %r", event)
    return "Pong", 200


def workflow_run(event: object):
    try:
        logger.debug("Workflow run event: %r", event)
        repository = event['data']['repository']
        logger.debug("Workflow repository: %r", repository)
        workflow = event['data']['workflow']
        logger.debug("Workflow: %r", workflow)
        workflow_run = event['data']['workflow_run']
        logger.debug("Workflow run: %r", workflow_run)
        workflow_name = workflow['path'].replace('.github/workflows/', '')
        logger.debug("Workflow NAME: %r", workflow_name)
        workflow_resource = f"repos/{repository['full_name']}/actions/workflows/{workflow_name}"
        logger.debug("Workflow Resource: %r", workflow_resource)
        instances = TestInstance.find_by_resource(workflow_resource)
        logger.debug("Instances: %r", instances)
        with cache.transaction():
            for i in instances:
                i.get_test_builds(limit=10)
                i.get_test_build(workflow_run['id'])
                i.last_test_build
        return f"Test instance related with resource '{workflow_resource}' updated", 200
    except Exception as e:
        logger.error(e)
        return "Internal Error", 500


# Register Handlers
__event_handlers__ = {
    "ping": ping,
    "workflow_run": workflow_run,
}


def get_event_map() -> dict:
    return __event_handlers__.copy()
