# Copyright (c) 2020-2024 CRS4
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

from __future__ import annotations

import base64
import fnmatch
import ftplib
import functools
import glob
import inspect
import json
import logging
import os
import random
import re
import shutil
import socket
import string
import struct
import subprocess
import tempfile
import time
import urllib
import uuid
import zipfile
from datetime import datetime, timezone
from importlib import import_module
from os.path import basename, dirname, isfile, join
from typing import (BinaryIO, Dict, Iterable, List, Literal, Optional, Tuple,
                    Type)
from urllib.parse import urlparse

import flask
import git
import giturlparse
import networkx as nx
import pygit2
import requests
import yaml
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from dateutil import parser
from wtforms import ValidationError

from lifemonitor.cache import cached

from . import exceptions as lm_exceptions

logger = logging.getLogger()


def split_by_crlf(s):
    return [v for v in s.splitlines() if v]


def datetime_as_timestamp_with_msecs(
        d: datetime = datetime.now(timezone.utc)) -> int:
    return int(d.timestamp() * 1000)


def datetime_to_utc_unix_timestamp(dt: datetime) -> int:
    return dt.replace(tzinfo=timezone.utc).timestamp()


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


def walk(path, topdown=True, onerror=None, followlinks=False, exclude=None):
    exclude = frozenset(exclude or [])
    for root, dirs, files in os.walk(path, topdown=topdown, onerror=onerror, followlinks=followlinks):
        if exclude:
            dirs[:] = [_ for _ in dirs if _ not in exclude]
            files[:] = [_ for _ in files if _ not in exclude]

        yield root, dirs, files


def to_camel_case(snake_str) -> str:
    """
    Convert snake_case string to a camel_case string
    :param snake_str:
    :return:
    """
    return ''.join(x.title() for x in snake_str.split('_'))


def to_snake_case(camel_str) -> str:
    """
    Convert camel_case string to a snake_case string
    :param camel_str:
    :return:
    """
    # pattern = re.compile(r'(?<!^)(?=[A-Z])')
    # return pattern.sub('_', "".join(camel_str.split())).lower()
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', camel_str).lower()


def to_kebab_case(camel_str) -> str:
    """
    Convert camel_case string to a kebab_case string
    :param camel_str:
    :return:
    """
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    return pattern.sub('-', "".join(camel_str.split())).lower()


def sizeof_fmt(num, suffix='B'):
    # Thanks to Sridhar Ratnakumar
    # https://stackoverflow.com/questions/1094841/get-human-readable-version-of-file-size
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def hide_secret(text: str, secret: str, replace_with="*****") -> str:
    text = str(text) if not isinstance(text, str) else text
    return text if not text else text.replace(secret, replace_with)


def decodeBase64(str, as_object=False, encoding='utf-8'):
    result = base64.b64decode(str)
    if not result:
        return None
    if encoding:
        result = result.decode(encoding)
        if as_object:
            result = json.loads(result)
    return result


def get_netloc(url: str) -> str:
    return urlparse(url).netloc


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


def get_valid_server_domains():
    return ['/', get_netloc(get_base_url()), get_netloc(get_external_server_url())]


def get_validation_schema_url():
    return f"{get_external_server_url()}/integrations/github/config/schema.json"


def validate_url(url: str) -> bool:
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return False


@cached(client_scope=False)
def is_service_alive(url: str, timeout: Optional[int] = None) -> bool:
    try:
        try:
            timeout = timeout or flask.current_app.config.get("SERVICE_AVAILABILITY_TIMEOUT", 1)
        except Exception:
            timeout = 1
        response = requests.get(url, timeout=timeout)
        if response.status_code < 500:
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        logger.error(f'Error checking service availability: {e}')
        return False


def assert_service_is_alive(url: str, timeout: Optional[int] = None):
    if not is_service_alive(url, timeout=timeout):
        raise lm_exceptions.UnavailableServiceException(detail=f"Service not available: {url}", service=url)


def get_last_update(path: str):
    return time.ctime(max(os.stat(root).st_mtime for root, _, _ in os.walk(path)))


def match_ref(candidate: str, refs: Iterable[str]) -> Optional[Tuple[str, str]]:
    """
    Checks the patterns in `refs` to see if any elements match the canditate string
    according to Unix filename pattern matching (fnmatch.fnmatchcase).
    For instance:
        * candidate = "v1.0.1"; refs = ['v*.*.*'] -> Match
        * candidate = "1.0.1"; refs = ['v*.*.*'] -> No match
        * candidate = "pippo"; refs = ['*.*.*'] -> No match

    If a match is found, returns tuple (candidate, matching ref).
    If no match is found, returns None.
    """
    if not candidate:
        return None
    for pattern in refs:
        logger.debug("Searching match for %s (pattern: %s)", candidate, pattern)
        if fnmatch.fnmatchcase(candidate, pattern):
            logger.debug("Match found: %r === %r", candidate, pattern)
            return (candidate, pattern)
    logger.debug("Unable to find a match for %s (refs: %s)", candidate, refs)
    return None


