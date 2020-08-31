import os
import logging
from flask import current_app

# Config a module level logger
logger = logging.getLogger(__name__)


def normalize_userinfo(client, data):
    logger.debug("User data: %r", data)
    data = data["data"]
    params = {
        'sub': str(data['id']),
        'name': data['attributes']['title'],
        # TODO: check if it is possible to decode the email
        'email': data['attributes']['mbox_sha1sum'],
        # TODO: check if the username can be retrieved from API
        'preferred_username': data['id'],
        'profile': data['links']["self"],
        'picture': data['attributes']['avatar'],
        'website': '',
    }
    return params


class Seek(object):
    NAME = 'seek'
    # define API URLs
    _api_base_url = current_app.config.get(
        "{}_API_BASE_URL".format(NAME.upper()), 'https://workflowhub.eu')
    _api_urls = (
        ('API_BASE_URL', _api_base_url),
        ('ACCESS_TOKEN_URL', os.path.join(_api_base_url, '/oauth/token')),
        ('AUTHORIZE_URL', os.path.join(_api_base_url, '/oauth/authorize')),
        ('USERINFO_ENDPOINT', os.path.join(_api_base_url,
                                           '/people/current?format=json'))
    )
    # init the OAuth configuration with static settings
    OAUTH_CONFIG = {
        'client_kwargs': {'scope': 'read'},
        'userinfo_compliance_fix': normalize_userinfo,
    }
    # append the API urls to the configuration
    for url in _api_urls:
        OAUTH_CONFIG[url[0].lower()] = current_app.config.get(
            "{}_{}".format(NAME.upper(), url[0]), url[1])


def refresh_oauth2_token(func):
    from . import refresh_oauth2_provider_token
    return refresh_oauth2_provider_token(func, 'seek')
