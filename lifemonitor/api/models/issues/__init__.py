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

import abc
import inspect
import logging
import os
from enum import Enum
from hashlib import sha1
from importlib import import_module
from pathlib import Path
from typing import List, Optional, Type

import networkx as nx

from lifemonitor.api.models import repositories

# set module level logger
logger = logging.getLogger(__name__)


class IssueMessage:

    class TYPE(Enum):
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"

    def __init__(self, type: TYPE, text: str) -> None:
        self._type = type
        self._text = text

    def __eq__(self, other):
        if isinstance(other, IssueMessage):
            return self.type == other.type and self.text == other.text
        return False

    @property
    def type(self) -> TYPE:
        return self._type

    @property
    def text(self) -> str:
        return self._text


class WorkflowRepositoryIssue():

    __issues__: List[WorkflowRepositoryIssue] = None

    name: str = "A workflow repository issue"
    description: str = ""
    labels = []
    depends_on = []

    def __init__(self):
        self._changes = []
        self._messages: List[IssueMessage] = []

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
        return bool(self._changes) and len(self._changes) > 0

    def add_message(self, message: IssueMessage):
        self._messages.append(message)

    def remove_message(self, message: IssueMessage):
        self._messages.remove(message)

    def get_messages(self) -> List[IssueMessage]:
        return self._messages

    def has_messages(self) -> bool:
        return len(self._messages) > 0

    @classmethod
    def get_identifier(cls) -> str:
        return cls.to_string(cls)

    @classmethod
    def to_string(cls, issue_type: WorkflowRepositoryIssue | Type[WorkflowRepositoryIssue]) -> str:
        class_name = None
        if isinstance(issue_type, WorkflowRepositoryIssue):
            class_name = issue_type.__class__.__name__
        elif inspect.isclass(issue_type):
            if not issubclass(issue_type, WorkflowRepositoryIssue):
                raise ValueError("Invalid issue type")
            class_name = issue_type.__name__
        logger.debug("Class Name: %r", class_name)
        # Get the parent package name (we use the package as a category)
        tail_package = issue_type.__module__.rsplit('.', 1)[-1]
        return f"{tail_package}.{class_name}"

    @classmethod
    def from_string(cls, issue_name: str) -> Type[WorkflowRepositoryIssue] | None:
        for issue in cls.types():
            if issue.name == issue_name:
                return issue
        return None

    @classmethod
    def all(cls) -> List[Type[WorkflowRepositoryIssue]]:
        if not cls.__issues__:
            cls.__issues__ = find_issue_types()
        return [_() for _ in cls.__issues__]

    @classmethod
    def types(cls) -> List[Type[WorkflowRepositoryIssue]]:
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


def load_issue(issue_file) -> List[Type[WorkflowRepositoryIssue]]:
    issues = {}
    base_module = '{}'.format(os.path.join(os.path.dirname(issue_file)).replace('./', '').replace('/', '.'))
    m = '{}.{}'.format(base_module, os.path.basename(issue_file)[:-3])
    logger.debug("BaseModule: %r -- Module: %r" % (base_module, m))
    mod = import_module(m)
    for _, obj in inspect.getmembers(mod):
        if inspect.isclass(obj) \
            and inspect.getmodule(obj) == mod \
            and obj != WorkflowRepositoryIssue \
                and issubclass(obj, WorkflowRepositoryIssue):
            issues[obj.name] = obj
    return issues.values()


def find_issue_types(path: Optional[str] = None) -> List[Type[WorkflowRepositoryIssue]]:
    errors = []
    issues = {}
    g = nx.DiGraph()
    base_path = Path(path) if path else Path(__file__).parent

    module_files = (f for f in base_path.glob('**/*.py')
                    if f.is_file() and f.name != '__init__.py')
    module_names = ['.' + str(m_file.relative_to(base_path).with_suffix('')).replace('/', '.')
                    for m_file in module_files]

    for m in module_names:
        try:
            # import relative to current module
            mod = import_module(m, __name__)
            logger.debug("Successfully imported check module %s", m)

            for _, obj in inspect.getmembers(mod):
                if inspect.isclass(obj) \
                    and inspect.getmodule(obj) == mod \
                    and obj != WorkflowRepositoryIssue \
                        and issubclass(obj, WorkflowRepositoryIssue):
                    issues[obj.__name__] = obj
                    dependencies = getattr(obj, 'depends_on', None)
                    if not dependencies or len(dependencies) == 0:
                        g.add_edge('r', obj.__name__)
                    else:
                        for dep in dependencies:
                            g.add_edge(dep.__name__, obj.__name__)
        except ModuleNotFoundError as e:
            logger.exception(e)
            logger.error("ModuleNotFoundError: Unable to load module %s", m)
            errors.append(m)
    if len(errors) > 0:
        logger.error("** There were some errors loading application modules.**")
        if logger.isEnabledFor(logging.DEBUG):
            logger.error("** Unable to load issues from %s", ", ".join(errors))
    logger.debug("Issues: %r", [_.__name__ for _ in issues.values()])
    sorted_issues = [issues[_] for _ in nx.dfs_preorder_nodes(g, source='r') if _ != 'r']
    logger.debug("Sorted issues: %r", [_.__name__ for _ in sorted_issues])
    return sorted_issues


__all__ = ["WorkflowRepositoryIssue"]
