# Copyright (c) 2020-2022 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""\
Execute a CWL workflow from a crate and check results.
"""

import argparse
import pathlib
import shutil
import subprocess
import tempfile

from rocrate.rocrate import ROCrate


PLANEMO_ENTITY = "https://w3id.org/ro/terms/test#PlanemoEngine"


# In this crate, the workflow depends on tools which are expected to be in
# ../tools. Currently there is no general way to express this relationship, so
# we run this ad-hoc patch.
def fix_tools_path(crate_dir, def_path):
    tools_path = crate_dir / "tools"
    new_tools_path = def_path.parent.parent / "tools"
    if not new_tools_path.exists():
        print(f"{tools_path} --> {new_tools_path}")
        shutil.copytree(tools_path, new_tools_path)


def check_workflow(crate, crate_dir):
    main_workflow = crate.mainEntity
    print("main workflow:", main_workflow.id)
    for suite in crate.test_suites:
        def_path = crate_dir / suite.definition.id
        workflow = suite["mainEntity"] or main_workflow
        workflow_path = crate_dir / workflow.id
        print("running suite:", suite.id)
        print("definition path:", def_path)
        print("workflow:", workflow.id)
        assert suite.definition.engine.id == PLANEMO_ENTITY
        new_workflow_path = def_path.parent / workflow_path.name
        # Planemo expects the test file in the same dir as the workflow
        shutil.copy2(workflow_path, new_workflow_path)
        fix_tools_path(crate_dir, def_path)
        cmd = ["planemo", "test", "--engine", "cwltool", new_workflow_path]
        print("Running Planemo")
        p = subprocess.run(cmd)
        p.check_returncode()
        print("OK")


def main(args):
    wd = pathlib.Path(tempfile.mkdtemp(prefix="life_monitor_"))
    crate_dir = wd / pathlib.Path(args.crate_dir).name
    shutil.copytree(args.crate_dir, crate_dir)
    crate = ROCrate(crate_dir)
    check_workflow(crate, crate_dir)
    shutil.rmtree(wd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("crate_dir", metavar="CRATE_DIR",
                        help="top-level crate directory")
    main(parser.parse_args())
