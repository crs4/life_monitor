
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

import base64
import logging
import os
import re
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional

from lifemonitor.api.models.repositories.base import (
    WorkflowRepository, WorkflowRepositoryMetadata)
from lifemonitor.api.models.repositories.files import (RepositoryFile,
                                                       WorkflowFile)
from lifemonitor.config import BaseConfig
from lifemonitor.exceptions import (DecodeROCrateException, LifeMonitorException,
                                    NotValidROCrateException)
from lifemonitor.utils import extract_zip, walk

# set module level logger
logger = logging.getLogger(__name__)


class LocalWorkflowRepository(WorkflowRepository):

    def __init__(self,
                 local_path: Optional[str] = None,
                 exclude: Optional[List[str]] = None) -> None:
        super().__init__(local_path, exclude)
        self._transient_files = {'add': {}, 'remove': {}}

    @classmethod
    def _file_key_(cls, f: RepositoryFile) -> str:
        return f"{f.dir}/{f.name}"

    @property
    def files(self) -> List[RepositoryFile]:
        result = []
        skip = self._transient_files['remove'].keys()
        for root, _, files in walk(self.local_path, exclude=self.exclude):
            dirname = root.replace(self.local_path, '.')
            for name in files:
                if f"{dirname}/{name}" not in skip:
                    result.append(RepositoryFile(self.local_path, name, dir=dirname))
        result.extend([v for k, v in self._transient_files['add'].items() if k not in skip])
        return result

    def add_file(self, file: RepositoryFile):
        assert isinstance(file, RepositoryFile), file
        self._transient_files['add'][self._file_key_(file)] = file
        self._transient_files['remove'].pop(self._file_key_(file), None)

    def remove_file(self, file: RepositoryFile):
        assert isinstance(file, RepositoryFile), file
        self._transient_files['remove'][self._file_key_(file)] = file
        self._transient_files['add'].pop(self._file_key_(file), None)
        if file.name == WorkflowRepositoryMetadata.DEFAULT_METADATA_FILENAME:
            self._metadata = None

    def save(self):
        for f in self._transient_files['remove'].values():
            if f.repository_path == self.local_path:
                logger.debug("Removing file: %r", f)
                os.remove(f.path)
        for f in self._transient_files['add'].values():
            logger.debug("Removing file: %r", f)
            shutil.copy(f.path, RepositoryFile(self.local_path, f.name, f.type, f.dir))
        self.reset()

    def reset(self):
        self._transient_files['add'].clear()
        self._transient_files['remove'].clear()

    @property
    def metadata(self) -> WorkflowRepositoryMetadata:
        if not self._metadata:
            try:
                self._metadata = WorkflowRepositoryMetadata(self, init=False)
            except ValueError:
                return None
        return self._metadata \
            if self._file_key_(self._metadata.repository_file) not in self._transient_files['remove'] \
            else None

    def find_file_by_pattern(self, search: str, path: Optional[str] = None) -> RepositoryFile:
        logger.warning("Searching file: %r %r", search, path)
        return next((f for f in self.files if re.search(search, f.name) and (not path or f.dir == path or f.dir == f"./{path}")), None)

    def find_file_by_name(self, name: str, path: Optional[str] = None) -> RepositoryFile:
        logger.warning("Searching file: %r %r", name, path)
        return next((f for f in self.files if f.name == name and (not path or f.path == path or f.dir == f"./{path}")), None)

    def find_workflow(self) -> WorkflowFile:
        for file in self.files:
            wf = WorkflowFile.is_workflow(file)
            if wf:
                logger.debug("Detected workflow: %r", wf)
                return wf
        return None


class TemporaryLocalWorkflowRepository(LocalWorkflowRepository):

    def __init__(self,
                 local_path: Optional[str] = None,
                 exclude: Optional[List[str]] = None,
                 auto_cleanup: bool = True) -> None:
        self.auto_cleanup = auto_cleanup
        super().__init__(local_path, exclude)

    def cleanup(self) -> None:
        logger.debug("Cleaning temp extraction folder of zipped repository @ %s ...", self.local_path)
        shutil.rmtree(self.local_path, ignore_errors=True)

    def __del__(self):
        if self.auto_cleanup:
            self.cleanup()
        else:
            logger.warning("Auto clean up disabled for repo: %r", self)


class ZippedWorkflowRepository(TemporaryLocalWorkflowRepository):

    def __init__(self, archive_path: str | Path, exclude: Optional[List[str]] = None, auto_cleanup: bool = True) -> None:
        local_path = tempfile.mkdtemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        super().__init__(local_path=local_path, exclude=exclude, auto_cleanup=auto_cleanup)
        try:
            extract_zip(archive_path, local_path)
            self.archive_path = archive_path
            logger.debug("Local path: %r", self.local_path)
        except FileNotFoundError as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            raise LifeMonitorException('Unable to process the Workflow ROCrate locally', detail=str(e), status=404)


class Base64WorkflowRepository(TemporaryLocalWorkflowRepository):

    def __init__(self, base64_rocrate: str) -> None:
        local_path = tempfile.mkdtemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        super().__init__(local_path, auto_cleanup=True)
        try:
            rocrate = base64.b64decode(base64_rocrate)
            zip_file = zipfile.ZipFile(BytesIO(rocrate))
            zip_file.extractall(local_path)
        except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
            msg = "RO-crate has bad zip format"
            logger.error(msg + ": %s", e)
            raise NotValidROCrateException(detail=msg, original_error=str(e))
        except Exception as e:
            logger.debug(e)
            raise DecodeROCrateException(detail=str(e))
