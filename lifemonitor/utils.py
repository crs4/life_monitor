import json
import logging
import os
import tempfile
import zipfile

import flask
import requests
from flask import url_for

RO_CRATE_METADATA_FILENAME = "ro-crate-metadata.jsonld"
RO_CRATE_TEST_DEFINITION_FILENAME = "test-suite-definition.json"

logger = logging.getLogger()


def bool_from_string(s) -> bool:
    if s is None or s == "":
        return None
    if s.lower() in {'t', 'true', '1'}:
        return True
    if s.lower() in {'f', 'false', '0'}:
        return False
    raise ValueError(f"Invalid string value for boolean. Got '{s}'")


def to_camel_case(snake_str) -> str:
    """
    Convert snake_case string to a camel_case string
    :param snake_str:
    :return:
    """
    return ''.join(x.title() for x in snake_str.split('_'))


def download_url(url, target_path=None, token=None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    with requests.Session() as session:
        session.headers.update(headers)
        with session.get(url, stream=True) as r:
            r.raise_for_status()
            if not target_path:
                target_path = tempfile.mktemp()
            with open(target_path, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8192):
                    fd.write(chunk)
    return target_path


def extract_zip(archive_path, target_path=None):
    if not target_path:
        target_path = tempfile.mkdtemp()
    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        zip_ref.extractall(target_path)
    return target_path


def load_ro_crate_metadata(roc_path):
    file_path = os.path.join(roc_path, RO_CRATE_METADATA_FILENAME)
    with open(file_path) as data_file:
        logger.info("Loading RO Crate Metadata @ %s", file_path)
        return json.load(data_file)


def load_test_definition_filename(filename):
    with open(filename) as f:
        return json.load(f)


def search_for_test_definition(roc_path, ro_crate_metadata: dict):
    # first search on the root roc_path for a test_definition file
    filename = os.path.join(roc_path, RO_CRATE_TEST_DEFINITION_FILENAME)
    if os.path.exists(filename):
        return load_test_definition_filename(filename)
    # check for if there exists a ZIP archive as root Dataset containing the actual RO crate
    graph = ro_crate_metadata.get("@graph", None)
    if not graph:
        return None

    mid = main_entity = None
    for node in graph:
        nid = node.get("@id", None)
        ntype = node.get("@type", None)
        if nid and nid == "./" and ntype and ntype == "Dataset":
            main_entity = node.get("mainEntity", None)
            break

    if main_entity:
        mid = main_entity.get("@id", None)
        if not mid:
            return None

    # check if the main_entity if a ZIP file
    if not mid.endswith(".zip"):
        return None
    dataset_path = extract_zip(os.path.join(roc_path, mid))
    print("Dataset path: %s", dataset_path)
    dataset_metadata = load_ro_crate_metadata(dataset_path)
    print("Dataset meatadata: %r", dataset_metadata)
    return search_for_test_definition(dataset_path, dataset_metadata)


def push_request_to_session(name):
    flask.session[f'{name}_next_endpoint'] = flask.request.endpoint
    flask.session[f'{name}_next_args'] = flask.request.args
    flask.session[f'{name}_next_forms'] = flask.request.form


def pop_request_from_session(name):
    endpoint = flask.session.pop(f'{name}_next_endpoint', None)
    if endpoint:
        return {
            "endpoint": endpoint,
            "args": flask.session.pop(f'{name}_next_args'),
            "form": flask.session.pop(f'{name}_next_forms')
        }
    return None
