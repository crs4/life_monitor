#!/usr/bin/env python

# Copyright (c) 2020-2021 CRS4
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

# List of RO-Crates to be created.
# New RO-crates are created by copying a path under crates_source_path to a path under crates_target_path.
# List contains strings and tuples.
#   * tuple t: a new ro-crate will be created by copying path crates_source_path/t[0] to path crates_target_path/t[1]
#   * string s: shortcut for a tuple (s, s)
test_crates = ['ro-crate-cwl-basefreqsum', 'ro-crate-galaxy-sortchangecase']
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-travis'))
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-invalid-service-type'))
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-invalid-service-url'))
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-github-actions'))
test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-no-name'))

test_crates.append(('ro-crate-galaxy-sortchangecase', 'ro-crate-galaxy-sortchangecase-rate-limit-exceeded'))

# clean up RO-Crates folder
if os.path.exists(crates_target_path):
    shutil.rmtree(crates_target_path)
os.makedirs(crates_target_path, exist_ok=True)

# copy base RO-Crates
for c in test_crates:
    source_dir, target_dir = c if isinstance(c, tuple) else (c, c)
    shutil.copytree(os.path.join(crates_source_path, source_dir), os.path.join(crates_target_path, target_dir))


def patch_metadata_graph_node(metadata_file, node, properties):
    # path RO-crate metadata node
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
                              'resource': 'job/test/',
                              "runsOn": {
                                  "@id": "https://w3id.org/ro/terms/test#JenkinsService"
                              }
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase/ro-crate-metadata.json',
                          node=("@type", "TestService"),
                          properties={
                              "@id": "https://w3id.org/ro/terms/test#JenkinsService",
                              "name": "Jenkins",
                              "url": {
                                  "@id": "http://jenkins:8080"
                              }
                          })


patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-rate-limit-exceeded/ro-crate-metadata.json',
                          node=("@type", "TestInstance"),
                          properties={
                              'url': 'http://ratelimit:8080/',
                              'resource': 'job/test/',
                              "runsOn": {
                                  "@id": "https://w3id.org/ro/terms/test#RateLimitExceededService"
                              }
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-rate-limit-exceeded/ro-crate-metadata.json',
                          node=("@type", "TestService"),
                          properties={
                              "@id": "https://w3id.org/ro/terms/test#RateLimitExceededService",
                              "name": "RateLimit",
                              "url": {
                                  "@id": "http://ratelimit:8080"
                              }
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-travis/ro-crate-metadata.json',
                          node=("name", "sort-and-change-case"),
                          properties={
                              'name': 'sort-and-change-case-travis'
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-travis/ro-crate-metadata.json',
                          node=("@type", "TestInstance"),
                          properties={
                              "runsOn": {
                                  "@id": "https://w3id.org/ro/terms/test#TravisService"
                              },
                              "url": "https://api.travis-ci.org",
                              "resource": "github/crs4/pydoop"
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-travis/ro-crate-metadata.json',
                          node=("@type", "TestService"),
                          properties={
                              "@id": "https://w3id.org/ro/terms/test#TravisService",
                              "name": "Travis",
                              "url": {
                                  "@id": "https://travis-ci.org"
                              }
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

# GitHub Actions crate
patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-github-actions/ro-crate-metadata.json',
                          node=("@type", "TestInstance"),
                          properties={
                              'url': 'https://api.github.com',
                              'resource': 'repos/crs4/life_monitor/actions/workflows/docs.yaml',
                              'runsOn': {"@id": "https://w3id.org/ro/terms/test#GithubService"}
                          })
patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-github-actions/ro-crate-metadata.json',
                          node=("@type", "TestService"),
                          properties={
                              "@id": "https://w3id.org/ro/terms/test#GithubService",
                              "name": "Github",
                              "url": {"@id": "https://github.com"}
                          })

patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-no-name/ro-crate-metadata.json',
                          node=("@type", "Dataset"),
                          properties={
                              'name': None
                          })
patch_metadata_graph_node('crates/ro-crate-galaxy-sortchangecase-no-name/ro-crate-metadata.json',
                          node=("@id", "sort-and-change-case.ga"),
                          properties={
                              'name': None
                          })

# create zip archives
print("Creating RO-Crate archives:")
for c in test_crates:
    archive = c[1] if isinstance(c, tuple) else c
    print("- %s... " % archive, end='')
    shutil.make_archive("{}.crate".format(archive), 'zip', os.path.join(crates_target_path, archive))
    print("DONE")
