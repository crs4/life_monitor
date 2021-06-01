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
from lifemonitor.db import db
from lifemonitor.auth.models import User
from .rocrate import ROCrate

# 'status' module
from .status import Status, AggregateTestStatus, WorkflowStatus, SuiteStatus

# 'registries' package
from .registries import WorkflowRegistry, WorkflowRegistryClient

# 'workflows' package
from .workflows import Workflow, WorkflowVersion

# 'testsuites' package
from .testsuites import TestSuite, TestInstance, ManagedTestInstance, BuildStatus, TestBuild

# 'testing_services'
from .services import TestingService, \
    GitHubTestingService, GitHubTestBuild, \
    JenkinsTestingService, JenkinsTestBuild, \
    TravisTestingService, TravisTestBuild, \
    TestingServiceToken, TestingServiceTokenManager


__all__ = [
    "AggregateTestStatus",
    "BuildStatus",
    "db",
    "GitHubTestBuild",
    "GitHubTestingService",
    "JenkinsTestBuild",
    "JenkinsTestingService",
    "ManagedTestInstance",
    "ROCrate",
    "Status",
    "SuiteStatus",
    "TestBuild",
    "TestingService",
    "TestingServiceToken",
    "TestingServiceTokenManager",
    "TestInstance",
    "TestSuite",
    "TravisTestBuild",
    "TravisTestingService",
    "User",
    "Workflow",
    "WorkflowRegistry",
    "WorkflowRegistryClient",
    "WorkflowStatus",
    "WorkflowVersion",
]

# set module level logger
logger = logging.getLogger(__name__)
