import logging
from functools import wraps
from importlib import import_module
from flask import g, request, redirect, url_for
from lifemonitor.common import LifeMonitorException
from lifemonitor.utils import push_request_to_session

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
