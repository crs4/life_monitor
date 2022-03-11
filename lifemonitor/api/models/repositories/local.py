
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
import re
import shutil
import tempfile

from lifemonitor.api.models.repositories.base import (
    WorkflowRepository, WorkflowRepositoryMetadata)
from lifemonitor.api.models.repositories.files import (RepositoryFile,
                                                       WorkflowFile)
from lifemonitor.config import BaseConfig
from lifemonitor.exceptions import IllegalStateException
from lifemonitor.utils import extract_zip

# set module level logger
logger = logging.getLogger(__name__)


class LocalWorkflowRepository(WorkflowRepository):

    def __init__(self, local_path: str = None) -> None:
        self._local_path = local_path
        self._metadata = None

    @property
    def local_path(self) -> str:
        return self._local_path

    @property
    def metadata(self) -> WorkflowRepositoryMetadata:
        if not self._metadata:
            try:
                self._metadata = WorkflowRepositoryMetadata(self, init=False)
            except ValueError:
                return None
        return self._metadata

    def find_file_by_pattern(self, search: str) -> RepositoryFile:
        for root, _, files in os.walk(self.local_path):
            for name in files:
                if re.search(search, name):
                    return RepositoryFile(name, dir=root)
        return None

    def find_file_by_name(self, name: str) -> RepositoryFile:
        for root, _, files in os.walk(self.local_path):
            for fn in files:
                if name == fn:
                    return RepositoryFile(name, dir=root)
        return None

    def find_workflow(self) -> WorkflowFile:
        for root, _, files in os.walk(self.local_path):
            for name in files:
                for ext, wf_type in WorkflowFile.extension_map.items():
                    if re.search(rf"\.{ext}$", name):
                        return RepositoryFile(name, type=wf_type, dir=root)
        return None

    def make_crate(self):
        self._metadata = WorkflowRepositoryMetadata(self, init=True)
        self._metadata.write(self._local_path)

    def write_zip(self, target_path: str):
        if not self.metadata:
            raise IllegalStateException(detail="Missing RO Crate metadata")
        self.metadata.write_zip(target_path)


class ZippedWorkflowRepository(LocalWorkflowRepository):

    def __init__(self, archive_path: str = None) -> None:
        local_path = tempfile.mkdtemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        extract_zip(archive_path, local_path)
        super().__init__(local_path=local_path)

    def __del__(self):
        logger.debug(f"Cleaning temp extraction folder of zipped repository @ {self.local_path} .... ")
        shutil.rmtree(self.local_path, ignore_errors=True)
        logger.debug(f"Cleaning temp extraction folder of zipped repository @ {self.local_path} .... ")
