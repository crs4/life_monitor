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
import logging
import lifemonitor.common as common
from importlib import import_module
from os.path import dirname, basename, isfile, join

# set module level logger
logger = logging.getLogger(__name__)


__registry_types__ = {}


def load_registry_types():
    global __registry_types__
    modules_files = glob.glob(join(dirname(__file__), "*.py"))
    modules = ['{}'.format(basename(f)[:-3])
               for f in modules_files if isfile(f) and not f.endswith('__init__.py')]
    for m in modules:
        registry_class = f"{m.capitalize()}WorkflowRegistry"
        registry_client_class = f"{m.capitalize()}WorkflowRegistryClient"
        try:
            mod = import_module(f"{__name__}.{m}")
            __registry_types__[m] = (
                getattr(mod, registry_class),
                getattr(mod, registry_client_class)
            )
        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f"Unable to load registry module {m}")
            logger.exception(e)
    return __registry_types__.copy()


def get_registry_class(registry_type):
    try:
        return __registry_types__[registry_type][0]
    except AttributeError as e:
        logger.exception(e)
        raise common.WorkflowRegistryNotSupportedException(registry_type=registry_type)


def get_registry_client_class(registry_type):
    try:
        return __registry_types__[registry_type][1]
    except AttributeError as e:
        logger.exception(e)
        raise common.WorkflowRegistryNotSupportedException(registry_type=registry_type)
