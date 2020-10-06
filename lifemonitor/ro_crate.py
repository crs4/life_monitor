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
RO-Crate support.

TODO: get rid of this module and depend on ro-crate-py instead once it's stable.

https://www.researchobject.org/ro-crate
https://github.com/workflowhub-eu/about/wiki/Workflow-RO-Crate
https://github.com/ResearchObject/ro-crate-py
"""

import json
from pathlib import Path

METADATA_BASENAME = "ro-crate-metadata.json"  # since RO-Crate 1.1
LEGACY_METADATA_BASENAME = "ro-crate-metadata.jsonld"
WORKFLOW_TYPES = {"File", "SoftwareSourceCode", "ComputationalWorkflow"}
LEGACY_WORKFLOW_TYPES = {"File", "SoftwareSourceCode", "Workflow"}


def find_root_entity(entity_map):
    for entity in entity_map.values():
        try:
            conforms_to = entity["conformsTo"]
        except KeyError:
            continue
        if conforms_to.get("@id", "").startswith("https://w3id.org/ro/crate/"):
            try:
                root_id = entity["about"]["@id"]
            except (KeyError, TypeError):
                continue
            if root_id in entity_map:
                return entity_map[root_id]
    for name in METADATA_BASENAME, LEGACY_METADATA_BASENAME:
        try:
            root_id = entity_map[name]["about"]["@id"]
        except (KeyError, TypeError):
            continue
        if root_id in entity_map:
            return entity_map[root_id]
    raise ValueError("root data entity not found in crate")


def find_main_workflow(entity_map, root=None):
    if root is None:
        root = find_root_entity(entity_map)
    try:
        main_wf = entity_map[root["mainEntity"]["@id"]]
    except (KeyError, TypeError):
        raise ValueError("main workflow not found in crate")
    if not WORKFLOW_TYPES.issubset(main_wf["@type"]):
        if not LEGACY_WORKFLOW_TYPES.issubset(main_wf["@type"]):
            raise ValueError("main workflow does not have the required types")
    return main_wf


def find_test_dir(entity_map):
    for id_, e in entity_map.items():
        t = e["@type"]
        t = set(t) if isinstance(t, list) else set([t])
        if "Dataset" not in t:
            continue
        # Dataset @id SHOULD end with '/'
        # Path automatically strips trailing '/' and leading './'
        if str(Path(id_)) == "test":
            return id_
    return None


def parse_metadata(crate_dir):
    crate_dir = Path(crate_dir)
    metadata_path = crate_dir / METADATA_BASENAME
    if not metadata_path.is_file():
        metadata_path = crate_dir / LEGACY_METADATA_BASENAME
        if not metadata_path.is_file():
            raise RuntimeError(f"{metadata_path} not found")
    with open(metadata_path, "rt") as f:
        json_data = json.load(f)
    entities = {_["@id"]: _ for _ in json_data["@graph"]}
    main_wf = find_main_workflow(entities)
    test_dir = find_test_dir(entities)
    main_wf_path = crate_dir / main_wf["@id"]
    if not main_wf_path.is_file():
        raise ValueError(f"main workflow {main_wf_path} not found")
    if test_dir is not None:
        test_dir = crate_dir / test_dir
        if not test_dir.is_dir():
            raise ValueError(f"test directory {test_dir} not found")
    return main_wf_path, test_dir