def notify_updates(workflows: List, type: str = 'sync', delay: int = 0):
    from lifemonitor.ws import io
    io.publish_message({
        "type": type,
        "data": [{
            'uuid': str(w["uuid"]),
            'version': w.get("version", None),
            'lastUpdate': (w.get('lastUpdate', None) or datetime.now(tz=timezone.utc)).timestamp()
        } for w in workflows]
    }, delay=delay)


def notify_workflow_version_updates(workflows: List, type: str = 'sync', delay: int = 0):
    from lifemonitor.ws import io
    io.publish_message({
        "type": type,
        "data": [{
            'uuid': str(w.workflow.uuid),
            'version': w.version,
            'lastUpdate':  # datetime.now(tz=timezone.utc).timestamp()
            max(
                w.modified.timestamp(),
                w.workflow.modified.timestamp()
            )
        } for w in workflows]
    }, delay=delay)


def load_modules(path: str = None, include: List[str] = None, exclude: List[str] = None) -> Dict[str, Type]:
    errors = []

    logger.debug("Include modules: %r", include)
    logger.debug("Exclude modules: %r", exclude)

    loaded_modules = {}
    current_path = path or os.path.dirname(__file__)
    for dirpath, _, _ in os.walk(current_path):
        # computer subpackage modules
        modules_files = [f for f in glob.glob(os.path.join(dirpath, "*.py")) if os.path.isfile(f) and not f.endswith('__init__.py')]
        logger.debug("Module files: %r", modules_files)

        for f in modules_files:
            module_name = os.path.basename(f)[:-3]
            logger.debug("Checking module: %r", module_name)
            logger.debug(include and (module_name not in include))
            fully_qualified_module_name = '{}.{}'.format('lifemonitor.tasks.jobs', module_name)
            if (include and (module_name not in include)) or (exclude and (module_name in exclude)):
                logger.warning("Skipping module '%s'", fully_qualified_module_name)
                continue
            # load subclasses of T from detected modules
            try:
                loaded_modules[fully_qualified_module_name] = import_module(fully_qualified_module_name)
            except ModuleNotFoundError as e:
                logger.exception(e)
                logger.error("ModuleNotFoundError: Unable to load module %s", fully_qualified_module_name)
                errors.append(fully_qualified_module_name)
    if len(errors) > 0:
        logger.error("** There were some errors loading application modules.**")
        if logger.isEnabledFor(logging.DEBUG):
            logger.error("** Unable to load types from %s", ", ".join(errors))
    logger.debug("Loaded modules: %r", loaded_modules)
    return loaded_modules


def find_types(T: Type, path: str = None) -> Dict[str, Type]:
    errors = []
    types = {}
    g = nx.DiGraph()
    root_path = os.path.abspath(os.path.dirname(f"{__file__}/../../"))
    # current_path = path or os.path.dirname(__file__)
    base_path = os.path.abspath(path or os.path.dirname(__file__))
    logger.debug("Base path: %r", base_path)

    # base module
    base_module_relative_path = base_path.replace(f"{root_path}/", '')
    logger.debug("Base module relative path: %r", base_module_relative_path)
    base_module = base_module_relative_path.replace('/', '.')
    logger.debug("Base module: %r", base_module)

    for dirpath, _, _ in os.walk(base_path):
        # compute path and name of current subpackage
        current_relative_path = dirpath.replace(f"{root_path}/", '')
        current_package = current_relative_path.replace('/', '.')
        # computer subpackage modules
        modules_files = glob.glob(os.path.join(dirpath, "*.py"))
        logger.debug("Module files: %r", modules_files)
        modules = ['{}.{}'.format(current_package, os.path.basename(f)[:-3])
                   for f in modules_files if os.path.isfile(f) and not f.endswith('__init__.py')]
        # load subclasses of T from detected modules
        for m in modules:
            try:
                mod = import_module(m)
                for _, obj in inspect.getmembers(mod):
                    if inspect.isclass(obj) \
                        and inspect.getmodule(obj) == mod \
                        and obj != T \
                            and issubclass(obj, T):
                        types[obj.__name__] = obj
                        dependencies = getattr(obj, 'depends_on', None)
                        if not dependencies or len(dependencies) == 0:
                            g.add_edge('r', obj.__name__)
                        else:
                            for dep in dependencies:
                                g.add_edge(dep.__name__, obj.__name__)
            except ModuleNotFoundError as e:
                logger.exception(e)
                logger.error("ModuleNotFoundError: Unable to load module %s", m)
                errors.append(m)

    logger.debug("Values: %r", types)
    if len(errors) > 0:
        logger.error("** There were some errors loading application modules.**")
        if logger.isEnabledFor(logging.DEBUG):
            logger.error("** Unable to load types from %s", ", ".join(errors))
    logger.debug("Types: %r", [_.__name__ for _ in types.values()])
    sorted_types = {_: types[_] for _ in nx.dfs_preorder_nodes(g, source='r') if _ != 'r'}
    logger.debug("Sorted types: %r", [_ for _ in sorted_types])
    return sorted_types


