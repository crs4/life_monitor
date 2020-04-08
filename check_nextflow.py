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
Execute a Nextflow workflow from a crate and check results.
"""

import argparse
import configparser
import json
import os
import shutil
import subprocess
import tempfile

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


def read_params(fname):
    config = configparser.ConfigParser()
    parser.optionxform = str  # preserve key case
    config.read(fname)
    d = os.path.abspath(os.path.dirname(fname))
    # assumes inputs and outputs are filesystem paths
    inputs = {k: os.path.join(d, v) for k, v in config["inputs"].items()}
    outputs = {k: os.path.join(d, v) for k, v in config["outputs"].items()}
    return {"inputs": inputs, "outputs": outputs}


def compare_outputs(out_map):
    for out, exp_out in out_map.items():
        # simple byte-by-byte equality, also assumes "small" files
        with open(out, "rb") as f, open(exp_out, "rb") as fexp:
            if f.read() != fexp.read():
                raise RuntimeError(f"outputs {out} and {exp_out} differ")


def check_workflow(wf_fn, config):
    wd = tempfile.mkdtemp(prefix="check_nextflow_")
    cmd = ["nextflow", wf_fn]
    out_map = {}
    for k, v in config["inputs"].items():
        cmd.extend([f"--{k}", v])
    for i, (k, exp_out) in enumerate(config["outputs"].items()):
        out = os.path.join(wd, str(i))
        cmd.extend([f"--{k}", out])
        out_map[out] = exp_out
    subprocess.run(cmd)
    compare_outputs(out_map)
    shutil.rmtree(wd)
    print("OK")


def main(args):
    metadata = parse_metadata(args.crate_dir)
    wf_fn = os.path.join(args.crate_dir, metadata["main"])
    test_dir = os.path.join(args.crate_dir, "test")
    if not os.path.isdir(test_dir):
        if metadata["test"]:
            raise RuntimeError("test dir not found")
        else:
            print("crate has no tests, nothing to do")
            return
    cfg_fn = os.path.join(test_dir, "params.cfg")
    config = read_params(cfg_fn)
    check_workflow(wf_fn, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("crate_dir", metavar="CRATE_DIR",
                        help="top-level crate directory")
    main(parser.parse_args())
