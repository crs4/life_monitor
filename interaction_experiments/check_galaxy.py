# Copyright (c) 2020-2021 CRS4
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
Execute a Galaxy workflow from a crate and check results.
"""

import argparse
import pathlib
import shutil
import subprocess
import tempfile

from rocrate.rocrate import ROCrate


GALAXY_IMG = "bgruening/galaxy-stable:20.05"
PLANEMO_ENTITY = "https://w3id.org/ro/terms/test#PlanemoEngine"


def dump_test_suites(crate):
    print("test suites:")
    for suite in crate.test_dir["about"]:
        print(" ", suite.id)
        print("    workflow:", suite["mainEntity"].id)
        print("    instances:")
        for inst in suite.instance:
            print("     ", inst.id)
            print("       service:", inst.service.name)
            print("       url:", inst.url)
            print("       resource:", inst.resource)
        print("   definition:")
        print("     id:", suite.definition.id)
        engine = suite.definition.engine
        print("     engine:", engine.name)
        print("     engine version:", suite.definition.engineVersion)


# pip install planemo
def check_workflow(crate, crate_dir):
    main_workflow = crate.root_dataset["mainEntity"]
    print("main workflow:", main_workflow.id)
    suite = crate.test_dir["about"][0]
    def_path = crate_dir / suite.definition.id
    workflow = suite["mainEntity"]
    workflow_path = crate_dir / workflow.id
    print("running suite:", suite.id)
    print("definition path:", def_path)
    print("workflow:", workflow.id)
    assert suite.definition.engine.id == PLANEMO_ENTITY
    new_workflow_path = def_path.parent / workflow_path.name
    # Planemo expects the test file in the same dir as the workflow
    shutil.copy2(workflow_path, new_workflow_path)
    cmd = ["planemo", "test", "--engine", "docker_galaxy",
           "--docker_galaxy_image", GALAXY_IMG, new_workflow_path]
    print("Running Planemo (this may take a while)")
    p = subprocess.run(cmd)
    p.check_returncode()
    print("OK")


def main(args):
    wd = pathlib.Path(tempfile.mkdtemp(prefix="life_monitor_"))
    crate_dir = wd / pathlib.Path(args.crate_dir).name
    shutil.copytree(args.crate_dir, crate_dir)
    crate = ROCrate(crate_dir)
    dump_test_suites(crate)
    check_workflow(crate, crate_dir)
    shutil.rmtree(wd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("crate_dir", metavar="CRATE_DIR",
                        help="top-level crate directory")
    main(parser.parse_args())
