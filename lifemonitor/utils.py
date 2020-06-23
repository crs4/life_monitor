import os
import json
import logging
import requests
import tempfile
import zipfile

RO_CRATE_METADATA_FILENAME = "ro-crate-metadata.jsonld"

logger = logging.getLogger()


def to_camel_case(snake_str) -> str:
    """
    Convert snake_case string to a camel_case string
    :param snake_str:
    :return:
    """
    return ''.join(x.title() for x in snake_str.split('_'))


def download_url(url, target_path=None, token=None):
    session = requests.Session()
    headers = {}
    if not target_path:
        target_path = tempfile.mktemp()
    if token:
        headers['Authorization'] = 'Bearer {}'.format(token)
    session.headers.update(headers)
    r = session.get(url)
    with open(target_path, 'wb') as fd:
        fd.write(r.content)
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
