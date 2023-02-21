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

from flask import Blueprint, Flask
from lifemonitor.auth.services import authorized_by_session_or_apikey

import lifemonitor.metrics.model as stats
from lifemonitor.metrics.model import get_metric_key

#
logger = logging.getLogger(__name__)


# Initialize metrics endpoint
blueprint = Blueprint('metrics', __name__)


def register_blueprint(app: Flask, url_prefix: str, metrics_prefix: str):
    app.register_blueprint(blueprint, url_prefix=url_prefix)



@blueprint.route('/users', methods=('GET',))
@authorized_by_session_or_apikey
def users():
    return f"{get_metric_key('users')} {stats.users()}"


@blueprint.route('/workflows', methods=('GET',))
@authorized_by_session_or_apikey
def workflows():
    return f"{get_metric_key('workflows')} {stats.workflows()}"


@blueprint.route('/workflow_versions', methods=('GET',))
@authorized_by_session_or_apikey
def count_workflow_versions():
    return f"{get_metric_key('workflow_versions')} {stats.workflow_versions()}"


@blueprint.route('/workflow_registries', methods=('GET',))
@authorized_by_session_or_apikey
def count_workflow_registries():
    return f"{get_metric_key('workflow_registries')} {stats.workflow_registries()}"


@blueprint.route('/workflow_suites', methods=('GET',))
@authorized_by_session_or_apikey
def count_workflow_suites():
    return f"{get_metric_key('workflow_suites')} {stats.workflow_suites()}"


@blueprint.route('/workflow_test_instances', methods=('GET',))
@authorized_by_session_or_apikey
def count_workflow_test_instances():
    return f"{get_metric_key('workflow_suites')} {stats.workflow_test_instances()}"
