import logging
import requests
from urllib.parse import urljoin
from lifemonitor import common
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
            'mbox_sha1sum': data['attributes']['mbox_sha1sum'],
            # 'preferred_username': data['id'],
            'profile': data['links']["self"],
            'picture': data['attributes']['avatar'],
            'website': '',
        }
        return params

    def get_user_info(self, provider_user_id, token, normalized=True):
        response = requests.get(urljoin(self.api_base_url,
                                        f'/people/{provider_user_id}?format=json'),
                                headers={'Authorization': f'Bearer {token["access_token"]}'})
        user_info = response.json()
        if response.status_code != 200:
            raise common.LifeMonitorException(
                title="Not found",
                status=response.status_code, detail="Unable to get user data",
                errors=user_info['errors'])
        return user_info['data'] if not normalized else self.normalize_userinfo(None, user_info)


def refresh_oauth2_token(func):
    from . import refresh_oauth2_provider_token
    return refresh_oauth2_provider_token(func, 'seek')
