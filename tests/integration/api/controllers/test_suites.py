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

import json
import logging
import pytest

from tests import utils
from tests.conftest_types import ClientAuthenticationMethod


logger = logging.getLogger()


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_suite(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow,
                                                   public=client_auth_method == ClientAuthenticationMethod.NOAUTH)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)

    response = app_client.get(f"{utils.build_suites_path(suite.uuid)}", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    assert data['uuid'] == str(suite.uuid), "Invalid UUID"
    for p in ["roc_suite", "definition", "instances"]:
        assert p in data, f"Missing required property {p}"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_suite_status(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow,
                                                   public=client_auth_method == ClientAuthenticationMethod.NOAUTH)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)

    response = app_client.get(f"{utils.build_suites_path(suite.uuid)}/status", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    assert data['suite_uuid'] == str(suite.uuid), "Invalid UUID"
    for p in ["status", "latest_builds"]:
        assert p in data, f"Missing required property {p}"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_suite_instances(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow,
                                                   public=client_auth_method == ClientAuthenticationMethod.NOAUTH)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)

    response = app_client.get(f"{utils.build_suites_path(suite.uuid)}/instances",
                              headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    for p in ["items"]:
        assert p in data, f"Missing required property {p}"
