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

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from lifemonitor import utils

from .base import RepositoryFile

# set module level logger
logger = logging.getLogger(__name__)


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

    def get_content(self, binary_mode: bool = False, refresh: bool = False, **kwargs):
        data = self.data.copy() if self.data else {}
        data.update(kwargs)
        if (not self._content or refresh) and self.dir:
            is_template = self.template_file_path.endswith('.j2')
            if is_template:
                jinja_env = Environment(loader=FileSystemLoader("/", followlinks=True), autoescape=select_autoescape())
                template = jinja_env.get_template(self.template_file_path.lstrip('/'))
                self._content = template.render(filename=self.name,
                                                workflow_snakecase_name=utils.to_snake_case(data.get('workflow_name', '')),
                                                workflow_kebabcase_name=utils.to_kebab_case(data.get('workflow_name', '')),
                                                **data) + '\n'
            else:
                with open(self.template_file_path, 'rb' if binary_mode and not is_template else 'r') as f:
                    content = f.read()
                self._content = content
        return self._content

    def write(self, binary_mode: bool = False, output_file_path: str = None, **kwargs):
        content = self.get_content(binary_mode=binary_mode, **kwargs)
        with open(output_file_path or self._output_file_path, 'wb' if binary_mode else 'w') as f:
            f.write(content)
