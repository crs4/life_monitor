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

import logging
import uuid

import pytest

from tests import utils
from tests.conftest_types import ClientAuthenticationMethod

logger = logging.getLogger()


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.API_KEY,
], indirect=True)
def test_github_service(app_client, client_auth_method,
                        user1, user1_auth, client_credentials_registry):
    wf = {
        'uuid': str(uuid.uuid4()),
        'version': '1',
        'roc_link': "http://webserver:5000/download?file=ro-crate-galaxy-sortchangecase-github-actions.crate.zip",
        'name': 'Galaxy workflow tested with GitHub Actions',
        'authorization': app_client.application.config['WEB_SERVER_AUTH_TOKEN']
    }

    response = app_client.post('/users/current/workflows', json=wf, headers=user1_auth)
    utils.assert_status_code(201, response.status_code)
    registration_data = response.json

    assert registration_data['wf_uuid'] == wf['uuid']
    assert registration_data['wf_version'] == wf['version']
    assert registration_data['name'] == wf['name']

    # verify that the workflow is registered
    response = app_client.get(f"/workflows/{registration_data['wf_uuid']}",
                              query_string={'previous_versions': False},
                              headers=user1_auth)
    utils.assert_status_code(200, response.status_code)

    response = app_client.get(f"/workflows/{registration_data['wf_uuid']}/status", headers=user1_auth)
    utils.assert_status_code(200, response.status_code)

    status_data = response.json
    assert status_data['version']['version'] == wf['version']
    assert status_data['aggregate_test_status'] != 'not_available'
    assert len(status_data['latest_builds']) == 1

    the_build = status_data['latest_builds'][0]
    assert 'status' in the_build
    assert the_build['status'] is not None
    assert the_build['instance']['service']['type'] == 'github'
    assert 'github.com' in the_build['instance']['service']['url']
    assert the_build['instance']['resource']
    assert not the_build['instance']['managed']
    assert the_build['timestamp']