def datetime_to_isoformat(dt: datetime) -> str:
    """Convert a datetime to ISO datetime format.

    :param dt: The datetime to convert.
    :return: The datetime converted to ISO format.
    """
    return dt.isoformat(timespec="auto") + "Z"


def isoformat_to_datetime(iso: str) -> datetime:
    """Convert an ISO datetime string to a datetime.

    :param iso: The ISO datetime string to convert.
    :return: The ISO datetime string converted to a datetime.
    """
    logger.debug(f"Converting {iso}")
    date_str = iso[:-1] if iso.endswith('Z') else iso
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        logger.debug("Unable to convert datetime with 'datetime.fromisoformat'")
    try:
        date_format = "%Y-%m-%dT%H:%M:%S.%f" if "." in iso else "%Y-%m-%dT%H:%M:%S"
        logger.debug(f"Date format: {date_format}")
        logger.debug(f"Date string to parse: {date_str}")
        return datetime.strptime(date_str, date_format)
    except ValueError as e:
        raise ValueError(f"Datetime string {iso} is not in ISO format") from e


def get_current_username() -> str:
    try:
        return os.environ["USER"]
    except KeyError:
        try:
            import pwd
            return pwd.getpwuid(os.getuid()).pw_name
        except Exception as e:
            logger.warning("Unable to get current username: %s", e)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    return "unknown"


def parse_date_interval(interval: str) -> Tuple[Literal['<=', '>=', '<', '>', '..'], Optional[datetime], datetime]:
    """Parse a date interval string.

    :param interval: The date interval string to parse. The format is
        ``<operator><date>`` where ``<operator>`` is one of ``<``, ``>``, ``<=``,
        ``>=`` and ``<date>`` is a date string in ISO format; or ``<date>..<date>``
        where ``operator`` is ``..`` and ``<date>`` is a date string in ISO format.

    :return: A tuple containing the operator, start date and end date.
    :raises ValueError: If the date interval string is invalid.
    """
    if not interval:
        raise ValueError("Invalid date interval: empty string")
    start_date = end_date = operator = None
    if interval.startswith("<="):
        operator = "<="
        end_date = isoformat_to_datetime(interval[2:])
    elif interval.startswith(">="):
        operator = ">="
        start_date = isoformat_to_datetime(interval[2:])
    elif interval.startswith("<"):
        operator = "<"
        end_date = isoformat_to_datetime(interval[1:])
    elif interval.startswith(">"):
        operator = ">"
        start_date = isoformat_to_datetime(interval[1:])
    elif ".." in interval:
        operator = ".."
        dates = interval.split("..")
        if len(dates) != 2:
            raise ValueError(f"Invalid date interval: {interval}")
        start_date = isoformat_to_datetime(dates[0])
        end_date = isoformat_to_datetime(dates[1])
    else:
        raise ValueError(f"Invalid date interval: {interval}")
    return operator, start_date, end_date


class ROCrateLinkContext(object):

    def __init__(self, rocrate_or_link: str):
        self.rocrate_or_link = rocrate_or_link
        self._local_path = None

    def __enter__(self):
        # Returns a roc_link.
        # If the input is an encoded rocrate, it will be decoded,
        # written into a local file and a local roc_link will be returned.
        logger.debug("Entering ROCrateLinkContext: %r", self.rocrate_or_link)
        if validate_url(self.rocrate_or_link):
            logger.debug("RO-Crate param is a link: %r", self.rocrate_or_link)
            return self.rocrate_or_link
        if self.rocrate_or_link:
            if os.path.isdir(self.rocrate_or_link) or os.path.isfile(self.rocrate_or_link):
                return self.rocrate_or_link
            try:
                rocrate = base64.b64decode(self.rocrate_or_link)
                from . import config
                temp_rocrate_file = tempfile.NamedTemporaryFile(delete=False,
                                                                dir=config.BaseConfig.BASE_TEMP_FOLDER,
                                                                prefix="base64-rocrate")
                temp_rocrate_file.write(rocrate)
                local_roc_link = f"tmp://{temp_rocrate_file.name}"
                logger.debug("ROCrate written to %r", temp_rocrate_file.name)
                logger.debug("Local roc_link: %r", local_roc_link)
                self._local_path = temp_rocrate_file
                return local_roc_link
            except Exception as e:
                logger.debug(e)
                raise lm_exceptions.DecodeROCrateException(detail=str(e))
        logger.debug("RO-Crate link is undefined!!!")
        return None

    def __exit__(self, type, value, traceback):
        logger.debug("Exiting ROCrateLinkContext...")
        if self._local_path and (isinstance(self._local_path, str) or isinstance(self._local_path, os.PathLike)):
            try:
                os.remove(self._local_path)
                logger.debug("Temporary file removed: %r", self._local_path)
            except Exception as e:
                logger.error("Error deleting temp rocrate: %r", str(e))
        else:
            logger.debug("Nothing to remove: local path is %r", self._local_path)


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


