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
import re
from typing import Dict, List, Optional

import lifemonitor.api.models.repositories as repos
import lifemonitor.api.models.repositories.files as repo_files

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

    def __init__(self, data: Optional[Dict[str, str]] = None,
                 local_path: Optional[str] = None,
                 init_git: bool = False) -> None:
        super().__init__(data=data, local_path=local_path, init_git=init_git)

    @property
    def files(self) -> List[repo_files.base.RepositoryFile]:
        result = []
        # skip = self._transient_files['remove'].keys()
        for root, _, files in os.path.walk(self.local_path, exclude=self.exclude):
            dirname = root.replace(self.local_path, '.')
            for name in files:
                # if f"{dirname}/{name}" not in skip:
                result.append(repo_files.base.RepositoryFile(self.local_path, name, dir=dirname))
        result.extend([v for k, v in self._transient_files['add'].items()])
        return result

    def generate(self, target_path: str = None) -> repos.LocalWorkflowRepository:
        target_path = target_path or self.local_path
        logger.debug("Rendering template files to %s...", target_path)
        # name, description, author, version="1.0dev", no_git=False, force=False, outdir=None
        from nf_core.create import PipelineCreate
        create_obj = PipelineCreate(
            re.sub(r"\s+", "", self.data.get("workflow_name")),
            self.data.get("workflow_description"),
            self.data.get("workflow_author", ""),
            self.data.get("workflow_version", "0.1.0"),
            False, True, outdir=target_path, plain=True
        )
        create_obj.init_pipeline()

        # patch prettier config to ignore crate and lm metadata
        with open(os.path.join(target_path, '.prettierignore'), 'a') as out:
            out.write('ro-crate-metadata.json\n')
            out.write('lifemonitor.yaml\n')
            out.write('bin/check_samplesheet.py\n')
        # patch editor config to ignore license
        with open(os.path.join(target_path, '.editorconfig'), 'a') as file:
            file.write(ignore_license)
        # patch permission of checker script
        os.chmod(os.path.join(target_path, 'bin/check_samplesheet.py'), 0o777)
        logger.debug("Rendering template files to %s... DONE", target_path)

        # create the repository object
        repo = self.__init_repo_object__(target_path)
        # generate metadata
        opts = self.data.copy()
        opts.update({
            'root': target_path,
        })
        repo.generate_metadata(**self.data)
        # return the repository object
        return repo
