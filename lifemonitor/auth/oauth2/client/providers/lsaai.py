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
from flask import current_app

# Config a module level logger
logger = logging.getLogger(__name__)


def normalize_userinfo(client, data):
    logger.debug("LSAAI Data: %r", data)
    preferred_username = data.get('eduperson_principal_name')[0].replace('@lifescience-ri.eu', '') \
        if 'eduperson_principal_namex' in data and len(data['eduperson_principal_name']) > 0 \
        else data['name'].replace(' ', '')
    params = {
        'sub': str(data['sub']),
        'name': data['name'],
        'email': data.get('email'),
        'preferred_username': preferred_username
        # 'profile': data['html_url'],
        # 'picture': data['avatar_url'],
        # 'website': data.get('blog'),
    }

    # The email can be be None despite the scope being 'user:email'.
    # That is because a user can choose to make his/her email private.
    # If that is the case we get all the users emails regardless if private or note
    # and use the one he/she has marked as `primary`
    try:
        if params.get('email') is None:
            resp = client.get('user/emails')
            resp.raise_for_status()
            data = resp.json()
            params["email"] = next(email['email'] for email in data if email['primary'])
    except Exception as e:
        logger.warning("Unable to get user email. Reason: %r", str(e))
    return params


class LsAAI:
    name = 'LifeScience RI'
    client_name = 'lsaai'
    oauth_config = {
        'client_id': current_app.config.get('LSAAI_CLIENT_ID', None),
        'client_secret': current_app.config.get('LSAAI_CLIENT_SECRET', None),
        'client_name': client_name,
        'uri': 'https://proxy.aai.lifescience-ri.eu',
        'api_base_url': 'https://proxy.aai.lifescience-ri.eu',
        'access_token_url': 'https://proxy.aai.lifescience-ri.eu/OIDC/token',
        'authorize_url': 'https://proxy.aai.lifescience-ri.eu/saml2sp/OIDC/authorization',
        'client_kwargs': {'scope': 'openid profile email orcid eduperson_principal_name'},
        'userinfo_endpoint': 'https://proxy.aai.lifescience-ri.eu/OIDC/userinfo',
        'userinfo_compliance_fix': normalize_userinfo,
        'server_metadata_url': 'https://proxy.aai.lifescience-ri.eu/.well-known/openid-configuration'
    }

    def __repr__(self) -> str:
        return "LSAAI Provider"

    @staticmethod
    def normalize_userinfo(client, data):
        return normalize_userinfo(client, data)