def copy_file_from_local_url(url, target_path: str = None):
    '''
    Copy file from parsed url to target path
    :param parsed_url: parsed url
    :param target_path: if None, a temporary file will be created
    :return:
    '''
    logger.debug("Copying local resource %s to local path %s", url, target_path)
    try:
        if target_path:
            shutil.copyfile(url, target_path)
        else:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                shutil.copyfile(url, tmp_file.name)
                target_path = tmp_file.path
        return target_path
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        raise lm_exceptions.DownloadException('Error copying local resource: %s' % e)


def download_file_from_remote_url(url, target_path: str = None,
                                  authorization: str = None):
    '''
    Download file from parsed url to target path
    :param parsed_url: parsed url
    :param target_path: if None, a temporary file will be created
    :return:
    '''
    logger.debug("Downloading remote resource %s to local path %s", url, target_path)

    # inner function to handle exceptions
    def handle_download_exception(url: str,
                                  exception: Exception,
                                  status: int = 400, detail: Optional[str] = None):
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(exception)

        raise lm_exceptions.DownloadException(
            detail=f"Error downloading from {url}" if not detail else detail,
            status=status,
            original_error=str(exception))

    try:
        if target_path:
            with open(target_path, 'wb') as fd:
                _download_from_remote(url, fd, authorization=authorization)
        else:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                _download_from_remote(url, tmp_file, authorization=authorization)
                target_path = tmp_file.path
        return target_path
    except urllib.error.URLError as e:
        handle_download_exception(url, e)
    except requests.exceptions.HTTPError as e:
        handle_download_exception(url, e, status=e.response.status_code)
    except requests.exceptions.ConnectionError as e:
        handle_download_exception(url, e, status=404, detail=f"Unable to establish connection to {url}")
    except IOError as e:
        handle_download_exception(url, e, status=500)
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        raise lm_exceptions.DownloadException('Error downloading remote resource: %s' % e)


def download_url(url: str, target_path: str = None, authorization: str = None) -> str:
    if not target_path:
        logger.warning("Target path is not defined: a temporary file will be created")

    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme == '' or parsed_url.scheme in ['file', 'tmp']:
        target_path = copy_file_from_local_url(parsed_url.path, target_path)
    else:
        logger.debug("Downloading %s to local path %s", url, target_path)
        target_path = download_file_from_remote_url(url, target_path, authorization=authorization)

    return target_path


def extract_zip(archive_path, target_path=None):
    from . import config
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


def get_domain(value):
    try:
        return urlparse(value).netloc.split(':')[0]
    except Exception:
        raise ValueError("Invalid URL: %r" % value)


def _make_git_credentials_callback(token: str = None):
    return pygit2.RemoteCallbacks(pygit2.UserPass('x-access-token', token)) if token else None


def clone_repo(url: str, ref: Optional[str] = None, target_path: Optional[str] = None, auth_token: Optional[str] = None,
               remote_url: Optional[str] = None, remote_branch: Optional[str] = None, remote_user_token: Optional[str] = None) -> str:
    local_path = target_path
    try:
        from . import config
        logger.debug("Local CLONE: %r - %r", url, ref)
        if not local_path:
            local_path = tempfile.TemporaryDirectory(dir=config.BaseConfig.BASE_TEMP_FOLDER).name
        user_credentials = _make_git_credentials_callback(auth_token)
        clone = pygit2.clone_repository(url, local_path, callbacks=user_credentials)
        if ref is not None:
            for ref_name in [ref, ref.replace('refs/heads', 'refs/remotes/origin')]:
                try:
                    if ref == "HEAD" or ref == 'refs/remotes/origin/HEAD':
                        clone.checkout_head()
                    else:
                        ref_obj = clone.lookup_reference(ref_name)
                        clone.checkout(ref_obj)
                    break
                except KeyError:
                    logger.debug(f"Invalid repo reference: unable to find the reference {ref} on the repo {url}")
        if remote_url:
            user_credentials = _make_git_credentials_callback(remote_user_token)
            remote = clone.create_remote("remote", url=remote_url)
            remote.push([f'+{ref}:refs/heads/{remote_branch}'], callbacks=user_credentials)
        return local_path
    except pygit2.errors.GitError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if 'authentication' in str(e):
            raise lm_exceptions.NotAuthorizedException("Token authorization not valid")
        raise lm_exceptions.DownloadException(detail=str(e))
    finally:
        logger.debug("Clean up clone local path: %r %r .....", target_path, local_path)
        if target_path is None:
            logger.debug("Deleting clone local path: %r %r", target_path, local_path)
            shutil.rmtree(local_path, ignore_errors=True)
        logger.debug("Clean up clone local path: %r %r ..... DONE", target_path, local_path)


