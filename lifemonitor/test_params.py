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
Handle Workflow RO-Crate test parameters.
"""

import itertools
import json
import os
import yaml


class Part:

    @classmethod
    def from_json(cls, data):
        return cls(data["@id"], data["name"], data["@type"])

    def __init__(self, id, name, type):
        self.id = id
        self.name = name
        self.type = type


class Dataset:

    @classmethod
    def from_json(cls, data):
        return cls([Part.from_json(_) for _ in data["hasPart"]])

    def __init__(self, parts):
        self.parts = parts
        self.parts_map = {_.name: _ for _ in self.parts}


class Test:

    @classmethod
    def from_json(cls, data):
        entities = {_["@id"]: _ for _ in data["@graph"]}
        return cls(Dataset.from_json(entities["inputs"]),
                   Dataset.from_json(entities["outputs"]))

    def __init__(self, inputs, outputs):
        self.inputs = inputs
        self.outputs = outputs

    def cwl_job(self):
        job = {}
        for name, part in self.inputs.parts_map.items():
            if part.type == "File":
                v = {"class": "File", "path": part.id}
            elif part.type == "Text":
                v = part.id
            else:
                raise RuntimeError(f"Unsupported parameter type: {part.type}")
            job[name] = v
        return job

    def to_planemo(self, doc="tests"):
        test = {"doc": doc, "job": self.cwl_job()}
        for name, part in self.outputs.parts_map.items():
            if part.type == "File":
                test[name] = {"path": part.id}
            else:
                raise RuntimeError(f"Unsupported parameter type: {part.type}")
        return test


def read_params(fname, abs_paths=False):
    with open(fname, "rt") as f:
        json_data = json.load(f)
    t = Test.from_json(json_data)
    if abs_paths:
        d = os.path.abspath(os.path.dirname(fname))
        for p in itertools.chain(t.inputs.parts, t.outputs.parts):
            if p.type == "File":
                p.id = os.path.join(d, p.id)
    return t


def write_planemo_tests(tests, fname, doc=None):
    if doc is None:
        doc = os.path.splitext(os.path.basename(fname))[0]
    data = [_.to_planemo(doc=doc) for _ in tests]
    with open(fname, "wt") as f:
        yaml.dump(data, f)
