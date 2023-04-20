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

from prometheus_client import Gauge


# initialize logger
logger = logging.getLogger(__name__)

# Set the global prefix for LifeMonitor metrics
PREFIX = "lifemonitor_api"


def get_metric_key(key: str) -> str:
    return f"{PREFIX}_{key}"


# number of users
users = Gauge(get_metric_key('users'), "Number of users registered on the LifeMonitor instance", )
# number of workflows
workflows = Gauge(get_metric_key('workflows'), "Number of workflows registered on the LifeMonitor instance")
# number of workflow versions
workflow_versions = Gauge(get_metric_key('workflow_versions'), "Number of workflow versions registered on the LifeMonitor instance")
# number of workflow registries
workflow_registries = Gauge(get_metric_key('workflow_registries'), "Number of workflow registries registered on the LifeMonitor instance")
# number of workflow suites
workflow_suites = Gauge(get_metric_key('workflow_suites'), "Number of workflow suites registered on the LifeMonitor instance")
# number of workflow test instances
workflow_test_instances = Gauge(get_metric_key('workflow_test_instances'), "Number of workflow test instances registered on the LifeMonitor instance")
