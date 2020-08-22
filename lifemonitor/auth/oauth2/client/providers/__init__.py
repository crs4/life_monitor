import logging
from functools import wraps
from flask import g, request, redirect, url_for

from lifemonitor.utils import push_request_to_session

# Config a module level logger
logger = logging.getLogger(__name__)


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
