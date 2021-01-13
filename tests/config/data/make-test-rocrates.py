#!/usr/bin/env python

import os
import json
import shutil
import logging

# configure logging
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

# settings
current_path = os.path.realpath(os.getcwd())
logger.debug("CURRENT PATH: %s", current_path)

crates_source_path = os.path.join(current_path, "../../../interaction_experiments/data/crates")
logger.debug("RO-CRATES SOURCE PATH: %s", crates_source_path)

crates_target_path = os.path.join(current_path, "crates")
logger.debug("RO-CRATES SOURCE PATH: %s", crates_target_path)

# list of RO-Crates
test_crates = ['ro-crate-cwl-basefreqsum', 'ro-crate-galaxy-sortchangecase']
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-invalid-service-type'))
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-invalid-service-url'))

# clean up RO-Crates folder
if os.path.exists(crates_target_path):
    shutil.rmtree(crates_target_path)
os.makedirs(crates_target_path, exist_ok=True)
# copy base RO-Crates
for c in test_crates:
    source_dir, target_dir = c if type(c) is tuple else (c, c)
    shutil.copytree(os.path.join(crates_source_path, source_dir), os.path.join(crates_target_path, target_dir))

# generate an invalid testing service type


def patch_metadata_graph_node(metadata_file, node, properties):
    with open(metadata_file) as f:
        data = json.load(f)
    for n in data['@graph']:
        if node[0] in n and n[node[0]] == node[1]:
            for k, v in properties.items():
                n[k] = v
    with open(metadata_file, 'w') as out:
        out.write(json.dumps(data, indent=2))


# patch crates
patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase/ro-crate-metadata.json',
                          node=("@type", "TestInstance"),
                          properties={
                              'url': 'http://jenkins:8080/',
                              'resource': 'job/test/'
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-invalid-service-url/ro-crate-metadata.json',
                          node=("name", "sort-and-change-case"),
                          properties={
                              'name': 'sort-and-change-case-invalid-service-url'
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-invalid-service-url/ro-crate-metadata.json',
                          node=("@type", "TestInstance"),
                          properties={
                              'url': 'http://127.0.0.1:67890'
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-invalid-service-type/ro-crate-metadata.json',
                          node=("@type", "TestInstance"),
                          properties={
                              "runsOn": {
                                  "@id": "https://w3id.org/ro/terms/test#JenkinsXService"
                              },
                          })
patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-invalid-service-type/ro-crate-metadata.json',
                          node=("@type", "TestService"),
                          properties={
                              "@id": "https://w3id.org/ro/terms/test#JenkinsXService"
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-invalid-service-type/ro-crate-metadata.json',
                          node=("name", "sort-and-change-case"),
                          properties={
                              'name': 'sort-and-change-case-invalid-service-type'
                          })

# create zip archives
print("Creating RO-Crate archives:")
for c in test_crates:
    archive = c[1] if type(c) is tuple else c
    print("- %s... " % archive, end='')
    shutil.make_archive("{}.crate".format(archive), 'zip', os.path.join(crates_target_path, archive))
    print("DONE")
