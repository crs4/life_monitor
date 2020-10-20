# Copyright (c) 2020 CRS4
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
import os
import shutil
import subprocess
import tempfile

import yaml
import lifemonitor.ro_crate as roc
import lifemonitor.test_metadata as tm

YamlDumper = getattr(yaml, "CDumper", getattr(yaml, "Dumper"))
GALAXY_IMG = "bgruening/galaxy-stable:20.05"


def dump_instances(tests):
    print("references to test instances:")
    for t in tests:
        print(t.name)
        if t.instance:
            for i in t.instance:
                print("    name:", i.name)
                print("    service:")
                print("        type:", i.service.type)
                print("        url:", i.service.url)
                print("        resource:", i.service.resource)


# pip install planemo
def check_workflow(wf_fn, tests):
    wd = tempfile.mkdtemp(prefix="check_galaxy_")
    wf_bn = os.path.basename(wf_fn)
    wf_tmp_fn = os.path.join(wd, wf_bn)
    shutil.copy2(wf_fn, wf_tmp_fn)
    head, tail = os.path.splitext(wf_bn)
    test_fn = os.path.join(wd, f"{head}-test.yml")
    for t in tests:
        print("RUNNING", t.name)
        assert t.definition.engine.type == "planemo"
        cases = tm.read_planemo(t.definition.path)
        tm.paths_to_abs(cases, t.definition.path)
        with open(test_fn, "wt") as f:
            yaml.dump(cases, f, YamlDumper)
        cmd = ["planemo", "test", "--engine", "docker_galaxy",
               "--docker_galaxy_image", GALAXY_IMG, wf_tmp_fn]
        p = subprocess.run(cmd)
        p.check_returncode()
        print(f"{t.name}: OK")
    shutil.rmtree(wd)


def main(args):
    wf_path, test_dir = roc.parse_metadata(args.crate_dir)
    if not test_dir:
        print("crate has no tests, nothing to do")
        return
    cfg_fn = roc.get_test_metadata_path(test_dir)
    tests = tm.read_tests(cfg_fn, abs_paths=True)
    dump_instances(tests)
    check_workflow(wf_path, tests)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("crate_dir", metavar="CRATE_DIR",
                        help="top-level crate directory")
    main(parser.parse_args())
