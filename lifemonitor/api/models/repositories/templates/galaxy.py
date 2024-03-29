# Copyright (c) 2020-2024 CRS4
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

import os
from typing import Dict

from lifemonitor.utils import to_kebab_case

from . import WorkflowRepositoryTemplate


class GalaxyRepositoryTemplate(WorkflowRepositoryTemplate):

    def get_defaults(self) -> Dict:
        defaults = WorkflowRepositoryTemplate.get_defaults()
        defaults.update({
            'ci_workflow': 'main.yml',
        })
        return defaults

    def write(self, target_path: str, overwrite: bool = False):
        super().write(target_path, overwrite)
        # rename files according to best practices
        os.rename(os.path.join(target_path, 'workflow.ga'),
                  os.path.join(target_path, f"{to_kebab_case(self.data.get('workflow_name', 'workflow'))}.ga"))
        os.rename(os.path.join(target_path, 'workflow-test.yml'),
                  os.path.join(target_path, f"{to_kebab_case(self.data.get('workflow_name', 'workflow'))}-test.yml"))
