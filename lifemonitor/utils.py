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


import base64
import functools
import glob
import json
import logging
import os
import random
import re
import shutil
import pygit2
import socket
import string
import tempfile
import urllib
import uuid
import zipfile
from importlib import import_module
from os.path import basename, dirname, isfile, join
from typing import List

import flask
import requests
import yaml

from . import config
from . import exceptions as lm_exceptions

logger = logging.getLogger()


def split_by_crlf(s):
    return [v for v in s.splitlines() if v]


def values_as_list(values, in_separator='\\s?,\\s?|\\s+'):
    if not values:
        return []
    if isinstance(values, list):
        return values
    if isinstance(values, str):
        try:
            return values_as_list(json.loads(values))
        except json.JSONDecodeError:
            try:
                return values_as_list(re.split(in_separator, values))
            except Exception as e:
                raise ValueError("Invalid format: %r", str(e))
    else:
        raise ValueError("Invalid format")


def values_as_string(values, in_separator='\\s?,\\s?|\\s+', out_separator=" "):
    if not values:
        return ""
    if isinstance(values, str):
        try:
            return out_separator.join(json.loads(values))
        except json.JSONDecodeError:
            try:
                return out_separator.join(re.split(in_separator, values))
            except Exception as e:
                raise ValueError("Invalid format: %r", str(e))
    elif isinstance(values, list):
        return out_separator.join(values)
    else:
        raise ValueError("Invalid format")


def boolean_value(value) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool_from_string(value)
    raise ValueError(f"Invalid value for boolean. Got '{value}'")


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


def sizeof_fmt(num, suffix='B'):
    # Thanks to Sridhar Ratnakumar
    # https://stackoverflow.com/questions/1094841/get-human-readable-version-of-file-size
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def decodeBase64(str, as_object=False, encoding='utf-8'):
    result = base64.b64decode(str)
    if not result:
        return None
    if encoding:
        result = result.decode(encoding)
        if as_object:
            result = json.loads(result)
    return result


def get_base_url():
    server_name = None
    try:
        server_name = flask.current_app.config.get("SERVER_NAME", None)
    except RuntimeError as e:
        logger.warning(str(e))
    if server_name is None:
        server_name = f"{socket.gethostbyname(socket.gethostname())}:8000"
    return f"https://{server_name}"


def get_external_server_url():
    external_server_url = None
    try:
        external_server_url = flask.current_app.config.get("EXTERNAL_SERVER_URL", None)
    except RuntimeError as e:
        logger.warning(str(e))
    return get_base_url() if not external_server_url else external_server_url


def validate_url(url: str) -> bool:
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_rocrate_link(rocrate_or_link: str) -> str:
    # Returns a roc_link.
    # If the input is an encoded rocrate, it will be decoded,
    # written into a local file and a local roc_link will be returned.
    if validate_url(rocrate_or_link):
        return rocrate_or_link
    if rocrate_or_link:
        try:
            rocrate = base64.b64decode(rocrate_or_link)
            temp_rocrate_file = tempfile.NamedTemporaryFile(delete=False, prefix="/tmp/")
            temp_rocrate_file.write(rocrate)
            local_roc_link = f"tmp://{temp_rocrate_file.name}"
            logger.debug("ROCrate written to %r", temp_rocrate_file.name)
            logger.debug("Local roc_link: %r", local_roc_link)
            return local_roc_link
        except Exception as e:
            logger.debug(e)
            raise lm_exceptions.DecodeROCrateException(detail=str(e))


def _download_from_remote(url, output_stream, authorization=None):
    with requests.Session() as session:
        if authorization:
            session.headers['Authorization'] = authorization
        with session.get(url, stream=True) as r:
            if r.status_code == 401 or r.status_code == 403:
                raise lm_exceptions.NotAuthorizedException(details=r.content)
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                output_stream.write(chunk)