def checkout_ref(repo_path: str, ref: str, auth_token: Optional[str] = None, branch_name: Optional[str] = None) -> str:
    try:
        clone = pygit2.Repository(repo_path)
        if ref is not None:
            try:
                if "HEAD" in ref:
                    clone.checkout_head()
                else:
                    ref_obj = clone.lookup_reference(ref)
                    clone.checkout(ref_obj)
            except KeyError:
                logger.debug(f"Invalid repo reference: unable to find the reference {ref} on the repo {repo_path}")
        if branch_name:
            branch_ref = f'refs/heads/{branch_name}'
            clone.branches.create(branch_name, clone.head.peel())
            ref_obj = clone.lookup_reference(branch_ref)
            clone.checkout(ref_obj)
        return repo_path
    except pygit2.errors.GitError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if 'authentication' in str(e):
            raise lm_exceptions.NotAuthorizedException("Token authorization not valid")
        raise lm_exceptions.DownloadException(detail=str(e))


def detect_default_remote_branch(local_repo_path: str) -> Optional[str]:
    '''Return the default remote branch of the repo; None if not found'''
    assert os.path.isdir(local_repo_path), "Path should be a folder"
    try:
        pattern = r"HEAD branch: (\w+)"
        repo = git.Repo(local_repo_path)
        for remote in repo.remotes:
            try:
                output = subprocess.run(['git', 'remote', 'show', remote.url],
                                        check=False, stdout=subprocess.PIPE, cwd=local_repo_path).stdout.decode('utf-8')
                match = re.search(pattern, output)
                if match:
                    detected_branch = match.group(1)
                    logger.debug("Found default branch %r for remote %r", detected_branch, remote.url)
                    return detected_branch
            except Exception as e:
                logger.debug("Unable to get default branch for remote %r: %r", remote.url, e)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
    except Exception as e:
        logger.error(e)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return None


def get_current_active_branch(local_repo_path: str) -> str:
    assert os.path.isdir(local_repo_path), "Path should be a folder"
    try:
        repo = git.Repo(local_repo_path)
        return repo.active_branch.name
    except git.InvalidGitRepositoryError:
        raise ValueError(f"Invalid git repository: {local_repo_path}")
    except Exception as e:
        raise lm_exceptions.LifeMonitorException(detail=f"Unable to get the current active branch: {e}")


class RemoteGitRepoInfo(giturlparse.result.GitUrlParsed):
    pathname: str = None
    protocol: str = None
    owner: str = None

    def __init__(self, parsed_info):
        # fix for giturlparse: protocols are not parsed correctly
        if 'protocols' in parsed_info:
            del parsed_info['protocols']
        super().__init__(parsed_info)

    @property
    def fullname(self):
        return f"{self.owner}/{self.repo}"

    @property
    def urls(self) -> Dict[str, str]:
        urls = super().urls
        # fix for giturlparse: https urls should not have a .git suffix
        urls['https'] = urls['https'].rstrip('.git')
        return urls

    @property
    def protocols(self) -> List[str]:
        return list(self.urls.keys())

    @property
    def license(self) -> Optional[str]:
        try:
            if self.host == 'github.com':
                l_info = requests.get(f"https://api.github.com/repos/{self.fullname}/license")
                self._license = l_info.json()['license']['spdx_id']
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.error(e)
        return self._license

    @staticmethod
    def parse(git_remote_url: str) -> RemoteGitRepoInfo:
        return RemoteGitRepoInfo(giturlparse.parser.parse(git_remote_url))


def get_current_ref(local_repo_path: str) -> str:
    assert os.path.isdir(local_repo_path), "Path should be a folder"
    repo = pygit2.Repository(local_repo_path)
    return repo.head.name


def detect_ref_type(ref: str) -> str:
    # TODO: to be extended
    ref_map = {
        "refs/tags": "tag",
        "refs/pull": "pull_request"
    }
    return next((v for k, v in ref_map.items() if k in ref), "branch")


def find_refs_by_commit(repo: pygit2.Repository, commit: str):
    refs = []
    for ref_name in repo.references:
        ref = repo.lookup_reference(ref_name)
        if ref.target == commit:
            refs.append({
                'shorthand': ref.shorthand,
                'ref': ref.name,
                'type': detect_ref_type(ref.name)
            })
    return refs


def find_commit_info(repo: pygit2.Repository, commit=None, ref=None) -> pygit2.Object:
    assert isinstance(repo, pygit2.Repository), repo
    for c in repo.walk(ref or repo.head.target):
        if not commit or c.hex == commit or str(c.hex) == str(commit):
            return c
    return None


