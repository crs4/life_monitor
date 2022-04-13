
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
            with open(f"{self.dir}/{self.name}", 'rb' if binary_mode else 'r') as f:
                return f.read()
        return self._content

    @staticmethod
    def get_type(filename: str) -> str:
        parts = os.path.splitext(filename) if filename else None
        return parts[1].replace('.', '') if parts and len(parts) > 0 else None
