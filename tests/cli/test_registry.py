# Copyright (c) 2020-2024 CRS4
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
from lifemonitor.commands import registry
from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api.services import LifeMonitor

logger = logging.getLogger(__name__)


def test_registry_add(cli_runner, provider_type,
                      random_string, fake_uri):
    result = cli_runner.invoke(registry.add_registry, [
        random_string,
        provider_type.value,
        random_string,
        random_string,
        fake_uri,
        "--client-auth-method", "client_secret_basic",
        "--redirect-uris", fake_uri
    ])
    logger.info(result.output)
    assert 'Error' not in result.output, "Invalid CLI options"
    for p in ['CLIENT ID', 'CLIENT SECRET', 'SCOPES', 'REDIRECT URIs']:
        assert p in result.output, f"'{p}' not found as command output"


def test_registry_update(cli_runner, provider_type,
                         random_string, fake_uri):
    reg = LifeMonitor.get_instance().add_workflow_registry(
        provider_type.value, random_string, random_string, random_string,
        api_base_url=fake_uri, redirect_uris=fake_uri)
    assert isinstance(reg, WorkflowRegistry), "Unexpected object instance"
    result = cli_runner.invoke(registry.update_registry, [
        str(reg.uuid),
        "--name", f"{random_string}_",
        "--client-id", f"{random_string}_x1",
        "--client-secret", f"{random_string}_x2",
        "--api-url", fake_uri,
        "--redirect-uris", f"{fake_uri}",
        "--client-auth-method", 'client_secret_basic'
    ])
    logger.info(result.output)
    assert len(result.output) > 0, "No output"
    assert 'Error' not in result.output, "Invalid CLI options"
    assert 'ERROR' not in result.output, "Update error"


def test_registry_list(cli_runner, provider_type,
                       random_string, fake_uri):

    reg = LifeMonitor.get_instance().add_workflow_registry(
        provider_type.value, random_string, random_string, random_string,
        api_base_url=fake_uri)
    assert isinstance(reg, WorkflowRegistry), "Unexpected object instance"
    result = cli_runner.invoke(registry.list_registries, [])
    logger.debug(result.output)
    assert 'Workflow Registries' in result.output, "Missing header"
    assert str(reg.uuid) in result.output, f"Missing workflow registry '{reg.uuid}'"
