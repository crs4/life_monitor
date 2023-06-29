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
from typing import Dict, List, Optional

from lifemonitor.api.models.repositories.files import (TemplateRepositoryFile,
                                                       WorkflowFile)
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository
from lifemonitor.utils import find_types, to_kebab_case

from ..base import WorkflowRepository, WorkflowRepositoryMetadata

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepositoryTemplate():

    # template subclasses
    templates: List[WorkflowRepositoryTemplate] = None

    def __init__(self, data: Optional[Dict[str, str]] = None,
                 local_path: Optional[str] = None, init_git: bool = False) -> None:
        # if local_path is None then create a temporary directory
        if not local_path:
            local_path = tempfile.NamedTemporaryFile(dir='/tmp').name
        # init local path
        self._local_path = local_path
        self._files = None
        # init default data
        self._data = self.get_defaults()
        # update data with the provided one
        if data:
            self._data.update(data)
        # set flag to indicate if the template has been initialised as a git repository
        self._init_git = init_git
        self._dirty = True

    @classmethod
    def get_defaults(cls) -> Dict:
        return {}

    @property
    def type(self) -> str:
        wf_type = self.__class__.__name__.replace("RepositoryTemplate", "").lower()
        return wf_type if wf_type != 'workflow' else 'other'

    @property
    def local_path(self) -> str:
        return self._local_path

    @property
    def data(self) -> Dict:
        return self._data

    @data.setter
    def data(self, data: Dict):
        assert isinstance(data, dict), data
        self._data.update(data)
        self._dirty = True

    @property
    def init_git(self) -> bool:
        return self._init_git

    @init_git.setter
    def init_git(self, init_git: bool):
        self._init_git = init_git

    @property
    def _templates_base_path(self) -> str:
        return "lifemonitor/templates/repositories"

    @property
    def template_path(self) -> str:
        return os.path.join(self._templates_base_path, self.type)

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

    def __init_repo_object__(self, target_path: str) -> LocalWorkflowRepository:
        # prepare the metadata to initialise the repository
        data = {
            'name': self.data.get('workflow_name', 'MyWorkflow'),
            'license': self.data.get('workflow_license', 'MIT'),
            'owner': self.data.get('workflow_author', 'lm'),
            'exclude': self.data.get('exclude', []),
            'remote_url': self.data.get('repo_url', None),
        }
        # initialise the repository
        repo = LocalWorkflowRepository(target_path, **data) \
            if not self.init_git else LocalGitWorkflowRepository(target_path, **data)
        # return the repository object
        return repo

    def generate(self, target_path: Optional[str] = None) -> WorkflowRepository:
        target_path = target_path or self.local_path
        # create the target directory if it does not exist
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)
        # initialise the target directory as a git repository
        if self._init_git and not WorkflowRepository.is_git_repository(target_path):
            pygit2.init_repository(target_path, bare=False)
        # initialise the repository object
        repo = self.__init_repo_object__(target_path)
        # render the template files
        logger.debug("Rendering template files to %s...", target_path)
        self.write(target_path)
        logger.debug("Rendering template files to %s... DONE", target_path)
        # generate the metadata
        opts = self.data.copy()
        opts.update({
            'root': target_path,
        })
        metadata = repo.generate_metadata(**opts)
        assert isinstance(metadata, WorkflowRepositoryMetadata), "Error generating workflow repository metadata"
        # return the repository
        return repo

    def write(self, target_path: str, overwrite: bool = False) -> None:
        for f in self.files:
            base_path = os.path.join(target_path, f.dir)
            file_path = os.path.join(base_path, f.name)
            os.makedirs(base_path, exist_ok=True)
            file_exists = os.path.isfile(file_path)
            if not file_exists or overwrite:
                logger.debug("%s file: %r", "Overwriting" if file_exists else "Writing", file_path)
                with open(file_path, "w") as out:
                    out.write(f.get_content())

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
