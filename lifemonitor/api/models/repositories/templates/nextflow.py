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

import nf_core
import nf_core.create
from lifemonitor.api.models.repositories.files.base import RepositoryFile
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository

from . import WorkflowRepositoryTemplate

# set module level logger
logger = logging.getLogger(__name__)

# Ignore LICENSE
ignore_license = """
# Ignore LICENSE
[**/LICENSE]
charset = unset
end_of_line = unset
insert_final_newline = unset
trim_trailing_whitespace = unset
indent_style = unset
indent_size = unset
"""


class NextflowRepositoryTemplate(WorkflowRepositoryTemplate):

    def __init__(self, name: str, local_path: str = None, data: dict = None, exclude: List[str] = None) -> None:
        super().__init__(name, local_path, data, exclude)

    @property
    def files(self) -> List[RepositoryFile]:
        result = []
        # skip = self._transient_files['remove'].keys()
        for root, _, files in os.path.walk(self.local_path, exclude=self.exclude):
            dirname = root.replace(self.local_path, '.')
            for name in files:
                # if f"{dirname}/{name}" not in skip:
                result.append(RepositoryFile(self.local_path, name, dir=dirname))
        result.extend([v for k, v in self._transient_files['add'].items()])
        return result

    def generate(self, target_path: str = None) -> LocalWorkflowRepository:
        target_path = target_path or self.local_path
        logger.debug("Rendering template files to %s...", target_path)
        # name, description, author, version="1.0dev", no_git=False, force=False, outdir=None
        create_obj = nf_core.create.PipelineCreate(
            self.data.get("workflow_name"),
            self.data.get("workflow_description", ""),
            self.data.get("workflow_author", ""), 
            self.data.get('workflow_version', "0.1.0"),
            False, True, target_path)
        create_obj.init_pipeline()
        # patch prettier config to ignore crate and lm metadata
        with open(os.path.join(self.local_path, '.prettierignore'), 'a') as out:
            out.write('ro-crate-metadata.json\n')
            out.write('lifemonitor.yaml\n')
        # patch editor config to ignore license
        with open(os.path.join(self.local_path, '.editorconfig'), 'a') as file:
            file.write(ignore_license)
        # patch permission of checker script
        os.chmod(os.path.join(self.local_path, 'bin/check_samplesheet.py'), 0o777)

        logger.debug("Rendering template files to %s... DONE", target_path)
        repo = LocalWorkflowRepository(target_path)
        opts = self.data.copy()
        opts.update({
            'root': target_path,
        })
        repo.generate_metadata(**self.data)
        return repo
