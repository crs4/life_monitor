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

import json
import logging
import random
import string
import tempfile
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


def download_url(url, target_path=None, token=None):
    with requests.Session() as session:
        if token:
            session.headers['Authorization'] = f'Bearer {token}'
        with session.get(url, stream=True) as r:
            if r.status_code == 401 or r.status_code == 403:
                raise NotAuthorizedException(r.content)
            r.raise_for_status()
            if not target_path:
                target_path = tempfile.mktemp()
            with open(target_path, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8192):
                    fd.write(chunk)
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
