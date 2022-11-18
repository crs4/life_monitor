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
import tempfile
from typing import Dict, List

from lifemonitor.api.models.repositories.files import (TemplateRepositoryFile,
                                                       WorkflowFile)
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository
from lifemonitor.utils import find_types, to_kebab_case

from ..base import WorkflowRepository, WorkflowRepositoryMetadata

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepositoryTemplate(WorkflowRepository):

    # template subclasses
    templates: List[WorkflowRepositoryTemplate] = None

    def __init__(self, name: str, local_path: str = None,
                 data: dict = None, exclude: List[str] = None) -> None:
        if not local_path:
            local_path = tempfile.NamedTemporaryFile(dir='/tmp').name
        super().__init__(local_path, exclude=exclude)
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

    def get_workflow_name(self) -> str:
        # try to find a valid extension for the workflow of this template
        prefix = to_kebab_case(self.name)
        wext = WorkflowFile.get_workflow_extensions(self.name)
        if wext and len(wext) > 0:
            return f"{prefix}.{wext.pop()}"  # pick the first
        return prefix

    def _load_files(self, path: str = None):
        result = []
        paths = [path] if path else None
        if not paths:
            paths = [os.path.join(self._templates_base_path, 'base'), self.template_path]
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

    def generate(self, target_path: str = None) -> LocalWorkflowRepository:
        target_path = target_path or self.local_path
        logger.debug("Rendering template files to %s...", target_path)
        self.write(target_path)
        logger.debug("Rendering template files to %s... DONE", target_path)
        repo = LocalWorkflowRepository(target_path)
        opts = self.data.copy()
        opts.update({
            'root': target_path,
        })
        repo.generate_metadata(**self.data)
        return repo

    def generate_metadata(self) -> WorkflowRepositoryMetadata:
        self._metadata = WorkflowRepositoryMetadata(self, init=True, exclude=self.exclude,
                                                    local_path=self._local_path)
        self._metadata.add_workflow(self.get_workflow_name(),
                                    lang=self.name, properties={
                                        'name': self.data.get('workflow_title', None)} if self.data else None)
        self._metadata.write(self._local_path)
        return self._metadata

    def write(self, target_path: str):
        super().write(target_path)
        # rename files according to best practices
        if self.name == "galaxy":
            os.rename(os.path.join(target_path, 'workflow.ga'),
                      os.path.join(target_path, f"{to_kebab_case(self.data.get('workflow_name', 'workflow'))}.ga"))
            os.rename(os.path.join(target_path, 'workflow-test.yml'),
                      os.path.join(target_path, f"{to_kebab_case(self.data.get('workflow_name', 'workflow'))}-test.yml"))

    @classmethod
    def _types(cls) -> List[WorkflowRepositoryTemplate]:
        if not cls.templates:
            cls.templates = find_types(WorkflowRepositoryTemplate, path=os.path.dirname(__file__))
        return cls.templates

    @classmethod
    def _get_type(cls, name: str) -> WorkflowRepositoryTemplate:
        try:
            return cls._types()[f"{name.capitalize()}RepositoryTemplate"]
        except KeyError:
            return WorkflowRepositoryTemplate

    @classmethod
    def new_instance(cls, name: str, local_path: str = None,
                     data: dict = None, exclude: List[str] = None) -> WorkflowRepositoryTemplate:
        tmpl_type = cls._get_type(name)
        logger.debug("Using template type: %s", tmpl_type)
        return tmpl_type(name, local_path=local_path, data=data, exclude=exclude)
