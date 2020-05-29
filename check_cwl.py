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
Execute a CWL workflow from a crate and check results.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile

import lifemonitor.test_params as tp

METADATA_BASENAME = "ro-crate-metadata.jsonld"


# https://github.com/workflowhub-eu/about/wiki/Workflow-RO-Crate
# https://researchobject.github.io/ro-crate/1.0/
def parse_metadata(crate_dir):
    fn = os.path.join(crate_dir, METADATA_BASENAME)
    if not os.path.isfile(fn):
        raise RuntimeError(f"{METADATA_BASENAME} not found in {crate_dir}")
    with open(fn, "rt") as f:
        json_data = json.load(f)
    entities = {_["@id"]: _ for _ in json_data["@graph"]}
    md_desc = entities[METADATA_BASENAME]
    root = entities[md_desc["about"]["@id"]]
    main = entities[root["mainEntity"]["@id"]]
    assert main["@type"] == ["File", "SoftwareSourceCode", "Workflow"]
    # Dataset @id SHOULD end with /
    return {
        "main": main["@id"],
        "test": "test" in [_.rstrip("/") for _ in entities]
    }


def compare_outputs(out_map):
    for out, exp_out in out_map.items():
        # simple byte-by-byte equality, also assumes "small" files
        with open(out, "rb") as f, open(exp_out, "rb") as fexp:
            if f.read() != fexp.read():
                raise RuntimeError(f"outputs {out} and {exp_out} differ")


def write_test_file(config, out_fn):
    with open(out_fn, "wt") as f:
        f.write("- doc: cwl workflow tests\n")
        f.write("  job:\n")
        # embed job in the test file
        for k, v in config.inputs.parts_map.items():
            if v.type == "File":
                f.write(f"    {k}:\n")
                f.write("      class: File\n")
                f.write(f"      path: {v.id}\n")
            elif v.type == "Text":
                f.write(f"    {k}: {v.id}\n")
            else:
                raise RuntimeError("Unknown parameter type: {v.type}")
        f.write("  outputs:\n")
        for k, v in config.outputs.parts_map.items():
            if v.type == "File":
                f.write(f"    {k}:\n")
                f.write(f"      path: {v.id}\n")
            else:
                raise RuntimeError("Unknown parameter type: {v.type}")


# pip install planemo
def check_workflow(crate_dir, metadata, config):
    wd = tempfile.mkdtemp(prefix="check_cwl_")
    crate_dir_bn = os.path.basename(crate_dir)
    tmp_crate_dir = os.path.join(wd, crate_dir_bn)
    wf_fn = os.path.join(tmp_crate_dir, metadata["main"])
    wf_bn = os.path.basename(wf_fn)
    shutil.copytree(crate_dir, tmp_crate_dir)
    head, tail = os.path.splitext(wf_bn)
    wf_dir = os.path.dirname(wf_fn)
    test_fn = os.path.join(wf_dir, f"{head}_test.yml")
    write_test_file(config, test_fn)
    cmd = ["planemo", "test", "--engine", "cwltool", wf_fn]
    p = subprocess.run(cmd)
    p.check_returncode()
    shutil.rmtree(wd)
    print("OK")


def main(args):
    metadata = parse_metadata(args.crate_dir)
    test_dir = os.path.join(args.crate_dir, "test")
    if not os.path.isdir(test_dir):
        if metadata["test"]:
            raise RuntimeError("test dir not found")
        else:
            print("crate has no tests, nothing to do")
            return
    cfg_fn = os.path.join(test_dir, "params.jsonld")
    config = tp.read_params(cfg_fn, abs_paths=True)
    check_workflow(args.crate_dir, metadata, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("crate_dir", metavar="CRATE_DIR",
                        help="top-level crate directory")
    main(parser.parse_args())
