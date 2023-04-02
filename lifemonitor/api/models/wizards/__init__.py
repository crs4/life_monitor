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

import copy
import glob
import inspect
import logging
import os
from ast import Dict
from hashlib import sha1
from importlib import import_module
from posixpath import basename, dirname
from typing import Callable, List, Optional, Type

from genericpath import isfile
from lifemonitor.api.models.repositories.base import WorkflowRepository
from lifemonitor.api.models.repositories.files import RepositoryFile

from ..issues import WorkflowRepositoryIssue

# set module level logger
logger = logging.getLogger(__name__)


class Wizard():

    # map issue -> wizard
    __wizards__: Optional[Dict] = None

    # main wizard attributes
    title: str = "Wizard"
    description: str = ""
    steps: List[Step] = []
    issue: Optional[Type] = None

    def __init__(self, issue: WorkflowRepositoryIssue,
                 steps: Optional[List[Step]] = None,
                 io_handler: Optional[IOHandler] = None):
        self.issue = issue
        self._io_handler = io_handler
        self.current_step: Optional[Step] = None
        self._steps_list = steps if steps else self.steps
        self.__steps: Optional[List[Step]] = None

    @property
    def id(self) -> str:
        return f'lifemonitor-wizard-{sha1(self.title.encode()).hexdigest()}'

    @property
    def _steps(self) -> List[Step]:
        if self.__steps is None:
            self.__steps = []
            for step in self._steps_list:
                s = copy.deepcopy(step)
                self.add_step(s)
                logger.debug("Added step %r -- %r", s, s.wizard)
        return self.__steps

    @property
    def io_handler(self) -> Optional[IOHandler]:
        return self._io_handler

    @io_handler.setter
    def io_handler(self, handler: IOHandler):
        self._io_handler = handler

    def add_step(self, step: Step):
        assert isinstance(step, Step), step
        step.wizard = self
        self._steps.append(step)

    def remove_step(self, step: Step):
        self._steps.remove(step)
        step.wizard = None

    def get_steps(self) -> List[Step]:
        return self._steps

    def get_step_index(self, step) -> int:
        logger.debug("Current list of steps: %r", self._steps)
        try:
            return self._steps.index(step)
        except Exception as e:
            logger.exception(e)
            return None

    def get_step_by_class(self, step_class) -> Step:
        for step in self._steps:
            if isinstance(step, step_class):
                return step
        return None

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if value and isinstance(value, Step):
            step_index = self.get_step_index(value)
            if step_index >= 0:
                value = self._steps[step_index]
        return value

    def get_next_step(self, current_step: Step = None, ignore_skip=False) -> Optional[Step]:
        current_step = current_step or self.current_step
        step_index = self.get_step_index(current_step) if current_step else -1
        logger.debug("Current step index: %r", step_index)
        logger.debug("Number of steps of %r: %r", self, len(self._steps))
        while step_index < len(self._steps) - 1:
            step_index += 1
            logger.debug("Checking index: %r", step_index)
            step = self._steps[step_index]
            logger.debug("Step: %r", step)
            if step and (ignore_skip or not step.to_skip()):
                return step
        return None

    def find_step(self, text: str) -> Optional[Step]:
        for s in self._steps:
            logger.debug("Checking match between text '%s' with step '%s' (wizard: %r)", text, s.title, s.wizard)
            if s.match(text):
                return s
        return None

    @classmethod
    def __wizard_issue_map__(cls) -> Dict:
        if not cls.__wizards__:
            cls.__wizards__ = find_wizards()
        return cls.__wizards__

    @classmethod
    def all(cls) -> List[Wizard]:
        return list(cls.__wizard_issue_map__().values())

    @classmethod
    def find_by_issue(cls, issue) -> Wizard:
        return cls.__wizard_issue_map__().get(
            issue.__class__ if isinstance(issue, WorkflowRepositoryIssue) else issue, None)


def find_wizards() -> Dict[object, Wizard]:
    modules_files = glob.glob(os.path.join(dirname(__file__), "*.py"))
    modules = ['{}.{}'.format(__name__, basename(f)[:-3])
               for f in modules_files if isfile(f) and not f.endswith('__init__.py')]
    errors = []
    wizards = {}
    for m in modules:
        try:
            mod = import_module(m)
            for _, obj in inspect.getmembers(mod):
                if inspect.isclass(obj) \
                    and obj != Wizard \
                        and issubclass(obj, Wizard):
                    wizards[obj.issue] = obj
        except ModuleNotFoundError:
            logger.error("ModuleNotFoundError: Unable to load module %s", m)
            errors.append(m)
    if len(errors) > 0:
        logger.error("** There were some errors loading application modules.**")
        if logger.isEnabledFor(logging.DEBUG):
            logger.error("** Unable to load wizards from %s", ", ".join(errors))
    return wizards


class IOHandler():

    def get_input(self, question: QuestionStep) -> object:
        pass

    def get_input_as_text(self, question: QuestionStep) -> str:
        pass

    def get_help(self):
        pass

    def as_string(self, step: Step, append_help: bool = False) -> str:
        pass

    def write(self, step: Step, append_help: bool = False):
        pass


class Step():

    title: str
    description: str

    def __init__(self, title: str, description: str = None, when: Callable = None) -> None:
        self.title = title
        self.description = description
        self._when = when
        self._wizard: Wizard = None

    @property
    def id(self) -> str:
        result = self.title
        # if self.wizard is not None:
        #     result += self.wizard.title
        return f'wizard-step-{sha1(result.encode()).hexdigest()}'

    def __eq__(self, __o: object) -> bool:
        if __o and isinstance(__o, self.__class__):
            return self.title == __o.title
        return False

    def __repr__(self) -> str:
        return f"Step: {self.title} of wizard '{self.wizard}'"

    @property
    def wizard(self) -> Wizard:
        return self._wizard

    @wizard.setter
    def wizard(self, value: Wizard):
        self._wizard = value

    @property
    def issue(self) -> WorkflowRepositoryIssue:
        return self._wizard.issue if self._wizard else None

    @property
    def next(self) -> Step:
        try:
            logger.debug("Current list of steps: %r", self.wizard._steps)
            return self.wizard.get_next_step(self)
        except ValueError as e:
            logger.exception(e)
            return None

    def to_skip(self) -> bool:
        return self._when and not self._when(self.wizard)

    def as_string(self, append_help: bool = False) -> str:
        return self.wizard.io_handler.as_string(self, append_help=append_help) if self.wizard else self.title

    def match(self, text: str) -> bool:
        return (self.title and self.title in text) or text.strip(self.wizard.io_handler.get_help()) == self.as_string()


class QuestionStep(Step):

    options: List = []

    def __init__(self, title: str, options: List = None,
                 description: str = None, when: Callable = None) -> None:
        super().__init__(title, description, when=when)
        self.options = options if options else []

    def get_answer(self) -> object:
        return self.wizard.io_handler.get_input(self)

    @property
    def answer(self) -> str:
        return self.wizard.io_handler.get_input_as_text(self)


class UpdateStep(Step):

    files: List[RepositoryFile] = []

    def __init__(self, title: str, files: List[RepositoryFile] = None,
                 description: str = None, when: Callable = None, callback: Callable = None) -> None:
        super().__init__(title, description, when=when)
        self._files = files if files else []
        self.callback = callback

    def get_files(self, repo: WorkflowRepository, target_path: str = None) -> List[RepositoryFile]:
        result = self._files.copy()
        if self.callback:
            result.extend(self.callback(self.wizard, repo, target_path))
        return result


__all__ = ["Wizard", "Step", "QuestionStep", "UpdateStep", "IOHandler"]
