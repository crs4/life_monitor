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
Test metadata support.

Specs: https://github.com/crs4/life_monitor/wiki/Test-Metadata-Draft-Spec
"""

import json
from collections import Mapping
from pathlib import Path

import yaml


YamlLoader = getattr(yaml, "CLoader", getattr(yaml, "Loader"))


# TODO: check if this is a solved problem somewhere
def norm_abs_path(path, ref_path):
    """\
    Convert `path` to absolute assuming it's relative to ref_path (file or dir).
    """
    path, ref_path = Path(path), Path(ref_path).absolute()
    ref_dir = ref_path if ref_path.is_dir() else ref_path.parent
    return ref_dir / path


def paths_to_abs(data, ref_path):
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "path":
                data[k] = str(norm_abs_path(v, ref_path))
            else:
                paths_to_abs(v, ref_path)
    if isinstance(data, list):
        for d in data:
            paths_to_abs(d, ref_path)


class Service:

    @classmethod
    def from_json(cls, data):
        return cls(data["type"], data["url"], data["resource"])

    def __init__(self, type, url, resource):
        self.type = type
        self.url = url
        self.resource = resource

    def __repr__(self):
        return f"{self.__class__.__name__}{self.type, self.url, self.resource}"


class Instance:

    @classmethod
    def from_json(cls, data):
        if not data:
            return None
        return cls(data["name"], Service.from_json(data["service"]))

    def __init__(self, name, service):
        self.name = name
        self.service = service

    def __repr__(self):
        return f"{self.__class__.__name__}{self.name, self.service}"


class TestEngine:

    @classmethod
    def from_json(cls, data):
        return cls(data["type"], data["version"])

    # TODO: handle version requirement
    def __init__(self, type, version):
        self.type = type
        self.version = version

    def __repr__(self):
        return f"{self.__class__.__name__}{self.type, self.version}"


class TestDefinition:

    @classmethod
    def from_json(cls, data):
        if not data:
            return None
        return cls(TestEngine.from_json(data["test_engine"]), data["path"])

    # TODO: add support for payload
    def __init__(self, engine, path):
        self.engine = engine
        self.path = path

    def __repr__(self):
        return f"{self.__class__.__name__}{self.engine, self.path}"


class Test:

    @classmethod
    def from_json(cls, data):
        return cls(
            data["name"],
            [Instance.from_json(_) for _ in data.get("instance", [])],
            TestDefinition.from_json(data.get("definition", {}))
        )

    def __init__(self, name, instance, definition):
        self.name = name
        self.instance = instance
        self.definition = definition

    def __repr__(self):
        return f"{self.__class__.__name__}{self.name, self.instance, self.definition}"


def read_tests(fname, abs_paths=True):
    tests = []
    with open(fname, "rt") as f:
        json_data = json.load(f)
    # TODO: handle id and format
    for t in json_data["test"]:
        t = Test.from_json(t)
        if abs_paths:
            t.definition.path = str(norm_abs_path(t.definition.path, fname))
        tests.append(t)
    return tests


def read_planemo(fname):
    """\
    Read Planemo test cases from file.

    Normalizes all jobs to embedded form.
    """
    rval = []
    with open(fname, "rt") as f:
        cases = yaml.load(f, YamlLoader)
    for c in cases:
        if not isinstance(c["job"], Mapping):
            job_path = norm_abs_path(c["job"], fname)
            with open(job_path, "rt") as f:
                job = yaml.load(f, YamlLoader)
            c["job"] = job
        rval.append(c)
    return rval
