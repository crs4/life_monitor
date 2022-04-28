
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
from typing import List

import yaml
import lifemonitor.api.models as models
from .files import RepositoryFile, TemplateRepositoryFile

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepositoryConfig(RepositoryFile):

    FILENAME = "lifemonitor.yaml"

    def __init__(self, path: str) -> None:
        super().__init__(path, name=self.FILENAME, type='yaml')
        self.__raw_data = None

    def load(self) -> dict:
        return yaml.safe_load(self.get_content())

    @property
    def _raw_data(self) -> dict:
        if not self.__raw_data:
            self.__raw_data = self.load()
        return self.__raw_data

    @property
    def workflow_name(self) -> str:
        return self._raw_data.get('name', None)

    @property
    def public(self) -> bool:
        return self._raw_data.get('public', False)

    @property
    def checker_enabled(self) -> bool:
        try:
            return self._raw_data['issues']['check']
        except (AttributeError, KeyError):
            return True

    @property
    def include_issues(self) -> List[str]:
        try:
            return self._raw_data['issues']['include'].split(',')
        except (AttributeError, KeyError):
            return []

    @property
    def exclude_issues(self) -> List[str]:
        try:
            return self._raw_data['issues']['exclude'].split(',')
        except (AttributeError, KeyError):
            return []

    def _get_refs_list(self, refs="branches,tags") -> List:
        on_push = self._raw_data.get('on_push', None)
        if on_push and refs:
            return [_ for ref in refs.split(",") for _ in on_push.get(ref, [])]
        return None

    @property
    def registries(self) -> List[models.WorkflowRegistry]:
        registries = {}
        for rfs in self._get_refs_list():
            for r in rfs.get("update_registries", []):
                if not registries.get(r, None):
                    registries[r] = models.WorkflowRegistry.find_by_name(r)
        return list(registries.values())

    def _get_refs(self, type: str) -> List[str]:
        result = {}
        for r in self._get_refs_list(type):
            if not result.get(r['name'], None):
                result[r['name']] = r
        return result

    @property
    def branches(self) -> List[str]:
        return self._get_refs('branches')

    @property
    def tags(self) -> List[str]:
        return self._get_refs('tags')

    @classmethod
    def new(cls, repository_path: str, workflow_title: str = "Workflow RO-Crate", public: bool = False) -> WorkflowRepositoryConfig:
        tmpl = TemplateRepositoryFile(repository_path="lifemonitor/templates/repositories/base", name=f"{cls.FILENAME}.j2")
        registries = models.WorkflowRegistry.all()
        tmpl.write(workflow_title=workflow_title, public=public,
                   registries=registries, registries_csv=",".join([r.name for r in registries]),
                   output_file_path=os.path.join(repository_path, cls.FILENAME))
        return cls(path=repository_path)
