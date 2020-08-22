import logging

# Config a module level logger
logger = logging.getLogger(__name__)


def normalize_userinfo(client, data):
    logger.debug("User data: %r", data)
    data = data["data"]
    params = {
        'sub': str(data['id']),
        'name': data['attributes']['title'],
        'email': data['attributes']['mbox_sha1sum'],  # TODO: check if it is possible to decode the email
        'preferred_username': data['id'],  # TODO: check if the username can be retrived from API
        'profile': data['links']["self"],
        'picture': data['attributes']['avatar'],
        'website': '',
    }
    return params


class Seek(object):
    NAME = 'seek'
    OAUTH_CONFIG = {
        'api_base_url': 'https://rachk8s.me:3000',
        'access_token_url': 'oauth/token',
        'authorize_url': 'oauth/authorize',
        'client_kwargs': {'scope': 'read'},
        'userinfo_endpoint': 'https://rachk8s.me:3000/people/current?format=json',
        'userinfo_compliance_fix': normalize_userinfo,
    }


def refresh_oauth2_token(func):
    from . import refresh_oauth2_provider_token
    return refresh_oauth2_provider_token(func, 'seek')
