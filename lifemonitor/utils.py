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

import glob
import json
import logging
import random
import shutil
import socket
import string
import tempfile
import urllib
import uuid
import functools
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


def uuid_param(uuid_value) -> uuid.UUID:
    if isinstance(uuid_value, str):
        logger.debug("Converting UUID: %r", uuid_value)
        uuid_value = uuid.UUID(uuid_value)
    return uuid_value


def to_camel_case(snake_str) -> str:
    """
    Convert snake_case string to a camel_case string
    :param snake_str:
    :return:
    """
    return ''.join(x.title() for x in snake_str.split('_'))


def get_base_url():
    server_name = None
    try:
        server_name = flask.current_app.config.get("SERVER_NAME", None)
    except RuntimeError as e:
        logger.warning(str(e))
    if server_name is None:
        server_name = f"{socket.gethostbyname(socket.gethostname())}:8000"
    return f"https://{server_name}"


def _download_from_remote(url, output_stream, authorization=None):
    with requests.Session() as session:
        if authorization:
            session.headers['Authorization'] = authorization
        with session.get(url, stream=True) as r:
            if r.status_code == 401 or r.status_code == 403:
                raise NotAuthorizedException(details=r.content)
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
    logger.debug("Archive path: %r", archive_path)
    logger.debug("Target path: %r", target_path)
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


def next_route_aware(func):

    @functools.wraps(func)
    def decorated_view(*args, **kwargs):
        # save the 'next' parameter to allow automatic redirect after OAuth2 authorization
        NextRouteRegistry.save()
        return func(*args, **kwargs)
    return decorated_view


class NextRouteRegistry(object):

    __LM_NEXT_ROUTE_REGISTRY__ = "lifemonitor_next_route_registry"

    @classmethod
    def _get_route_registry(cls):
        registry = flask.session.get(cls.__LM_NEXT_ROUTE_REGISTRY__, None)
        if registry is None:
            registry = []
        else:
            registry = json.loads(registry)
        return registry

    @classmethod
    def _save_route_registry(cls, registry):
        flask.session[cls.__LM_NEXT_ROUTE_REGISTRY__] = json.dumps(registry)
        logger.debug("Route registry saved")

    @classmethod
    def save(cls, route=None):
        route = route or flask.request.args.get('next', False)
        logger.debug("'next' route param found: %r", route)
        if route:
            registry = cls._get_route_registry()
            registry.append(route)
            logger.debug("Route registry changed: %r", registry)
            cls._save_route_registry(registry)

    @classmethod
    def pop(cls, default=None):
        route = flask.request.args.get('next', None)
        logger.debug("'next' route as param: %r", route)
        if route is None:
            registry = cls._get_route_registry()
            try:
                route = registry.pop()
                logger.debug("Route registry changed: %r", registry)
                logger.debug("Remove route: %r", route)
            except IndexError as e:
                logger.debug(e)
            finally:
                cls._save_route_registry(registry)
        return route or default

    @classmethod
    def clear(cls):
        flask.session[cls.__LM_NEXT_ROUTE_REGISTRY__] = json.dumps([])


class ClassManager:

    def __init__(self, package, class_prefix="", class_suffix="", skip=None, lazy=True):
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
        if not lazy:
            self._load_concrete_types()

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

    def get_classes(self):
        return [_[0] for _ in self._load_concrete_types().values()]
