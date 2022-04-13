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
from typing import Dict, List

from lifemonitor.api.models.repositories.files import TemplateRepositoryFile

from .base import WorkflowRepository

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepositoryTemplate(WorkflowRepository):

    def __init__(self, name: str, local_path: str = ".", data: dict = None) -> None:
        super().__init__(local_path)
        self.name = name
        self._files = None
        self._data = data or {}
        self._dirty = True

    @property
    def data(self) -> Dict:
        return self._data

    @data.setter
    def data(self, data: Dict):
        assert isinstance(data, dict), data
        self._data.update(data)
        self._dirty = True

    @property
    def _templates_base_path(self) -> str:
        return "lifemonitor/templates/repositories"

    @property
    def template_path(self) -> str:
        return os.path.join(self._templates_base_path, self.name)

    @property
    def files(self) -> List[TemplateRepositoryFile]:
        if not self._files or self._dirty:
            self._files = self._load_files()
            self._dirty = False
        return self._files

    def _load_files(self, path: str = None):
        result = []
        paths = [path or self.template_path]
        if not path:
            paths.append(os.path.join(self._templates_base_path, 'base'))
        for base_path in paths:
            for root, _, files in os.walk(base_path):
                logger.debug("Root: %r", root)
                dirname = root.replace(base_path, ".")
                for filename in files:
                    logger.debug("FileName: %r", filename)
                    result.append(
                        TemplateRepositoryFile(base_path, filename, filename,
                                               dir=dirname, data=self.data))
        return result

    def get_files(self, **kwargs) -> List[TemplateRepositoryFile]:
        return self.files

    def get_file(self, name: str) -> TemplateRepositoryFile:
        for f in self.files:
            if f.name == name or f"{f.name}.j2" == name:
                return f
        return None
