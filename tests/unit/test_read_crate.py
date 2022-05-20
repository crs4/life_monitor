# Copyright (c) 2020-2022 CRS4
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

from copy import deepcopy
import json

from rocrate.rocrate import ROCrate
from lifemonitor.test_metadata import get_roc_suites


ENTITIES = {_["@id"]: _ for _ in [
    {
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "about": {"@id": "./"},
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}
    },
    {
        "@id": "./",
        "@type": "Dataset",
        "mainEntity": {"@id": "sort-and-change-case.ga"},
        "hasPart": [
            {"@id": "sort-and-change-case.ga"},
            {"@id": "test/test1/sort-and-change-case-test.yml"}
        ],
        "mentions": [{"@id": "#test1"}]
    },
    {
        "@id": "sort-and-change-case.ga",
        "@type": ["File", "SoftwareSourceCode", "ComputationalWorkflow"],
        "programmingLanguage": {"@id": "https://galaxyproject.org/"},
        "name": "sort-and-change-case"
    },
    {
        "@id": "#test1",
        "name": "test1",
        "@type": "TestSuite",
        "mainEntity": {"@id": "sort-and-change-case.ga"},
        "instance": [{"@id": "#test1_1"}],
        "definition": {"@id": "test/test1/sort-and-change-case-test.yml"}
    },
    {
        "@id": "#test1_1",
        "name": "test1_1",
        "@type": "TestInstance",
        "runsOn": {"@id": "https://w3id.org/ro/terms/test#JenkinsService"},
        "url": "http://example.org/jenkins",
        "resource": "job/tests/"
    },
    {
        "@id": "test/test1/sort-and-change-case-test.yml",
        "@type": ["File", "TestDefinition"],
        "conformsTo": {"@id": "https://w3id.org/ro/terms/test#PlanemoEngine"},
        "engineVersion": ">=0.70"
    },
    {
        "@id": "https://w3id.org/ro/terms/test#JenkinsService",
        "@type": "TestService",
        "name": "Jenkins",
        "url": {"@id": "https://www.jenkins.io"}
    },
    {
        "@id": "https://w3id.org/ro/terms/test#PlanemoEngine",
        "@type": "SoftwareApplication",
        "name": "Planemo",
        "url": {"@id": "https://github.com/galaxyproject/planemo"}
    }
]}


EXPECTED_ROC_SUITES = {
    "#test1": {
        "roc_suite": "#test1",
        "name": "test1",
        "instances": [
            {
                "roc_instance": "#test1_1",
                "name": "test1_1",
                "resource": "job/tests/",
                "service": {
                    "type": "jenkins",
                    "url": "http://example.org/jenkins"
                }
            }
        ],
        "definition": {
            "test_engine": {
                "type": "planemo",
                "version": ">=0.70"
            },
            "path": "test/test1/sort-and-change-case-test.yml"
        }
    }
}


def _write_crate(crate_path, entities):
    crate_path.mkdir(exist_ok=True)
    with open(crate_path / "ro-crate-metadata.json", "wt") as f:
        json.dump({
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": list(entities.values())
        }, f, indent=2)


def test_get_roc_suites(tmpdir):
    crate_dir = tmpdir / "lm_test_crate"
    _write_crate(crate_dir, ENTITIES)
    crate = ROCrate(crate_dir)
    roc_suites = get_roc_suites(crate)
    assert roc_suites == EXPECTED_ROC_SUITES
    # check single value for instance
    entities = deepcopy(ENTITIES)
    entities["#test1"]["instance"] = {"@id": "#test1_1"}
    _write_crate(crate_dir, entities)
    crate = ROCrate(crate_dir)
    roc_suites = get_roc_suites(crate)
    assert roc_suites == EXPECTED_ROC_SUITES
