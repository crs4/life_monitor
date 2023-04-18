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

import glob
import inspect
import logging
import os
from importlib import import_module
from typing import Dict, List, Optional, Set, Tuple, Type

from ..base import RepositoryFile

# set module level logger
logger = logging.getLogger(__name__)


class WorkflowFile(RepositoryFile):

    __workflow_types__: Dict[str, Type] | None = None

    def __init__(self, repository_path: str, name: str, type: Optional[str] = None, dir: str = ".",
                 content=None, raw_file: Optional[RepositoryFile] = None) -> None:
        super().__init__(repository_path, name, type, dir, content)
        self._raw_file = raw_file

    def __repr__(self) -> str:
        return f"Workflow \"{self.name}\" (type: {self.type}, path: {self.path})"

    def get_content(self, binary_mode: bool = False):
        if self._content:
            return self._content
        elif self._raw_file:
            return self._raw_file.get_content(binary_mode=binary_mode)
        return super().get_content(binary_mode=binary_mode)

    @property
    def raw_file(self) -> RepositoryFile | None:
        return self._raw_file

    @classmethod
    def get_workflow_extensions(cls, workflow_type: str) -> Set[str] | None:
        try:
            return {_[1] for _ in cls.__get_workflow_types__()[workflow_type].__get_file_patterns__()}
        except AttributeError:
            logger.warning("Unable to find the workflow type: %s", workflow_type)
        return None

    @classmethod
    def get_types(cls) -> List[Type]:
        return cls.__get_workflow_types__().values()

    @classmethod
    def __type_name__(cls) -> str:
        return cls.__name__.replace('WorkflowFile', '').lower()

    @classmethod
    def __from_file__(cls, file: RepositoryFile) -> WorkflowFile:
        return cls(file.repository_path, file.name, cls.__type_name__(),
                   dir=file.dir, content=file._content, raw_file=file)

    @classmethod
    def __get_file_patterns__(cls, subtype: Type = None) -> Tuple[Tuple[str, str, str]] | None:
        return getattr(subtype or cls, "FILE_PATTERNS", None)

    @classmethod
    def is_workflow(cls, file: RepositoryFile) -> WorkflowFile | None:
        if not file:
            return None

        subtypes = (cls,)
        if cls == WorkflowFile:
            subtypes = cls.get_types()
        # check file by pattern
        # a pattern is a triple (name, extension, dir)
        for subtype in subtypes:
            patterns = cls.__get_file_patterns__(subtype=subtype)
            logger.debug("Default patterns for workflow type %s: %r", subtype.__name__, patterns)
            if patterns:
                f_name, f_ext, f_dir = file.splitext() + (file.dir,)
                for p_name, p_ext, p_dir in patterns:
                    if p_name and p_name != f_name:
                        continue
                    if p_ext and p_ext != f_ext:
                        continue
                    if p_dir and p_dir != f_dir:
                        continue
                    return subtype.__from_file__(file)
        return None

    @classmethod
    def __get_workflow_types__(cls) -> Dict[str, Type]:
        if not cls.__workflow_types__:
            logger.debug("Loading workflow types....")
            modules_files = glob.glob(os.path.join(os.path.dirname(__file__), "*.py"))
            modules = ['{}.{}'.format(__name__, os.path.basename(f)[:-3])
                       for f in modules_files if os.path.isfile(f) and not f.endswith('__init__.py')]
            cls.__workflow_types__ = {}
            errors = []
            for m in modules:
                try:
                    mod = import_module(m)
                    for _, obj in inspect.getmembers(mod):
                        if inspect.isclass(obj) \
                            and obj != WorkflowFile \
                                and issubclass(obj, WorkflowFile):
                            cls.__workflow_types__[obj.__type_name__()] = obj
                except ModuleNotFoundError:
                    logger.error("ModuleNotFoundError: Unable to load module %s", m)
                    errors.append(m)
            if len(errors) > 0:
                logger.error("** There were some errors loading application modules.**")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.error("** Unable to load workflow types from %s", ", ".join(errors))
            logger.debug("Loading workflow types.... DONE")
        return cls.__workflow_types__