def get_git_repo_revision(local_repo_path: str, commit: str = None) -> Dict:
    assert os.path.isdir(local_repo_path), "Path should be a folder"
    repo = pygit2.Repository(local_repo_path)
    last_commit = find_commit_info(repo, commit)
    refs = find_refs_by_commit(repo, repo.head.target)
    assert isinstance(last_commit, pygit2.Object), "Unable to find the last repo commit"
    return {
        "sha": repo.head.target,
        "created": datetime.fromtimestamp(last_commit.commit_time),
        "refs": refs,
        "type": detect_ref_type(repo.head.name),
        "remotes": [_.url for _ in repo.remotes]
    }


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
    def description(self):
        return self.specs['info']['description']

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
    def save(cls, route=None, skipValidation: bool = False):
        route = route or flask.request.args.get('next', False)
        logger.debug("'next' route param found: %r", route)
        if route:
            try:
                if not skipValidation:
                    cls.validate_next_route_url(route)
                registry = cls._get_route_registry()
                registry.append(route)
                logger.debug("Route registry changed: %r", registry)
                cls._save_route_registry(registry)
            except ValidationError as e:
                logger.error(e)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)

    @classmethod
    def pop(cls, default=None, skipValidation=False):
        # extract the route from the request
        route = flask.request.args.get('next', None)
        logger.debug("'next' route as param: %r", route)
        # if the route is not defined as param, try to get it from the registry
        if route is None:
            registry = cls._get_route_registry()
            logger.debug("Route registry: %r", registry)
            try:
                route = registry.pop()
                logger.debug("Route registry changed: %r", registry)
                logger.debug("Remove route: %r", route)
            except IndexError as e:
                logger.debug(e)
            finally:
                cls._save_route_registry(registry)
        if skipValidation:
            return route or default
        # if the route is not defined, set the default route as next route
        if not route:
            route = default
        # validate the actual route
        try:
            logger.debug("Validating route: %r", route)
            cls.validate_next_route_url(route)
        except ValidationError as e:
            logger.error(e)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            # if the route is not valid, try to get the default route
            try:
                cls.validate_next_route_url(default)
                route = default
            except ValidationError as ex:
                logger.error(ex)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(ex)
                route = None
        # return the validated route
        return route

    @classmethod
    def clear(cls):
        flask.session[cls.__LM_NEXT_ROUTE_REGISTRY__] = json.dumps([])

    @classmethod
    def validate_next_route_url(cls, url: str) -> bool:
        # check whether the URL is valid
        url_domain = None
        try:
            logger.debug("Validating URL: %r", url)
            url_domain = get_netloc(url)
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        # check whether a url domain has been extracted
        logger.debug("URL domain: %r", url_domain)
        if url_domain is None:
            raise ValidationError("Invalid URL: unable to detect domain")
        # check if the URL domain matches the main domain of the back-end app
        valid_server_domains = get_valid_server_domains()
        logger.debug("Valid app domains: %r", valid_server_domains)
        if not url_domain or url_domain in valid_server_domains:
            return True
        # check whether the URL belong to a client
        from lifemonitor.auth.oauth2.server.models import Client
        for c in Client.all():
            for c_redirect_uri in c.redirect_uris:
                try:
                    if url_domain == get_netloc(c_redirect_uri):
                        logger.debug(f"Found a match for the URL url: {url}")
                        return True
                except Exception as e:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
        # the URL doesn't belong to any of the client domains
        raise ValidationError(message="URL not allowed as next route")


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


