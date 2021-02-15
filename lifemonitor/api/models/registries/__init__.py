from __future__ import annotations


import glob
import logging
import lifemonitor.common as common
from importlib import import_module
from os.path import dirname, basename, isfile, join

from .registry import WorkflowRegistry, WorkflowRegistryClient

# set module level logger
logger = logging.getLogger(__name__)


__all__ = ["WorkflowRegistry", "WorkflowRegistryClient"]


__registry_types__ = {}


def load_registry_types():
    global __registry_types__
    modules_files = glob.glob(join(dirname(__file__), "*.py"))
    modules = ['{}'.format(basename(f)[:-3])
               for f in modules_files if isfile(f) \
                    and not f.endswith('__init__.py') \
                    and not f.endswith('registry.py')]
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
