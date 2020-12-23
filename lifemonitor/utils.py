import json
import logging
import random
import shutil
import string
import tempfile
import urllib
import zipfile

import flask
import requests

from .common import NotAuthorizedException, NotValidROCrateException

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


def _download_from_remote(url, output_stream, authorization=None):
    with requests.Session() as session:
        if authorization:
            session.headers['Authorization'] = authorization
        with session.get(url, stream=True) as r:
            if r.status_code == 401 or r.status_code == 403:
                raise NotAuthorizedException(r.content)
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                output_stream.write(chunk)


def download_url(url, target_path=None, authorization=None):
    if not target_path:
        target_path = tempfile.mktemp()
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme == '' or parsed_url.scheme == 'file':
        shutil.copyfile(parsed_url.path, target_path)
    else:
        with open(target_path, 'wb') as fd:
            _download_from_remote(url, fd, authorization)
    return target_path


def extract_zip(archive_path, target_path=None):
    try:
        if not target_path:
            target_path = tempfile.mkdtemp()
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(target_path)
        return target_path
    except Exception as e:
        raise NotValidROCrateException(e)


def load_test_definition_filename(filename):
    with open(filename) as f:
        return json.load(f)


def generate_username(user_info):
    return ''.join(random.choice(string.ascii_letters + string.digits) for i in range(10))


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
