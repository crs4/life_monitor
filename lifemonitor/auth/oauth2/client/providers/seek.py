import logging
from ..models import OAuth2IdentityProvider

# Config a module level logger
logger = logging.getLogger(__name__)


class Seek(OAuth2IdentityProvider):
    # Default settings
    defaults = {
        "client_kwargs": {'scope': 'read'},
        "api_base_url": 'https://workflowhub.eu',
        "authorize_url": '/oauth/authorize',
        "access_token_url": '/oauth/token',
        "userinfo_endpoint": '/people/current?format=json'
    }

    __mapper_args__ = {
        'polymorphic_identity': 'seek'
    }

    def __init__(self, name, client_id, client_secret,
                 api_base_url=defaults['api_base_url'],
                 authorize_url=defaults['authorize_url'],
                 access_token_url=defaults['access_token_url'],
                 userinfo_endpoint=defaults['userinfo_endpoint'],
                 client_kwargs=defaults['client_kwargs'],
                 **kwargs):
        logger.debug("Seek Provider Data: %r", kwargs)
        super().__init__(name, client_id, client_secret,
                         api_base_url, authorize_url,
                         access_token_url,
                         userinfo_endpoint,
                         client_kwargs=client_kwargs,
                         **kwargs)

    @staticmethod
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


def refresh_oauth2_token(func):
    from . import refresh_oauth2_provider_token
    return refresh_oauth2_provider_token(func, 'seek')
