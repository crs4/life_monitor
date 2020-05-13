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
    d = os.path.abspath(os.path.dirname(fname))
    with open(fname, "rt") as f:
        json_data = json.load(f)
    entities = {_["@id"]: _ for _ in json_data["@graph"]}
    inputs, outputs = {}, {}
    for p in entities["inputs"]["hasPart"]:
        if p["@type"] == "File":
            p["@id"] = os.path.join(d, p["@id"])
        inputs[p["name"]] = p
    for p in entities["outputs"]["hasPart"]:
        if p["@type"] == "File":
            p["@id"] = os.path.join(d, p["@id"])
        outputs[p["name"]] = p
    return {"inputs": inputs, "outputs": outputs}


def compare_outputs(out_map):
    for out, exp_out in out_map.items():
        # simple byte-by-byte equality, also assumes "small" files
        with open(out, "rb") as f, open(exp_out, "rb") as fexp:
            if f.read() != fexp.read():
                raise RuntimeError(f"outputs {out} and {exp_out} differ")


def write_job_file(config, fn):
    with open(fn, "wt") as f:
        for k, v in config["inputs"].items():
            if v["@type"] == "File":
                f.write(f"{k}:\n")
                f.write(f"  class: File\n")
                f.write(f"  path: {v['@id']}\n")
            elif v["@type"] == "Text":
                f.write(f"{k}: {v['@id']}\n")
            else:
                raise RuntimeError("Unknown parameter type: {v['@type']}")


# pip install cwlref-runner
def check_workflow(wf_fn, config):
    wd = tempfile.mkdtemp(prefix="check_cwl_")
    job_fn = os.path.join(wd, "job.yml")
    write_job_file(config, job_fn)
    cmd = ["cwl-runner", "--outdir", wd, wf_fn, job_fn]
    # The output matching is more or less hardcoded here. It should be
    # inferred from the workflow definition in some way
    output = os.path.join(wd, config["inputs"]["freqs_sum_file_name"]["@id"])
    exp_output = config["outputs"]["freqs_sum"]["@id"]
    out_map = {output: exp_output}
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
    cfg_fn = os.path.join(test_dir, "params.jsonld")
    config = read_params(cfg_fn)

    check_workflow(wf_fn, config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("crate_dir", metavar="CRATE_DIR",
                        help="top-level crate directory")
    main(parser.parse_args())