class FtpUtils():

    def __init__(self, host, user, password, enable_tls) -> None:
        self._ftp = None
        self.host = host
        self.user = user
        self.passwd = password
        self.tls_enabled = enable_tls
        self._metadata_remote_files = {}

    def __del__(self):
        if self._ftp:
            try:
                logger.debug("Closing remote connection...")
                self._ftp.close()
                logger.debug("Closing remote connection... DONE")
            except Exception as e:
                logger.debug(e)

    @property
    def ftp(self) -> ftplib.FTP_TLS:
        if not self._ftp:
            cls = ftplib.FTP_TLS if self.tls_enabled else ftplib.FTP
            self._ftp = cls(self.host)
            self._ftp.login(self.user, self.passwd)
        return self._ftp

    def is_dir(self, path) -> bool:
        """ Check whether a remote path is a directory """
        cwd = self.ftp.pwd()
        try:
            self.ftp.cwd(path)
            return True
        except Exception:
            return False
        finally:
            self.ftp.cwd(cwd)

    def get_file_metadata(self, directory, filename, use_cache=False):
        metadata = self._metadata_remote_files.get(directory, False) if use_cache else None
        if not metadata:
            metadata = [_ for _ in self.ftp.mlsd(directory)]
            self._metadata_remote_files[directory] = metadata
        for f in metadata:
            if f[0] == filename:
                fmeta = f[1]
                logger.debug("File metadata: %r", fmeta)
                return fmeta
        return None

    def sync(self, source, target):
        for root, dirs, files in os.walk(source, topdown=True):
            for name in dirs:
                local_path = os.path.join(root, name)
                logger.debug("Local directory path: %s", local_path)
                remote_file_path = local_path.replace(source, target)
                logger.debug("Remote directory path: %s", remote_file_path)
                try:
                    self.ftp.mkd(remote_file_path)
                    logger.debug("Created remote directory: %s", remote_file_path)
                except Exception as e:
                    logger.debug("Unable to create remote directory: %s", remote_file_path)
                    logger.debug(str(e))

            for name in files:
                local_path = os.path.join(root, name)
                remote_file_path = f"{target}/{local_path.replace(source + '/', '')}"
                logger.debug("Local filepath: %s", local_path)
                logger.debug("Remote filepath: %s", remote_file_path)
                upload_file = True
                try:
                    metadata = self.get_file_metadata(
                        os.path.dirname(remote_file_path), name, use_cache=True)
                    if metadata:
                        timestamp = metadata['modify']
                        remote_time = parser.parse(timestamp).isoformat(' ', 'seconds')
                        local_time = datetime.utcfromtimestamp(os.path.getmtime(local_path)).isoformat(' ', 'seconds')
                        logger.debug("Checking: %r - %r", remote_time, local_time)
                        if local_time <= remote_time:
                            upload_file = False
                            logger.debug("File %s not changed... skip upload", remote_file_path)
                        else:
                            self.ftp.delete(remote_file_path)
                            logger.debug("File %s changed... it requires to be reuploaded", remote_file_path)
                    else:
                        logger.debug("File %s doesn't exist @ remote path %s", name, remote_file_path)
                except Exception as e:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception(e)
                if upload_file:
                    with open(local_path, 'rb') as fh:
                        self.ftp.storbinary('STOR %s' % remote_file_path, fh)
                    logger.info("Local file '%s' uploaded on remote @ %s", local_path, remote_file_path)
        # remove obsolete files on the remote target
        self.remove_obsolete_remote_files(source, target)

    def remove_obsolete_remote_files(self, source, target):
        """ Remove obsolete files on the remote target """
        for path in self.ftp.nlst(target):
            logger.debug("Checking remote path: %r", path)
            local_path = path.replace(target, source)
            logger.debug("Local path corresponding to remote %s is: %s", path, local_path)
            if self.is_dir(path):
                logger.debug("Is dir: %s", path)
                self.remove_obsolete_remote_files(local_path, path)
                # remove remote folder if empty
                if len(self.ftp.nlst(path)) == 0:
                    self.ftp.rmd(path)
                    logger.debug("Removed remote folder '%s'", path)
            else:
                if not os.path.isfile(local_path):
                    logger.debug("Removing remote file '%s'...", path)
                    try:
                        self.ftp.delete(path)
                        logger.debug("Removed remote file '%s'", path)
                    except Exception as e:
                        logger.debug(e)
                else:
                    logger.debug("File %s exists @ %s", path, local_path)

    def rm_tree(self, path):
        """Recursively delete a directory tree on a remote server."""
        try:
            names = self.ftp.nlst(path)
        except ftplib.all_errors as e:
            logger.debug('Could not remove {0}: {1}'.format(path, e))
            return

        for name in names:
            if os.path.split(name)[1] in ('.', '..'):
                continue
            logger.debug('Checking {0}'.format(name))
            if self.is_dir(name):
                self.rm_tree(name)
            else:
                self.ftp.delete(name)
        try:
            self.ftp.rmd(path)
        except ftplib.all_errors as e:
            logger.debug('Could not remove {0}: {1}'.format(path, e))


def generate_symmetric_encryption_key() -> bytes:
    """Generate a new encryption key"""
    key = None
    try:
        key = Fernet.generate_key()
        logger.debug("Encryption key generated: %r", key)
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
    return key


def generate_asymmetric_encryption_keys(
        key_filename: str = "lifemonitor.key",
        public_exponent=65537, key_size=2048) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:

    # Generate the RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=public_exponent,
        key_size=key_size,
    )

    # Write the private key to a file
    with open(f"{key_filename}", "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    # Extract the corresponding public key
    public_key = private_key.public_key()

    # Write the public key to a file
    with open(f"{key_filename}.pub", "wb") as key_file:
        key_file.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )

    return private_key, public_key