def check_resource_exists(url, authorizations: List = None):
    errors = []
    authorizations = authorizations or [None]
    with requests.Session() as session:
        for authorization in authorizations:
            try:
                logger.debug("Checking head URL: %s", url)
                auth_header = authorization.as_http_header() if authorization else None
                if auth_header:
                    session.headers['Authorization'] = auth_header
                else:
                    session.headers.pop('Authorization', None)
                response = session.head(url)
                logger.debug("Check URL (with auth=%r): %r", auth_header is not None, response)
                if response.status_code == 200 or response.status_code == 302:
                    return True
            except lm_exceptions.NotAuthorizedException as e:
                logger.info("Caught authorization error exception while downloading and processing RO-crate: %s", e)
                errors.append(str(e))
            except Exception as e:
                # errors.append(str(e))
                logger.debug(e)
    if len(errors) > 0:
        raise lm_exceptions.NotAuthorizedException(detail=f"Not authorized to download {url}", original_errors=errors)
    return False


def download_url(url: str, target_path: str = None, authorization: str = None) -> str:
    if not target_path:
        target_path = tempfile.mktemp()
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme == '' or parsed_url.scheme in ['file', 'tmp']:
            logger.debug("Copying %s to local path %s", url, target_path)
            shutil.copyfile(parsed_url.path, target_path)
        else:
            logger.debug("Downloading %s to local path %s", url, target_path)
            with open(target_path, 'wb') as fd:
                _download_from_remote(url, fd, authorization)
            logger.info("Fetched %s of data from %s",
                        sizeof_fmt(os.path.getsize(target_path)), url)
    except urllib.error.URLError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        raise \
            lm_exceptions.DownloadException(
                detail=f"Error downloading from {url}",
                status=400,
                original_error=str(e))
    except requests.exceptions.HTTPError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        raise \
            lm_exceptions.DownloadException(
                detail=f"Error downloading from {url}",
                status=e.response.status_code,
                original_error=str(e))
    except requests.exceptions.ConnectionError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        raise \
            lm_exceptions.DownloadException(
                detail=f"Unable to establish connection to {url}",
                status=404,
                original_error=str(e))
    except IOError as e:
        # requests raised on an exception as we were trying to download.
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        raise \
            lm_exceptions.DownloadException(
                detail=f"Error downloading from {url}",
                status=500,
                original_error=str(e))
    return target_path


def extract_zip(archive_path, target_path=None):
    logger.debug("Archive path: %r", archive_path)
    logger.debug("Target path: %r", target_path)
    try:
        if not target_path:
            target_path = tempfile.mkdtemp(dir=config.BaseConfig.BASE_TEMP_FOLDER)
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(target_path)
        return target_path
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        msg = "Downloaded RO-crate has bad zip format"
        logger.error(msg + ": %s", e)
        raise lm_exceptions.NotValidROCrateException(detail=msg, original_error=str(e))


def _make_git_credentials_callback(token: str = None):
    return pygit2.RemoteCallbacks(pygit2.UserPass('x-access-token', token)) if token else None


def clone_repo(url: str, branch: str = None, target_path: str = None, auth_token: str = None,
               remote_url: str = None, remote_branch: str = None, remote_user_token: str = None):
    try:
        local_path = target_path
        if not local_path:
            local_path = tempfile.TemporaryDirectory(dir=config.BaseConfig.BASE_TEMP_FOLDER).name
        user_credentials = _make_git_credentials_callback(auth_token)
        clone = pygit2.clone_repository(url, local_path,
                                        checkout_branch=branch, callbacks=user_credentials)
        if remote_url:
            user_credentials = _make_git_credentials_callback(remote_user_token)
            remote = clone.create_remote("remote", url=remote_url)
            remote.push([f'+refs/heads/{branch}:refs/heads/{remote_branch}'], callbacks=user_credentials)
        return local_path
    except pygit2.errors.GitError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if 'authentication' in str(e):
            raise lm_exceptions.NotAuthorizedException("Token authorization not valid")
        raise lm_exceptions.DownloadException(detail=str(e))
    finally:
        if target_path is None:
            shutil.rmtree(local_path, ignore_errors=True)


