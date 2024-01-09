# Copyright (c) 2020-2022 CRS4
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

import logging
from urllib.parse import urljoin

import requests

from lifemonitor import exceptions

from ..models import OAuth2IdentityProvider, OAuthIdentity

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

    def __repr__(self) -> str:
        return f"Seek Provider {self.name}"

    @staticmethod
    def normalize_userinfo(client, data):
        data = data["data"]
        params = {
            'sub': str(data['id']),
            'name': data['attributes']['title'],
            'mbox_sha1sum': data['attributes']['mbox_sha1sum'],
            'preferred_username': data['attributes']['title'].replace(" ", ""),
            'profile': data['links']["self"],
            'picture': data['attributes']['avatar'],
            'website': '',
        }
        return params

    def get_user_profile_html(self, provider_user_id) -> str:
        return urljoin(self.api_base_url,
                       f'/people/{provider_user_id}?format=json')

    def get_user_info(self, provider_user_id, token, normalized=True):
        response = requests.get(self.get_user_profile_html(provider_user_id),
                                headers={'Authorization': f'Bearer {token["access_token"]}'})
        if response.status_code != 200:
            try:
                raise exceptions.LifeMonitorException(
                    status=response.status_code, detail="Unable to get user data",
                    errors=response.json()['errors'])
            except Exception:
                raise exceptions.LifeMonitorException(
                    status=response.status_code, detail="Unable to get user data")

        user_info = response.json()
        logger.debug("USER info: %r", user_info)
        return user_info['data'] if not normalized else self.normalize_userinfo(None, user_info)

    @classmethod
    def get_user_profile_page(cls, user_identity: OAuthIdentity):
        logger.debug("user: %r", user_identity)
        # the user profile page can require user_provider_id
        if not user_identity:
            logger.warning("No identity found for user %r", user_identity)
            return None
        assert isinstance(user_identity.provider, cls), "Invalid provider"
        return user_identity.provider.get_user_profile_html(user_identity.provider_user_id)


def refresh_oauth2_token(func):
    from . import refresh_oauth2_provider_token
    return refresh_oauth2_provider_token(func, 'seek')
