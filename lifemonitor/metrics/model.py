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

from lifemonitor.api.models import (TestInstance, TestSuite, Workflow,
                                    WorkflowRegistry, WorkflowVersion)
from lifemonitor.auth.models import User

#
logger = logging.getLogger(__name__)

# Set the global prefix for LifeMonitor metrics
PREFIX = "lifemonitor"


def get_metric_key(key: str) -> str:
    return f"{PREFIX}_{key}"


def users():
    return len(User.all())


def workflows():
    return len(Workflow.all())


def workflow_versions():
    return len(WorkflowVersion.all())


def workflow_registries():
    return len(WorkflowRegistry.all())


def workflow_suites():
    return len(TestSuite.all())


def workflow_test_instances():
    return len(TestInstance.all())
