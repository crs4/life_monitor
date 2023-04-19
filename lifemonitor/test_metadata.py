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
Test metadata support.

https://crs4.github.io/life_monitor/workflow_testing_ro_crate
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

import yaml

YamlLoader = getattr(yaml, "CLoader", getattr(yaml, "Loader"))


JENKINS = "https://w3id.org/ro/terms/test#JenkinsService"
TRAVIS = "https://w3id.org/ro/terms/test#TravisService"
GITHUB = "https://w3id.org/ro/terms/test#GithubService"
PLANEMO = "https://w3id.org/ro/terms/test#PlanemoEngine"
_TO_OLD_TYPES = {
    JENKINS: "jenkins",
    TRAVIS: "travis",
    GITHUB: "github",
    PLANEMO: "planemo",
}


# TODO: check if this is a solved problem somewhere
def norm_abs_path(path, ref_path):
    """\
    Convert `path` to absolute assuming it's relative to ref_path (file or dir).
    """
    path, ref_path = Path(path), Path(ref_path).absolute()
    ref_dir = ref_path if ref_path.is_dir() else ref_path.parent
    return ref_dir / path


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


def get_roc_suites(crate) -> Dict[str, Any] | None:
    """
    Generate a DTO of test suites
    extracted from a Workflow Test RO-Crate.
    The result is a dict of the following form:

        <ROC_SUITE_ID>: {
            "roc_suite": <ROC_SUITE_ID>,
            "name": ...,
            "definition": {
                "test_engine": {
                    "type": t,
                    "version": ...,
                },
                "path": ...,
            },
            "instances": [
                {
                    "roc_instance": <ROC_INSTANCE_ID>,
                    "name": ...,
                    "resource": ...,
                    "service": {
                        "type": ...,
                        "url": ...,
                    },
                }
            ]
        }
    """
    if not crate.test_suites:
        return None
    rval = {}
    for suite in crate.test_suites:
        suite_data = {
            "roc_suite": suite.id,
            "name": suite.name,
        }
        rval[suite.id] = suite_data
        instance = suite.instance
        suite_data["instances"] = []
        if instance:
            if not isinstance(instance, list):
                instance = [instance]
            for inst in instance:
                t = _TO_OLD_TYPES.get(inst.service.id, "unknown")
                suite_data["instances"].append({
                    "roc_instance": inst.id,
                    "name": inst.name,
                    "resource": inst.resource,
                    "service": {
                        "type": t,
                        "url": inst.url,
                    },
                })
        definition = suite.definition
        if definition:
            t = _TO_OLD_TYPES.get(definition.conformsTo.id, "unknown")
            suite_data["definition"] = {
                "test_engine": {
                    "type": t,
                    "version": definition.engineVersion,
                },
                "path": definition.id,
            }
        else:
            suite_data["definition"] = {}
    return rval


def get_workflow_authors(crate, suite_id=None):
    """\
    Get the authors of the main workflow.

    If suite_id is not None, try retrieving the authors from that suite's
    mainEntity (in principle, this might be different from the crate's
    mainEntity).

    Return a list of dictionaries with keys "name" and "url" (note that the
    "url" field can have a value of None). If no author is found, the returned
    list will be empty. Example output:

      [
        {
           "name": "Josiah Carberry",
           "url": "https://orcid.org/0000-0002-1825-0097"
        },
        {
          "name": "mickeymouse",
          "url": None
        }
      ]
    """
    suite = None if suite_id is None else crate.get(suite_id)
    workflow = suite.get("mainEntity") if suite else crate.mainEntity
    if not workflow:
        # not a valid Workflow RO-Crate
        return []
    author = workflow.get("author", workflow.get("creator"))
    if not author:
        return []
    if not isinstance(author, list):
        author = [author]
    rval = []
    for a in author:
        id_ = a if isinstance(a, str) else a.id
        name = None if isinstance(a, str) else a.get("name")
        if name is None:
            name = id_.lstrip("#")
        if id_.startswith("http://") or id_.startswith("https://"):
            url = id_
        else:
            url = None if isinstance(a, str) else a.get("url")
        rval.append({"name": name, "url": url})
    return rval
