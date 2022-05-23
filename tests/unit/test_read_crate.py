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
from lifemonitor.test_metadata import get_roc_suites, get_workflow_author


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
        "author": {"@id": "https://orcid.org/0000-0001-8271-5429"},
        "name": "sort-and-change-case"
    },
    {
        "@id": "https://orcid.org/0000-0001-8271-5429",
        "@type": "Person",
        "name": "Simone Leo"
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


def test_get_workflow_author(tmpdir):
    crate_dir = tmpdir / "lm_test_crate"
    _write_crate(crate_dir, ENTITIES)
    crate = ROCrate(crate_dir)
    assert get_workflow_author(crate) == {
        "id": "https://orcid.org/0000-0001-8271-5429",
        "name": "Simone Leo",
        "url": "https://orcid.org/0000-0001-8271-5429",
    }
    # author as string
    entities = deepcopy(ENTITIES)
    entities["sort-and-change-case.ga"]["author"] = "https://orcid.org/0000-0001-8271-5429"
    _write_crate(crate_dir, entities)
    crate = ROCrate(crate_dir)
    assert get_workflow_author(crate) == {
        "id": "https://orcid.org/0000-0001-8271-5429",
        "name": None,
        "url": "https://orcid.org/0000-0001-8271-5429",
    }
    # workflow from suite
    entities = deepcopy(ENTITIES)
    entities["foo.ga"] = {
        "@id": "foo.ga",
        "@type": ["File", "SoftwareSourceCode", "ComputationalWorkflow"],
        "programmingLanguage": {"@id": "https://galaxyproject.org/"},
        "author": "Mickey Mouse"
    }
    entities["#test1"]["mainEntity"] = {"@id": "foo.ga"}
    entities["./"]["hasPart"].append({"@id": "foo.ga"})
    _write_crate(crate_dir, entities)
    crate = ROCrate(crate_dir)
    assert get_workflow_author(crate, suite_id="#test1") == {
        "id": "Mickey Mouse",
        "name": None,
        "url": None,
    }
    # no workflow
    entities = deepcopy(ENTITIES)
    for id_ in "./", "#test1":
        del entities[id_]["mainEntity"]
    _write_crate(crate_dir, entities)
    crate = ROCrate(crate_dir)
    for suite_id in None, "#test1":
        assert get_workflow_author(crate, suite_id=suite_id) is None
    # no author
    entities = deepcopy(ENTITIES)
    del entities["sort-and-change-case.ga"]["author"]
    _write_crate(crate_dir, entities)
    crate = ROCrate(crate_dir)
    assert get_workflow_author(crate) is None
    # URL from url
    entities = deepcopy(ENTITIES)
    del entities["https://orcid.org/0000-0001-8271-5429"]
    entities["#sl"] = {
        "@id": "#sl",
        "@type": "Person",
        "name": "Simone Leo",
        "url": "https://orcid.org/0000-0001-8271-5429"
    }
    entities["sort-and-change-case.ga"]["author"] = {"@id": "#sl"}
    _write_crate(crate_dir, entities)
    crate = ROCrate(crate_dir)
    assert get_workflow_author(crate) == {
        "id": "#sl",
        "name": "Simone Leo",
        "url": "https://orcid.org/0000-0001-8271-5429",
    }
