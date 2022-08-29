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
import re
from typing import List

import git
import nf_core.create
from lifemonitor.api.models.repositories.files.base import RepositoryFile
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository
from nf_core import utils as nf_core_utils

from . import WorkflowRepositoryTemplate

# set module level logger
logger = logging.getLogger(__name__)

# log loaded nf_core.utils is loaded
logger.debug("Loaded module 'nf-core.utils': %r", nf_core_utils)

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
        create_obj = NextflowPipeline(
            self.data.get("workflow_name"),
            self.data.get("workflow_description", ""),
            self.data.get("workflow_author", ""),
            self.data.get('workflow_version', "0.1.0"),
            False, True, target_path)
        create_obj.init_pipeline()

        # patch prettier config to ignore crate and lm metadata
        with open(os.path.join(target_path, '.prettierignore'), 'a') as out:
            out.write('ro-crate-metadata.json\n')
            out.write('lifemonitor.yaml\n')
        # patch editor config to ignore license
        with open(os.path.join(target_path, '.editorconfig'), 'a') as file:
            file.write(ignore_license)
        # patch permission of checker script
        os.chmod(os.path.join(target_path, 'bin/check_samplesheet.py'), 0o777)

        logger.debug("Rendering template files to %s... DONE", target_path)
        repo = LocalWorkflowRepository(local_path=target_path)
        opts = self.data.copy()
        opts.update({
            'root': target_path,
        })
        repo.generate_metadata(**self.data)
        return repo


class NextflowPipeline(nf_core.create.PipelineCreate):
    
    
    #  self.short_name = name.lower().replace(r"/\s+/", "-").replace("nf-core/", "").replace("/", "-")
    #     self.name = f"nf-core/{self.short_name}"
    #     self.name_noslash = self.name.replace("/", "-")
    #     self.name_docker = self.name.replace("nf-core", "nfcore")
    #     self.logo_light = f"{self.name_noslash}_logo_light.png"
    #     self.logo_dark = f"{self.name_noslash}_logo_dark.png"

    def __init__(self, name, description, author, version="1.0dev", no_git=False, force=False, outdir=None):
        """ Override default constructor to properly set workflow name"""
        # short_name = re.sub(r"\s+", "-", name.lower()).replace("nf-core/", "").replace("/", "_")
        # name = f"nf-core/{short_name}"
        # name_noslash = name.replace("/", "-")
        # if not outdir:
        #     outdir = os.path.join(os.getcwd(), name_noslash)
        super().__init__(re.sub(r"\s+", "", name), description, author, version, no_git, force, outdir)
        # override default name
        # self.name = name
        # self.short_name = short_name
        # self.name_noslash = name_noslash
        # self.name_docker = name.replace("nf-core", "nfcore")
        # self.logo_light = f"{name_noslash}_logo_light.png"
        # self.logo_dark = f"{name_noslash}_logo_dark.png"

    def git_init_pipeline(self):
        """Initialises the new pipeline as a Git repository and submits first commit."""
        logger.info("Initialising pipeline git repository")
        repo = git.Repo.init(self.outdir)
        repo.git.add(A=True)
        repo.index.commit(f"initial template build from nf-core/tools, version {nf_core.__version__}")
        # Add TEMPLATE branch to git repository
        repo.git.branch("TEMPLATE")
        repo.git.branch("dev")
        logger.info(
            "Done. Remember to add a remote and push to GitHub:\n"
            f"[white on grey23] cd {self.outdir} \n"
            " git remote add origin git@github.com:USERNAME/REPO_NAME.git \n"
            " git push --all origin                                       "
        )
        logger.info("This will also push your newly created dev branch and the TEMPLATE branch for syncing.")
