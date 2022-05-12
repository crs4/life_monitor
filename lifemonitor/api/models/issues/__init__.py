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

import abc
import glob
import inspect
import logging
import os
from functools import cmp_to_key
from hashlib import sha1
from importlib import import_module
from typing import List, Type

from lifemonitor.api.models import repositories
from lifemonitor.utils import to_snake_case

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowRepositoryIssue():

    __issues__: List[WorkflowRepositoryIssue] = None

    name: str = "A workflow repository issue"
    description: str = ""
    labels = []
    depends_on = []

    def __init__(self):
        self._changes = []

    @property
    def id(self) -> str:
        return f'lifemonitor-issue-{sha1(self.name.encode()).hexdigest()}'

    @property
    def identifier(self) -> str:
        return self.get_identifier()

    @classmethod
    def get_group(cls) -> str:
        return cls.__module__

    @abc.abstractmethod
    def check(self, repo: repositories.WorkflowRepository) -> bool:
        """
        Check if the repo is affected by this issue.

        Args:
            repo (WorkflowRepository): a workflow repository instance

        Returns:
            bool: <code>true</code> if the repo is affected by this issue;
        <code>false</code> otherwise.
        """
        pass

    def add_change(self, file: repositories.RepositoryFile):
        self._changes.append(file)

    def remove_change(self, file: repositories.RepositoryFile):
        self._changes.remove(file)

    def get_changes(self, repo: repositories.WorkflowRepository) -> List[repositories.RepositoryFile]:
        return self._changes

    def has_changes(self) -> bool:
        return self._changes and len(self._changes) > 0

    @classmethod
    def get_identifier(cls) -> str:
        return cls.to_string(cls)

    @classmethod
    def to_string(cls, issue_type) -> str:
        class_name = None
        if isinstance(issue_type, WorkflowRepositoryIssue):
            class_name = issue_type.__class__.__name__
        elif inspect.isclass(issue_type):
            if not issubclass(issue_type, WorkflowRepositoryIssue):
                raise ValueError("Invalid issue type")
            class_name = issue_type.__name__
        logger.debug("Class Name: %r", class_name)
        return to_snake_case(class_name)

    @classmethod
    def from_string(cls, issue_name: str) -> WorkflowRepositoryIssue:
        for issue in cls.types():
            if issue.name == issue_name:
                return issue
        return None

    @classmethod
    def all(cls) -> List[WorkflowRepositoryIssue]:
        if not cls.__issues__:
            cls.__issues__ = find_issue_types()
        return [_() for _ in cls.__issues__]

    @classmethod
    def types(cls) -> Type[WorkflowRepositoryIssue]:
        if not cls.__issues__:
            cls.__issues__ = find_issue_types()
        return cls.__issues__

    @staticmethod
    def generate_template(class_name: str, name: str, description: str = "", depends_on: str = "", labels: str = "") -> Type[WorkflowRepositoryIssue]:
        from jinja2 import BaseLoader, Environment
        with open(os.path.join(os.path.dirname(__file__), "issue.j2")) as f:
            rtemplate = Environment(loader=BaseLoader()).from_string(f.read())
            return rtemplate.render(class_name=class_name, name=name,
                                    description=description, depends_on=depends_on, labels=labels)


def _compare_issues(issue1: WorkflowRepositoryIssue, issue2: WorkflowRepositoryIssue):
    if len(issue1.depends_on) == 0 or issue1 in issue2.depends_on:
        return -1
    if len(issue2.depends_on) == 0 or issue2 in issue1.depends_on:
        return 1
    return 0


def load_issue(issue_file) -> List[WorkflowRepositoryIssue]:
    issues = {}
    base_module = '{}'.format(os.path.join(os.path.dirname(issue_file)).replace('/', '.'))
    m = '{}.{}'.format(base_module, os.path.basename(issue_file)[:-3])
    mod = import_module(m)
    for _, obj in inspect.getmembers(mod):
        if inspect.isclass(obj) \
            and inspect.getmodule(obj) == mod \
            and obj != WorkflowRepositoryIssue \
                and issubclass(obj, WorkflowRepositoryIssue):
            issues[obj.name] = obj
    return issues.values()


def find_issue_types(path: str = None) -> List[WorkflowRepositoryIssue]:
    errors = []
    issues = {}
    current_path = path or os.path.dirname(__file__)
    for dirpath, dirnames, filenames in os.walk(current_path):
        base_path = dirpath.replace(f"{current_path}/", '')
        for dirname in [d for d in dirnames if d not in ['__pycache__']]:
            base_module = '{}.{}'.format(__name__, os.path.join(base_path, dirname).replace('/', '.'))
            modules_files = glob.glob(os.path.join(dirpath, dirname, "*.py"))
            logger.debug(modules_files)
            modules = ['{}.{}'.format(base_module, os.path.basename(f)[:-3])
                       for f in modules_files if os.path.isfile(f) and not f.endswith('__init__.py')]
            for m in modules:
                try:
                    mod = import_module(m)
                    for _, obj in inspect.getmembers(mod):
                        if inspect.isclass(obj) \
                            and inspect.getmodule(obj) == mod \
                            and obj != WorkflowRepositoryIssue \
                                and issubclass(obj, WorkflowRepositoryIssue):
                            issues[obj.name] = obj
                except ModuleNotFoundError as e:
                    logger.exception(e)
                    logger.error("ModuleNotFoundError: Unable to load module %s", m)
                    errors.append(m)
    if len(errors) > 0:
        logger.error("** There were some errors loading application modules.**")
        if logger.isEnabledFor(logging.DEBUG):
            logger.error("** Unable to load issues from %s", ", ".join(errors))
    return [i for i in sorted(issues.values(), key=cmp_to_key(_compare_issues))]


__all__ = ["WorkflowRepositoryIssue"]