def encrypt_file(input_file: BinaryIO, output_file: BinaryIO, key: bytes,
                 encryption_asymmetric: bool = False,
                 raise_error: bool = True, block=65536) -> bool:
    """Encrypt a file using AES-256-CBC"""
    # check if input and output are valid
    if not input_file or not output_file:
        raise ValueError("Invalid input/output file")
    # check if the input file exists
    if not os.path.exists(input_file.name):
        raise ValueError(f"Input file {input_file.name} does not exist")
    # check if the key is valid
    if not key:
        raise ValueError("Invalid encryption key")
    try:
        logger.warning("Encryption asymmetric: %r", encryption_asymmetric)
        # encrypt the file chunk by chunk
        # using a symmetric encryption algorithm
        if not encryption_asymmetric:
            cipher = Fernet(key)
            while True:
                chunk = input_file.read(block)
                if not chunk or len(chunk) == 0:
                    break
                enc = cipher.encrypt(chunk)
                output_file.write(struct.pack('<I', len(enc)))
                output_file.write(enc)
                if len(chunk) < block:
                    break
        # encrypt the file chunk by chunk
        # using an asymmetric encryption algorithm
        else:
            logger.debug("Loading public key...")
            public_key = serialization.load_pem_public_key(
                key,
                # backend=default_backend()
            )
            logger.debug("Loading public key... DONE")

            while True:
                chunk = input_file.read(190)
                if not chunk or len(chunk) == 0:
                    break
                encrypted_chunk = public_key.encrypt(
                    chunk,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                output_file.write(encrypted_chunk)
        return True
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if raise_error:
            raise lm_exceptions.LifeMonitorException(detail=str(e))
    return False


def encrypt_folder(input_folder: str, output_folder: str,
                   key: bytes, block=65536, encryption_asymmetric: bool = False,
                   raise_error: bool = True) -> bool:

    # check if the input folder exists
    if not os.path.exists(input_folder):
        raise ValueError(f"Input folder {input_folder} does not exist")

    # check if the key is valid
    if not key:
        raise ValueError("Invalid encryption key")

    # initialize the counter
    count = 0
    try:
        # walk on the input folder
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                input_file = os.path.join(root, file)
                logger.debug(f"Input file: {input_file}")
                file_output_folder = root.replace(input_folder, output_folder)
                logger.debug(f"File output folder: {file_output_folder}")
                if not os.path.exists(file_output_folder):
                    os.makedirs(file_output_folder, exist_ok=True)
                    logger.debug(f"Created folder: {file_output_folder}")
                output_file = f"{os.path.join(file_output_folder, file)}.enc"
                logger.debug(f"Encrypting file: {input_file}")
                logger.debug(f"Output file: {output_file}")
                with open(input_file, "rb") as f:
                    with open(output_file, "wb") as o:
                        encrypt_file(f, o, key, raise_error=raise_error, block=block,
                                     encryption_asymmetric=encryption_asymmetric)
                        logger.debug(f"File encrypted: {output_file}")
                        print(f"File encrypted: {output_file}")
                        count += 1
                        logger.debug(f"File encrypted: {count}")
        logger.debug(f"Encryption completed: {count} files encrypted on {output_folder}")
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if raise_error:
            raise lm_exceptions.LifeMonitorException(detail=str(e))
    return count


def decrypt_file(input_file: BinaryIO, output_file: BinaryIO, key: bytes,
                 encryption_asymmetric: bool = False, block=65536,
                 raise_error: bool = True) -> bool:
    """Decrypt a file using AES-256-CBC"""
    # check if input and output are valid
    if not input_file or not output_file:
        raise ValueError("Invalid input/output file")
    # check if the input file exists
    if not os.path.exists(input_file.name):
        raise ValueError(f"Input file {input_file.name} does not exist")
    # check if the key is valid
    if not key:
        raise ValueError("Invalid encryption key")
    try:
        # decrypt the file chunk by chunk
        # using a symmetric encryption algorithm
        if not encryption_asymmetric:
            cipher = Fernet(key)
            while True:
                size_data = input_file.read(4)
                if len(size_data) == 0:
                    break
                chunk = input_file.read(struct.unpack('<I', size_data)[0])
                dec = cipher.decrypt(chunk)
                output_file.write(dec)
                if len(chunk) < 4:
                    break
        # decrypt the file chunk by chunk
        # using an asymmetric encryption algorithm
        else:
            logger.debug("Loading private key...")
            private_key = serialization.load_pem_private_key(
                key,
                password=None,
                # backend=default_backend()
            )
            logger.debug("Loading private key... DONE")
            while True:
                encrypted_chunk = input_file.read(256)
                if not encrypted_chunk or len(encrypted_chunk) == 0:
                    break  # End of file
                decrypted_chunk = private_key.decrypt(
                    encrypted_chunk,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                output_file.write(decrypted_chunk)
        return True
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if raise_error:
            raise lm_exceptions.LifeMonitorException(detail=str(e))
    return False


def decrypt_folder(input_folder: str, output_folder: str,
                   key: bytes, asymmetric_encryption: bool = False,
                   raise_error: bool = True) -> int:

    # check if the input folder exists
    if not os.path.exists(input_folder):
        raise ValueError(f"Input folder {input_folder} does not exist")

    # check if the key is valid
    if not key:
        raise ValueError("Invalid encryption key")

    # walk on the input folder
    count = 0
    try:
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                input_file = os.path.join(root, file)
                file_output_folder = root.replace(input_folder, output_folder)
                logger.debug(f"File output folder: {file_output_folder}")
                if not os.path.exists(file_output_folder):
                    os.makedirs(file_output_folder, exist_ok=True)
                    logger.debug(f"Created folder: {file_output_folder}")
                output_file = f"{os.path.join(file_output_folder, file).removesuffix('.enc')}"
                logger.debug(f"Decrypting file: {input_file}")
                logger.debug(f"Output file: {output_file}")
                with open(input_file, "rb") as f:
                    with open(output_file, "wb") as o:
                        decrypt_file(f, o, key, raise_error=raise_error,
                                     encryption_asymmetric=asymmetric_encryption)
                        logger.debug(f"File decrypted: {output_file}")
                        print(f"File decrypted: {output_file}")
                        count += 1
                        logger.debug(f"File decrypted: {count}")
        logger.debug(f"Decryption completed: {count} files decrypted on {output_folder}")
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        if raise_error:
            raise lm_exceptions.LifeMonitorException(detail=str(e))
    return count
