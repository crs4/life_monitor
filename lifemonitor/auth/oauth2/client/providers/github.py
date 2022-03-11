# Copyright (c) 2020-2021 CRS4
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
    logger.debug(data)
    params = {
        'sub': str(data['id']),
        'name': data['name'],
        'email': data.get('email'),
        'preferred_username': data['login'],
        'profile': data['html_url'],
        'picture': data['avatar_url'],
        'website': data.get('blog'),
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


class GitHub:
    name = 'github'
    oauth_config = {
        'client_id': current_app.config.get('GITHUB_CLIENT_ID', None),
        'client_secret': current_app.config.get('GITHUB_CLIENT_SECRET', None),
        'uri': 'https://github.com',
        'api_base_url': 'https://api.github.com',
        'access_token_url': 'https://github.com/login/oauth/access_token',
        'authorize_url': 'https://github.com/login/oauth/authorize',
        'client_kwargs': {'scope': 'read:user user:email'},
        'userinfo_endpoint': 'https://api.github.com/user',
        'userinfo_compliance_fix': normalize_userinfo,
    }

    def __repr__(self) -> str:
        return f"Github Provider {self.name}"

    @staticmethod
    def normalize_userinfo(client, data):
        return normalize_userinfo(client, data)
