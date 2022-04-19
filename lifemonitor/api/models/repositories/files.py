
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
from typing import Dict, Optional

from flask import render_template_string

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowFile():

    extension_map = {
        'ga': 'galaxy',
        'smk': 'snakemake',
        'ipynb': 'jupyter',
        'sh': 'bash',
    }

    def __init__(self, path: str, type_: str, name: str = None) -> None:
        self.path = path
        self.type = type_
        self.name = name

    def __repr__(self) -> str:
        return f"Workflow \"{self.name}\" (type: {self.type}, path: {self.path})"


class RepositoryFile():

    def __init__(self, repository_path: str, name: str,
                 type: str = None, dir: str = ".", content=None) -> None:
        self.repository_path = repository_path
        self.name = name
        self.dir = dir
        self._type = type
        self._content = content

    def __repr__(self) -> str:
        return f"File {self.name} (dir: {self.dir})"

    @property
    def type(self) -> str:
        if not self._type and self.name:
            return self.get_type(self.name)
        return self._type

    @property
    def path(self) -> str:
        dir_path = self.dir
        if self.repository_path:
            dir_path = os.path.abspath(os.path.join(self.repository_path, dir_path))
        return os.path.join(dir_path, self.name)

    def get_content(self, binary_mode: bool = False):
        if not self._content and self.dir:
            with open(f"{self.path}", 'rb' if binary_mode else 'r') as f:
                return f.read()
        return self._content

    @staticmethod
    def get_type(filename: str) -> str:
        parts = os.path.splitext(filename) if filename else None
        return parts[1].replace('.', '') if parts and len(parts) > 0 else None


class TemplateRepositoryFile(RepositoryFile):

    def __init__(self, repository_path: str, name: str, type: str = None,
                 dir: str = ".", data: Dict = None) -> None:
        super().__init__(repository_path, name.replace('.j2', ''), type, dir, None)
        self.template_filename = name
        self._data = data

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.name} (dir: {self.dir})"

    @property
    def path(self) -> str:
        return self.template_file_path

    @property
    def data(self) -> Optional[Dict]:
        return self._data

    @property
    def template_file_path(self) -> str:
        return os.path.join(
            os.path.abspath(os.path.join(self.repository_path, self.dir)),
            self.template_filename)

    @property
    def _output_file_path(self) -> str:
        return os.path.join(
            os.path.abspath(os.path.join(self.repository_path, self.dir)),
            self.name)

    def get_content(self, binary_mode: bool = False, **kwargs):
        data = self.data.copy() if self.data else {}
        data.update(kwargs)
        if not self._content and self.dir:
            with open(self.template_file_path, 'rb' if binary_mode else 'r') as f:
                template = f.read()
                if self.template_file_path.endswith('.j2'):
                    template = render_template_string(template, **data)
                return template
        return self._content

    def write(self, binary_mode: bool = False, output_file_path: str = None, **kwargs):
        content = self.get_content(binary_mode=binary_mode, **kwargs)
        with open(output_file_path or self._output_file_path, 'wb' if binary_mode else 'w') as f:
            f.write(content)
