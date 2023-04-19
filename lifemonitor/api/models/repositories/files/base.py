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

import logging
import os
import re
from typing import Optional, Tuple

# set module level logger
logger = logging.getLogger(__name__)


class RepositoryFile():

    def __init__(self, repository_path: str, name: str,
                 type: Optional[str] = None, dir: str = ".", content=None) -> None:
        if not repository_path:
            raise ValueError("RepositoryPath constructed with empty repository_path")
        if not name:
            raise ValueError("RepositoryPath constructed with empty file name")
        self.repository_path = repository_path
        self.name = name
        self.dir = dir
        self._type = type or self.extension
        self._content = content

    def __repr__(self) -> str:
        return f"File {self.name} (dir: {self.dir})"

    @property
    def type(self) -> str:
        if not self._type and self.name:
            return self.get_type(self.name)
        return self._type

    @property
    def extension(self) -> str:
        return self.splitext()[1]

    @property
    def is_executable(self) -> bool:
        return os.access(self.path, os.X_OK)

    def splitext(self) -> Tuple[str, str]:
        return os.path.splitext(self.name)

    @property
    def is_binary(self) -> bool:
        try:
            with open(self.path) as f:
                f.readline()
            return False
        except UnicodeDecodeError:
            return True

    @property
    def path(self) -> str:
        dir_path = self.dir
        if self.repository_path:
            dir_path = os.path.abspath(os.path.join(self.repository_path, dir_path))
        return os.path.join(dir_path, self.name)

    def match(self, name: str, path: str = '.') -> bool:
        return self.name == name and self.has_path(path)

    def has_path(self, path) -> bool:
        return re.sub(r'\./?', '', self.dir) == re.sub(r'\./?', '', path)

    def get_content(self, binary_mode: bool = False) -> Optional[str | bytes]:
        if not self._content and self.dir:
            with open(f"{self.path}", 'rb' if binary_mode else 'r') as f:
                return f.read()
        return self._content

    @staticmethod
    def get_type(filename: str) -> str:
        parts = os.path.splitext(filename) if filename else None
        return parts[1].replace('.', '') if parts and len(parts) > 0 else None
