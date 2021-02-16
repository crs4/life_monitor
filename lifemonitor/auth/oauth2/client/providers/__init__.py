import glob
import logging
from functools import wraps
from importlib import import_module
from flask import g, request, redirect, url_for
from lifemonitor.exceptions import LifeMonitorException
from lifemonitor.utils import push_request_to_session
from os.path import dirname, basename, isfile, join

# Config a module level logger
logger = logging.getLogger(__name__)


class OAuth2ProviderNotSupportedException(LifeMonitorException):

    def __init__(self, detail="OAuth2 Provider not supported",
                 type="about:blank", status=400, instance=None, **kwargs):
        super().__init__(title="Bad request",
                         detail=detail, status=status, **kwargs)


def refresh_oauth2_provider_token(func, name):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        logger.debug("Current request endpoint: %r", request.endpoint)
        token = g.oauth2_registry.seek.token
        if token.is_expired():
            logger.info("Token expired!!!")
            push_request_to_session(name)
            return redirect(url_for('loginpass.login', name=name, next=request.endpoint))
        return func(*args, **kwargs)

    return decorated_view


def new_instance(provider_type, **kwargs):
    m = f"lifemonitor.auth.oauth2.client.providers.{provider_type.lower()}"
    try:
        mod = import_module(m)
        return getattr(mod, provider_type.capitalize())(**kwargs)
    except (ModuleNotFoundError, AttributeError) as e:
        logger.exception(e)
        raise OAuth2ProviderNotSupportedException(provider_type=provider_type, orig=e)


def register_providers():
    modules_files = glob.glob(join(dirname(__file__), "*.py"))
    modules = ['{}.{}'.format(__name__, basename(f)[:-3])
               for f in modules_files if isfile(f) and not f.endswith('__init__.py')]
    we_had_errors = False
    for m in modules:
        try:
            # Try to load the command module 'm'
            mod = import_module(m)
            logger.debug(f"Loaded module {m}: {mod}")
        except ModuleNotFoundError:
            logger.error("ModuleNotFoundError: Unable to load module %s", m)
            we_had_errors = True
    if we_had_errors:
        logger.error("** There were some errors loading application modules.**")
        logger.error("Some commands may not be available.")