def load_test_definition_filename(filename):
    with open(filename) as f:
        return json.load(f)


def compare_json(obj1, obj2) -> bool:
    json1 = json.dumps(obj1, sort_keys=True)
    json2 = json.dumps(obj2, sort_keys=True)
    result = json1 == json2
    logger.debug("The two JSON objects are different")
    return result


def generate_username(user_info, salt_length=4):
    return "{}{}".format(
        user_info.preferred_username,
        ''.join(random.choice(string.ascii_letters + string.digits) for i in range(salt_length)))


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


class OpenApiSpecs(object):

    __instance = None
    _specs = None

    def __init__(self):
        if self.__instance:
            raise RuntimeError("OpenApiSpecs instance already exists!")
        self.__instance = self

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    @staticmethod
    def load():
        with open('./specs/api.yaml') as file:
            return yaml.load(file, Loader=yaml.FullLoader)

    @property
    def specs(self):
        if not self._specs:
            self._specs = self.load()
        return self._specs.copy()

    @property
    def info(self):
        return self.specs['info']

    @property
    def version(self):
        return self.specs['info']['version']

    @property
    def components(self):
        return self.specs['components']

    @property
    def securitySchemes(self):
        return self.specs["components"]["securitySchemes"]

    def getSecuritySchemeScopes(self, securityScheme):
        try:
            scopes = {}
            scheme = self.securitySchemes[securityScheme]
            if "flows" in scheme:
                for flow in scheme['flows']:
                    scopes.update({s: d for s, d in scheme['flows'][flow]['scopes'].items()})
            return scopes
        except KeyError:
            raise ValueError("Invalid security scheme")

    @property
    def apikey_scopes(self):
        skip = ["registry.workflow.read", "registry.workflow.write", "registry.user.workflow.read", "registry.user.workflow.write"]
        return {k: v for k, v in self.all_scopes.items() if k not in skip}

    @property
    def registry_scopes(self):
        scopes = self.registry_client_scopes
        scopes.update(self.registry_code_flow_scopes)
        return scopes

    @property
    def registry_client_scopes(self):
        return self.getSecuritySchemeScopes('RegistryClientCredentials')

    @property
    def registry_code_flow_scopes(self):
        return self.getSecuritySchemeScopes('RegistryCodeFlow')

    @property
    def authorization_code_scopes(self):
        return self.getSecuritySchemeScopes('AuthorizationCodeFlow')

    @property
    def all_scopes(self):
        scopes = {}
        for scheme in self.securitySchemes:
            scopes.update(self.getSecuritySchemeScopes(scheme))
        return scopes


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
            modules_files = glob.glob(join(dirname(module_obj.__file__), "*.py"))
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

    @property
    def _concrete_types(self):
        return self._load_concrete_types()

    def add_class(self, type_name, type_class):
        self._concrete_types[type_name] = (type_class,)

    def remove_class(self, type_name):
        return self._concrete_types.pop(type_name, None)

    def get_class(self, concrete_type):
        return self._concrete_types[concrete_type][0]

    def get_classes(self):
        return [_[0] for _ in self._concrete_types.values()]


class Base64Encoder(object):

    _cache = {}

    @classmethod
    def encode_file(cls, file: str) -> str:
        data = cls._cache.get(file, None)
        if data is None:
            with open(file, "rb") as f:
                data = base64.b64encode(f.read())
                cls._cache[file] = data
        return data.decode()

    @classmethod
    def encode_object(cls, obj: object) -> str:
        key = hash(frozenset(obj.items()))
        data = cls._cache.get(key, None)
        if data is None:
            data = base64.b64encode(json.dumps(obj).encode())
            cls._cache[key] = data
        return data.decode()

    @classmethod
    def decode(cls, data: str) -> object:
        return base64.b64decode(data.encode())
