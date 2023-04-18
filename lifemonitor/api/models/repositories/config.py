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

import itertools as it
import logging
import os
import os.path
from typing import Dict, List, Optional

import yaml

import lifemonitor.api.models as models
from lifemonitor.schemas.validators import (ConfigFileValidator,
                                            ValidationResult)
from lifemonitor.utils import match_ref

from .files import RepositoryFile, TemplateRepositoryFile

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepositoryConfig(RepositoryFile):

    __BASE_FILENAME__ = "lifemonitor"
    DEFAULT_FILENAME = f".{__BASE_FILENAME__}.yaml"
    TEMPLATE_FILENAME = f"{DEFAULT_FILENAME}.j2"

    def __init__(self, repo_path: str) -> None:
        config_file = self._search_for_config_file(repo_path)
        if config_file:
            super().__init__(repo_path, name=config_file, type='yaml')
            self.__raw_data = None
        else:
            logger.debug("Cannot find configuration file in repository %s", repo_path)
            raise ValueError("cannot find configuration file in repository")

    @classmethod
    def _search_for_config_file(cls, repo_path: str) -> Optional[str]:
        for head, ext in it.product(('', '.'), ('yml', 'yaml')):
            filename = f"{head}{cls.__BASE_FILENAME__}.{ext}"
            p = f"{repo_path}/{filename}"
            if os.path.isfile(p):
                return filename
        return None  # file not found

    def load(self) -> dict:
        return yaml.safe_load(self.get_content())

    @property
    def _raw_data(self) -> dict:
        if not self.__raw_data:
            try:
                self.__raw_data = self.load()
            except Exception:
                self.__raw_data = {}
        return self.__raw_data

    @property
    def is_valid(self) -> bool:
        try:
            result: ValidationResult = ConfigFileValidator.validate(self.load())
            return result.valid
        except Exception:
            return False

    def validate(self) -> ValidationResult:
        return ConfigFileValidator.validate(self.load())

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

    def __parse_list__(self, property) -> List[str]:
        try:
            raw_data = self._raw_data['issues'][property]
            if isinstance(raw_data, str):
                return self._raw_data['issues'][property].split(',')
            elif isinstance(raw_data, list):
                return raw_data
            raise ValueError(f"Invalid format for '{property}' property")
        except (AttributeError, KeyError):
            return []

    @property
    def include_issues(self) -> List[str]:
        return self.__parse_list__('include')

    @property
    def exclude_issues(self) -> List[str]:
        return self.__parse_list__('exclude')

    def _get_push_data(self) -> Dict:
        return self._raw_data.get('push', None)

    def _get_refs_list(self, refs="branches,tags") -> List:
        on_push = self._raw_data.get('push', None)
        if on_push and refs:
            return [_ for ref in refs.split(",") for _ in on_push.get(ref, [])]
        return []

    def _get_ref_settings(self, ref: str, ref_type: str) -> Optional[Dict]:
        ref_pattern = match_ref(ref, self.branches if ref_type == 'branch' else self.tags)
        if not ref_pattern:
            return None
        logger.debug(f"ref {ref} matched with pattern {ref_pattern}")
        return next((r for r in self._raw_data['push']['branches' if ref_type == 'branch' else 'tags'] if r["name"] == ref_pattern[1]), None)

    def get_ref_settings(self, ref: str) -> Optional[Dict]:
        return self._get_ref_settings(ref, 'branch') or self._get_ref_settings(ref, 'tag') or None

    @property
    def registries(self) -> List[models.WorkflowRegistry]:
        registries = {}
        for rfs in self._get_refs_list():
            for r in rfs.get("update_registries", []):
                if not registries.get(r, None):
                    registries[r] = models.WorkflowRegistry.find_by_client_name(r)
        return list(registries.values())

    def get_ref_registries(self, ref_type: str, tag: str) -> List[models.WorkflowRegistry]:
        try:
            tag_data = next((r for r in self._raw_data['push'][ref_type] if r["name"] == tag), None)
            if not tag_data:
                return []
            registries = {}
            for r in tag_data.get("update_registries", []):
                if not registries.get(r, None):
                    registry = models.WorkflowRegistry.find_by_client_name(r)
                    if not registry:
                        logger.warning("Unable to find registry: %r", r)
                    registries[r] = models.WorkflowRegistry.find_by_client_name(r)
            return list(registries.values())
        except KeyError as e:
            logger.debug("KeyError: %r", str(e))
            return []

    def get_tag_registries(self, tag: str) -> List[models.WorkflowRegistry]:
        return self.get_ref_registries('tags', tag)

    def get_branch_registries(self, branch: str) -> List[models.WorkflowRegistry]:
        return self.get_ref_registries('branches', branch)

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
    def new(cls, repository_path: str, workflow_title: Optional[str] = None, public: bool = False, main_branch: str = "main") -> WorkflowRepositoryConfig:
        if workflow_title is None:
            workflow_title = "Workflow RO-Crate"
        tmpl = TemplateRepositoryFile(repository_path="lifemonitor/templates/repositories/base", name=cls.TEMPLATE_FILENAME)
        registries = ["wfhub", "wfhubdev"]
        issue_types = models.WorkflowRepositoryIssue.all()
        os.makedirs(repository_path, exist_ok=True)
        tmpl.write(workflow_title=workflow_title, main_branch=main_branch, public=public,
                   issues=issue_types, registries=registries,
                   output_file_path=os.path.join(repository_path, cls.DEFAULT_FILENAME))
        return cls(repo_path=repository_path)
