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
from lifemonitor.api import models
from tests import utils
from tests.conftest_types import ClientAuthenticationMethod

logger = logging.getLogger()


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_add_unmanaged_instance(app_client, client_auth_method, user1, user1_auth,
                                random_valid_workflow, unmanaged_test_instance):
    w, workflow = utils.pick_and_register_workflow(user1, random_valid_workflow)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    # get/check number of instances before
    num_of_instances = len(suite.test_instances)
    assert num_of_instances > 0, "Unexpected number of test instances"
    # post new unmanaged instance
    response = app_client.post(f"{utils.build_suites_path(suite.uuid)}/instances",
                               headers=user1_auth, json=unmanaged_test_instance)
    logger.debug(response)
    utils.assert_status_code(201, response.status_code)
    response_data = json.loads(response.data)
    assert "uuid" in response_data, "Unexpcted response: missing 'uuid'"
    # check number of instances after
    assert len(suite.test_instances) == num_of_instances + 1, "Unexpected number of instances"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_add_managed_instance(app_client, client_auth_method,
                              user1, user1_auth,
                              random_valid_workflow, managed_test_instance):
    w, workflow = utils.pick_and_register_workflow(user1, random_valid_workflow)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    # get/check number of instances before
    num_of_instances = len(suite.test_instances)
    assert num_of_instances > 0, "Unexpected number of test instances"
    # post new unmanaged instance
    response = app_client.post(f"{utils.build_suites_path(suite.uuid)}/instances",
                               headers=user1_auth, json=managed_test_instance)
    logger.debug(response)
    utils.assert_status_code(501, response.status_code)
    # check number of instances after
    assert len(suite.test_instances) == num_of_instances, "Unexpected number of instances"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_remove_instance(app_client, client_auth_method,
                         user1, user1_auth,
                         random_valid_workflow, unmanaged_test_instance):
    w, workflow = utils.pick_and_register_workflow(user1, random_valid_workflow)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    current_number_of_instances = len(suite.test_instances)
    assert current_number_of_instances > 0, "Unexpected number of test instances"

    delta = 5
    for i in range(1, delta + 1):
        suite.add_test_instance(user1['user'],
                                unmanaged_test_instance['managed'],
                                unmanaged_test_instance['name'],
                                unmanaged_test_instance['service']['type'],
                                unmanaged_test_instance['service']['url'],
                                unmanaged_test_instance['resource'])
        assert len(suite.test_instances) == current_number_of_instances + i, \
            "Unexpected number of test instances"
    count = 0
    current_number_of_instances += delta
    assert current_number_of_instances > 0, "Unexpected number of test instances"
    for instance in suite.test_instances:
        logger.debug("Removing instance: %r", instance)
        response = app_client.delete(f"{utils.build_instances_path(instance.uuid)}",
                                     headers=user1_auth)
        utils.assert_status_code(204, response.status_code)
        count += 1
        assert len(suite.test_instances) == current_number_of_instances - count
    assert len(suite.test_instances) == 0, "Unexpected number of instances"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_instance(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow,
                                                   public=client_auth_method == ClientAuthenticationMethod.NOAUTH)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    assert len(suite.test_instances) > 0, "Unexpected number of test instances"
    instance = suite.test_instances[0]
    logger.debug("The test instance: %r", instance)

    response = app_client.get(f"{utils.build_instances_path(instance.uuid)}",
                              headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    utils.assert_properties_exist(["name", "service"], data)
    assert data['uuid'] == str(instance.uuid), "Invalid UUID"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_instance_builds(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow,
                                                   public=client_auth_method == ClientAuthenticationMethod.NOAUTH)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    assert len(suite.test_instances) > 0, "Unexpected number of test instances"
    instance = suite.test_instances[0]
    logger.debug("The test instance: %r", instance)

    response = app_client.get(f"{utils.build_instances_path(instance.uuid)}/latest-builds?limit=2",
                              headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(200, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    assert "items" in data, "Missing item property"
    num_items = len(data['items'])
    logger.info("Number of items: %d", num_items)
    assert num_items > 0, "Unexpected number of items"
    # check one item
    item = data['items'][0]
    utils.assert_properties_exist(["build_id", "instance"], item)


def test_get_instance_builds_rate_limit_exceeded(app_client, client_auth_method, user1, user1_auth, rate_limit_exceeded_workflow: models.Workflow):
    workflow = rate_limit_exceeded_workflow.latest_version
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    assert len(suite.test_instances) > 0, "Unexpected number of test instances"
    instance = suite.test_instances[0]
    logger.debug("The test instance: %r", instance)
    response = app_client.get(f"{utils.build_instances_path(instance.uuid)}/latest-builds?limit=2", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(403, response.status_code)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['title'] == 'Rate Limit Exceeded', "Unexpected error title"


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_instance_builds_limit_parameter(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    assert len(suite.test_instances) > 0, "Unexpected number of test instances"
    instance = suite.test_instances[0]
    logger.debug("The test instance: %r", instance)

    # check limit parameter
    for limit in range(1, 4):
        response = app_client.get(f"{utils.build_instances_path(instance.uuid)}/latest-builds?limit={limit}",
                                  headers=user1_auth)
        logger.debug(response)
        utils.assert_status_code(200, response.status_code)
        data = json.loads(response.data)
        logger.debug("Response data: %r", data)
        # redundant check: the validation is performed by the connexion framework
        assert "items" in data, "Missing item property"
        num_items = len(data['items'])
        logger.info("Number of items: %d", num_items)
        assert num_items == limit, "Unexpected number of items"
        logger.info("Loaded builds: %s", data)


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_instance_build(app_client, client_auth_method, user1, user1_auth, valid_workflow):
    w, workflow = utils.pick_and_register_workflow(user1, valid_workflow,
                                                   public=client_auth_method == ClientAuthenticationMethod.NOAUTH)
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    assert len(suite.test_instances) > 0, "Unexpected number of test instances"
    instance = suite.test_instances[0]
    logger.debug("The test instance: %r", instance)
    assert len(instance.get_test_builds()) > 0, "Unexpected number of test builds"
    build = instance.get_test_builds()[0]

    response = app_client.get(f"{utils.build_instances_path(instance.uuid)}/builds/{build.id}",
                              headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(response.status_code, 200)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    # redundant check: the validation is performed by the connexion framework
    utils.assert_properties_exist(["build_id", "instance"], data)


@pytest.mark.parametrize("client_auth_method", [
    #    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_get_instance_build_rate_limit_exceeded(app_client, client_auth_method, user1, user1_auth, rate_limit_exceeded_workflow: models.Workflow):
    workflow = rate_limit_exceeded_workflow.latest_version
    assert len(workflow.test_suites) > 0, "Unexpected number of test suites"
    suite = workflow.test_suites[0]
    logger.debug("The test suite: %r", suite)
    assert len(suite.test_instances) > 0, "Unexpected number of test instances"
    instance = suite.test_instances[0]
    logger.debug("The test instance: %r", instance)

    response = app_client.get(f"{utils.build_instances_path(instance.uuid)}/builds/0", headers=user1_auth)
    logger.debug(response)
    utils.assert_status_code(response.status_code, 403)
    data = json.loads(response.data)
    logger.debug("Response data: %r", data)
    assert data['title'] == 'Rate Limit Exceeded', "Unexpected error title"
