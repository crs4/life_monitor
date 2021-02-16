import glob
import json
import logging
import random
import shutil
import string
import tempfile
import urllib
import zipfile
from importlib import import_module
from os.path import basename, dirname, isfile, join

import flask
import requests

from .exceptions import NotAuthorizedException, NotValidROCrateException

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


class ClassManager:

    def __init__(self, package, class_prefix="", class_suffix="", skip=None):
        self._package = package
        self._prefix = class_prefix
        self._suffix = class_suffix
        self._skip = ['__init__']
        if skip:
            if isinstance(skip, list):
                self._skip.extend(skip)
            else:
                self._skip.append(skip)
        self.__concrete_types__ = None

    def _load_concrete_types(self):
        if not self.__concrete_types__:
            self.__concrete_types__ = {}
            module_obj = import_module(self._package)
            print(module_obj)
            modules_files = glob.glob(join(dirname(module_obj.__file__), "*.py"))
            print(modules_files)
            modules = ['{}'.format(basename(f)[:-3]) for f in modules_files if isfile(f)]
            for m in modules:
                if m not in self._skip:
                    object_class = f"{self._prefix}{m.capitalize()}{self._suffix}"
                    try:
                        mod = import_module(f"{self._package}.{m}")
                        self.__concrete_types__[m] = (
                            getattr(mod, object_class),
                        )
                    except (ModuleNotFoundError, AttributeError) as e:
                        logger.warning(f"Unable to load object module {m}")
                        logger.exception(e)
        return self.__concrete_types__

    def get_class(self, concrete_type):
        return self._load_concrete_types()[concrete_type][0]
