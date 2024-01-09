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


import filecmp
import logging
import os
import tempfile
from typing import Dict, Union

import pytest
from lifemonitor.storage import RemoteStorage

logger = logging.getLogger(__name__)


def storage_config() -> Union[Dict[str, str], bool]:
    try:
        return {
            'endpoint_url': os.environ['S3_ENDPOINT_URL'],
            'aws_access_key_id': os.environ['S3_ACCESS_KEY'],
            'aws_secret_access_key': os.environ['S3_SECRET_KEY'],
            'bucket_name': "lm-tests"
        }
    except KeyError:
        return False


@pytest.fixture
def storage(app_context) -> RemoteStorage:
    return RemoteStorage(config=storage_config())  # type: ignore


@pytest.fixture
def filename():
    return "README.md"


@pytest.fixture
def test_data_folder():
    return "data"


def test_storage_not_enabled(app_context):
    r = RemoteStorage(config={})
    assert not r.enabled, "Storage should not be enabled"


@pytest.mark.skipif(not storage_config(), reason="Storage properly configured on environment")
def test_storage_enabled(app_context):
    r = RemoteStorage(config={})
    assert not r.enabled, "Storage should not be enabled"


@pytest.mark.skipif(not storage_config(), reason="Storage properly configured on environment")
def test_get_file(app_context, storage: RemoteStorage, test_data_folder: str, filename: str):

    remote_path = f"{test_data_folder}/test_file"

    # test file upload
    storage.put_file(filename, remote_path)

    # test if file exists
    assert storage.exists(remote_path), "Uploaded file not found on remote storage"

    # test file download
    with tempfile.NamedTemporaryFile(dir="/tmp") as out_file:
        storage.get_file(remote_path, out_file.name)
        assert filecmp.cmp(filename, out_file.name), "File not found"

    # test file deletion
    storage.delete_file(remote_path)
    assert not storage.exists(remote_path), f"File {remote_path} should not be there"

    # test folder deletion
    storage.delete_folder(test_data_folder)
    assert not storage.exists(test_data_folder), f"Data folder '{test_data_folder}' should not be there"
